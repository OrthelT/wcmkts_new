"""Benchmark page-load performance of the deployed app with a headless browser.

Each sample opens a fresh browser context (a new Streamlit session, so no
session-state carry-over), loads one page, and waits for the app to go quiet.
It then triggers an in-session rerun to measure the warm path.

Server-side caches (``st.cache_data`` / ``st.cache_resource``) are process-wide,
so only the very first sample after the app wakes is truly cold; it is recorded
under ``round`` 0 and should be read separately from the steady-state rounds.

Usage (Playwright is not a project dependency):

    uv run --with playwright python benchmarks/live_site.py --rounds 3 \
        --out benchmarks/results/baseline.json

Pass ``--chromium /path/to/chrome`` to use a pre-installed browser.

Must run from a network that allows WebSocket upgrades (Streamlit streams every
element over ``/_stcore/stream``). Behind a proxy that blocks them the hosting
shell loads but the app never renders, and every sample times out.

Timing resolution is ~100-200 ms: the sync Playwright API only dispatches
websocket events while the poll loop is inside a Playwright call.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone

from playwright.sync_api import Page, WebSocket, sync_playwright

BASE_URL = "https://wcmkts.streamlit.app"

# url_path -> label. Streamlit derives the path from the file name; the
# default page (market_dashboard) is served at "/".
PAGES = {
    "": "market_dashboard",
    "market_stats": "market_stats",
    "low_stock": "low_stock",
    "import_helper": "import_helper",
    "builder_helper": "builder_helper",
    "doctrine_status": "doctrine_status",
    "doctrine_report": "doctrine_report",
    "build_costs": "build_costs",
    "pricer": "pricer",
    "downloads": "downloads",
}

QUIET_S = 5.0  # no stream frames and no running indicator for this long == settled
TIMEOUT_S = 180.0
APP_FRAME = "/~/+/"

CONTENT_SELECTOR = (
    '[data-testid="stMain"] [data-testid="stElementContainer"]'
)
RUNNING_SELECTOR = (
    '[data-testid="stStatusWidget"] [data-testid="stStatusWidgetRunningIcon"],'
    ' [data-testid="stSpinner"], [data-testid="stSkeleton"]'
)
ERROR_SELECTOR = '[data-testid="stException"], [data-testid="stAlertContentError"]'


class StreamTap:
    """Record receive times and byte counts on the app's Streamlit websocket."""

    def __init__(self, t0: float):
        self.t0 = t0
        self.open_at: float | None = None
        self.last_frame_at: float | None = None
        self.frames = 0
        self.bytes = 0

    def attach(self, ws: WebSocket) -> None:
        if "_stcore/stream" not in ws.url:
            return
        self.open_at = self.open_at or time.perf_counter()
        ws.on("framereceived", self._on_frame)

    def _on_frame(self, payload) -> None:
        self.last_frame_at = time.perf_counter()
        self.frames += 1
        self.bytes += len(payload)

    def mark(self) -> None:
        """Reset counters for a new measurement window within the same session."""
        self.t0 = time.perf_counter()
        self.last_frame_at = None
        self.frames = 0
        self.bytes = 0

    def ms(self, t: float | None) -> float | None:
        return None if t is None else round((t - self.t0) * 1000)


def app_frame(page: Page):
    for f in page.frames:
        if APP_FRAME in f.url:
            return f
    return None


