"""NiceGUI proof-of-concept for the Winter Coalition Market Stats viewer.

Run it:
    uv run --with nicegui python poc/nicegui_app/app.py

Then open http://localhost:8080

What this POC demonstrates (the four pain points from the brief):
  1. Execution model — NiceGUI keeps per-user server-side state and updates
     only the widgets that change. The favorite toggles and filter below do NOT
     re-run the whole script the way Streamlit does.
  2. Performance — data is fetched once into server state; interactions mutate
     the view client-side (AG Grid) instead of re-querying.
  3. SSO/OAuth — reuses your existing EveSSOService for a real EVE login flow
     (DEMO fallback if no CCP app is registered).
  4. pyturso — local writes via the pull()/push() adapter (favorites persist
     in a local DB and write through to remote).

It imports your real services/ layer unchanged; only this presentation file is
new.
"""

from __future__ import annotations

import logging
import secrets

from nicegui import app, ui

import auth as poc_auth
from data import get_doctrine_table
from turso_adapter import TursoLikeAdapter

logging.basicConfig(level=logging.INFO)

# Singletons (per-process) — the equivalent of your @st.cache_resource layer.
_SSO_SERVICE, _SSO_MODE = poc_auth.build_sso_service()
_TURSO = TursoLikeAdapter()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _current_character() -> dict | None:
    """The logged-in identity for THIS browser session (per-user state)."""
    return app.storage.user.get("character")


def _header() -> None:
    with ui.header().classes("items-center justify-between"):
        ui.label("WC Market Stats — NiceGUI POC").classes("text-lg font-bold")
        with ui.row().classes("items-center gap-3"):
            ui.label(f"data: {_TURSO.backend}").classes("text-xs opacity-70")
            char = _current_character()
            if char:
                ui.label(f"👤 {char['character_name']}").classes("text-sm")
                ui.button("Log out", on_click=_logout).props("flat dense")
            else:
                ui.button("Log in with EVE", on_click=_start_login).props("dense")


def _start_login() -> None:
    if _SSO_MODE == "demo":
        # Clearly-labeled mock identity so per-user features still demo.
        app.storage.user["character"] = {
            "character_id": 90000001,
            "character_name": "Demo Pilot (mock)",
        }
        ui.notify("Logged in with a MOCK identity (set EVE_SSO_* env for real SSO)")
        ui.navigate.to("/")
        return

    state = _SSO_SERVICE.build_oauth_state()
    ui.navigate.to(poc_auth.authorization_url(_SSO_SERVICE, state))


def _logout() -> None:
    app.storage.user.pop("character", None)
    ui.navigate.to("/")


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@ui.page("/")
def index() -> None:
    _header()

    table = get_doctrine_table()
    char = _current_character()
    favorites = _TURSO.get_favorites(char["character_id"]) if char else set()

    with ui.column().classes("w-full p-4 gap-3"):
        ui.label("Doctrine Ships").classes("text-xl font-bold")
        if table.is_sample:
            ui.label(table.note).classes(
                "text-sm text-orange-700 bg-orange-100 p-2 rounded w-full"
            )
        else:
            ui.label(table.note).classes("text-sm text-green-700")

        # Per-user state demo: a search box that filters WITHOUT a full rerun.
        df = table.df
        records = df.to_dict("records")

        grid = ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "Ship", "field": "ship_name", "filter": True},
                    {"headerName": "Fit ID", "field": "fit_id", "width": 90},
                    {"headerName": "On Market", "field": "fits_on_mkt", "width": 110},
                    {"headerName": "Target", "field": "ship_target", "width": 100},
                    {
                        "headerName": "% Target",
                        "field": "pct_target",
                        "width": 110,
                        # Red < 50, amber < 100, green otherwise — a taste of the
                        # progress-bar styling from the dashboard task.
                        "cellClassRules": {
                            "text-red-600 font-bold": "x < 50",
                            "text-amber-600": "x >= 50 && x < 100",
                            "text-green-600": "x >= 100",
                        },
                    },
                ],
                "rowData": records,
                "rowSelection": "single",
            }
        ).classes("w-full h-96")

        search = ui.input("Filter ships…").classes("w-72")
        # Pure client-side filter — note: NO server round-trip, NO script rerun.
        search.on(
            "keydown.enter",
            lambda e: grid.run_grid_method(
                "setGridOption", "quickFilterText", search.value
            ),
        )
        search.on_value_change(
            lambda e: grid.run_grid_method(
                "setGridOption", "quickFilterText", e.value
            )
        )

        ui.separator()

        # Favorites: a LOCAL WRITE that pull/push-es via the turso adapter.
        ui.label("Favorite fits (local write → push to remote)").classes(
            "text-lg font-semibold"
        )
        if not char:
            ui.label("Log in to favorite fits (per-user state).").classes(
                "text-sm opacity-70"
            )
        else:
            with ui.row().classes("flex-wrap gap-2"):
                for rec in records:
                    fid = rec["fit_id"]
                    is_fav = fid in favorites
                    btn = ui.button(
                        f"{'★' if is_fav else '☆'} {rec['ship_name']}"
                    ).props("dense outline")
                    btn.on_click(
                        lambda _, fid=fid, b=btn, name=rec["ship_name"]: _toggle_fav(
                            char["character_id"], fid, b, name
                        )
                    )

        with ui.row().classes("mt-4 gap-2"):
            ui.button("pull() from remote", on_click=lambda: _do_pull()).props(
                "outline dense"
            )
            ui.button("push() to remote", on_click=lambda: _do_push()).props(
                "outline dense"
            )


def _toggle_fav(character_id: int, fit_id: int, button, name: str) -> None:
    now_fav = _TURSO.toggle_favorite(character_id, fit_id)
    button.text = f"{'★' if now_fav else '☆'} {name}"
    ui.notify(f"{'Added' if now_fav else 'Removed'} {name} (pushed to remote)")


def _do_pull() -> None:
    ok = _TURSO.pull()
    ui.notify("pull() ran (remote → local)" if ok else "pull() no-op (sqlite fallback)")


def _do_push() -> None:
    ok = _TURSO.push()
    ui.notify("push() ran (local → remote)" if ok else "push() no-op (sqlite fallback)")


@ui.page("/auth/callback")
def auth_callback(code: str = "", state: str = "") -> None:
    """EVE SSO redirect target — handled by your existing EveSSOService."""
    if _SSO_MODE == "demo":
        ui.label("SSO is in DEMO mode; nothing to handle here.")
        ui.navigate.to("/")
        return
    try:
        identity = _SSO_SERVICE.complete_login(code=code, state=state)
        payload = identity["payload"]
        app.storage.user["character"] = {
            "character_id": payload["character_id"],
            "character_name": payload["character_name"],
        }
        ui.notify(f"Welcome, {payload['character_name']}")
    except Exception as exc:  # noqa: BLE001 - surface the failure honestly
        ui.notify(f"Login failed: {exc}", type="negative")
    ui.navigate.to("/")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="WC Mkts NiceGUI POC",
        port=8080,
        storage_secret=secrets.token_urlsafe(32),
        reload=False,
    )
