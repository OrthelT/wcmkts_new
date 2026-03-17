"""Generate mockup images for the Market Stats page redesign."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image
import os

# ── Colour palette (Streamlit dark-ish theme) ────────────────────────────
BG = "#0E1117"
CARD_BG = "#262730"
CARD_BORDER = "#3D3D4E"
TEXT_WHITE = "#FAFAFA"
TEXT_GREY = "#A3A8B8"
TEXT_DIM = "#6B7280"
ACCENT_BLUE = "#4DA6FF"
ACCENT_GREEN = "#2ECC71"
ACCENT_RED = "#E74C3C"
ACCENT_ORANGE = "#F39C12"
TABLE_HEADER_BG = "#1A1D27"
TABLE_ROW_ALT = "#1E2130"
DIVIDER = "#3D3D4E"

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _rounded_rect(ax, x, y, w, h, color=CARD_BG, border_color=CARD_BORDER, radius=0.01, lw=1):
    """Draw a rounded rectangle on axes."""
    fancy = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad={radius}",
        facecolor=color,
        edgecolor=border_color,
        linewidth=lw,
    )
    ax.add_patch(fancy)
    return fancy


def _metric_card(ax, x, y, w, h, label, value, delta=None, delta_color=ACCENT_GREEN):
    """Draw a metric card."""
    _rounded_rect(ax, x, y, w, h)
    ax.text(x + w / 2, y + h * 0.65, value, fontsize=11, fontweight="bold",
            color=TEXT_WHITE, ha="center", va="center", family="monospace")
    ax.text(x + w / 2, y + h * 0.30, label, fontsize=7, color=TEXT_GREY,
            ha="center", va="center")
    if delta:
        ax.text(x + w * 0.85, y + h * 0.65, delta, fontsize=7, color=delta_color,
                ha="center", va="center")


def _table(ax, x, y, w, h, title, headers, rows, col_widths=None):
    """Draw a data table."""
    _rounded_rect(ax, x, y, w, h, border_color=CARD_BORDER)

    title_h = h * 0.12
    ax.text(x + 0.008, y + h - title_h * 0.4, title, fontsize=9, fontweight="bold",
            color=TEXT_WHITE, va="center")
    ax.plot([x, x + w], [y + h - title_h, y + h - title_h], color=ACCENT_BLUE, linewidth=1.5)

    n_cols = len(headers)
    if col_widths is None:
        col_widths = [w / n_cols] * n_cols

    header_h = h * 0.08
    header_y = y + h - title_h - header_h
    for i, hdr in enumerate(headers):
        cx = x + sum(col_widths[:i]) + col_widths[i] * 0.5
        ax.text(cx, header_y + header_h * 0.5, hdr, fontsize=6, color=ACCENT_BLUE,
                ha="center", va="center", fontweight="bold")
    ax.plot([x, x + w], [header_y, header_y], color=DIVIDER, linewidth=0.5)

    row_h = (header_y - y) / max(len(rows), 1)
    for r_idx, row in enumerate(rows):
        ry = header_y - (r_idx + 1) * row_h
        if r_idx % 2 == 1:
            _rounded_rect(ax, x + 0.002, ry, w - 0.004, row_h,
                          color=TABLE_ROW_ALT, border_color="none", lw=0)
        for c_idx, cell in enumerate(row):
            cx = x + sum(col_widths[:c_idx]) + col_widths[c_idx] * 0.5
            color = TEXT_WHITE
            if isinstance(cell, str):
                if cell.startswith("-"):
                    color = ACCENT_RED
                elif cell.endswith("%") and not cell.startswith("-"):
                    color = ACCENT_GREEN
            ax.text(cx, ry + row_h * 0.5, str(cell), fontsize=5.5, color=color,
                    ha="center", va="center", family="monospace")


# ═════════════════════════════════════════════════════════════════════════
# MOCKUP 1 – Full Page Overview
# ═════════════════════════════════════════════════════════════════════════

def mockup_full_page():
    fig, ax = plt.subplots(figsize=(14, 20))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Title bar ─────────────────────────────────────────────────────
    ax.text(0.5, 0.975, "Winter Coalition Market Stats — 4-HWWF Keepstar Market",
            fontsize=16, fontweight="bold", color=TEXT_WHITE, ha="center", va="center")
    ax.text(0.5, 0.961, "Redesigned Layout  •  Mockup", fontsize=8, color=TEXT_DIM, ha="center")

    # ── Section 1: Topline KPI cards ─────────────────────────────────
    y_kpi = 0.915
    kpi_h = 0.035
    kpi_w = 0.155
    gap = 0.012
    labels = ["Total Market Value", "Active Sell Orders", "Active Buy Orders",
              "Items Listed", "Avg Daily Volume", "Last Updated"]
    values = ["487.2B ISK", "12,847", "3,214", "4,892", "28.6B ISK", "14:32 UTC"]
    deltas = ["▲ 3.2%", "▲ 127", "▼ 42", "▲ 89", "▲ 8.1%", ""]
    delta_colors = [ACCENT_GREEN, ACCENT_GREEN, ACCENT_RED, ACCENT_GREEN, ACCENT_GREEN, TEXT_DIM]

    x_start = 0.02
    for i in range(6):
        _metric_card(ax, x_start + i * (kpi_w + gap), y_kpi, kpi_w, kpi_h,
                     labels[i], values[i], deltas[i], delta_colors[i])

    ax.text(0.02, 0.957, "MARKET OVERVIEW", fontsize=7, color=TEXT_GREY,
            fontweight="bold", va="center", style="italic")

    # ── Section 2: Four-table grid ───────────────────────────────────
    ax.text(0.02, 0.907, "COMMODITY TABLES", fontsize=7, color=TEXT_GREY,
            fontweight="bold", va="center", style="italic")

    table_w = 0.475
    table_h = 0.20
    x_left = 0.02
    x_right = 0.505
    y_top_row = 0.695
    y_bot_row = 0.48

    mineral_headers = ["Item", "Sell", "Stock", "Jita Sell", "Jita Buy", "% vs Jita"]
    mineral_cw = [table_w * f for f in [0.25, 0.15, 0.15, 0.15, 0.15, 0.15]]
    mineral_rows = [
        ["Tritanium", "3.99", "1.6B", "3.95", "3.79", "1.11%"],
        ["Pyerite", "21.91", "761M", "17.50", "17.38", "25.20%"],
        ["Mexallon", "84.96", "120M", "64.98", "64.37", "30.75%"],
        ["Isogen", "200.80", "39M", "184.00", "168.63", "9.13%"],
        ["Nocxium", "628.50", "42M", "778.33", "752.92", "-19.25%"],
        ["Zydrine", "1,069", "18M", "999.40", "957.11", "6.96%"],
        ["Megacyte", "2,742", "8.8M", "2,413", "2,213", "13.62%"],
        ["Morphite", "19,960", "1.1M", "20,003", "18,751", "-0.22%"],
    ]
    _table(ax, x_left, y_top_row, table_w, table_h, "Basic Minerals",
           mineral_headers, mineral_rows, mineral_cw)

    iso_headers = ["Item", "Sell", "Stock", "Jita Sell", "Jita Buy", "% vs Jita"]
    iso_cw = [table_w * f for f in [0.28, 0.14, 0.12, 0.15, 0.16, 0.15]]
    iso_rows = [
        ["Helium Isotopes", "809.80", "52M", "797.10", "745.52", "1.59%"],
        ["Oxygen Isotopes", "837.80", "54M", "757.44", "689.51", "10.61%"],
        ["Nitrogen Isotopes", "739.00", "33M", "632.10", "597.40", "16.91%"],
        ["Hydrogen Isotopes", "650.00", "41M", "569.47", "522.23", "14.14%"],
        ["Helium Fuel Block", "23,340", "255K", "18,981", "16,289", "22.97%"],
        ["Oxygen Fuel Block", "20,330", "214K", "17,680", "17,319", "14.99%"],
        ["Nitrogen Fuel Block", "17,500", "829K", "17,200", "16,946", "1.74%"],
        ["Hydrogen Fuel Block", "20,980", "53K", "17,330", "16,680", "21.06%"],
    ]
    _table(ax, x_right, y_top_row, table_w, table_h, "Isotopes & Fuel Blocks",
           iso_headers, iso_rows, iso_cw)

    # ── Ships table ──────────────────────────────────────────────────
    ship_headers = ["Ship", "Sell", "Stock", "Jita Sell", "Target", "Status"]
    ship_cw = [table_w * f for f in [0.28, 0.16, 0.12, 0.16, 0.12, 0.16]]
    ship_rows = [
        ["Muninn", "298M", "12", "265M", "20", "Low"],
        ["Eagle", "312M", "8", "278M", "15", "Low"],
        ["Cerberus", "285M", "22", "251M", "20", "OK"],
        ["Sacrilege", "340M", "5", "305M", "10", "Critical"],
        ["Basilisk", "310M", "14", "272M", "15", "OK"],
        ["Oneiros", "275M", "9", "240M", "12", "Low"],
        ["Scimitar", "290M", "18", "255M", "15", "OK"],
        ["Loki", "510M", "3", "465M", "8", "Critical"],
    ]
    _table(ax, x_left, y_bot_row, table_w, table_h, "Doctrine Ships",
           ship_headers, ship_rows, ship_cw)

    # ── Modules table ────────────────────────────────────────────────
    mod_headers = ["Module", "Sell", "Stock", "Jita Sell", "Demand/wk", "% vs Jita"]
    mod_cw = [table_w * f for f in [0.30, 0.14, 0.12, 0.14, 0.15, 0.15]]
    mod_rows = [
        ["720mm Howitzer II", "4.2M", "48", "3.8M", "32", "10.5%"],
        ["Heavy Assault Missile..II", "85K", "1,240", "72K", "890", "18.1%"],
        ["Large Shield Ext II", "2.8M", "156", "2.4M", "210", "16.7%"],
        ["Multispectrum Shield..", "1.9M", "89", "1.6M", "145", "18.8%"],
        ["50MN MWD II", "5.1M", "67", "4.5M", "52", "13.3%"],
        ["Damage Control II", "720K", "312", "610K", "480", "18.0%"],
        ["Ballistic Control Sys II", "1.1M", "198", "920K", "340", "19.6%"],
        ["Gyrostabilizer II", "980K", "245", "830K", "310", "18.1%"],
    ]
    _table(ax, x_right, y_bot_row, table_w, table_h, "Popular Modules",
           mod_headers, mod_rows, mod_cw)

    # ── Section 3: ISK Volume Chart ──────────────────────────────────
    ax.text(0.02, 0.468, "MARKET ACTIVITY", fontsize=7, color=TEXT_GREY,
            fontweight="bold", va="center", style="italic")

    chart_x, chart_y, chart_w, chart_h = 0.02, 0.24, 0.96, 0.22
    _rounded_rect(ax, chart_x, chart_y, chart_w, chart_h)

    ax.text(chart_x + 0.01, chart_y + chart_h - 0.015,
            "Daily ISK Volume — 30 Day Trend",
            fontsize=8, fontweight="bold", color=TEXT_WHITE)

    # Simulated bar chart
    np.random.seed(42)
    n_bars = 30
    bar_area_x = chart_x + 0.04
    bar_area_w = chart_w - 0.06
    bar_area_y = chart_y + 0.025
    bar_area_h = chart_h - 0.06
    values_chart = np.random.uniform(15, 45, n_bars) + np.linspace(0, 8, n_bars)
    max_v = values_chart.max()
    bar_w = bar_area_w / (n_bars * 1.3)

    for i, v in enumerate(values_chart):
        bx = bar_area_x + i * (bar_area_w / n_bars)
        bh = (v / max_v) * bar_area_h
        color = ACCENT_BLUE if v > 30 else "#2D5F8A"
        ax.add_patch(plt.Rectangle((bx, bar_area_y), bar_w, bh,
                                   facecolor=color, edgecolor="none", alpha=0.85))

    # Moving average line
    window = 7
    ma = np.convolve(values_chart, np.ones(window) / window, mode="valid")
    ma_x = [bar_area_x + (i + window // 2) * (bar_area_w / n_bars) + bar_w / 2
            for i in range(len(ma))]
    ma_y = [bar_area_y + (v / max_v) * bar_area_h for v in ma]
    ax.plot(ma_x, ma_y, color=ACCENT_ORANGE, linewidth=1.5, alpha=0.9)

    # Y-axis labels
    for frac, label in [(0, "0"), (0.5, "25B"), (1.0, "50B")]:
        ax.text(chart_x + 0.025, bar_area_y + frac * bar_area_h, label,
                fontsize=5, color=TEXT_DIM, ha="right", va="center")

    # Legend
    ax.add_patch(plt.Rectangle((chart_x + chart_w - 0.15, chart_y + chart_h - 0.02),
                                0.012, 0.006, facecolor=ACCENT_BLUE))
    ax.text(chart_x + chart_w - 0.133, chart_y + chart_h - 0.017, "Daily Volume",
            fontsize=5.5, color=TEXT_GREY, va="center")
    ax.plot([chart_x + chart_w - 0.075, chart_x + chart_w - 0.06],
            [chart_y + chart_h - 0.017, chart_y + chart_h - 0.017],
            color=ACCENT_ORANGE, linewidth=1.5)
    ax.text(chart_x + chart_w - 0.055, chart_y + chart_h - 0.017, "7-day MA",
            fontsize=5.5, color=TEXT_GREY, va="center")

    # ── Section 4: Bottom metrics strip ──────────────────────────────
    ax.text(0.02, 0.228, "30-DAY SUMMARY", fontsize=7, color=TEXT_GREY,
            fontweight="bold", va="center", style="italic")

    summary_y = 0.18
    summary_h = 0.04
    summary_w = 0.23
    gap_s = 0.013
    summaries = [
        ("Avg Daily ISK Volume", "28.6B ISK", "▲ 8.1%", ACCENT_GREEN),
        ("Avg Daily Items Sold", "142,560", "▲ 12.3%", ACCENT_GREEN),
        ("Total 30d Value", "858.3B ISK", "▲ 5.7%", ACCENT_GREEN),
        ("Total 30d Volume", "4.28M items", "▼ 2.1%", ACCENT_RED),
    ]
    for i, (lbl, val, delta, dc) in enumerate(summaries):
        _metric_card(ax, 0.02 + i * (summary_w + gap_s), summary_y, summary_w, summary_h,
                     lbl, val, delta, dc)

    # ── Section label: Top N Items ────────────────────────────────
    ax.text(0.02, 0.168, "TOP ITEMS", fontsize=7, color=TEXT_GREY,
            fontweight="bold", va="center", style="italic")

    topn_headers = ["#", "Item", "Daily ISK Volume", "30d Volume", "% of Market"]
    topn_cw_total = 0.96
    topn_cw = [topn_cw_total * f for f in [0.05, 0.35, 0.20, 0.20, 0.20]]
    topn_rows = [
        ["1", "PLEX", "4.82B ISK", "144.6B ISK", "16.8%"],
        ["2", "Skill Injector", "3.21B ISK", "96.3B ISK", "11.2%"],
        ["3", "Muninn", "1.87B ISK", "56.1B ISK", "6.5%"],
        ["4", "Tritanium", "1.54B ISK", "46.2B ISK", "5.4%"],
        ["5", "Eagle", "1.22B ISK", "36.6B ISK", "4.3%"],
    ]
    _table(ax, 0.02, 0.06, topn_cw_total, 0.10, "Top Items by ISK Volume (30 Days)",
           topn_headers, topn_rows, topn_cw)

    # ── Footer ───────────────────────────────────────────────────────
    ax.text(0.5, 0.035, "— Mockup: Proposed Market Stats Page Redesign —",
            fontsize=7, color=TEXT_DIM, ha="center", style="italic")
    ax.text(0.5, 0.02, "Sell/Buy order tables removed  •  Four-table commodity grid  •  Topline KPIs  •  Chart preserved",
            fontsize=6, color=TEXT_DIM, ha="center")

    plt.tight_layout(pad=0.5)
    path = os.path.join(OUT_DIR, "mockup_01_full_page.png")
    fig.savefig(path, dpi=180, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


# ═════════════════════════════════════════════════════════════════════════
# MOCKUP 2 – Four-Table Grid Close-Up with Status Indicators
# ═════════════════════════════════════════════════════════════════════════

def mockup_grid_detail():
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.97, "Four-Table Grid — Detail View",
            fontsize=14, fontweight="bold", color=TEXT_WHITE, ha="center")
    ax.text(0.5, 0.945, "Material commodities on top  •  Doctrine ships & popular modules on bottom",
            fontsize=8, color=TEXT_DIM, ha="center")

    table_w = 0.475
    table_h = 0.42
    x_left = 0.02
    x_right = 0.505
    y_top = 0.50
    y_bot = 0.04

    # ── Basic Minerals ───────────────────────────────────────────────
    m_hdr = ["", "Item", "Sell Price", "Stock", "Jita Sell", "Jita Buy", "% vs Jita"]
    m_cw = [table_w * f for f in [0.04, 0.22, 0.14, 0.12, 0.14, 0.14, 0.14]]
    m_rows = [
        ["●", "Tritanium", "3.99", "1.6B", "3.95", "3.79", "1.11%"],
        ["●", "Pyerite", "21.91", "761M", "17.50", "17.38", "25.20%"],
        ["●", "Mexallon", "84.96", "120M", "64.98", "64.37", "30.75%"],
        ["●", "Isogen", "200.80", "39M", "184.00", "168.63", "9.13%"],
        ["●", "Nocxium", "628.50", "42M", "778.33", "752.92", "-19.25%"],
        ["●", "Zydrine", "1,069.00", "18M", "999.40", "957.11", "6.96%"],
        ["●", "Megacyte", "2,742.00", "8.8M", "2,413.27", "2,213.17", "13.62%"],
        ["●", "Morphite", "19,960.00", "1.1M", "20,003.01", "18,751.38", "-0.22%"],
        ["●", "Magmatic Gas", "3,645.00", "1.7M", "2,250.00", "2,003.72", "62.00%"],
    ]
    _table(ax, x_left, y_top, table_w, table_h, "Basic Minerals",
           m_hdr, m_rows, m_cw)

    # ── Isotopes ─────────────────────────────────────────────────────
    i_hdr = ["", "Item", "Sell Price", "Stock", "Jita Sell", "Jita Buy", "% vs Jita"]
    i_cw = [table_w * f for f in [0.04, 0.24, 0.13, 0.11, 0.14, 0.14, 0.14]]
    i_rows = [
        ["●", "Helium Isotopes", "809.80", "52M", "797.10", "745.52", "1.59%"],
        ["●", "Oxygen Isotopes", "837.80", "54M", "757.44", "689.51", "10.61%"],
        ["●", "Nitrogen Isotopes", "739.00", "33M", "632.10", "597.40", "16.91%"],
        ["●", "Hydrogen Isotopes", "650.00", "41M", "569.47", "522.23", "14.14%"],
        ["●", "Helium Fuel Block", "23,340", "255K", "18,981", "16,289", "22.97%"],
        ["●", "Oxygen Fuel Block", "20,330", "214K", "17,680", "17,319", "14.99%"],
        ["●", "Nitrogen Fuel Block", "17,500", "829K", "17,200", "16,946", "1.74%"],
        ["●", "Hydrogen Fuel Block", "20,980", "53K", "17,330", "16,680", "21.06%"],
        ["●", "Liquid Ozone", "79.96", "6.4M", "97.86", "90.46", "-18.29%"],
    ]
    _table(ax, x_right, y_top, table_w, table_h, "Isotopes & Fuel Blocks",
           i_hdr, i_rows, i_cw)

    # ── Doctrine Ships ───────────────────────────────────────────────
    s_hdr = ["Ship", "Sell Price", "Stock", "Jita Sell", "Target", "Fits Avail", "Status"]
    s_cw = [table_w * f for f in [0.22, 0.14, 0.10, 0.14, 0.10, 0.14, 0.14]]
    s_rows = [
        ["Muninn", "298M", "12", "265M", "20", "8", "▼ Low"],
        ["Eagle", "312M", "8", "278M", "15", "5", "▼ Low"],
        ["Cerberus", "285M", "22", "251M", "20", "18", "● OK"],
        ["Sacrilege", "340M", "5", "305M", "10", "3", "▼▼ Crit"],
        ["Basilisk", "310M", "14", "272M", "15", "12", "● OK"],
        ["Oneiros", "275M", "9", "240M", "12", "6", "▼ Low"],
        ["Scimitar", "290M", "18", "255M", "15", "15", "● OK"],
        ["Loki", "510M", "3", "465M", "8", "2", "▼▼ Crit"],
        ["Jackdaw", "62M", "45", "54M", "30", "38", "▲ Good"],
    ]
    _table(ax, x_left, y_bot, table_w, table_h, "Doctrine Ships — Stock vs Targets",
           s_hdr, s_rows, s_cw)

    # ── Popular Modules ──────────────────────────────────────────────
    p_hdr = ["Module", "Sell Price", "Stock", "Jita Sell", "30d Vol", "% vs Jita"]
    p_cw = [table_w * f for f in [0.28, 0.14, 0.10, 0.14, 0.14, 0.14]]
    p_rows = [
        ["720mm Howitzer II", "4.2M", "48", "3.8M", "960", "10.5%"],
        ["Heavy Assault Msle L II", "85K", "1,240", "72K", "26.7K", "18.1%"],
        ["Large Shield Ext II", "2.8M", "156", "2.4M", "6.3K", "16.7%"],
        ["Multispect Shield HF II", "1.9M", "89", "1.6M", "4.4K", "18.8%"],
        ["50MN MWD II", "5.1M", "67", "4.5M", "1.6K", "13.3%"],
        ["Damage Control II", "720K", "312", "610K", "14.4K", "18.0%"],
        ["Ballistic Ctrl Sys II", "1.1M", "198", "920K", "10.2K", "19.6%"],
        ["Gyrostabilizer II", "980K", "245", "830K", "9.3K", "18.1%"],
        ["Stasis Webifier II", "1.3M", "178", "1.1M", "5.4K", "18.2%"],
    ]
    _table(ax, x_right, y_bot, table_w, table_h, "Popular Modules — Demand & Pricing",
           p_hdr, p_rows, p_cw)

    plt.tight_layout(pad=0.5)
    path = os.path.join(OUT_DIR, "mockup_02_grid_detail.png")
    fig.savefig(path, dpi=180, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


# ═════════════════════════════════════════════════════════════════════════
# MOCKUP 3 – Chart + Summary Strip
# ═════════════════════════════════════════════════════════════════════════

def mockup_chart_section():
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.97, "Chart & Summary Section — Detail View",
            fontsize=14, fontweight="bold", color=TEXT_WHITE, ha="center")

    # ── KPI strip ────────────────────────────────────────────────────
    kpi_y = 0.88
    kpi_h = 0.06
    kpi_w = 0.23
    gap = 0.013
    kpis = [
        ("Avg Daily ISK Volume", "28.6B ISK", "▲ 8.1% vs prior 30d", ACCENT_GREEN),
        ("Avg Daily Items Sold", "142,560", "▲ 12.3% vs prior 30d", ACCENT_GREEN),
        ("Total 30d Value", "858.3B ISK", "▲ 5.7% vs prior 30d", ACCENT_GREEN),
        ("Total 30d Volume", "4.28M items", "▼ 2.1% vs prior 30d", ACCENT_RED),
    ]
    for i, (lbl, val, delta, dc) in enumerate(kpis):
        _metric_card(ax, 0.02 + i * (kpi_w + gap), kpi_y, kpi_w, kpi_h,
                     lbl, val, delta, dc)

    # ── Chart area ───────────────────────────────────────────────────
    chart_x, chart_y, chart_w, chart_h = 0.02, 0.28, 0.96, 0.55
    _rounded_rect(ax, chart_x, chart_y, chart_w, chart_h)

    ax.text(chart_x + 0.015, chart_y + chart_h - 0.03,
            "Daily ISK Volume — All Market Items",
            fontsize=10, fontweight="bold", color=TEXT_WHITE)

    # Controls strip
    controls_y = chart_y + chart_h - 0.07
    ctrl_labels = ["Date Range ▾", "Period: Daily ▾", "MA: 7-day ▾", "Outliers: Cap ▾"]
    for i, label in enumerate(ctrl_labels):
        cx = chart_x + 0.015 + i * 0.14
        _rounded_rect(ax, cx, controls_y, 0.12, 0.025,
                      color="#333645", border_color="#555770", radius=0.005)
        ax.text(cx + 0.06, controls_y + 0.0125, label, fontsize=6,
                color=TEXT_GREY, ha="center", va="center")

    # Bar chart
    np.random.seed(42)
    n_bars = 30
    bar_area_x = chart_x + 0.06
    bar_area_w = chart_w - 0.08
    bar_area_y = chart_y + 0.04
    bar_area_h = chart_h - 0.15
    vals = np.random.uniform(18, 48, n_bars) + np.linspace(0, 10, n_bars)
    max_v = vals.max()
    bar_w_chart = bar_area_w / (n_bars * 1.3)

    for i, v in enumerate(vals):
        bx = bar_area_x + i * (bar_area_w / n_bars)
        bh = (v / max_v) * bar_area_h
        # Gradient-like coloring
        intensity = v / max_v
        r = int(30 + 47 * intensity)
        g = int(60 + 106 * intensity)
        b = int(120 + 135 * intensity)
        color = f"#{r:02x}{g:02x}{b:02x}"
        ax.add_patch(plt.Rectangle((bx, bar_area_y), bar_w_chart, bh,
                                   facecolor=color, edgecolor="none", alpha=0.9))

    # MA line
    window = 7
    ma = np.convolve(vals, np.ones(window) / window, mode="valid")
    ma_x = [bar_area_x + (i + window // 2) * (bar_area_w / n_bars) + bar_w_chart / 2
            for i in range(len(ma))]
    ma_y = [bar_area_y + (v / max_v) * bar_area_h for v in ma]
    ax.plot(ma_x, ma_y, color=ACCENT_ORANGE, linewidth=2, alpha=0.9)

    # Y-axis
    for frac, label in [(0, "0"), (0.25, "15B"), (0.5, "30B"), (0.75, "45B"), (1.0, "60B")]:
        ly = bar_area_y + frac * bar_area_h
        ax.text(chart_x + 0.045, ly, label, fontsize=5.5, color=TEXT_DIM, ha="right", va="center")
        ax.plot([chart_x + 0.055, chart_x + chart_w - 0.015], [ly, ly],
                color=DIVIDER, linewidth=0.3, alpha=0.5)

    # X-axis dates
    dates = ["Feb 15", "Feb 18", "Feb 21", "Feb 24", "Feb 27", "Mar 2",
             "Mar 5", "Mar 8", "Mar 11", "Mar 14"]
    for i, d in enumerate(dates):
        dx = bar_area_x + i * (bar_area_w / len(dates)) + bar_area_w / (2 * len(dates))
        ax.text(dx, bar_area_y - 0.015, d, fontsize=5, color=TEXT_DIM,
                ha="center", va="center", rotation=0)

    # Legend
    legend_y = chart_y + chart_h - 0.03
    ax.add_patch(plt.Rectangle((chart_x + chart_w - 0.20, legend_y - 0.003),
                                0.015, 0.008, facecolor=ACCENT_BLUE))
    ax.text(chart_x + chart_w - 0.18, legend_y + 0.001, "Daily ISK Volume",
            fontsize=6, color=TEXT_GREY, va="center")
    ax.plot([chart_x + chart_w - 0.10, chart_x + chart_w - 0.08],
            [legend_y + 0.001, legend_y + 0.001], color=ACCENT_ORANGE, linewidth=2)
    ax.text(chart_x + chart_w - 0.075, legend_y + 0.001, "7-day MA",
            fontsize=6, color=TEXT_GREY, va="center")

    # ── Top N Items table ────────────────────────────────────────────
    topn_y = 0.03
    topn_h = 0.22
    topn_hdr = ["Rank", "Item", "Avg Daily ISK", "Total 30d ISK", "Daily Items", "% of Market"]
    topn_cw_total = 0.96
    topn_cw = [topn_cw_total * f for f in [0.06, 0.30, 0.16, 0.18, 0.14, 0.14]]
    topn_rows = [
        ["1", "PLEX", "4.82B", "144.6B", "312", "16.8%"],
        ["2", "Large Skill Injector", "3.21B", "96.3B", "186", "11.2%"],
        ["3", "Muninn", "1.87B", "56.1B", "24", "6.5%"],
        ["4", "Tritanium", "1.54B", "46.2B", "12.4M", "5.4%"],
        ["5", "Eagle", "1.22B", "36.6B", "18", "4.3%"],
        ["6", "Helium Fuel Block", "980M", "29.4B", "1,280", "3.4%"],
        ["7", "Cerberus", "870M", "26.1B", "15", "3.0%"],
    ]
    _table(ax, 0.02, topn_y, topn_cw_total, topn_h,
           "Top Items by ISK Volume (30 Days)  —  Week ▾  |  ISK ▾  |  Daily ▾",
           topn_hdr, topn_rows, topn_cw)

    plt.tight_layout(pad=0.5)
    path = os.path.join(OUT_DIR, "mockup_03_chart_section.png")
    fig.savefig(path, dpi=180, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


if __name__ == "__main__":
    mockup_full_page()
    mockup_grid_detail()
    mockup_chart_section()
    print("\nAll mockups generated!")