def wait_settled(page: Page, tap: StreamTap, deadline: float) -> dict:
    """Poll until the app has content, nothing is running, and the stream is quiet."""
    first_content = None
    while time.perf_counter() < deadline:
        frame = app_frame(page)
        now = time.perf_counter()
        if frame is not None:
            try:
                has_content = frame.locator(CONTENT_SELECTOR).count() > 0
                running = frame.locator(RUNNING_SELECTOR).count() > 0
            except Exception:
                has_content, running = False, True
            if has_content and first_content is None:
                first_content = now
            quiet_since = tap.last_frame_at or tap.t0
            # frames > 0: the app's websocket actually delivered a script run. Without
            # it, "content" is just the hosting shell and the sample must not pass.
            if has_content and not running and tap.frames > 0 and now - quiet_since >= QUIET_S:
                errors = frame.locator(ERROR_SELECTOR).count()
                return {
                    "first_content_ms": tap.ms(first_content),
                    "settled_ms": tap.ms(tap.last_frame_at or first_content),
                    "ws_frames": tap.frames,
                    "ws_kb": round(tap.bytes / 1024, 1),
                    "errors": errors,
                    "timed_out": False,
                }
        page.wait_for_timeout(100)
    return {
        "first_content_ms": tap.ms(first_content),
        "settled_ms": None,
        "ws_frames": tap.frames,
        "ws_kb": round(tap.bytes / 1024, 1),
        "errors": None,
        "timed_out": True,
    }


def measure(browser, url_path: str, label: str, rnd: int, shots: str | None) -> dict:
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()
    t0 = time.perf_counter()
    tap = StreamTap(t0)
    page.on("websocket", tap.attach)
    result: dict = {"page": label, "round": rnd, "at": datetime.now(timezone.utc).isoformat()}
    try:
        page.goto(f"{BASE_URL}/{url_path}", wait_until="load", timeout=TIMEOUT_S * 1000)
        result["shell_load_ms"] = tap.ms(time.perf_counter())
        result.update(wait_settled(page, tap, t0 + TIMEOUT_S))
        result["ws_open_ms"] = round((tap.open_at - t0) * 1000) if tap.open_at else None
        frame = app_frame(page)
        result["frame_url"] = frame.url if frame else None
        if shots:
            page.screenshot(path=os.path.join(shots, f"{label}_r{rnd}.png"), full_page=True)

        # Warm path: same session, press "r" to rerun the script.
        if frame is not None and not result["timed_out"]:
            tap.mark()
            frame.locator("body").press("r")
            rerun = wait_settled(page, tap, time.perf_counter() + TIMEOUT_S)
            result["rerun_settled_ms"] = rerun["settled_ms"]
            result["rerun_ws_kb"] = rerun["ws_kb"]
    except Exception as exc:  # record, don't abort the whole run
        result["error"] = f"{type(exc).__name__}: {exc}".splitlines()[0]
    finally:
        ctx.close()
    return result


def summarize(samples: list[dict]) -> dict:
    out: dict = {}
    for label in PAGES.values():
        rows = [s for s in samples if s["page"] == label and s["round"] > 0]
        def col(key):
            return [s[key] for s in rows if s.get(key) is not None]
        out[label] = {
            key: {
                "median": statistics.median(v),
                "min": min(v),
                "max": max(v),
                "n": len(v),
            }
            for key in ("first_content_ms", "settled_ms", "rerun_settled_ms", "ws_kb")
            if (v := col(key))
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out", default="benchmarks/results/live.json")
    ap.add_argument("--chromium", default=None, help="Chromium executable path")
    ap.add_argument("--screenshots", default=None, help="Directory for per-sample screenshots")
    args = ap.parse_args()

    if args.screenshots:
        os.makedirs(args.screenshots, exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    samples: list[dict] = []
    with sync_playwright() as p:
        proxy = os.environ.get("HTTPS_PROXY")
        browser = p.chromium.launch(
            executable_path=args.chromium,
            proxy={"server": proxy} if proxy else None,
        )
        # Round 0: one pass to catch a cold (just-woken) server; excluded from summary.
        for rnd in range(0, args.rounds + 1):
            for url_path, label in PAGES.items():
                s = measure(browser, url_path, label, rnd, args.screenshots)
                samples.append(s)
                print(json.dumps(s), flush=True)
        browser.close()

    report = {
        "base_url": BASE_URL,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "quiet_window_s": QUIET_S,
        "rounds": args.rounds,
        "summary": summarize(samples),
        "samples": samples,
    }
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
