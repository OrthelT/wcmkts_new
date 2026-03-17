"""
UI Translation Helpers

Keeps lightweight frontend copy translations in one place.
"""

from typing import Final

from settings_service import SettingsService

DEFAULT_LANGUAGE: Final = SettingsService().default_language

LANGUAGE_OPTIONS: Final[dict[str, str]] = {
    "en": "🇬🇧 EN",
    "zh": "🇨🇳 CN",
    "de": "🇩🇪 DE",
    "fr": "🇫🇷 FR",
    "ru": "🇷🇺 RU",
    "es": "🇪🇸 ES",
    "ja": "🇯🇵 JP",
    "ko": "🇰🇷 KR",
}

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "app.page_title": "WinterCo Markets",
        "app.language_label": "Language",
        "nav.section.market_stats": "Market Stats",
        "nav.section.analysis_tools": "Analysis Tools",
        "nav.section.data": "Data",
        "nav.page.market_stats": "📈Market Stats",
        "nav.page.low_stock": "⚠️Low Stock",
        "nav.page.import_helper": "📦Import Helper",
        "nav.page.doctrine_status": "⚔️Doctrine Status",
        "nav.page.doctrine_report": "📝Doctrine Report",
        "nav.page.build_costs": "🏗️Build Costs",
        "nav.page.pricer": "🏷️Pricer",
        "nav.page.downloads": "📥Downloads",
        "doctrine_status.title": "{market_name} Doctrine Status",
        "doctrine_status.tab_market_stock": "Market Stock",
        "doctrine_status.tab_fit_details": "Fit Details",
        "doctrine_status.low_stock_modules": "Low Stock Modules",
        "doctrine_status.no_fits": "No doctrine fits found in the database.",
        "doctrine_report.subtitle": "{market_name} Market Status By Fleet Doctrine",
        "doctrine_report.no_data": "No data to display",
        "doctrine_report.metric_total_fits": "Total Fits Available",
        "doctrine_report.metric_total_hulls": "Total Hulls",
        "doctrine_report.metric_avg_target_pct": "Avg Target %",
        "doctrine_report.role_dps": "💥 **DPS** - Primary DPS Ships",
        "doctrine_report.role_logi": "🏥 **Logi** - Logistics Ships",
        "doctrine_report.role_links": "📡 **Links** - Command Ships",
        "doctrine_report.role_support": "🛠️ **Support** - EWAR, Tackle & Other Support Ships",
        "doctrine_report.stock_status": "Stock Status",
        "doctrine_report.stock_status_summary": (
            "*Summary of the stock status of the three lowest stock modules for each ship in the "
            "selected doctrine. Numbers in parentheses represent the number of fits that can be "
            "supported with the current stock of the item. Use the checkboxes to select items for "
            "export to a CSV file.*"
        ),
        "doctrine_report.fit_id": "Fit ID",
        "doctrine_report.target": "Target",
        "doctrine_report.no_target_found": "No target found for this fit",
        "doctrine_report.equivalent_stock_caption": "🔄 Stock includes equivalent modules",
        "doctrine_report.no_fits": "No doctrine fits found in the database.",
        "doctrine_report.select_doctrine": "Select a doctrine",
        "doctrine_report.target_multiplier": "Target Multiplier",
        "doctrine_report.target_multiplier_help": (
            "This multiplier is applied to the target value for each fit. It is used to make the "
            "target more or less aggressive. The default value is 1.0."
        ),
        "doctrine_report.current_target_multiplier": "Current Target Multiplier: {value}",
        "doctrine_report.ship_image_not_available": "🚀 Ship Image Not Available",
        "doctrine_report.doctrine_id": "Doctrine ID: {doctrine_id}",
        "doctrine_report.selected_items": "Selected Items",
        "doctrine_report.modules_label": "Modules:",
        "doctrine_report.no_items_selected": "No items selected",
        "doctrine_report.export_options": "Export Options",
        "doctrine_report.download_csv": "📥 Download CSV",
        "doctrine_report.clear_selection": "🗑️ Clear Selection",
        "doctrine_report.column_target_pct": "Target %",
        "doctrine_report.column_target": "Target",
        "doctrine_report.column_target_help": "Number of fits required for stock.",
        "doctrine_report.column_daily_sales": "Daily Sales",
        "doctrine_report.column_daily_sales_help": "Average daily sales over the last 30 days.",
        "doctrine_report.column_group_help": "Ship group.",
        "doctrine_report.column_ship": "Ship",
        "doctrine_report.column_ship_help": "Ship name.",
        "doctrine_report.column_ship_id_help": "Ship type ID.",
        "doctrine_report.column_fit_id": "Fit ID",
        "doctrine_report.column_fit_id_help": "Doctrine fit ID.",
        "doctrine_report.column_price_help": "Price of the ship.",
        "doctrine_report.column_total_cost": "Total Cost",
        "doctrine_report.column_total_cost_help": "Total cost of the fit.",
        "common.market_hub": "Market Hub",
        "common.select": "Select",
        "common.type_id": "Type ID",
        "common.item": "Item",
        "common.category": "Category",
        "common.group": "Group",
        "common.price": "Price",
        "low_stock.title": "{market_name} Low Stock Tool",
        "low_stock.description": (
            "This page shows items that are running low on the market. "
            "The **Days Remaining** column shows how many days of sales can be sustained "
            "by the current stock based on historical average sales. Items with fewer days "
            "remaining need attention. The **Used In Fits** column shows the doctrine ships "
            "that use the item, if any, and the number of fits the current market stock can support."
        ),
        "low_stock.filters_header": "Filters",
        "low_stock.filters_help": "Use the filters below to customize your view of low stock items.",
        "low_stock.item_type_filters": "Item Type Filters",
        "low_stock.doctrine_only": "Doctrine Items Only",
        "low_stock.doctrine_only_help": "Show only items that are used in a doctrine fit.",
        "low_stock.tech2_only": "Tech II Items Only",
        "low_stock.tech2_only_help": "Show only Tech II items (metaGroupID=2).",
        "low_stock.faction_only": "Faction Items Only",
        "low_stock.faction_only_help": "Show only faction items (metaGroupID=4).",
        "low_stock.category_filter": "Category Filter",
        "low_stock.select_categories": "Select Categories",
        "low_stock.select_categories_help": "Select one or more categories to filter the data.",
        "low_stock.doctrine_fit_filter": "Doctrine/Fit Filter",
        "low_stock.select_doctrine": "Select Doctrine",
        "low_stock.select_doctrine_help": "Filter to show only items from a specific doctrine.",
        "low_stock.select_fit": "Select Fit",
        "low_stock.select_fit_help": "Filter to show only items from a specific fit.",
        "low_stock.days_filter": "Days Remaining Filter",
        "low_stock.max_days_remaining": "Maximum Days Remaining",
        "low_stock.max_days_remaining_help": (
            "Show only items with days remaining less than or equal to this value."
        ),
        "low_stock.show_zero_volume_items": "Show 0 Volume Items",
        "low_stock.show_zero_volume_items_help": (
            "Include items whose 30-day average volume is zero."
        ),
        "low_stock.metric_critical": "Critical Items (≤3 days)",
        "low_stock.metric_low": "Low Stock Items (3-7 days)",
        "low_stock.metric_total": "Total Filtered Items",
        "low_stock.subheader_fit": "Low Stock: {ship_name}",
        "low_stock.subheader_doctrine": "Low Stock: {doctrine_name}",
        "low_stock.subheader_all": "Low Stock Items",
        "low_stock.column_select_help": "Check items you want to include in the CSV download.",
        "low_stock.column_item_help": "Name of the item.",
        "low_stock.column_volume_remaining": "Remaining",
        "low_stock.column_volume_remaining_help": "Total items currently available on the market.",
        "low_stock.column_fits": "Fits",
        "low_stock.column_fits_help": "Total fits that can be built from the stock of this item.",
        "low_stock.column_days": "Days",
        "low_stock.column_days_help": "Days of stock remaining based on historical average sales.",
        "low_stock.column_avg_vol": "Avg Vol",
        "low_stock.column_avg_vol_help": "Average volume over the last 30 days.",
        "low_stock.column_used_in_fits": "Used In Fits",
        "low_stock.column_used_in_fits_help": "Doctrine ships that use this item.",
        "low_stock.column_category_help": "Category of the item.",
        "low_stock.column_group_help": "Group of the item.",
        "low_stock.selected_items": (
            "{count} items selected. Visit the **Downloads** page for bulk CSV exports."
        ),
        "low_stock.chart_section": "Days Remaining by Item",
        "low_stock.chart_title": "Days of Stock Remaining",
        "low_stock.chart_days_label": "Days Remaining",
        "low_stock.chart_critical_level": "Critical Level (3 days)",
        "import_helper.title": "{market_name} Import Helper",
        "import_helper.description": (
            "Discover items where the local market price sits well above Jita sell. "
            "30D Profit uses `(Local Price - Jita Sell) * 30D Volume`, "
            "RRP uses `Jita Sell * (1 + Markup Margin)`, and Cap Utilis uses "
            "`((Local Price - Jita Sell) - Shipping Cost) / Jita Sell`."
        ),
        "import_helper.caption_green": "Green",
        "import_helper.caption_grey": "Grey",
        "import_helper.caption_estimated_price": (
            "{color_label} cells show estimated local prices at 140% of Jita sell "
            "(no local sell orders)"
        ),
        "import_helper.caption_floored_volume": (
            "{color_label} cells show 30D volume floored to 0.5 (insufficient history)"
        ),
        "import_helper.filters_header": "Filters",
        "import_helper.categories": "Categories",
        "import_helper.categories_help": "Limit the table to one or more item categories.",
        "import_helper.search_items": "Search Items",
        "import_helper.search_items_help": "Case-insensitive name filter.",
        "import_helper.profitable_only": "Positive Profit Only",
        "import_helper.profitable_only_help": (
            "Hide items where the local market price is not above Jita sell."
        ),
        "import_helper.min_capital_utilis": "Minimum Capital Utilis",
        "import_helper.min_capital_utilis_help": (
            "0.10 means at least 10% capital utilisation after shipping."
        ),
        "import_helper.min_turnover_30d": "Minimum 30D Turnover",
        "import_helper.min_turnover_30d_help": "Hide items whose 30D Turnover is below this value.",
        "import_helper.shipping_cost_per_m3": "Shipping Cost per m3",
        "import_helper.shipping_cost_per_m3_help": (
            "Used to calculate shipping cost. The default value comes from settings.toml."
        ),
        "import_helper.markup_margin": "Markup Margin",
        "import_helper.markup_margin_help": "Used for RRP. 0.20 means 20% above Jita sell.",
        "import_helper.metric_total_items": "Total Items",
        "import_helper.metric_profitable_items": "Positive Profit Items",
        "import_helper.metric_avg_capital_utilis": "Avg Capital Utilis",
        "import_helper.column_item_help": "Localized item name when available.",
        "import_helper.column_rrp_help": "Recommended retail price based on Jita sell and markup.",
        "import_helper.column_jita_sell_help": "Jita sell percentile price.",
        "import_helper.column_jita_buy_help": "Jita buy percentile price.",
        "import_helper.column_shipping_help": (
            "Calculated as item size in m3 multiplied by {shipping_cost_per_m3}."
        ),
        "import_helper.column_profit_30d_help": (
            "Calculated as (local price - Jita sell price) multiplied by traded volume over 30 days."
        ),
        "import_helper.column_turnover_30d_help": "30-day traded volume multiplied by Jita sell price.",
        "import_helper.column_volume_30d_help": "Total traded volume over the past 30 days.",
        "import_helper.column_capital_utilis_help": (
            "Calculated as ((local price - Jita sell price) - shipping cost) divided by Jita sell."
        ),
        "import_helper.column_rrp": "RRP",
        "import_helper.column_jita_sell": "Jita Sell",
        "import_helper.column_jita_buy": "Jita Buy",
        "import_helper.column_shipping": "Shipping",
        "import_helper.column_profit_30d": "30D Profit",
        "import_helper.column_turnover_30d": "30D Turnover",
        "import_helper.column_volume_30d": "30D Volume",
        "import_helper.column_capital_utilis": "Cap Utilis",
        "doctrine_status.logo_not_found": "Logo image not found",
        "doctrine_status.downloads_hint": "Use Downloads page for full data export",
        "doctrine_status.filter_doctrine": "Doctrine",
        "doctrine_status.filter_stock_status": "Stock Status",
        "doctrine_status.filter_ship_group": "Ship Group",
        "doctrine_status.no_filtered_fits": "No fits found with the selected filters.",
        "doctrine_status.ship_group_help": "Ship doctrine group.",
        "doctrine_status.image_not_available": "Image not available",
        "doctrine_status.fit_id_label": "ID: {fit_id}",
        "doctrine_status.fit_name_label": "Fit: {fit_name}",
        "doctrine_status.includes_equivalent_modules": "includes equivalent modules",
        "doctrine_status.critical_stock_level": "Critical stock level",
        "doctrine_status.low_stock_help": "Low stock",
        "doctrine_status.view_stock_breakdown": "📋 View stock breakdown",
        "doctrine_status.combined_stock_caption": "Combined stock from equivalent modules:",
        "doctrine_status.combined_total": "Combined Total: {total}",
        "doctrine_status.fit_header": "{ship_name} - Fit {fit_id}",
        "doctrine_status.load_fit_details": "Load Fit Details",
        "doctrine_status.no_fit_details": "No detailed fitting data available for this fit.",
        "doctrine_status.select_all": "📋 Select All",
        "doctrine_status.clear_all": "🗑️ Clear All",
        "doctrine_status.selected_items": "Selected Items",
        "doctrine_status.render_market_data": "📊 Render market data for export",
        "doctrine_status.market_data": "Market Data",
        "doctrine_status.market_data_line": "  {name} (Stock: {stock} | Fits: {fits} | Need: {need})",
        "doctrine_status.select_items_for_export": (
            "Select ships and modules to export by checking the boxes next to them."
        ),
        "doctrine_status.column_qty_per_fit": "Qty/Fit",
        "doctrine_status.column_qty_per_fit_help": "Quantity of this item per fit.",
        "doctrine_status.column_total_stock_help": "Total stock of this item.",
        "doctrine_status.column_category_id": "Category ID",
        "doctrine_status.column_category_id_help": "Category ID.",
        "market_stats.title": "Winter Coalition Market Stats - {market_name} Market {header_env}",
        "market_stats.show_all_data": "Show All Data",
        "market_stats.select_category": "Select Category",
        "market_stats.select_item": "Select Item",
        "market_stats.all_sell_orders": "All Sell Orders",
        "market_stats.winter_co_doctrine": "Winter Co. Doctrine",
        "market_stats.category_plural": "{category_name}s",
        "market_stats.thirty_day_market_stats": "30-Day Market Stats (expand to view metrics)",
        "market_stats.sell_orders_for": "Sell Orders for {name}",
        "market_stats.all_buy_orders": "All Buy Orders",
        "market_stats.buy_orders_for": "Buy Orders for {name}",
        "market_stats.market_value_buy_orders": "Market Value (buy orders)",
        "market_stats.total_buy_orders": "Total Buy Orders",
        "market_stats.no_current_buy_orders": "No current buy orders found for {item_name}",
        "market_stats.no_current_market_orders": "No current market orders found for {item_name}",
        "market_stats.market_history": "Market History - {item_name}",
        "market_stats.price_history": "Price History - {filter_info}",
        "market_stats.expand_market_history_data": "Expand to view Market History Data",
        "market_stats.fitting_data": "Fitting Data",
        "market_stats.check_db_state": "Check DB State",
        "market_stats.downloads_hint": (
            "*Visit the **Downloads** page for market data, doctrine fits, and SDE table exports.*"
        ),
        "market_stats.date_range": "Date Range",
        "market_stats.available_data_range": "Available data range: {start} to {end}",
        "market_stats.start_date": "Start Date",
        "market_stats.start_date_help": "Select start date (available: {start} to {end})",
        "market_stats.end_date": "End Date",
        "market_stats.end_date_help": "Select end date (available: {start} to {end})",
        "market_stats.chart_controls": "Chart Controls",
        "market_stats.moving_average_period": "Moving Average Period",
        "market_stats.moving_average": "Moving Average",
        "market_stats.date_aggregation": "Date Aggregation",
        "market_stats.date_period": "Date Period",
        "market_stats.period_daily": "Daily",
        "market_stats.period_weekly": "Weekly",
        "market_stats.period_monthly": "Monthly",
        "market_stats.period_yearly": "Yearly",
        "market_stats.outlier_handling": "Outlier Handling",
        "market_stats.outlier_method": "Outlier Method",
        "market_stats.outlier_method_cap": "Cap Outliers",
        "market_stats.outlier_method_remove": "Remove Outliers",
        "market_stats.outlier_method_none": "Show All Data",
        "market_stats.outlier_method_help": "How to handle extreme values that skew the chart scale.",
        "market_stats.outlier_sensitivity": "Outlier Sensitivity",
        "market_stats.outlier_sensitivity_help": (
            "Lower values mean more aggressive outlier detection (1.5 = standard IQR)."
        ),
        "market_stats.cap_at_percentile": "Cap at Percentile",
        "market_stats.cap_at_percentile_help": "Percentile to cap outliers at.",
        "market_stats.outlier_handling_explained": (
            "**Outlier Handling Explained:**\n"
            "- **Cap Outliers**: Replaces extreme values with a percentile-based limit\n"
            "- **Remove Outliers**: Completely removes extreme data points\n"
            "- **Show All Data**: No outlier handling"
        ),
        "market_stats.date": "Date",
        "market_stats.date_help": "Date of the data.",
        "market_stats.isk_volume": "ISK Volume",
        "market_stats.isk_volume_help": "ISK volume of the data.",
        "market_stats.filter_info": "Start Date: {start_date} | End Date: {end_date} | Date Period: {date_period}",
        "market_stats.filter_info_category": " | Category: {category_name}",
        "market_stats.no_market_history_for_category": "No market history data available for category: {category_name}",
        "market_stats.no_market_history": "No market history data available",
        "market_stats.no_market_history_selected_filters": "No market history data available for the selected filters",
        "market_stats.thirty_day_market_stats_with_label": "30-Day Market Stats ({label})",
        "market_stats.insufficient_data": "Insufficient data recorded for this item",
        "market_stats.avg_daily_isk_30d": "Avg Daily ISK (30d)",
        "market_stats.this_week_delta": "{value}% this week",
        "market_stats.avg_daily_items_30d": "Avg Daily Items (30d)",
        "market_stats.total_value_30d": "Total Value (30d)",
        "market_stats.total_volume_30d": "Total Volume (30d)",
        "market_stats.current_market_status": "Current Market Status",
        "market_stats.sell_price": "Sell Price",
        "market_stats.delta_vs_jita": "{value}% Jita",
        "market_stats.jita_sell_price": "Jita Sell Price",
        "market_stats.market_stock": "Market Stock",
        "market_stats.sell_orders_value": "Sell Orders Value",
        "market_stats.total_sell_orders": "Total Sell Orders",
        "market_stats.fits_on_market": "Fits on Market",
        "market_stats.fit_target_delta": (
            "Fit: {fit_id}, Target: {target}, Fits on Market: {fits_on_market}, Delta: {delta}"
        ),
        "market_stats.target_value": "Target: {target}",
        "market_stats.average_price": "Average Price",
        "market_stats.volume": "Volume",
        "market_stats.average_price_7d": "Average Price (7 days)",
        "market_stats.average_volume_7d": "Average Volume (7 days)",
        "market_stats.average_price_30d": "Average Price (30 days)",
        "market_stats.average_volume_30d": "Average Volume (30 days)",
        "market_stats.order_id": "Order ID",
        "market_stats.duration": "Duration",
        "market_stats.issued": "Issued",
        "market_stats.expires": "Expires",
        "pricer.title": "Winter Coalition Pricer",
        "pricer.description": "Price items and fittings using Jita and {market_name} market data.",
        "pricer.input_section": "Input",
        "pricer.input_placeholder": (
            "Paste items here in one of these formats:\n\n"
            "EFT Fitting:\n"
            "[Hurricane, PVP Fit]\n"
            "Damage Control II\n"
            "1600mm Steel Plates II\n"
            "...\n\n"
            "Tab-separated (item first):\n"
            "Tritanium\t10000\n"
            "Pyerite\t5000\n\n"
            "Tab-separated (qty first):\n"
            "10000\tTritanium\n"
            "5000\tPyerite"
        ),
        "pricer.input_label": "Paste EFT fitting or item list:",
        "pricer.price_items": "Price Items",
        "pricer.fetching_prices": "Fetching prices...",
        "pricer.format_label": "Format",
        "pricer.format_multibuy": "Multibuy/Item List",
        "pricer.totals": "Totals",
        "pricer.column_icon": "Icon",
        "pricer.column_icon_help": "Item icon.",
        "pricer.column_type_id_help": "Type ID.",
        "pricer.column_item_help": "Item name.",
        "pricer.column_qty": "Qty",
        "pricer.column_qty_help": "Quantity.",
        "pricer.column_slot": "Slot",
        "pricer.column_slot_help": "Slot type.",
        "pricer.column_local_sell": "{market_name} Sell",
        "pricer.column_local_sell_help": "{market_name} minimum sell price per unit.",
        "pricer.column_local_sell_volume": "{market_name} Vol",
        "pricer.column_local_sell_volume_help": "{market_name} sell volume.",
        "pricer.column_jita_sell": "Jita Sell",
        "pricer.column_jita_sell_help": "Jita sell price per unit.",
        "pricer.column_jita_buy": "Jita Buy",
        "pricer.column_jita_buy_help": "Jita buy price per unit.",
        "pricer.column_jita_sell_total": "Jita Sell Total",
        "pricer.column_jita_sell_total_help": "Total Jita sell value.",
        "pricer.column_jita_buy_total": "Jita Buy Total",
        "pricer.column_jita_buy_total_help": "Total Jita buy value.",
        "pricer.column_local_buy": "{market_name} Buy",
        "pricer.column_local_buy_help": "{market_name} maximum buy price per unit.",
        "pricer.column_local_sell_total": "{market_name} Sell Total",
        "pricer.column_local_sell_total_help": "Total {market_name} sell value.",
        "pricer.column_local_buy_total": "{market_name} Buy Total",
        "pricer.column_local_buy_total_help": "Total {market_name} buy value.",
        "pricer.column_volume": "Vol (m3)",
        "pricer.column_volume_help": "Volume per unit in m3.",
        "pricer.column_total_volume": "Total Vol (m3)",
        "pricer.column_total_volume_help": "Total volume (Qty x Volume).",
        "pricer.column_category_help": "Item category.",
        "pricer.column_avg_daily_volume": "Avg/Day",
        "pricer.column_avg_daily_volume_help": "Average daily sales volume (30-day).",
        "pricer.column_days_of_stock": "Days Stock",
        "pricer.column_days_of_stock_help": "Days of stock remaining based on average sales.",
        "pricer.column_is_doctrine_help": "Item is used in doctrine fits.",
        "pricer.column_doctrine_ships_help": "Doctrine ships that use this item.",
        "pricer.metric_local_sell_help": "Total value at {market_name} sell prices.",
        "pricer.metric_local_buy_help": "Total value at {market_name} buy prices.",
        "pricer.metric_jita_sell_help": "Total value at Jita sell prices.",
        "pricer.metric_jita_buy_help": "Total value at Jita buy prices.",
        "pricer.total_volume_label": "Total Volume",
        "pricer.items": "Items",
        "pricer.display": "Display",
        "pricer.display_item_prices": "item prices",
        "pricer.display_total_prices": "total prices",
        "pricer.display_help": "Toggle between per-unit prices and totals.",
        "pricer.show_jita_prices": "Show Jita Prices",
        "pricer.show_stock_metrics": "Show Stock Metrics",
        "pricer.show_stock_metrics_help": "Show average daily volume and days of stock.",
        "pricer.highlight_doctrine_items": "Highlight Doctrine Items",
        "pricer.highlight_doctrine_items_help": "Highlight items used in doctrine fits.",
        "pricer.issues": "Issues",
        "pricer.unpriced_items": "⚠️ {count} items could not be priced",
        "build_costs.title": "Build Cost Tool",
        "build_costs.category_label": "Select a category",
        "build_costs.category_placeholder": "Ship",
        "build_costs.category_help": "Select a category to filter the groups and items by.",
        "build_costs.group_label": "Select a group",
        "build_costs.item_label": "Select an item",
        "build_costs.runs_label": "Runs",
        "build_costs.me_label": "ME",
        "build_costs.te_label": "TE",
        "build_costs.material_price_source_label": "Select a material price source",
        "build_costs.material_price_source_help": (
            "This is the source of the material prices used in the calculations. ESI Average "
            "is the CCP average price used in the in-game industry window, Jita Sell is the "
            "minimum sale price in Jita, and Jita Buy is the maximum buy price in Jita."
        ),
        "build_costs.price_source_esi_average": "ESI Average",
        "build_costs.price_source_jita_sell": "Jita Sell",
        "build_costs.price_source_jita_buy": "Jita Buy",
        "build_costs.structure_compare_expander": "Select a structure to compare (optional)",
        "build_costs.structure_compare_label": "Structures",
        "build_costs.structure_compare_placeholder": "All Structures",
        "build_costs.structure_compare_help": (
            "Select a structure to compare the build cost against. Leave empty to show all "
            "structures."
        ),
        "build_costs.parameters_changed": (
            "⚠️ Parameters have changed. Click 'Recalculate' to get updated results."
        ),
        "build_costs.calculate": "Calculate",
        "build_costs.recalculate": "Recalculate",
        "build_costs.calculate_help": "Click to calculate the cost for the selected item.",
        "build_costs.industry_indexes_last_updated": "Industry indexes last updated: {timestamp}",
        "build_costs.progress_start": "Fetching data from {total} structures...",
        "build_costs.progress_fetching": "Fetching {current} of {total} structures: {structure}",
        "build_costs.no_results": (
            "No results returned. This is likely due to problems with the external industry data "
            "API. Please try again later."
        ),
        "build_costs.header": "Build cost for {item_name}",
        "build_costs.summary": (
            "Build cost for {item_name} with {runs} runs, {me} ME, {te} TE, {price_source} "
            "material price (type_id: {type_id})"
        ),
        "build_costs.metric_build_cost_per_unit": "Build cost per unit",
        "build_costs.metric_build_cost_per_unit_help": (
            "Based on the lowest cost structure: {structure}"
        ),
        "build_costs.metric_total_build_cost": "Total Build Cost",
        "build_costs.materials_job_cost": (
            "**Materials:** {materials} ISK | **Job cost:** {job_cost} ISK"
        ),
        "build_costs.market_price_summary": (
            "**{market_name} price:** <span style='color: orange;'>{price} ISK</span> "
            "(profit: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_market_price": "No {market_name} price data found for this item",
        "build_costs.jita_price_summary": (
            "**Jita price:** <span style='color: orange;'>{price} ISK</span> "
            "(profit: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_jita_price": "No Jita price data found for this item",
        "build_costs.super_note": (
            "<span style=\"font-weight: bold;\">Note:</span> "
            "<span style=\"color: orange;\">Only structures configured for supercapital "
            "construction are displayed.</span>"
        ),
        "build_costs.material_breakdown": "Material Breakdown",
        "build_costs.material_breakdown_for_structure": "Material Breakdown: {structure}",
        "build_costs.material_breakdown_selector": "Select a structure to view material breakdown",
        "build_costs.material_breakdown_selector_help": (
            "Choose a structure to see detailed material costs and quantities."
        ),
        "build_costs.material_breakdown_missing": "No data found for structure: {structure}",
        "build_costs.material_breakdown_summary": (
            "{item} Material Cost: <span style='color: orange;'>**{cost} ISK**</span> "
            "(*{volume} m3*) - {price_source}"
        ),
        "build_costs.material_breakdown_tip": (
            "💡 **Tip:** You can download this data as CSV using the download icon (⬇️) "
            "in the top-right corner of the table above."
        ),
        "build_costs.selected_structure": "Selected structure",
        "build_costs.empty_subheader": "WC Markets Build Cost Tool",
        "build_costs.empty_description": (
            "Find a build cost for an item by selecting a category, group, and item in the "
            "sidebar. The build cost is calculated for all structures in the database and "
            "ordered by total cost from lowest to highest. You can also compare against a "
            "specific structure and inspect a material breakdown for each result."
        ),
        "build_costs.tool_description": """
    - <span style="font-weight: bold; color: orange;">Runs:</span> The number of runs to calculate the cost for.
    - <span style="font-weight: bold; color: orange;">ME:</span> The material efficiency of the blueprint. (default 0)
    - <span style="font-weight: bold; color: orange;">TE:</span> The time efficiency of the blueprint. (default 0)
    - <span style="font-weight: bold; color: orange;">Material price source:</span> The source of the material prices used in the calculations.
        - *ESI Average* - the CCP average price used in the in-game industry window.
        - *Jita Sell* - the minimum price of sale orders in Jita.
        - *Jita Buy* - the maximum price of buy orders in Jita.
    - <span style="font-weight: bold; color: orange;">Structure:</span> The structure to compare the cost to build against. (optional)
    - <span style="font-weight: bold; color: orange;">Skills:</span> All skills are assumed to be at level 5.
    """,
        "build_costs.no_buildable_items": (
            "No buildable items found for group: {group_name}. This may indicate a missing SDE "
            "table such as `industryActivityProducts`. Try syncing the database or selecting a "
            "different group."
        ),
        "build_costs.load_items_error": "Failed to load items for group: {error}",
        "build_costs.invalid_selected_item": "Selected item: {item_name} is not a buildable item",
        "build_costs.item_not_found": "Selected item: {item_name} was not found in the types database",
        "build_costs.invalid_item": "Invalid item: {error}",
        "build_costs.select_valid_item": (
            "Selected item: {item_name} is not a buildable item. Please select a valid item "
            "from the sidebar."
        ),
        "build_costs.unknown_type": "Unknown ({type_id})",
        "build_costs.special_group_sovereignty_hub": "Sovereignty Hub",
        "build_costs.column_structure": "Structure",
        "build_costs.column_structure_help": "Structure name.",
        "build_costs.column_structure_type": "Type",
        "build_costs.column_units": "Units",
        "build_costs.column_units_help": "Number of units built.",
        "build_costs.column_total_cost": "Total Cost",
        "build_costs.column_total_cost_help": "Total cost of building the units.",
        "build_costs.column_cost_per_unit": "Cost per Unit",
        "build_costs.column_cost_per_unit_help": "Cost per unit of the item.",
        "build_costs.column_material_cost": "Material Cost",
        "build_costs.column_material_cost_help": "Total material cost.",
        "build_costs.column_total_job_cost": "Total Job Cost",
        "build_costs.column_total_job_cost_help": (
            "Total job cost including facility tax, SCC surcharge, and system cost index."
        ),
        "build_costs.column_facility_tax": "Facility Tax",
        "build_costs.column_facility_tax_help": "Facility tax cost.",
        "build_costs.column_scc_surcharge": "SCC Surcharge",
        "build_costs.column_scc_surcharge_help": "SCC surcharge cost.",
        "build_costs.column_system_cost_index": "Cost Index",
        "build_costs.column_rigs": "Rigs",
        "build_costs.column_rigs_help": "Rigs fitted to the structure.",
        "build_costs.column_comparison_cost": "Comparison Cost",
        "build_costs.column_comparison_cost_help": "Difference from the selected structure total cost.",
        "build_costs.column_comparison_cost_per_unit": "Comparison Cost per Unit",
        "build_costs.column_comparison_cost_per_unit_help": (
            "Difference from the selected structure cost per unit."
        ),
        "build_costs.column_material_help": "The name of the required material.",
        "build_costs.column_quantity": "Quantity",
        "build_costs.column_quantity_help": "Amount of material needed.",
        "build_costs.column_volume_per_unit": "Volume/Unit",
        "build_costs.column_volume_per_unit_help": "Volume per unit of material (m3).",
        "build_costs.column_total_volume": "Total Volume",
        "build_costs.column_total_volume_help": "Total volume of this material (m3).",
        "build_costs.column_unit_price": "Unit Price",
        "build_costs.column_unit_price_help": "Cost per unit of material (ISK).",
        "build_costs.column_total_cost_materials_help": "Total cost for this material (ISK).",
        "build_costs.column_percent_total": "% of Total",
        "build_costs.column_percent_total_help": "Percentage of the total material cost.",
    },
    "zh": {
        "app.page_title": "凛冬联盟市场",
        "app.language_label": "语言",
        "nav.section.market_stats": "市场统计",
        "nav.section.analysis_tools": "分析工具",
        "nav.section.data": "数据",
        "nav.page.market_stats": "📈市场统计",
        "nav.page.low_stock": "⚠️低库存",
        "nav.page.import_helper": "📦进货助手",
        "nav.page.doctrine_status": "⚔️建制状态",
        "nav.page.doctrine_report": "📝建制报告",
        "nav.page.build_costs": "🏗️制造成本",
        "nav.page.pricer": "🏷️估价器",
        "nav.page.downloads": "📥下载",
        "doctrine_status.title": "{market_name} 建制状态",
        "doctrine_status.tab_market_stock": "市场库存",
        "doctrine_status.tab_fit_details": "装配详情",
        "doctrine_status.low_stock_modules": "低库存装备",
        "doctrine_status.no_fits": "数据库中未找到舰队配置。",
        "doctrine_report.subtitle": "{market_name} 舰队配置市场状态",
        "doctrine_report.no_data": "没有可显示的数据",
        "doctrine_report.metric_total_fits": "可用总配置数",
        "doctrine_report.metric_total_hulls": "船体总数",
        "doctrine_report.metric_avg_target_pct": "平均目标百分比",
        "doctrine_report.role_dps": "💥 **DPS** - 主力输出舰船",
        "doctrine_report.role_logi": "🏥 **后勤** - 维修后勤舰船",
        "doctrine_report.role_links": "📡 **指挥** - 指挥舰船",
        "doctrine_report.role_support": "🛠️ **支援** - EWAR、截击及其他支援舰船",
        "doctrine_report.stock_status": "库存状态",
        "doctrine_report.stock_status_summary": (
            "*显示所选配置中每艘船最低库存的三个模块的库存状态摘要。括号内的数字表示当前库存可支持的配置数量。"
            "使用复选框选择要导出的物品。*"
        ),
        "doctrine_report.fit_id": "建制 ID",
        "doctrine_report.target": "目标",
        "doctrine_report.no_target_found": "未找到该配置的目标值",
        "doctrine_report.equivalent_stock_caption": "🔄 库存包含等效模块",
        "doctrine_report.no_fits": "数据库中未找到舰队配置。",
        "doctrine_report.select_doctrine": "选择建制",
        "doctrine_report.target_multiplier": "目标倍率",
        "doctrine_report.target_multiplier_help": "该倍率会应用到每个建制的目标值上，用于让目标更激进或更保守。默认值为 1.0。",
        "doctrine_report.current_target_multiplier": "当前目标倍率: {value}",
        "doctrine_report.ship_image_not_available": "🚀 舰船图像不可用",
        "doctrine_report.doctrine_id": "建制 ID: {doctrine_id}",
        "doctrine_report.selected_items": "已选物品",
        "doctrine_report.modules_label": "模块:",
        "doctrine_report.no_items_selected": "未选择任何物品",
        "doctrine_report.export_options": "导出选项",
        "doctrine_report.download_csv": "📥 下载 CSV",
        "doctrine_report.clear_selection": "🗑️ 清除选择",
        "doctrine_report.column_target_pct": "目标 %",
        "doctrine_report.column_target": "目标",
        "doctrine_report.column_target_help": "库存需要达到的配置数量。",
        "doctrine_report.column_daily_sales": "日均销量",
        "doctrine_report.column_daily_sales_help": "过去 30 天的平均日销量。",
        "doctrine_report.column_group_help": "舰船分组。",
        "doctrine_report.column_ship": "舰船",
        "doctrine_report.column_ship_help": "舰船名称。",
        "doctrine_report.column_ship_id_help": "舰船类型 ID。",
        "doctrine_report.column_fit_id": "配置 ID",
        "doctrine_report.column_fit_id_help": "舰队配置 ID。",
        "doctrine_report.column_price_help": "舰船价格。",
        "doctrine_report.column_total_cost": "总成本",
        "doctrine_report.column_total_cost_help": "该建制的总成本。",
        "common.market_hub": "市场中心",
        "common.select": "选择",
        "common.type_id": "类型 ID",
        "common.item": "物品",
        "common.category": "类别",
        "common.group": "分组",
        "common.price": "价格",
        "low_stock.title": "{market_name} 低库存工具",
        "low_stock.description": (
            "此页面显示市场中库存偏低的物品。**剩余天数** 列表示按历史平均销量计算，当前库存还能维持多少天。"
            "**已用于配置** 列显示使用该物品的舰船配置，以及当前库存可支持的配置数量。"
        ),
        "low_stock.filters_header": "筛选",
        "low_stock.filters_help": "使用以下筛选条件自定义低库存视图。",
        "low_stock.item_type_filters": "物品类型筛选",
        "low_stock.doctrine_only": "仅显示建制装备",
        "low_stock.doctrine_only_help": "仅显示建制装备。",
        "low_stock.tech2_only": "仅显示 Tech II",
        "low_stock.tech2_only_help": "仅显示 Tech II 物品（metaGroupID=2）。",
        "low_stock.faction_only": "仅显示势力物品",
        "low_stock.faction_only_help": "仅显示势力物品（metaGroupID=4）。",
        "low_stock.category_filter": "类别筛选",
        "low_stock.select_categories": "选择类别",
        "low_stock.select_categories_help": "选择一个或多个类别进行筛选。",
        "low_stock.doctrine_fit_filter": "建制筛选",
        "low_stock.select_doctrine": "选择建制",
        "low_stock.select_doctrine_help": "只显示建制装备。",
        "low_stock.select_fit": "选择建制",
        "low_stock.select_fit_help": "只显示建制装备。",
        "low_stock.days_filter": "剩余天数筛选",
        "low_stock.max_days_remaining": "最大剩余天数",
        "low_stock.max_days_remaining_help": "仅显示剩余天数小于或等于该值的物品。",
        "low_stock.show_zero_volume_items": "显示 0 销量物品",
        "low_stock.show_zero_volume_items_help": "包含过去 30 天平均销量为 0 的物品。",
        "low_stock.metric_critical": "严重短缺（≤3 天）",
        "low_stock.metric_low": "低库存（3-7 天）",
        "low_stock.metric_total": "筛选后总数",
        "low_stock.subheader_fit": "低库存: {ship_name}",
        "low_stock.subheader_doctrine": "低库存: {doctrine_name}",
        "low_stock.subheader_all": "低库存物品",
        "low_stock.column_select_help": "勾选要包含在 CSV 下载中的物品。",
        "low_stock.column_item_help": "物品名称。",
        "low_stock.column_volume_remaining": "剩余",
        "low_stock.column_volume_remaining_help": "当前市场中可用的总数量。",
        "low_stock.column_fits": "可配数量",
        "low_stock.column_fits_help": "按该物品库存可组装的总配置数。",
        "low_stock.column_days": "天数",
        "low_stock.column_days_help": "按历史平均销量估算的剩余天数。",
        "low_stock.column_avg_vol": "日销量",
        "low_stock.column_avg_vol_help": "过去 30 天平均销量。",
        "low_stock.column_used_in_fits": "已用于配置",
        "low_stock.column_used_in_fits_help": "使用该物品的舰船配置。",
        "low_stock.column_category_help": "物品类别。",
        "low_stock.column_group_help": "物品分组。",
        "low_stock.selected_items": "已选择 {count} 个物品。可前往 **Downloads** 页面批量导出 CSV。",
        "low_stock.chart_section": "按物品显示剩余天数",
        "low_stock.chart_title": "库存剩余天数",
        "low_stock.chart_days_label": "剩余天数",
        "low_stock.chart_critical_level": "严重阈值（3 天）",
        "import_helper.title": "{market_name} 进货助手",
        "import_helper.description": (
            "查找本地市场价格明显高于吉他卖价的物品。30 天利润使用 "
            "`(本地价格 - 吉他卖价) * 日均销量 * 30`，RRP 使用 `吉他卖价 * (1 + 加价率)`，"
            "资本利用率使用 `((本地价格 - 吉他卖价) - 运费) / 吉他卖价`。"
        ),
        "import_helper.caption_green": "绿色",
        "import_helper.caption_grey": "灰色",
        "import_helper.caption_estimated_price": (
            "{color_label}背景表示按吉他卖价140%估算的本地价格（无本地卖单）"
        ),
        "import_helper.caption_floored_volume": (
            "{color_label}背景表示 30 天成交量因历史不足而按0计算"
        ),
        "import_helper.filters_header": "筛选",
        "import_helper.categories": "类别",
        "import_helper.categories_help": "将表格限制为一个或多个物品类别。",
        "import_helper.search_items": "搜索物品",
        "import_helper.search_items_help": "不区分大小写的名称筛选。",
        "import_helper.profitable_only": "仅显示正利润",
        "import_helper.profitable_only_help": "隐藏本地市场价格不高于吉他卖价的物品。",
        "import_helper.min_capital_utilis": "最小资本利用率",
        "import_helper.min_capital_utilis_help": "0.10 表示运费后至少有 10% 的资本利用率。",
        "import_helper.min_turnover_30d": "最小 30 天成交额",
        "import_helper.min_turnover_30d_help": "隐藏 30 天成交额低于该值的物品。",
        "import_helper.shipping_cost_per_m3": "每立方米运费",
        "import_helper.shipping_cost_per_m3_help": "用于计算运费。默认值来自 settings.toml。",
        "import_helper.markup_margin": "加价率",
        "import_helper.markup_margin_help": "用于计算建议零售价。0.20 表示高于吉他卖价 20%。",
        "import_helper.metric_total_items": "物品总数",
        "import_helper.metric_profitable_items": "正利润物品",
        "import_helper.metric_avg_capital_utilis": "平均资本利用率",
        "import_helper.column_item_help": "如有可用翻译则显示本地化物品名称。",
        "import_helper.column_rrp_help": "基于吉他卖价和加价率计算的建议零售价。",
        "import_helper.column_jita_sell_help": "吉他卖单价格。",
        "import_helper.column_jita_buy_help": "吉他买单价格。",
        "import_helper.column_shipping_help": "按物品体积 m3 乘以 {shipping_cost_per_m3} 计算。",
        "import_helper.column_profit_30d_help": "按（本地价格 - 吉他卖价）乘以日均销量再乘 30 计算。",
        "import_helper.column_turnover_30d_help": "30 天销量乘以 吉他卖价。",
        "import_helper.column_volume_30d_help": "日均销量乘以 30。",
        "import_helper.column_capital_utilis_help": "按 ((本地价格 - 吉他卖价) - 运费) / 吉他卖价 计算。",
        "import_helper.column_rrp": "建议价",
        "import_helper.column_jita_sell": "吉他卖价",
        "import_helper.column_jita_buy": "吉他买价",
        "import_helper.column_shipping": "运费",
        "import_helper.column_profit_30d": "30 天利润",
        "import_helper.column_turnover_30d": "30 天成交额",
        "import_helper.column_volume_30d": "30 天销量",
        "import_helper.column_capital_utilis": "资本利用率",
        "doctrine_status.logo_not_found": "未找到徽标图片",
        "doctrine_status.downloads_hint": "完整数据导出请使用下载页面",
        "doctrine_status.filter_doctrine": "建制",
        "doctrine_status.filter_stock_status": "库存状态",
        "doctrine_status.filter_ship_group": "舰船分组",
        "doctrine_status.no_filtered_fits": "所选筛选条件下未找到装配。",
        "doctrine_status.ship_group_help": "舰队建制分组。",
        "doctrine_status.image_not_available": "图片不可用",
        "doctrine_status.fit_id_label": "ID: {fit_id}",
        "doctrine_status.fit_name_label": "装配: {fit_name}",
        "doctrine_status.includes_equivalent_modules": "包含等效装备",
        "doctrine_status.critical_stock_level": "库存严重不足",
        "doctrine_status.low_stock_help": "库存偏低",
        "doctrine_status.view_stock_breakdown": "📋 查看库存明细",
        "doctrine_status.combined_stock_caption": "等效装备合并库存：",
        "doctrine_status.combined_total": "合计库存: {total}",
        "doctrine_status.fit_header": "{ship_name} - 装配 {fit_id}",
        "doctrine_status.load_fit_details": "加载装配详情",
        "doctrine_status.no_fit_details": "该装配没有可用的详细数据。",
        "doctrine_status.select_all": "📋 全选",
        "doctrine_status.clear_all": "🗑️ 全部清除",
        "doctrine_status.selected_items": "已选物品",
        "doctrine_status.render_market_data": "📊 生成导出市场数据",
        "doctrine_status.market_data": "市场数据",
        "doctrine_status.market_data_line": "  {name} (库存: {stock} | 装配数: {fits} | 需求: {need})",
        "doctrine_status.select_items_for_export": "勾选舰船和装备以加入导出列表。",
        "doctrine_status.column_qty_per_fit": "每套数量",
        "doctrine_status.column_qty_per_fit_help": "每套装配所需数量。",
        "doctrine_status.column_total_stock_help": "该物品的总库存。",
        "doctrine_status.column_category_id": "类别 ID",
        "doctrine_status.column_category_id_help": "物品类别 ID。",
        "market_stats.title": "Winter Coalition 市场统计 - {market_name} 市场 {header_env}",
        "market_stats.show_all_data": "显示全部数据",
        "market_stats.select_category": "选择类别",
        "market_stats.select_item": "选择物品",
        "market_stats.all_sell_orders": "全部卖单",
        "market_stats.winter_co_doctrine": "凛冬建制",
        "market_stats.category_plural": "{category_name}",
        "market_stats.thirty_day_market_stats": "30日市场统计（展开查看）",
        "market_stats.sell_orders_for": "{name} 的卖单",
        "market_stats.all_buy_orders": "全部买单",
        "market_stats.buy_orders_for": "{name} 的买单",
        "market_stats.market_value_buy_orders": "买单总价值",
        "market_stats.total_buy_orders": "买单总数",
        "market_stats.no_current_buy_orders": "{item_name} 当前没有买单",
        "market_stats.no_current_market_orders": "{item_name} 当前没有市场订单",
        "market_stats.market_history": "市场历史 - {item_name}",
        "market_stats.price_history": "价格历史 - {filter_info}",
        "market_stats.expand_market_history_data": "展开查看市场历史数据",
        "market_stats.fitting_data": "装配数据",
        "market_stats.check_db_state": "检查数据库状态",
        "market_stats.downloads_hint": "*访问**下载**页面以导出市场、建制和 SDE 数据。*",
        "market_stats.date_range": "日期范围",
        "market_stats.available_data_range": "可用数据范围：{start} 到 {end}",
        "market_stats.start_date": "开始日期",
        "market_stats.start_date_help": "选择开始日期（可用范围：{start} 到 {end}）",
        "market_stats.end_date": "结束日期",
        "market_stats.end_date_help": "选择结束日期（可用范围：{start} 到 {end}）",
        "market_stats.chart_controls": "图表控制",
        "market_stats.moving_average_period": "移动平均周期",
        "market_stats.moving_average": "移动平均",
        "market_stats.date_aggregation": "日期聚合",
        "market_stats.date_period": "日期周期",
        "market_stats.period_daily": "日",
        "market_stats.period_weekly": "周",
        "market_stats.period_monthly": "月",
        "market_stats.period_yearly": "年",
        "market_stats.outlier_handling": "异常值处理",
        "market_stats.outlier_method": "异常值方法",
        "market_stats.outlier_method_cap": "截断异常值",
        "market_stats.outlier_method_remove": "移除异常值",
        "market_stats.outlier_method_none": "显示全部数据",
        "market_stats.outlier_method_help": "处理会拉偏图表比例的极端值。",
        "market_stats.outlier_sensitivity": "异常值敏感度",
        "market_stats.outlier_sensitivity_help": "数值越低，异常值检测越激进（1.5 为标准 IQR）。",
        "market_stats.cap_at_percentile": "截断百分位",
        "market_stats.cap_at_percentile_help": "用于截断异常值的百分位。",
        "market_stats.outlier_handling_explained": (
            "**异常值处理说明：**\n"
            "- **截断异常值**：用百分位上限替换极端值\n"
            "- **移除异常值**：完全删除极端数据点\n"
            "- **显示全部数据**：不处理异常值"
        ),
        "market_stats.date": "日期",
        "market_stats.date_help": "数据日期。",
        "market_stats.isk_volume": "ISK 交易额",
        "market_stats.isk_volume_help": "该时间段的 ISK 交易额。",
        "market_stats.filter_info": "开始日期: {start_date} | 结束日期: {end_date} | 周期: {date_period}",
        "market_stats.filter_info_category": " | 类别: {category_name}",
        "market_stats.no_market_history_for_category": "类别 {category_name} 没有市场历史数据",
        "market_stats.no_market_history": "没有可用的市场历史数据",
        "market_stats.no_market_history_selected_filters": "所选筛选条件下没有市场历史数据",
        "market_stats.thirty_day_market_stats_with_label": "30日市场统计（{label}）",
        "market_stats.insufficient_data": "该物品记录的数据不足",
        "market_stats.avg_daily_isk_30d": "30日平均日 ISK",
        "market_stats.this_week_delta": "本周 {value}%",
        "market_stats.avg_daily_items_30d": "30日平均日销量",
        "market_stats.total_value_30d": "30日总价值",
        "market_stats.total_volume_30d": "30日总销量",
        "market_stats.current_market_status": "当前市场状态",
        "market_stats.sell_price": "卖出价格",
        "market_stats.delta_vs_jita": "相对吉他 {value}%",
        "market_stats.jita_sell_price": "吉他卖价",
        "market_stats.market_stock": "市场库存",
        "market_stats.sell_orders_value": "卖单总价值",
        "market_stats.total_sell_orders": "卖单总数",
        "market_stats.fits_on_market": "市场可装配数",
        "market_stats.fit_target_delta": "装配: {fit_id}, 目标: {target}, 市场装配数: {fits_on_market}, 差值: {delta}",
        "market_stats.target_value": "目标: {target}",
        "market_stats.average_price": "平均价格",
        "market_stats.volume": "成交量",
        "market_stats.average_price_7d": "7日平均价格",
        "market_stats.average_volume_7d": "7日平均成交量",
        "market_stats.average_price_30d": "30日平均价格",
        "market_stats.average_volume_30d": "30日平均成交量",
        "market_stats.order_id": "订单 ID",
        "market_stats.duration": "时长",
        "market_stats.issued": "发布时间",
        "market_stats.expires": "到期时间",
        "pricer.title": "Winter Coalition 估价器",
        "pricer.description": "使用吉他和 {market_name} 市场数据为物品和装配定价。",
        "pricer.input_section": "输入",
        "pricer.input_placeholder": (
            "请粘贴以下任一格式：\n\n"
            "EFT 装配：\n"
            "[Hurricane, PVP Fit]\n"
            "Damage Control II\n"
            "1600mm Steel Plates II\n"
            "...\n\n"
            "制表符分隔（物品在前）：\n"
            "Tritanium\t10000\n"
            "Pyerite\t5000\n\n"
            "制表符分隔（数量在前）：\n"
            "10000\tTritanium\n"
            "5000\tPyerite"
        ),
        "pricer.input_label": "粘贴 EFT 装配或物品清单：",
        "pricer.price_items": "开始定价",
        "pricer.fetching_prices": "正在获取价格...",
        "pricer.format_label": "格式",
        "pricer.format_multibuy": "多买/物品清单",
        "pricer.totals": "汇总",
        "pricer.column_icon": "图标",
        "pricer.column_icon_help": "物品图标。",
        "pricer.column_type_id_help": "类型 ID。",
        "pricer.column_item_help": "物品名称。",
        "pricer.column_qty": "数量",
        "pricer.column_qty_help": "数量。",
        "pricer.column_slot": "槽位",
        "pricer.column_slot_help": "槽位类型。",
        "pricer.column_local_sell": "{market_name} 卖价",
        "pricer.column_local_sell_help": "{market_name} 每单位最低卖价。",
        "pricer.column_local_sell_volume": "{market_name} 挂单量",
        "pricer.column_local_sell_volume_help": "{market_name} 卖单数量。",
        "pricer.column_jita_sell": "吉他卖价",
        "pricer.column_jita_sell_help": "吉他每单位卖价。",
        "pricer.column_jita_buy": "吉他买价",
        "pricer.column_jita_buy_help": "吉他每单位买价。",
        "pricer.column_jita_sell_total": "吉他卖价总计",
        "pricer.column_jita_sell_total_help": "按吉他卖价计算的总价值。",
        "pricer.column_jita_buy_total": "吉他买价总计",
        "pricer.column_jita_buy_total_help": "按吉他买价计算的总价值。",
        "pricer.column_local_buy": "{market_name} 买价",
        "pricer.column_local_buy_help": "{market_name} 每单位最高买价。",
        "pricer.column_local_sell_total": "{market_name} 卖价总计",
        "pricer.column_local_sell_total_help": "按 {market_name} 卖价计算的总价值。",
        "pricer.column_local_buy_total": "{market_name} 买价总计",
        "pricer.column_local_buy_total_help": "按 {market_name} 买价计算的总价值。",
        "pricer.column_volume": "体积 (m3)",
        "pricer.column_volume_help": "每单位体积（m3）。",
        "pricer.column_total_volume": "总体积 (m3)",
        "pricer.column_total_volume_help": "总体积（数量 x 体积）。",
        "pricer.column_category_help": "物品类别。",
        "pricer.column_avg_daily_volume": "日均",
        "pricer.column_avg_daily_volume_help": "30日平均日成交量。",
        "pricer.column_days_of_stock": "库存天数",
        "pricer.column_days_of_stock_help": "基于日均销量估算的库存可维持天数。",
        "pricer.column_is_doctrine_help": "该物品用于建制装配。",
        "pricer.column_doctrine_ships_help": "使用该物品的建制舰船。",
        "pricer.metric_local_sell_help": "按 {market_name} 卖价计算的总价值。",
        "pricer.metric_local_buy_help": "按 {market_name} 买价计算的总价值。",
        "pricer.metric_jita_sell_help": "按吉他卖价计算的总价值。",
        "pricer.metric_jita_buy_help": "按吉他买价计算的总价值。",
        "pricer.total_volume_label": "总体积",
        "pricer.items": "物品",
        "pricer.display": "显示方式",
        "pricer.display_item_prices": "单价",
        "pricer.display_total_prices": "总价",
        "pricer.display_help": "在单价和总价之间切换。",
        "pricer.show_jita_prices": "显示吉他价格",
        "pricer.show_stock_metrics": "显示库存指标",
        "pricer.show_stock_metrics_help": "显示日均成交量和库存天数。",
        "pricer.highlight_doctrine_items": "高亮建制物品",
        "pricer.highlight_doctrine_items_help": "高亮用于建制装配的物品。",
        "pricer.issues": "问题",
        "pricer.unpriced_items": "⚠️ 有 {count} 个物品无法定价",
        "build_costs.title": "制造成本工具",
        "build_costs.category_label": "选择类别",
        "build_costs.category_placeholder": "舰船",
        "build_costs.category_help": "选择一个类别来筛选分组和物品。",
        "build_costs.group_label": "选择分组",
        "build_costs.item_label": "选择物品",
        "build_costs.runs_label": "制造次数",
        "build_costs.me_label": "ME",
        "build_costs.te_label": "TE",
        "build_costs.material_price_source_label": "选择材料价格来源",
        "build_costs.material_price_source_help": (
            "用于计算材料成本的价格来源。ESI Average 是游戏工业窗口使用的 CCP 平均价，"
            "Jita Sell 是吉他最低卖单价，Jita Buy 是吉他最高买单价。"
        ),
        "build_costs.price_source_esi_average": "ESI 平均价",
        "build_costs.price_source_jita_sell": "吉他卖价",
        "build_costs.price_source_jita_buy": "吉他买价",
        "build_costs.structure_compare_expander": "选择要比较的建筑（可选）",
        "build_costs.structure_compare_label": "建筑",
        "build_costs.structure_compare_placeholder": "所有建筑",
        "build_costs.structure_compare_help": "选择一个建筑来比较制造成本；留空则显示所有建筑。",
        "build_costs.parameters_changed": "⚠️ 参数已更改。请点击“重新计算”以刷新结果。",
        "build_costs.calculate": "计算",
        "build_costs.recalculate": "重新计算",
        "build_costs.calculate_help": "点击计算所选物品的制造成本。",
        "build_costs.industry_indexes_last_updated": "工业指数最后更新时间: {timestamp}",
        "build_costs.progress_start": "正在从 {total} 个建筑获取数据...",
        "build_costs.progress_fetching": "正在获取第 {current}/{total} 个建筑: {structure}",
        "build_costs.no_results": "没有返回结果。这通常意味着外部工业数据 API 出现问题，请稍后再试。",
        "build_costs.header": "{item_name} 的制造成本",
        "build_costs.summary": (
            "{item_name} 的制造成本计算参数: {runs} 次, ME {me}, TE {te}, "
            "材料价格来源为 {price_source} (type_id: {type_id})"
        ),
        "build_costs.metric_build_cost_per_unit": "单件制造成本",
        "build_costs.metric_build_cost_per_unit_help": "基于成本最低的建筑: {structure}",
        "build_costs.metric_total_build_cost": "总制造成本",
        "build_costs.materials_job_cost": "**材料:** {materials} ISK | **工单费:** {job_cost} ISK",
        "build_costs.market_price_summary": (
            "**{market_name} 价格:** <span style='color: orange;'>{price} ISK</span> "
            "(利润: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_market_price": "未找到该物品在 {market_name} 的价格数据",
        "build_costs.jita_price_summary": (
            "**吉他价格:** <span style='color: orange;'>{price} ISK</span> "
            "(利润: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_jita_price": "未找到该物品的吉他价格数据",
        "build_costs.super_note": (
            "<span style=\"font-weight: bold;\">注意:</span> "
            "<span style=\"color: orange;\">这里只显示可用于超级旗舰建造的建筑。</span>"
        ),
        "build_costs.material_breakdown": "材料明细",
        "build_costs.material_breakdown_for_structure": "材料明细: {structure}",
        "build_costs.material_breakdown_selector": "选择一个建筑查看材料明细",
        "build_costs.material_breakdown_selector_help": "选择一个建筑以查看详细材料数量和成本。",
        "build_costs.material_breakdown_missing": "未找到建筑数据: {structure}",
        "build_costs.material_breakdown_summary": (
            "{item} 材料成本: <span style='color: orange;'>**{cost} ISK**</span> "
            "(*{volume} m3*) - {price_source}"
        ),
        "build_costs.material_breakdown_tip": (
            "💡 **提示:** 你可以使用上方表格右上角的下载图标（⬇️）将数据导出为 CSV。"
        ),
        "build_costs.selected_structure": "选定建筑",
        "build_costs.empty_subheader": "WC Markets 制造成本工具",
        "build_costs.empty_description": (
            "在侧边栏选择类别、分组和物品即可查询制造成本。系统会计算数据库中所有建筑的造价，"
            "并按总成本从低到高排序。你也可以选择某个建筑进行对比，并查看每个结果的材料明细。"
        ),
        "build_costs.tool_description": """
    - <span style="font-weight: bold; color: orange;">制造次数:</span> 要计算的制造次数。
    - <span style="font-weight: bold; color: orange;">ME:</span> 蓝图材料效率。（默认 0）
    - <span style="font-weight: bold; color: orange;">TE:</span> 蓝图时间效率。（默认 0）
    - <span style="font-weight: bold; color: orange;">材料价格来源:</span> 计算中使用的材料价格来源。
        - *ESI 平均价* - 游戏工业窗口使用的 CCP 平均价。
        - *吉他卖价* - 吉他最低卖单价格。
        - *吉他买价* - 吉他最高买单价格。
    - <span style="font-weight: bold; color: orange;">建筑:</span> 用于比较制造成本的建筑。（可选）
    - <span style="font-weight: bold; color: orange;">技能:</span> 默认所有相关技能均为 5 级。
    """,
        "build_costs.no_buildable_items": (
            "分组 {group_name} 中没有可制造的物品。这可能表示缺少 SDE 表，例如 "
            "`industryActivityProducts`。请尝试同步数据库或选择其他分组。"
        ),
        "build_costs.load_items_error": "加载分组物品失败: {error}",
        "build_costs.invalid_selected_item": "所选物品 {item_name} 不是可制造物品",
        "build_costs.item_not_found": "在类型数据库中未找到所选物品: {item_name}",
        "build_costs.invalid_item": "无效物品: {error}",
        "build_costs.select_valid_item": "所选物品 {item_name} 不是可制造物品，请从侧边栏重新选择。",
        "build_costs.unknown_type": "未知 ({type_id})",
        "build_costs.special_group_sovereignty_hub": "主权中心",
        "build_costs.column_structure": "建筑",
        "build_costs.column_structure_help": "建筑名称。",
        "build_costs.column_structure_type": "类型",
        "build_costs.column_units": "数量",
        "build_costs.column_units_help": "制造出的单位数量。",
        "build_costs.column_total_cost": "总成本",
        "build_costs.column_total_cost_help": "制造这些单位的总成本。",
        "build_costs.column_cost_per_unit": "单件成本",
        "build_costs.column_cost_per_unit_help": "该物品的单件制造成本。",
        "build_costs.column_material_cost": "材料成本",
        "build_costs.column_material_cost_help": "总材料成本。",
        "build_costs.column_total_job_cost": "总工单费",
        "build_costs.column_total_job_cost_help": "包含设施税、SCC 附加费和系统成本指数的总工单费。",
        "build_costs.column_facility_tax": "设施税",
        "build_costs.column_facility_tax_help": "设施税成本。",
        "build_costs.column_scc_surcharge": "SCC 附加费",
        "build_costs.column_scc_surcharge_help": "SCC 附加费成本。",
        "build_costs.column_system_cost_index": "成本指数",
        "build_costs.column_rigs": "插装",
        "build_costs.column_rigs_help": "该建筑安装的插装。",
        "build_costs.column_comparison_cost": "比较成本",
        "build_costs.column_comparison_cost_help": "与所选建筑总成本的差值。",
        "build_costs.column_comparison_cost_per_unit": "比较单件成本",
        "build_costs.column_comparison_cost_per_unit_help": "与所选建筑单件成本的差值。",
        "build_costs.column_material_help": "所需材料名称。",
        "build_costs.column_quantity": "数量",
        "build_costs.column_quantity_help": "所需材料数量。",
        "build_costs.column_volume_per_unit": "单件体积",
        "build_costs.column_volume_per_unit_help": "每单位材料的体积（m3）。",
        "build_costs.column_total_volume": "总体积",
        "build_costs.column_total_volume_help": "该材料的总体积（m3）。",
        "build_costs.column_unit_price": "单价",
        "build_costs.column_unit_price_help": "每单位材料成本（ISK）。",
        "build_costs.column_total_cost_materials_help": "该材料的总成本（ISK）。",
        "build_costs.column_percent_total": "总成本占比",
        "build_costs.column_percent_total_help": "该材料占总材料成本的比例。",
    },
    "de": {
        "app.page_title": "WinterCo Märkte",
        "app.language_label": "Sprache",
        "nav.section.market_stats": "Marktstatistiken",
        "nav.section.analysis_tools": "Analysewerkzeuge",
        "nav.section.data": "Daten",
        "nav.page.market_stats": "📈Marktstatistiken",
        "nav.page.low_stock": "⚠️Niedriger Bestand",
        "nav.page.import_helper": "📦Importhilfe",
        "nav.page.doctrine_status": "⚔️Doktrinstatus",
        "nav.page.doctrine_report": "📝Doktrinbericht",
        "nav.page.build_costs": "🏗️Produktionskosten",
        "nav.page.pricer": "🏷️Preisrechner",
        "nav.page.downloads": "📥Downloads",
        "doctrine_status.title": "Doktrinstatus von {market_name}",
        "doctrine_status.tab_market_stock": "Marktbestand",
        "doctrine_status.tab_fit_details": "Fit-Details",
        "doctrine_status.low_stock_modules": "Module mit niedrigem Bestand",
        "doctrine_status.no_fits": "Keine Doktrin-Fits in der Datenbank gefunden.",
        "doctrine_report.subtitle": "Marktstatus von {market_name} nach Flottendoktrin",
        "doctrine_report.no_data": "Keine Daten zum Anzeigen",
        "doctrine_report.metric_total_fits": "Verfügbare Fits gesamt",
        "doctrine_report.metric_total_hulls": "Rümpfe gesamt",
        "doctrine_report.metric_avg_target_pct": "Durchschnittliches Ziel %",
        "doctrine_report.role_dps": "💥 **DPS** - Primäre DPS-Schiffe",
        "doctrine_report.role_logi": "🏥 **Logi** - Logistikschiffe",
        "doctrine_report.role_links": "📡 **Links** - Kommandoschiffe",
        "doctrine_report.role_support": "🛠️ **Support** - EWAR, Tackle und andere Unterstützungsschiffe",
        "doctrine_report.stock_status": "Bestandsstatus",
        "doctrine_report.stock_status_summary": (
            "*Zusammenfassung des Bestandsstatus der drei Module mit dem niedrigsten Bestand für jedes "
            "Schiff in der ausgewählten Doktrin. Zahlen in Klammern zeigen, wie viele Fits mit dem "
            "aktuellen Bestand unterstützt werden können. Verwende die Kontrollkästchen für den CSV-Export.*"
        ),
        "doctrine_report.fit_id": "Fit-ID",
        "doctrine_report.target": "Ziel",
        "doctrine_report.no_target_found": "Kein Ziel für diesen Fit gefunden",
        "doctrine_report.equivalent_stock_caption": "🔄 Bestand enthält äquivalente Module",
        "doctrine_report.no_fits": "Keine Doktrin-Fits in der Datenbank gefunden.",
        "doctrine_report.select_doctrine": "Doktrin auswählen",
        "doctrine_report.target_multiplier": "Zielmultiplikator",
        "doctrine_report.target_multiplier_help": (
            "Dieser Multiplikator wird auf den Zielwert jedes Fits angewendet. Damit kann das Ziel "
            "aggressiver oder konservativer gesetzt werden. Der Standardwert ist 1.0."
        ),
        "doctrine_report.current_target_multiplier": "Aktueller Zielmultiplikator: {value}",
        "doctrine_report.ship_image_not_available": "🚀 Schiffsbild nicht verfügbar",
        "doctrine_report.doctrine_id": "Doktrin-ID: {doctrine_id}",
        "doctrine_report.selected_items": "Ausgewählte Elemente",
        "doctrine_report.modules_label": "Module:",
        "doctrine_report.no_items_selected": "Keine Elemente ausgewählt",
        "doctrine_report.export_options": "Exportoptionen",
        "doctrine_report.download_csv": "📥 CSV herunterladen",
        "doctrine_report.clear_selection": "🗑️ Auswahl löschen",
        "doctrine_report.column_target_pct": "Ziel %",
        "doctrine_report.column_target": "Ziel",
        "doctrine_report.column_target_help": "Anzahl der Fits, die für den Bestand benötigt werden.",
        "doctrine_report.column_daily_sales": "Tägliche Verkäufe",
        "doctrine_report.column_daily_sales_help": "Durchschnittliche tägliche Verkäufe der letzten 30 Tage.",
        "doctrine_report.column_group_help": "Schiffsgruppe.",
        "doctrine_report.column_ship": "Schiff",
        "doctrine_report.column_ship_help": "Schiffsname.",
        "doctrine_report.column_ship_id_help": "Schiffstyp-ID.",
        "doctrine_report.column_fit_id": "Fit-ID",
        "doctrine_report.column_fit_id_help": "Doktrin-Fit-ID.",
        "doctrine_report.column_price_help": "Preis des Schiffs.",
        "doctrine_report.column_total_cost": "Gesamtkosten",
        "doctrine_report.column_total_cost_help": "Gesamtkosten des Fits.",
        "common.market_hub": "Markthub",
        "common.select": "Auswählen",
        "common.type_id": "Typ-ID",
        "common.item": "Artikel",
        "common.category": "Kategorie",
        "common.group": "Gruppe",
        "common.price": "Preis",
        "low_stock.title": "Werkzeug für niedrigen Bestand von {market_name}",
        "low_stock.description": (
            "Diese Seite zeigt Artikel mit niedrigem Marktbestand. Die Spalte **Days Remaining** zeigt, "
            "wie viele Verkaufstage der aktuelle Bestand auf Basis des historischen Durchschnitts trägt. "
            "Die Spalte **Used In Fits** zeigt die Doktrinschiffe, die den Artikel verwenden, und wie viele "
            "Fits vom aktuellen Bestand unterstützt werden."
        ),
        "low_stock.filters_header": "Filter",
        "low_stock.filters_help": "Verwende die folgenden Filter, um die Ansicht anzupassen.",
        "low_stock.item_type_filters": "Artikelfilter",
        "low_stock.doctrine_only": "Nur Doktrinartikel",
        "low_stock.doctrine_only_help": "Nur Artikel anzeigen, die in einer Doktrin verwendet werden.",
        "low_stock.tech2_only": "Nur Tech-II-Artikel",
        "low_stock.tech2_only_help": "Nur Tech-II-Artikel anzeigen (metaGroupID=2).",
        "low_stock.faction_only": "Nur Fraktionsartikel",
        "low_stock.faction_only_help": "Nur Fraktionsartikel anzeigen (metaGroupID=4).",
        "low_stock.category_filter": "Kategoriefilter",
        "low_stock.select_categories": "Kategorien auswählen",
        "low_stock.select_categories_help": "Eine oder mehrere Kategorien zum Filtern auswählen.",
        "low_stock.doctrine_fit_filter": "Doktrin-/Fit-Filter",
        "low_stock.select_doctrine": "Doktrin auswählen",
        "low_stock.select_doctrine_help": "Nur Artikel einer bestimmten Doktrin anzeigen.",
        "low_stock.select_fit": "Fit auswählen",
        "low_stock.select_fit_help": "Nur Artikel eines bestimmten Fits anzeigen.",
        "low_stock.days_filter": "Filter für verbleibende Tage",
        "low_stock.max_days_remaining": "Maximale verbleibende Tage",
        "low_stock.max_days_remaining_help": "Nur Artikel mit gleicher oder geringerer Tageszahl anzeigen.",
        "low_stock.metric_critical": "Kritische Artikel (≤3 Tage)",
        "low_stock.metric_low": "Artikel mit niedrigem Bestand (3-7 Tage)",
        "low_stock.metric_total": "Gefilterte Artikel gesamt",
        "low_stock.subheader_fit": "Niedriger Bestand: {ship_name}",
        "low_stock.subheader_doctrine": "Niedriger Bestand: {doctrine_name}",
        "low_stock.subheader_all": "Artikel mit niedrigem Bestand",
        "low_stock.column_select_help": "Markiere Artikel für den CSV-Download.",
        "low_stock.column_item_help": "Name des Artikels.",
        "low_stock.column_volume_remaining": "Rest",
        "low_stock.column_volume_remaining_help": "Aktuell verfügbare Gesamtmenge auf dem Markt.",
        "low_stock.column_fits": "Fits",
        "low_stock.column_fits_help": "Gesamtzahl der Fits, die mit diesem Bestand gebaut werden können.",
        "low_stock.column_days": "Tage",
        "low_stock.column_days_help": "Verbleibende Bestandstage basierend auf historischen Durchschnittsverkaufen.",
        "low_stock.column_avg_vol": "Durchschn. Vol.",
        "low_stock.column_avg_vol_help": "Durchschnittliches Volumen der letzten 30 Tage.",
        "low_stock.column_used_in_fits": "Verwendet in Fits",
        "low_stock.column_used_in_fits_help": "Doktrinschiffe, die diesen Artikel verwenden.",
        "low_stock.column_category_help": "Kategorie des Artikels.",
        "low_stock.column_group_help": "Gruppe des Artikels.",
        "low_stock.selected_items": (
            "{count} Artikel ausgewählt. Besuche die **Downloads**-Seite für CSV-Sammel-Exporte."
        ),
        "low_stock.chart_section": "Verbleibende Tage nach Artikel",
        "low_stock.chart_title": "Verbleibende Bestandstage",
        "low_stock.chart_days_label": "Verbleibende Tage",
        "low_stock.chart_critical_level": "Kritisches Niveau (3 Tage)",
        "import_helper.title": "Importhilfe für {market_name}",
        "import_helper.description": (
            "Finde Artikel, bei denen der lokale Marktpreis deutlich über dem Jita-Verkaufspreis liegt. "
            "Der 30-Tage-Gewinn verwendet "
            "`(Lokaler Preis - Jita Sell) * durchschnittliches Tagesvolumen * 30`, der RRP verwendet "
            "`Jita Sell * (1 + Aufschlag)` und Cap Utilis verwendet "
            "`((Lokaler Preis - Jita Sell) - Versandkosten) / Jita Sell`."
        ),
        "import_helper.caption_green": "Gruen",
        "import_helper.caption_grey": "Grau",
        "import_helper.caption_estimated_price": (
            "{color_label} markierte Zellen zeigen geschaetzte lokale Preise mit 120 % "
            "des Jita-Sell-Preises (keine lokalen Verkaufsorders)"
        ),
        "import_helper.caption_floored_volume": (
            "{color_label} markierte Zellen zeigen auf 0.5 gesetztes 30D-Volumen "
            "(unzureichende Historie)"
        ),
        "import_helper.filters_header": "Filter",
        "import_helper.categories": "Kategorien",
        "import_helper.categories_help": "Die Tabelle auf eine oder mehrere Kategorien beschränken.",
        "import_helper.search_items": "Artikel suchen",
        "import_helper.search_items_help": "Namensfilter ohne Beachtung der Groß-/Kleinschreibung.",
        "import_helper.profitable_only": "Nur positiver Gewinn",
        "import_helper.profitable_only_help": "Artikel ausblenden, deren lokaler Preis nicht über Jita Sell liegt.",
        "import_helper.min_capital_utilis": "Minimale Kapitaleffizienz",
        "import_helper.min_capital_utilis_help": "0.10 bedeutet mindestens 10 % Kapitaleffizienz nach Versand.",
        "import_helper.min_turnover_30d": "Minimaler 30D-Umsatz",
        "import_helper.min_turnover_30d_help": "Artikel mit geringerem 30-Tage-Umsatz ausblenden.",
        "import_helper.shipping_cost_per_m3": "Versandkosten pro m3",
        "import_helper.shipping_cost_per_m3_help": (
            "Wird für die Versandkostenberechnung verwendet. Der Standardwert kommt aus settings.toml."
        ),
        "import_helper.markup_margin": "Aufschlag",
        "import_helper.markup_margin_help": "Wird für den RRP verwendet. 0.20 bedeutet 20 % über Jita Sell.",
        "import_helper.metric_total_items": "Artikel gesamt",
        "import_helper.metric_profitable_items": "Profitable Artikel",
        "import_helper.metric_avg_capital_utilis": "Durchschn. Kapitaleffizienz",
        "import_helper.column_item_help": "Lokalisierter Artikelname, falls verfügbar.",
        "import_helper.column_rrp_help": "Empfohlener Verkaufspreis basierend auf Jita Sell und Aufschlag.",
        "import_helper.column_jita_sell_help": "Jita-Verkaufspreis.",
        "import_helper.column_jita_buy_help": "Jita-Kaufpreis.",
        "import_helper.column_shipping_help": (
            "Berechnet als Artikelgröße in m3 multipliziert mit {shipping_cost_per_m3}."
        ),
        "import_helper.column_profit_30d_help": "Berechnet als (lokaler Preis - Jita-Verkaufspreis) mal Tagesvolumen mal 30.",
        "import_helper.column_turnover_30d_help": "In 30 Tagen verkaufte Einheiten multipliziert mit Jita Sell.",
        "import_helper.column_volume_30d_help": "Berechnet als durchschnittliches Tagesvolumen mal 30.",
        "import_helper.column_capital_utilis_help": "Berechnet als ((lokaler Preis - Jita Sell) - Versand) geteilt durch Jita Sell.",
        "import_helper.column_rrp": "RRP",
        "import_helper.column_jita_sell": "Jita Sell",
        "import_helper.column_jita_buy": "Jita Buy",
        "import_helper.column_shipping": "Versand",
        "import_helper.column_profit_30d": "30D Gewinn",
        "import_helper.column_turnover_30d": "30D Umsatz",
        "import_helper.column_volume_30d": "30D Volumen",
        "import_helper.column_capital_utilis": "Kapitaleffizienz",
        "build_costs.title": "Produktionskostenrechner",
        "build_costs.category_label": "Kategorie auswählen",
        "build_costs.category_placeholder": "Schiff",
        "build_costs.category_help": "Kategorie auswählen, um Gruppen und Artikel zu filtern.",
        "build_costs.group_label": "Gruppe auswählen",
        "build_costs.item_label": "Artikel auswählen",
        "build_costs.runs_label": "Läufe",
        "build_costs.me_label": "ME",
        "build_costs.te_label": "TE",
        "build_costs.material_price_source_label": "Quelle für Materialpreise auswählen",
        "build_costs.material_price_source_help": (
            "Quelle der Materialpreise für die Berechnung. ESI Average ist der CCP-Durchschnitt "
            "im Industrie-Fenster, Jita Sell ist der niedrigste Verkaufspreis in Jita und Jita "
            "Buy der höchste Ankaufspreis in Jita."
        ),
        "build_costs.price_source_esi_average": "ESI Durchschnitt",
        "build_costs.price_source_jita_sell": "Jita Verkauf",
        "build_costs.price_source_jita_buy": "Jita Ankauf",
        "build_costs.structure_compare_expander": "Struktur zum Vergleich auswählen (optional)",
        "build_costs.structure_compare_label": "Strukturen",
        "build_costs.structure_compare_placeholder": "Alle Strukturen",
        "build_costs.structure_compare_help": (
            "Wähle eine Struktur, mit der die Baukosten verglichen werden sollen. Leer lassen, "
            "um alle Strukturen anzuzeigen."
        ),
        "build_costs.parameters_changed": (
            "⚠️ Parameter wurden geändert. Klicke auf 'Neu berechnen', um die Ergebnisse zu aktualisieren."
        ),
        "build_costs.calculate": "Berechnen",
        "build_costs.recalculate": "Neu berechnen",
        "build_costs.calculate_help": "Klicke, um die Kosten für den ausgewählten Artikel zu berechnen.",
        "build_costs.industry_indexes_last_updated": "Industrieindizes zuletzt aktualisiert: {timestamp}",
        "build_costs.progress_start": "Daten von {total} Strukturen werden geladen...",
        "build_costs.progress_fetching": "Lade {current} von {total} Strukturen: {structure}",
        "build_costs.no_results": (
            "Keine Ergebnisse zurückgegeben. Wahrscheinlich gibt es ein Problem mit der externen "
            "Industrie-API. Bitte spater erneut versuchen."
        ),
        "build_costs.header": "Produktionskosten für {item_name}",
        "build_costs.summary": (
            "Produktionskosten für {item_name} mit {runs} Läufen, {me} ME, {te} TE und "
            "{price_source} als Materialpreisquelle (type_id: {type_id})"
        ),
        "build_costs.metric_build_cost_per_unit": "Baukosten pro Einheit",
        "build_costs.metric_build_cost_per_unit_help": "Basierend auf der günstigsten Struktur: {structure}",
        "build_costs.metric_total_build_cost": "Gesamte Baukosten",
        "build_costs.materials_job_cost": "**Materialien:** {materials} ISK | **Jobkosten:** {job_cost} ISK",
        "build_costs.market_price_summary": (
            "**{market_name}-Preis:** <span style='color: orange;'>{price} ISK</span> "
            "(Gewinn: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_market_price": "Keine {market_name}-Preisdaten für diesen Artikel gefunden",
        "build_costs.jita_price_summary": (
            "**Jita-Preis:** <span style='color: orange;'>{price} ISK</span> "
            "(Gewinn: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_jita_price": "Keine Jita-Preisdaten für diesen Artikel gefunden",
        "build_costs.super_note": (
            "<span style=\"font-weight: bold;\">Hinweis:</span> "
            "<span style=\"color: orange;\">Es werden nur Strukturen für Supercapital-Bau "
            "angezeigt.</span>"
        ),
        "build_costs.material_breakdown": "Materialaufschlüsselung",
        "build_costs.material_breakdown_for_structure": "Materialaufschlüsselung: {structure}",
        "build_costs.material_breakdown_selector": "Struktur für Materialaufschlüsselung auswählen",
        "build_costs.material_breakdown_selector_help": (
            "Wähle eine Struktur, um detaillierte Materialkosten und Mengen anzuzeigen."
        ),
        "build_costs.material_breakdown_missing": "Keine Daten für Struktur gefunden: {structure}",
        "build_costs.material_breakdown_summary": (
            "{item} Materialkosten: <span style='color: orange;'>**{cost} ISK**</span> "
            "(*{volume} m3*) - {price_source}"
        ),
        "build_costs.material_breakdown_tip": (
            "💡 **Tipp:** Diese Daten können über das Download-Symbol (⬇️) oben rechts in der Tabelle "
            "als CSV heruntergeladen werden."
        ),
        "build_costs.selected_structure": "Ausgewählte Struktur",
        "build_costs.empty_subheader": "WC Markets Produktionskostenrechner",
        "build_costs.empty_description": (
            "Wähle in der Seitenleiste Kategorie, Gruppe und Artikel aus, um Baukosten zu berechnen. "
            "Die Kosten werden für alle Strukturen in der Datenbank berechnet und nach Gesamtkosten "
            "sortiert. Optional kann mit einer bestimmten Struktur verglichen und die "
            "Materialaufschlüsselung angezeigt werden."
        ),
        "build_costs.tool_description": """
    - <span style="font-weight: bold; color: orange;">Laufe:</span> Anzahl der zu berechnenden Produktionslaufe.
    - <span style="font-weight: bold; color: orange;">ME:</span> Materialeffizienz der Blaupause. (Standard 0)
    - <span style="font-weight: bold; color: orange;">TE:</span> Zeiteffizienz der Blaupause. (Standard 0)
    - <span style="font-weight: bold; color: orange;">Materialpreisquelle:</span> Quelle der verwendeten Materialpreise.
        - *ESI Durchschnitt* - der CCP-Durchschnittspreis im Industrie-Fenster.
        - *Jita Verkauf* - der niedrigste Verkaufspreis in Jita.
        - *Jita Ankauf* - der hochste Ankaufspreis in Jita.
    - <span style="font-weight: bold; color: orange;">Struktur:</span> Struktur fur den Kostenvergleich. (optional)
    - <span style="font-weight: bold; color: orange;">Skills:</span> Alle Skills werden als Stufe 5 angenommen.
    """,
        "build_costs.no_buildable_items": (
            "Keine herstellbaren Artikel für Gruppe {group_name} gefunden. Möglicherweise fehlt "
            "eine SDE-Tabelle wie `industryActivityProducts`. Versuche einen Sync oder wähle "
            "eine andere Gruppe."
        ),
        "build_costs.load_items_error": "Artikel für die Gruppe konnten nicht geladen werden: {error}",
        "build_costs.invalid_selected_item": "Ausgewählter Artikel {item_name} ist nicht herstellbar",
        "build_costs.item_not_found": "Ausgewählter Artikel {item_name} wurde in der Typdatenbank nicht gefunden",
        "build_costs.invalid_item": "Ungültiger Artikel: {error}",
        "build_costs.select_valid_item": (
            "Ausgewählter Artikel {item_name} ist nicht herstellbar. Bitte wähle einen gültigen "
            "Artikel in der Seitenleiste."
        ),
        "build_costs.unknown_type": "Unbekannt ({type_id})",
        "build_costs.special_group_sovereignty_hub": "Souveränitäts-Hub",
        "build_costs.column_structure": "Struktur",
        "build_costs.column_structure_help": "Name der Struktur.",
        "build_costs.column_structure_type": "Typ",
        "build_costs.column_units": "Einheiten",
        "build_costs.column_units_help": "Anzahl der gebauten Einheiten.",
        "build_costs.column_total_cost": "Gesamtkosten",
        "build_costs.column_total_cost_help": "Gesamtkosten für die Produktion dieser Einheiten.",
        "build_costs.column_cost_per_unit": "Kosten pro Einheit",
        "build_costs.column_cost_per_unit_help": "Baukosten pro Einheit des Artikels.",
        "build_costs.column_material_cost": "Materialkosten",
        "build_costs.column_material_cost_help": "Gesamte Materialkosten.",
        "build_costs.column_total_job_cost": "Gesamte Jobkosten",
        "build_costs.column_total_job_cost_help": (
            "Gesamte Jobkosten inklusive Anlagensteuer, SCC-Aufschlag und Systemkostenindex."
        ),
        "build_costs.column_facility_tax": "Anlagensteuer",
        "build_costs.column_facility_tax_help": "Kosten der Anlagensteuer.",
        "build_costs.column_scc_surcharge": "SCC-Aufschlag",
        "build_costs.column_scc_surcharge_help": "Kosten des SCC-Aufschlags.",
        "build_costs.column_system_cost_index": "Kostenindex",
        "build_costs.column_rigs": "Rigs",
        "build_costs.column_rigs_help": "In der Struktur verbaute Rigs.",
        "build_costs.column_comparison_cost": "Vergleichskosten",
        "build_costs.column_comparison_cost_help": "Differenz zu den Gesamtkosten der ausgewählten Struktur.",
        "build_costs.column_comparison_cost_per_unit": "Vergleichskosten pro Einheit",
        "build_costs.column_comparison_cost_per_unit_help": (
            "Differenz zu den Kosten pro Einheit der ausgewählten Struktur."
        ),
        "build_costs.column_material_help": "Name des benötigten Materials.",
        "build_costs.column_quantity": "Menge",
        "build_costs.column_quantity_help": "Benotigte Materialmenge.",
        "build_costs.column_volume_per_unit": "Volumen/Einheit",
        "build_costs.column_volume_per_unit_help": "Volumen pro Materialeinheit (m3).",
        "build_costs.column_total_volume": "Gesamtvolumen",
        "build_costs.column_total_volume_help": "Gesamtvolumen dieses Materials (m3).",
        "build_costs.column_unit_price": "Einheitspreis",
        "build_costs.column_unit_price_help": "Kosten pro Materialeinheit (ISK).",
        "build_costs.column_total_cost_materials_help": "Gesamtkosten für dieses Material (ISK).",
        "build_costs.column_percent_total": "% des Gesamtwerts",
        "build_costs.column_percent_total_help": "Anteil an den gesamten Materialkosten.",
    },
    "fr": {
        "app.page_title": "Marchés WinterCo",
        "app.language_label": "Langue",
        "nav.section.market_stats": "Statistiques de marché",
        "nav.section.analysis_tools": "Outils d'analyse",
        "nav.section.data": "Données",
        "nav.page.market_stats": "📈Stats Marché",
        "nav.page.low_stock": "⚠️Stock Faible",
        "nav.page.import_helper": "📦Aide Import",
        "nav.page.doctrine_status": "⚔️État Doctrine",
        "nav.page.doctrine_report": "📝Rapport Doctrine",
        "nav.page.build_costs": "🏗️Coûts Production",
        "nav.page.pricer": "🏷️Tarificateur",
        "nav.page.downloads": "📥Téléchargements",
        "doctrine_status.title": "État Doctrine {market_name}",
        "doctrine_status.tab_market_stock": "Stock Marche",
        "doctrine_status.tab_fit_details": "Details du Fit",
        "doctrine_status.low_stock_modules": "Modules à Stock Faible",
        "doctrine_status.no_fits": "Aucun fit de doctrine trouvé dans la base de données.",
        "doctrine_report.subtitle": "État du marché de {market_name} par doctrine",
        "doctrine_report.no_data": "Aucune donnée à afficher",
        "doctrine_report.metric_total_fits": "Total fits disponibles",
        "doctrine_report.metric_total_hulls": "Total coques",
        "doctrine_report.metric_avg_target_pct": "Moyenne objectif %",
        "doctrine_report.role_dps": "💥 **DPS** - Vaisseaux DPS principaux",
        "doctrine_report.role_logi": "🏥 **Logi** - Vaisseaux logistiques",
        "doctrine_report.role_links": "📡 **Links** - Vaisseaux de commandement",
        "doctrine_report.role_support": "🛠️ **Support** - EWAR, tackle et autres soutiens",
        "doctrine_report.stock_status": "État du stock",
        "doctrine_report.stock_status_summary": (
            "*Résumé de l'état du stock des trois modules les plus faibles pour chaque vaisseau de la "
            "doctrine sélectionnée. Les nombres entre parenthèses indiquent combien de fits sont "
            "possibles avec le stock actuel. Utilisez les cases à cocher pour exporter en CSV.*"
        ),
        "doctrine_report.fit_id": "ID Fit",
        "doctrine_report.target": "Cible",
        "doctrine_report.no_target_found": "Aucune cible trouvée pour ce fit",
        "doctrine_report.equivalent_stock_caption": "🔄 Le stock inclut des modules equivalents",
        "doctrine_report.no_fits": "Aucun fit de doctrine trouvé dans la base de données.",
        "doctrine_report.select_doctrine": "Sélectionner une doctrine",
        "doctrine_report.target_multiplier": "Multiplicateur de cible",
        "doctrine_report.target_multiplier_help": (
            "Ce multiplicateur s'applique à la cible de chaque fit pour la rendre plus ou moins agressive. "
            "La valeur par défaut est 1.0."
        ),
        "doctrine_report.current_target_multiplier": "Multiplicateur de cible actuel : {value}",
        "doctrine_report.ship_image_not_available": "🚀 Image du vaisseau indisponible",
        "doctrine_report.doctrine_id": "Doctrine ID : {doctrine_id}",
        "doctrine_report.selected_items": "Objets sélectionnés",
        "doctrine_report.modules_label": "Modules :",
        "doctrine_report.no_items_selected": "Aucun objet sélectionné",
        "doctrine_report.export_options": "Options d'export",
        "doctrine_report.download_csv": "📥 Télécharger CSV",
        "doctrine_report.clear_selection": "🗑️ Effacer la sélection",
        "doctrine_report.column_target_pct": "Objectif %",
        "doctrine_report.column_target": "Cible",
        "doctrine_report.column_target_help": "Nombre de fits requis en stock.",
        "doctrine_report.column_daily_sales": "Ventes quotidiennes",
        "doctrine_report.column_daily_sales_help": "Ventes moyennes sur les 30 derniers jours.",
        "doctrine_report.column_group_help": "Groupe du vaisseau.",
        "doctrine_report.column_ship": "Vaisseau",
        "doctrine_report.column_ship_help": "Nom du vaisseau.",
        "doctrine_report.column_ship_id_help": "ID du type de vaisseau.",
        "doctrine_report.column_fit_id": "ID Fit",
        "doctrine_report.column_fit_id_help": "ID du fit de doctrine.",
        "doctrine_report.column_price_help": "Prix du vaisseau.",
        "doctrine_report.column_total_cost": "Coût total",
        "doctrine_report.column_total_cost_help": "Coût total du fit.",
        "common.market_hub": "Hub de marche",
        "common.select": "Sélection",
        "common.type_id": "ID Type",
        "common.item": "Objet",
        "common.category": "Catégorie",
        "common.group": "Groupe",
        "common.price": "Prix",
        "low_stock.title": "Outil Stock Faible {market_name}",
        "low_stock.description": (
            "Cette page montre les objets bientot en rupture. **Days Remaining** indique "
            "combien de jours les ventes peuvent etre soutenues avec le stock actuel. "
            "**Used In Fits** montre les doctrines utilisant l'objet et le nombre de fits possibles."
        ),
        "low_stock.filters_header": "Filtres",
        "low_stock.filters_help": "Utilisez les filtrés ci-dessous pour personnaliser la vue.",
        "low_stock.item_type_filters": "Filtres de type",
        "low_stock.doctrine_only": "Objets de doctrine uniquement",
        "low_stock.doctrine_only_help": "Afficher seulement les objets utilises dans une doctrine.",
        "low_stock.tech2_only": "Objets Tech II uniquement",
        "low_stock.tech2_only_help": "Afficher seulement les objets Tech II (metaGroupID=2).",
        "low_stock.faction_only": "Objets faction uniquement",
        "low_stock.faction_only_help": "Afficher seulement les objets faction (metaGroupID=4).",
        "low_stock.category_filter": "Filtre de catégorie",
        "low_stock.select_categories": "Sélectionner des catégories",
        "low_stock.select_categories_help": "Sélectionnez une ou plusieurs catégories.",
        "low_stock.doctrine_fit_filter": "Filtre doctrine/fit",
        "low_stock.select_doctrine": "Sélectionner une doctrine",
        "low_stock.select_doctrine_help": "N'afficher que les objets d'une doctrine spécifique.",
        "low_stock.select_fit": "Sélectionner un fit",
        "low_stock.select_fit_help": "N'afficher que les objets d'un fit spécifique.",
        "low_stock.days_filter": "Filtre jours restants",
        "low_stock.max_days_remaining": "Jours restants maximum",
        "low_stock.max_days_remaining_help": "Afficher seulement les objets au-dessous de cette limite.",
        "low_stock.metric_critical": "Objets critiques (≤3 jours)",
        "low_stock.metric_low": "Objets faibles (3-7 jours)",
        "low_stock.metric_total": "Total filtrés",
        "low_stock.subheader_fit": "Stock faible : {ship_name}",
        "low_stock.subheader_doctrine": "Stock faible : {doctrine_name}",
        "low_stock.subheader_all": "Objets à stock faible",
        "low_stock.column_select_help": "Cochez les objets a inclure dans l'export CSV.",
        "low_stock.column_item_help": "Nom de l'objet.",
        "low_stock.column_volume_remaining": "Restant",
        "low_stock.column_volume_remaining_help": "Quantite totale actuellement disponible.",
        "low_stock.column_fits": "Fits",
        "low_stock.column_fits_help": "Nombre total de fits possibles avec ce stock.",
        "low_stock.column_days": "Jours",
        "low_stock.column_days_help": "Jours de stock restants selon la moyenne historique.",
        "low_stock.column_avg_vol": "Vol. moy.",
        "low_stock.column_avg_vol_help": "Volume moyen sur 30 jours.",
        "low_stock.column_used_in_fits": "Utilise dans les fits",
        "low_stock.column_used_in_fits_help": "Vaisseaux de doctrine utilisant cet objet.",
        "low_stock.column_category_help": "Catégorie de l'objet.",
        "low_stock.column_group_help": "Groupe de l'objet.",
        "low_stock.selected_items": "{count} objets sélectionnés. Consultez **Downloads** pour les exports CSV.",
        "low_stock.chart_section": "Jours restants par objet",
        "low_stock.chart_title": "Jours de stock restants",
        "low_stock.chart_days_label": "Jours restants",
        "low_stock.chart_critical_level": "Niveau critique (3 jours)",
        "import_helper.title": "Aide Import {market_name}",
        "import_helper.description": (
            "Trouvez les objets dont le prix local dépasse nettement le prix de vente Jita. "
            "Le profit 30J utilise `(Prix local - Vente Jita) * Volume moyen quotidien * 30`, le RRP utilise "
            "`Vente Jita * (1 + marge)`."
        ),
        "import_helper.caption_green": "Vert",
        "import_helper.caption_grey": "Gris",
        "import_helper.caption_estimated_price": (
            "Les cellules {color_label} indiquent des prix locaux estimes a 120 % "
            "de la vente Jita (aucun ordre de vente local)"
        ),
        "import_helper.caption_floored_volume": (
            "Les cellules {color_label} indiquent un volume 30J force a 0.5 "
            "(historique insuffisant)"
        ),
        "import_helper.filters_header": "Filtres",
        "import_helper.categories": "Catégories",
        "import_helper.categories_help": "Limiter le tableau a une ou plusieurs catégories.",
        "import_helper.search_items": "Rechercher des objets",
        "import_helper.search_items_help": "Filtre par nom sans tenir compte de la casse.",
        "import_helper.profitable_only": "Profit positif uniquement",
        "import_helper.profitable_only_help": "Masquer les objets dont le prix local n'est pas supérieur a Jita.",
        "import_helper.min_capital_utilis": "Capital Utilis minimum",
        "import_helper.min_capital_utilis_help": "0,10 signifie au moins 10 % apres expédition.",
        "import_helper.min_turnover_30d": "CA minimum sur 30J",
        "import_helper.min_turnover_30d_help": "Masquer les objets sous ce chiffre d'affaires 30J.",
        "import_helper.shipping_cost_per_m3": "Coût d'expédition par m3",
        "import_helper.shipping_cost_per_m3_help": (
            "Utilise pour calculer l'expédition. La valeur par défaut vient de settings.toml."
        ),
        "import_helper.markup_margin": "Marge",
        "import_helper.markup_margin_help": "Utilisee pour le RRP. 0,20 signifie 20 % au-dessus de Jita.",
        "import_helper.metric_total_items": "Total objets",
        "import_helper.metric_profitable_items": "Objets profitables",
        "import_helper.metric_avg_capital_utilis": "Capital Utilis moyen",
        "import_helper.column_item_help": "Nom localisé si disponible.",
        "import_helper.column_rrp_help": "Prix conseillé base sur Jita et la marge.",
        "import_helper.column_jita_sell_help": "Prix de vente Jita.",
        "import_helper.column_jita_buy_help": "Prix d'achat Jita.",
        "import_helper.column_shipping_help": (
            "Calcule comme volume m3 multiplié par {shipping_cost_per_m3}."
        ),
        "import_helper.column_profit_30d_help": "Calcule a partir du profit unitaire et du volume moyen sur 30 jours.",
        "import_helper.column_turnover_30d_help": "Unités vendues sur 30 jours multipliées par le prix Jita.",
        "import_helper.column_volume_30d_help": "Volume moyen quotidien multiplié par 30.",
        "import_helper.column_capital_utilis_help": "Efficacité du capital apres expédition.",
        "import_helper.column_rrp": "RRP",
        "import_helper.column_jita_sell": "Vente Jita",
        "import_helper.column_jita_buy": "Achat Jita",
        "import_helper.column_shipping": "Expédition",
        "import_helper.column_profit_30d": "Profit 30J",
        "import_helper.column_turnover_30d": "CA 30J",
        "import_helper.column_volume_30d": "Volume 30J",
        "import_helper.column_capital_utilis": "Capital Utilis",
        "build_costs.title": "Outil de Coût de Production",
        "build_costs.category_label": "Sélectionner une catégorie",
        "build_costs.category_placeholder": "Vaisseau",
        "build_costs.category_help": "Sélectionnez une catégorie pour filtrer les groupes et les objets.",
        "build_costs.group_label": "Sélectionner un groupe",
        "build_costs.item_label": "Sélectionner un objet",
        "build_costs.runs_label": "Cycles",
        "build_costs.me_label": "ME",
        "build_costs.te_label": "TE",
        "build_costs.material_price_source_label": "Sélectionner une source de prix des matériaux",
        "build_costs.material_price_source_help": (
            "Source des prix matériaux utilisee pour le calcul. ESI Average est le prix moyen CCP "
            "de la fenetre industrielle, Jita Sell est le prix de vente minimum a Jita, et Jita "
            "Buy est le prix d'achat maximum a Jita."
        ),
        "build_costs.price_source_esi_average": "Moyenne ESI",
        "build_costs.price_source_jita_sell": "Vente Jita",
        "build_costs.price_source_jita_buy": "Achat Jita",
        "build_costs.structure_compare_expander": "Sélectionner une structure de comparaison (optionnel)",
        "build_costs.structure_compare_label": "Structures",
        "build_costs.structure_compare_placeholder": "Toutes les structures",
        "build_costs.structure_compare_help": (
            "Choisissez une structure pour comparer les couts de production. Laissez vide pour "
            "afficher toutes les structures."
        ),
        "build_costs.parameters_changed": (
            "⚠️ Les parametres ont change. Cliquez sur 'Recalculer' pour mettre a jour les résultats."
        ),
        "build_costs.calculate": "Calculer",
        "build_costs.recalculate": "Recalculer",
        "build_costs.calculate_help": "Cliquez pour calculer le coût de l'objet sélectionné.",
        "build_costs.industry_indexes_last_updated": "Indices industriels mis à jour le : {timestamp}",
        "build_costs.progress_start": "Récupération des données de {total} structures...",
        "build_costs.progress_fetching": "Récupération {current} sur {total} structures : {structure}",
        "build_costs.no_results": (
            "Aucun résultat retourne. Il s'agit probablement d'un probleme avec l'API industrielle "
            "externe. Réessayez plus tard."
        ),
        "build_costs.header": "Coût de production pour {item_name}",
        "build_costs.summary": (
            "Coût de production pour {item_name} avec {runs} cycles, {me} ME, {te} TE et "
            "{price_source} comme source de prix des matériaux (type_id : {type_id})"
        ),
        "build_costs.metric_build_cost_per_unit": "Coût de production par unite",
        "build_costs.metric_build_cost_per_unit_help": "Base sur la structure la moins chère : {structure}",
        "build_costs.metric_total_build_cost": "Coût total de production",
        "build_costs.materials_job_cost": "**Matériaux :** {materials} ISK | **Cout job :** {job_cost} ISK",
        "build_costs.market_price_summary": (
            "**Prix {market_name} :** <span style='color: orange;'>{price} ISK</span> "
            "(profit : {profit} ISK | {margin}%)"
        ),
        "build_costs.no_market_price": "Aucune donnée de prix {market_name} pour cet objet",
        "build_costs.jita_price_summary": (
            "**Prix Jita :** <span style='color: orange;'>{price} ISK</span> "
            "(profit : {profit} ISK | {margin}%)"
        ),
        "build_costs.no_jita_price": "Aucune donnée de prix Jita pour cet objet",
        "build_costs.super_note": (
            "<span style=\"font-weight: bold;\">Note :</span> "
            "<span style=\"color: orange;\">Seules les structures configurees pour la construction "
            "de supercapitaux sont affichees.</span>"
        ),
        "build_costs.material_breakdown": "Détail des matériaux",
        "build_costs.material_breakdown_for_structure": "Détail des matériaux : {structure}",
        "build_costs.material_breakdown_selector": "Sélectionner une structure pour voir le detail des matériaux",
        "build_costs.material_breakdown_selector_help": (
            "Choisissez une structure pour afficher les quantites et couts detailles des matériaux."
        ),
        "build_costs.material_breakdown_missing": "Aucune donnee trouvée pour la structure : {structure}",
        "build_costs.material_breakdown_summary": (
            "Cout matériaux de {item} : <span style='color: orange;'>**{cost} ISK**</span> "
            "(*{volume} m3*) - {price_source}"
        ),
        "build_costs.material_breakdown_tip": (
            "💡 **Astuce :** Vous pouvez télécharger ces données en CSV via l'icone de telechargement "
            "(⬇️) en haut à droite du tableau."
        ),
        "build_costs.selected_structure": "Structure sélectionnée",
        "build_costs.empty_subheader": "Outil de Coût de Production WC Markets",
        "build_costs.empty_description": (
            "Sélectionnez une catégorie, un groupe et un objet dans la barre latérale pour calculer "
            "le coût de production. Les résultats sont calcules pour toutes les structures de la base "
            "et triés par cout total. Vous pouvez aussi comparer avec une structure precise et afficher "
            "le detail des matériaux."
        ),
        "build_costs.tool_description": """
    - <span style="font-weight: bold; color: orange;">Cycles :</span> Nombre de cycles a calculer.
    - <span style="font-weight: bold; color: orange;">ME :</span> Efficacite materielle du blueprint. (par defaut 0)
    - <span style="font-weight: bold; color: orange;">TE :</span> Efficacite temporelle du blueprint. (par defaut 0)
    - <span style="font-weight: bold; color: orange;">Source de prix des materiaux :</span> Source de prix utilisee pour les calculs.
        - *Moyenne ESI* - prix moyen CCP de la fenetre industrielle.
        - *Vente Jita* - prix de vente minimum a Jita.
        - *Achat Jita* - prix d'achat maximum a Jita.
    - <span style="font-weight: bold; color: orange;">Structure :</span> Structure de comparaison des couts. (optionnel)
    - <span style="font-weight: bold; color: orange;">Competences :</span> Toutes les competences sont supposees au niveau 5.
    """,
        "build_costs.no_buildable_items": (
            "Aucun objet constructible trouvé pour le groupe {group_name}. Cela peut indiquer "
            "qu'une table SDE comme `industryActivityProducts` manque. Essayez une synchronisation "
            "ou choisissez un autre groupe."
        ),
        "build_costs.load_items_error": "Impossible de charger les objets du groupe : {error}",
        "build_costs.invalid_selected_item": "L'objet sélectionné {item_name} n'est pas constructible",
        "build_costs.item_not_found": "L'objet sélectionné {item_name} est introuvable dans la base de types",
        "build_costs.invalid_item": "Objet invalide : {error}",
        "build_costs.select_valid_item": (
            "L'objet sélectionné {item_name} n'est pas constructible. Veuillez choisir un objet "
            "valide dans la barre latérale."
        ),
        "build_costs.unknown_type": "Inconnu ({type_id})",
        "build_costs.special_group_sovereignty_hub": "Hub de souverainete",
        "build_costs.column_structure": "Structure",
        "build_costs.column_structure_help": "Nom de la structure.",
        "build_costs.column_structure_type": "Type",
        "build_costs.column_units": "Unités",
        "build_costs.column_units_help": "Nombre d'unités produites.",
        "build_costs.column_total_cost": "Coût total",
        "build_costs.column_total_cost_help": "Coût total pour produire ces unités.",
        "build_costs.column_cost_per_unit": "Cout par unite",
        "build_costs.column_cost_per_unit_help": "Coût de production par unite.",
        "build_costs.column_material_cost": "Cout matériaux",
        "build_costs.column_material_cost_help": "Coût total des matériaux.",
        "build_costs.column_total_job_cost": "Coût total du job",
        "build_costs.column_total_job_cost_help": (
            "Coût total du job incluant taxe d'installation, surcharge SCC et indice système."
        ),
        "build_costs.column_facility_tax": "Taxe d'installation",
        "build_costs.column_facility_tax_help": "Coût de la taxe d'installation.",
        "build_costs.column_scc_surcharge": "Surcharge SCC",
        "build_costs.column_scc_surcharge_help": "Coût de la surcharge SCC.",
        "build_costs.column_system_cost_index": "Indice de cout",
        "build_costs.column_rigs": "Rigs",
        "build_costs.column_rigs_help": "Rigs installés sur la structure.",
        "build_costs.column_comparison_cost": "Coût de comparaison",
        "build_costs.column_comparison_cost_help": "Difference avec le cout total de la structure sélectionnée.",
        "build_costs.column_comparison_cost_per_unit": "Coût de comparaison par unite",
        "build_costs.column_comparison_cost_per_unit_help": (
            "Difference avec le cout par unite de la structure sélectionnée."
        ),
        "build_costs.column_material_help": "Nom du matériau requis.",
        "build_costs.column_quantity": "Quantite",
        "build_costs.column_quantity_help": "Quantite de matériau nécessaire.",
        "build_costs.column_volume_per_unit": "Volume/unite",
        "build_costs.column_volume_per_unit_help": "Volume par unite de matériau (m3).",
        "build_costs.column_total_volume": "Volume total",
        "build_costs.column_total_volume_help": "Volume total de ce matériau (m3).",
        "build_costs.column_unit_price": "Prix unitaire",
        "build_costs.column_unit_price_help": "Cout par unite de matériau (ISK).",
        "build_costs.column_total_cost_materials_help": "Coût total pour ce matériau (ISK).",
        "build_costs.column_percent_total": "% du total",
        "build_costs.column_percent_total_help": "Pourcentage du cout total des matériaux.",
    },
    "ru": {
        "app.page_title": "Рынки WinterCo",
        "app.language_label": "Язык",
        "nav.section.market_stats": "Статистика рынка",
        "nav.section.analysis_tools": "Инструменты анализа",
        "nav.section.data": "Данные",
        "nav.page.market_stats": "📈Статистика",
        "nav.page.low_stock": "⚠️Низкие запасы",
        "nav.page.import_helper": "📦Помощник импорта",
        "nav.page.doctrine_status": "⚔️Статус доктрины",
        "nav.page.doctrine_report": "📝Отчёт доктрины",
        "nav.page.build_costs": "🏗️Стоимость производства",
        "nav.page.pricer": "🏷️Оценка",
        "nav.page.downloads": "📥Загрузки",
        "doctrine_status.title": "Статус доктрины {market_name}",
        "doctrine_status.tab_market_stock": "Рыночный запас",
        "doctrine_status.tab_fit_details": "Детали фита",
        "doctrine_status.low_stock_modules": "Модули с низким запасом",
        "doctrine_status.no_fits": "В базе данных не найдены фиты доктрины.",
        "doctrine_report.subtitle": "Статус рынка {market_name} по доктринам",
        "doctrine_report.no_data": "Нет данных для отображения",
        "doctrine_report.metric_total_fits": "Всего доступных фитов",
        "doctrine_report.metric_total_hulls": "Всего корпусов",
        "doctrine_report.metric_avg_target_pct": "Средний target %",
        "doctrine_report.role_dps": "💥 **DPS** — Основные DPS корабли",
        "doctrine_report.role_logi": "🏥 **Logi** — Логистические корабли",
        "doctrine_report.role_links": "📡 **Links** — Командные корабли",
        "doctrine_report.role_support": "🛠️ **Support** — EWAR, tackle и другая поддержка",
        "doctrine_report.stock_status": "Статус запаса",
        "doctrine_report.stock_status_summary": (
            "*Сводка по статусу трёх модулей с самым низким запасом для каждого корабля в выбранной "
            "доктрине. Числа в скобках показывают, сколько фитов поддерживает текущий запас. "
            "Используйте флажки для выбора элементов для CSV.*"
        ),
        "doctrine_report.fit_id": "Fit ID",
        "doctrine_report.target": "Target",
        "doctrine_report.no_target_found": "Для этого фита target не найден",
        "doctrine_report.equivalent_stock_caption": "🔄 Запас включает эквивалентные модули",
        "doctrine_report.no_fits": "В базе данных не найдены фиты доктрины.",
        "doctrine_report.select_doctrine": "Выберите доктрину",
        "doctrine_report.target_multiplier": "Множитель target",
        "doctrine_report.target_multiplier_help": (
            "Этот множитель применяется к target для каждого фита, чтобы сделать его более или менее агрессивным. "
            "Значение по умолчанию 1.0."
        ),
        "doctrine_report.current_target_multiplier": "Текущий множитель target: {value}",
        "doctrine_report.ship_image_not_available": "🚀 Изображение корабля недоступно",
        "doctrine_report.doctrine_id": "Doctrine ID: {doctrine_id}",
        "doctrine_report.selected_items": "Выбранные предметы",
        "doctrine_report.modules_label": "Модули:",
        "doctrine_report.no_items_selected": "Нет выбранных предметов",
        "doctrine_report.export_options": "Параметры экспорта",
        "doctrine_report.download_csv": "📥 Скачать CSV",
        "doctrine_report.clear_selection": "🗑️ Очистить выбор",
        "doctrine_report.column_target_pct": "Target %",
        "doctrine_report.column_target": "Target",
        "doctrine_report.column_target_help": "Количество фитов, необходимых в stock.",
        "doctrine_report.column_daily_sales": "Дневные продажи",
        "doctrine_report.column_daily_sales_help": "Средние дневные продажи за последние 30 дней.",
        "doctrine_report.column_group_help": "Группа корабля.",
        "doctrine_report.column_ship": "Корабль",
        "doctrine_report.column_ship_help": "Название корабля.",
        "doctrine_report.column_ship_id_help": "ID типа корабля.",
        "doctrine_report.column_fit_id": "Fit ID",
        "doctrine_report.column_fit_id_help": "ID фита доктрины.",
        "doctrine_report.column_price_help": "Цена корабля.",
        "doctrine_report.column_total_cost": "Общая стоимость",
        "doctrine_report.column_total_cost_help": "Общая стоимость фита.",
        "common.market_hub": "Торговый узел",
        "common.select": "Выбор",
        "common.type_id": "ID типа",
        "common.item": "Предмет",
        "common.category": "Категория",
        "common.group": "Группа",
        "common.price": "Цена",
        "low_stock.title": "Низкие запасы {market_name}",
        "low_stock.description": (
            "Эта страница показывает предметы с низким запасом на рынке. "
            "**Days Remaining** показывает, на сколько дней хватит текущего запаса. "
            "**Used In Fits** показывает доктрины, использующие предмет."
        ),
        "low_stock.filters_header": "Фильтры",
        "low_stock.filters_help": "Используйте эти фильтры для настройки вида.",
        "low_stock.item_type_filters": "Фильтры типа предмета",
        "low_stock.doctrine_only": "Только предметы доктрины",
        "low_stock.doctrine_only_help": "Показывать только предметы, используемые в доктрине.",
        "low_stock.tech2_only": "Только Tech II",
        "low_stock.tech2_only_help": "Показывать только предметы Tech II (metaGroupID=2).",
        "low_stock.faction_only": "Только фракционные",
        "low_stock.faction_only_help": "Показывать только фракционные предметы (metaGroupID=4).",
        "low_stock.category_filter": "Фильтр категории",
        "low_stock.select_categories": "Выберите категории",
        "low_stock.select_categories_help": "Выберите одну или несколько категорий.",
        "low_stock.doctrine_fit_filter": "Фильтр доктрины/фита",
        "low_stock.select_doctrine": "Выберите доктрину",
        "low_stock.select_doctrine_help": "Показывать только предметы определённой доктрины.",
        "low_stock.select_fit": "Выберите фит",
        "low_stock.select_fit_help": "Показывать только предметы определённого фита.",
        "low_stock.days_filter": "Фильтр оставшихся дней",
        "low_stock.max_days_remaining": "Максимум дней",
        "low_stock.max_days_remaining_help": "Показывать только предметы с днями не выше этого значения.",
        "low_stock.metric_critical": "Критические предметы (≤3 дня)",
        "low_stock.metric_low": "Низкий запас (3-7 дней)",
        "low_stock.metric_total": "Всего после фильтра",
        "low_stock.subheader_fit": "Низкий запас: {ship_name}",
        "low_stock.subheader_doctrine": "Низкий запас: {doctrine_name}",
        "low_stock.subheader_all": "Предметы с низким запасом",
        "low_stock.column_select_help": "Отметьте предметы для CSV экспорта.",
        "low_stock.column_item_help": "Название предмета.",
        "low_stock.column_volume_remaining": "Остаток",
        "low_stock.column_volume_remaining_help": "Общее количество, доступное на рынке.",
        "low_stock.column_fits": "Фиты",
        "low_stock.column_fits_help": "Сколько фитов можно собрать из этого запаса.",
        "low_stock.column_days": "Дни",
        "low_stock.column_days_help": "Оставшиеся дни по историческому среднему обороту.",
        "low_stock.column_avg_vol": "Средний объём",
        "low_stock.column_avg_vol_help": "Средний оборот за 30 дней.",
        "low_stock.column_used_in_fits": "Используется в фитах",
        "low_stock.column_used_in_fits_help": "Доктринные корабли, использующие этот предмет.",
        "low_stock.column_category_help": "Категория предмета.",
        "low_stock.column_group_help": "Группа предмета.",
        "low_stock.selected_items": "Выбрано предметов: {count}. Откройте **Downloads** для CSV экспортов.",
        "low_stock.chart_section": "Оставшиеся дни по предметам",
        "low_stock.chart_title": "Дни оставшегося запаса",
        "low_stock.chart_days_label": "Дни",
        "low_stock.chart_critical_level": "Критический уровень (3 дня)",
        "import_helper.title": "Помощник импорта {market_name}",
        "import_helper.description": (
            "Найдите предметы, где локальная цена значительно выше Jita sell. "
            "Прибыль за 30 дней считается как "
            "`(Локальная цена - Jita Sell) * средний дневной оборот * 30`."
        ),
        "import_helper.caption_green": "Зелёные",
        "import_helper.caption_grey": "Серые",
        "import_helper.caption_estimated_price": (
            "{color_label} ячейки показывают оценочные локальные цены на уровне 140% "
            "от Jita sell (нет локальных sell-ордеров)"
        ),
        "import_helper.caption_floored_volume": (
            "{color_label} ячейки показывают объём за 30 дней, принудительно установленный "
            "на 0.5 (недостаточно истории)"
        ),
        "import_helper.filters_header": "Фильтры",
        "import_helper.categories": "Категории",
        "import_helper.categories_help": "Ограничить таблицу одной или несколькими категориями.",
        "import_helper.search_items": "Поиск предметов",
        "import_helper.search_items_help": "Фильтр по имени без учёта регистра.",
        "import_helper.profitable_only": "Только с прибылью",
        "import_helper.profitable_only_help": "Скрыть предметы, где локальная цена не выше Jita sell.",
        "import_helper.min_capital_utilis": "Минимальный Capital Utilis",
        "import_helper.min_capital_utilis_help": "0.10 означает минимум 10% после доставки.",
        "import_helper.min_turnover_30d": "Минимальный оборот за 30 дней",
        "import_helper.min_turnover_30d_help": "Скрыть предметы с оборотом ниже этого значения.",
        "import_helper.shipping_cost_per_m3": "Стоимость доставки за m3",
        "import_helper.shipping_cost_per_m3_help": (
            "Используется для расчёта доставки. Значение по умолчанию берётся из settings.toml."
        ),
        "import_helper.markup_margin": "Наценка",
        "import_helper.markup_margin_help": "Используется для RRP. 0.20 означает 20% выше Jita sell.",
        "import_helper.metric_total_items": "Всего предметов",
        "import_helper.metric_profitable_items": "Прибыльные предметы",
        "import_helper.metric_avg_capital_utilis": "Средний Capital Utilis",
        "import_helper.column_item_help": "Локализованное название предмета, если доступно.",
        "import_helper.column_rrp_help": "Рекомендуемая цена на основе Jita sell и наценки.",
        "import_helper.column_jita_sell_help": "Цена продажи Jita.",
        "import_helper.column_jita_buy_help": "Цена покупки Jita.",
        "import_helper.column_shipping_help": (
            "Считается как объём в m3 умноженный на {shipping_cost_per_m3}."
        ),
        "import_helper.column_profit_30d_help": "Расчёт прибыли за 30 дней.",
        "import_helper.column_turnover_30d_help": "Оборот за 30 дней по цене Jita sell.",
        "import_helper.column_volume_30d_help": "Средний оборот в день, умноженный на 30.",
        "import_helper.column_capital_utilis_help": "Эффективность использования капитала после доставки.",
        "import_helper.column_rrp": "RRP",
        "import_helper.column_jita_sell": "Jita Sell",
        "import_helper.column_jita_buy": "Jita Buy",
        "import_helper.column_shipping": "Доставка",
        "import_helper.column_profit_30d": "Прибыль 30д",
        "import_helper.column_turnover_30d": "Оборот 30д",
        "import_helper.column_volume_30d": "Объём 30д",
        "import_helper.column_capital_utilis": "Capital Utilis",
        "build_costs.title": "Инструмент стоимости производства",
        "build_costs.category_label": "Выберите категорию",
        "build_costs.category_placeholder": "Корабль",
        "build_costs.category_help": "Выберите категорию для фильтра групп и предметов.",
        "build_costs.group_label": "Выберите группу",
        "build_costs.item_label": "Выберите предмет",
        "build_costs.runs_label": "Прогонов",
        "build_costs.me_label": "ME",
        "build_costs.te_label": "TE",
        "build_costs.material_price_source_label": "Выберите источник цен материалов",
        "build_costs.material_price_source_help": (
            "Источник цен материалов для расчёта. ESI Average — это средняя цена CCP в "
            "окне производства, Jita Sell — минимальная цена продажи в Jita, а Jita Buy "
            "— максимальная цена покупки в Jita."
        ),
        "build_costs.price_source_esi_average": "Средняя ESI",
        "build_costs.price_source_jita_sell": "Продажа Jita",
        "build_costs.price_source_jita_buy": "Покупка Jita",
        "build_costs.structure_compare_expander": "Выберите структуру для сравнения (необязательно)",
        "build_costs.structure_compare_label": "Структуры",
        "build_costs.structure_compare_placeholder": "Все структуры",
        "build_costs.structure_compare_help": (
            "Выберите структуру для сравнения стоимости производства. Оставьте пустым, чтобы "
            "показать все структуры."
        ),
        "build_costs.parameters_changed": (
            "⚠️ Параметры изменились. Нажмите «Пересчитать» для обновления результатов."
        ),
        "build_costs.calculate": "Рассчитать",
        "build_costs.recalculate": "Пересчитать",
        "build_costs.calculate_help": "Нажмите для расчёта стоимости выбранного предмета.",
        "build_costs.industry_indexes_last_updated": "Промышленные индексы обновлены: {timestamp}",
        "build_costs.progress_start": "Получение данных из {total} структур...",
        "build_costs.progress_fetching": "Получение {current} из {total} структур: {structure}",
        "build_costs.no_results": (
            "Результатов нет. Вероятно, есть проблема с внешним API промышленных данных. "
            "Попробуйте позже."
        ),
        "build_costs.header": "Стоимость производства для {item_name}",
        "build_costs.summary": (
            "Стоимость производства для {item_name}: {runs} прогонов, {me} ME, {te} TE, "
            "источник цен материалов {price_source} (type_id: {type_id})"
        ),
        "build_costs.metric_build_cost_per_unit": "Стоимость за единицу",
        "build_costs.metric_build_cost_per_unit_help": "На основе самой дешёвой структуры: {structure}",
        "build_costs.metric_total_build_cost": "Общая стоимость производства",
        "build_costs.materials_job_cost": "**Материалы:** {materials} ISK | **Стоимость работы:** {job_cost} ISK",
        "build_costs.market_price_summary": (
            "**Цена {market_name}:** <span style='color: orange;'>{price} ISK</span> "
            "(прибыль: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_market_price": "Данные о цене {market_name} для этого предмета не найдены",
        "build_costs.jita_price_summary": (
            "**Цена Jita:** <span style='color: orange;'>{price} ISK</span> "
            "(прибыль: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_jita_price": "Данные о цене Jita для этого предмета не найдены",
        "build_costs.super_note": (
            "<span style=\"font-weight: bold;\">Примечание:</span> "
            "<span style=\"color: orange;\">Показаны только структуры, настроенные для "
            "строительства supercapital.</span>"
        ),
        "build_costs.material_breakdown": "Разбор материалов",
        "build_costs.material_breakdown_for_structure": "Разбор материалов: {structure}",
        "build_costs.material_breakdown_selector": "Выберите структуру для просмотра материалов",
        "build_costs.material_breakdown_selector_help": (
            "Выберите структуру, чтобы увидеть подробные количества и стоимость материалов."
        ),
        "build_costs.material_breakdown_missing": "Данные по структуре не найдены: {structure}",
        "build_costs.material_breakdown_summary": (
            "Стоимость материалов для {item}: <span style='color: orange;'>**{cost} ISK**</span> "
            "(*{volume} m3*) - {price_source}"
        ),
        "build_costs.material_breakdown_tip": (
            "💡 **Совет:** Эти данные можно скачать в CSV через иконку загрузки (⬇️) в правом "
            "верхнем углу таблицы."
        ),
        "build_costs.selected_structure": "Выбранная структура",
        "build_costs.empty_subheader": "Инструмент стоимости производства WC Markets",
        "build_costs.empty_description": (
            "Выберите категорию, группу и предмет на боковой панели, чтобы рассчитать стоимость "
            "производства. Результаты считаются для всех структур в базе и сортируются по "
            "общей стоимости. Также можно сравнить с конкретной структурой и посмотреть разбор "
            "материалов."
        ),
        "build_costs.tool_description": """
    - <span style="font-weight: bold; color: orange;">Прогонов:</span> Количество прогонов для расчёта.
    - <span style="font-weight: bold; color: orange;">ME:</span> Материальная эффективность чертежа. (по умолчанию 0)
    - <span style="font-weight: bold; color: orange;">TE:</span> Временная эффективность чертежа. (по умолчанию 0)
    - <span style="font-weight: bold; color: orange;">Источник цен материалов:</span> Источник цен, используемых в расчётах.
        - *Средняя ESI* — средняя цена CCP в окне производства.
        - *Продажа Jita* — минимальная цена продажи в Jita.
        - *Покупка Jita* — максимальная цена покупки в Jita.
    - <span style="font-weight: bold; color: orange;">Структура:</span> Структура для сравнения стоимости. (необязательно)
    - <span style="font-weight: bold; color: orange;">Навыки:</span> Предполагается, что все навыки на уровне 5.
    """,
        "build_costs.no_buildable_items": (
            "Для группы {group_name} не найдено производимых предметов. Возможно, отсутствует "
            "таблица SDE, например `industryActivityProducts`. Попробуйте синхронизацию или "
            "выберите другую группу."
        ),
        "build_costs.load_items_error": "Не удалось загрузить предметы для группы: {error}",
        "build_costs.invalid_selected_item": "Выбранный предмет {item_name} нельзя производить",
        "build_costs.item_not_found": "Выбранный предмет {item_name} не найден в базе типов",
        "build_costs.invalid_item": "Некорректный предмет: {error}",
        "build_costs.select_valid_item": (
            "Выбранный предмет {item_name} нельзя производить. Пожалуйста, выберите корректный "
            "предмет на боковой панели."
        ),
        "build_costs.unknown_type": "Неизвестно ({type_id})",
        "build_costs.special_group_sovereignty_hub": "Центр суверенитета",
        "build_costs.column_structure": "Структура",
        "build_costs.column_structure_help": "Название структуры.",
        "build_costs.column_structure_type": "Тип",
        "build_costs.column_units": "Единицы",
        "build_costs.column_units_help": "Количество произведённых единиц.",
        "build_costs.column_total_cost": "Общая стоимость",
        "build_costs.column_total_cost_help": "Общая стоимость производства этих единиц.",
        "build_costs.column_cost_per_unit": "Стоимость за единицу",
        "build_costs.column_cost_per_unit_help": "Стоимость производства одной единицы.",
        "build_costs.column_material_cost": "Стоимость материалов",
        "build_costs.column_material_cost_help": "Общая стоимость материалов.",
        "build_costs.column_total_job_cost": "Общая стоимость работы",
        "build_costs.column_total_job_cost_help": (
            "Общая стоимость работы, включая налог сооружения, сбор SCC и индекс системы."
        ),
        "build_costs.column_facility_tax": "Налог сооружения",
        "build_costs.column_facility_tax_help": "Стоимость налога сооружения.",
        "build_costs.column_scc_surcharge": "Сбор SCC",
        "build_costs.column_scc_surcharge_help": "Стоимость сбора SCC.",
        "build_costs.column_system_cost_index": "Индекс стоимости",
        "build_costs.column_rigs": "Риги",
        "build_costs.column_rigs_help": "Риги, установленные на структуре.",
        "build_costs.column_comparison_cost": "Сравнительная стоимость",
        "build_costs.column_comparison_cost_help": "Разница с общей стоимостью выбранной структуры.",
        "build_costs.column_comparison_cost_per_unit": "Сравнительная стоимость за единицу",
        "build_costs.column_comparison_cost_per_unit_help": (
            "Разница со стоимостью за единицу выбранной структуры."
        ),
        "build_costs.column_material_help": "Название требуемого материала.",
        "build_costs.column_quantity": "Количество",
        "build_costs.column_quantity_help": "Требуемое количество материала.",
        "build_costs.column_volume_per_unit": "Объём/единица",
        "build_costs.column_volume_per_unit_help": "Объём на единицу материала (m3).",
        "build_costs.column_total_volume": "Общий объём",
        "build_costs.column_total_volume_help": "Общий объём этого материала (m3).",
        "build_costs.column_unit_price": "Цена за единицу",
        "build_costs.column_unit_price_help": "Стоимость единицы материала (ISK).",
        "build_costs.column_total_cost_materials_help": "Общая стоимость этого материала (ISK).",
        "build_costs.column_percent_total": "% от итога",
        "build_costs.column_percent_total_help": "Доля в общей стоимости материалов.",
    },
    "es": {
        "app.page_title": "Mercados WinterCo",
        "app.language_label": "Idioma",
        "nav.section.market_stats": "Estadisticas del Mercado",
        "nav.section.analysis_tools": "Herramientas de Analisis",
        "nav.section.data": "Datos",
        "nav.page.market_stats": "📈Estadisticas",
        "nav.page.low_stock": "⚠️Stock Bajo",
        "nav.page.import_helper": "📦Asistente de Importacion",
        "nav.page.doctrine_status": "⚔️Estado de Doctrina",
        "nav.page.doctrine_report": "📝Informe de Doctrina",
        "nav.page.build_costs": "🏗️Costes de Fabricacion",
        "nav.page.pricer": "🏷️Calculadora",
        "nav.page.downloads": "📥Descargas",
        "doctrine_status.title": "Estado de Doctrina de {market_name}",
        "doctrine_status.tab_market_stock": "Stock de Mercado",
        "doctrine_status.tab_fit_details": "Detalles del Fit",
        "doctrine_status.low_stock_modules": "Modulos con Stock Bajo",
        "doctrine_status.no_fits": "No se encontraron fits de doctrina en la base de datos.",
        "doctrine_report.subtitle": "Estado del mercado de {market_name} por doctrina de flota",
        "doctrine_report.no_data": "No hay datos para mostrar",
        "doctrine_report.metric_total_fits": "Fits Totales Disponibles",
        "doctrine_report.metric_total_hulls": "Cascos Totales",
        "doctrine_report.metric_avg_target_pct": "Promedio del Objetivo %",
        "doctrine_report.stock_status": "Estado de Stock",
        "doctrine_report.no_fits": "No se encontraron fits de doctrina en la base de datos.",
        "doctrine_report.select_doctrine": "Selecciona una doctrina",
        "common.market_hub": "Hub de mercado",
        "common.select": "Seleccionar",
        "common.type_id": "ID de tipo",
        "common.item": "Articulo",
        "common.category": "Categoria",
        "common.group": "Grupo",
        "common.price": "Precio",
        "low_stock.title": "Herramienta de Stock Bajo de {market_name}",
        "low_stock.description": (
            "Esta pagina muestra los articulos con poco stock en el mercado. "
            "La columna **Days Remaining** estima cuantos dias dura el stock actual "
            "segun el volumen historico medio."
        ),
        "low_stock.filters_header": "Filtros",
        "import_helper.title": "Asistente de Importacion de {market_name}",
        "import_helper.description": (
            "Descubre articulos cuyo precio local esta muy por encima del Jita sell. "
            "El beneficio de 30D usa `(Precio local - Jita Sell) * volumen diario medio * 30`, el RRP usa "
            "`Jita Sell * (1 + margen)` y Cap Utilis usa "
            "`((Precio local - Jita Sell) - envio) / Jita Sell`."
        ),
        "import_helper.caption_green": "Verde",
        "import_helper.caption_grey": "Gris",
        "import_helper.caption_estimated_price": (
            "Las celdas {color_label} muestran precios locales estimados al 120 % "
            "del Jita sell (sin ordenes locales de venta)"
        ),
        "import_helper.caption_floored_volume": (
            "Las celdas {color_label} muestran volumen 30D ajustado a 0.5 "
            "(historial insuficiente)"
        ),
        "import_helper.filters_header": "Filtros",
        "import_helper.categories": "Categorias",
        "import_helper.categories_help": "Limita la tabla a una o varias categorias.",
        "import_helper.search_items": "Buscar articulos",
        "import_helper.search_items_help": "Filtro por nombre sin distinguir mayusculas.",
        "import_helper.profitable_only": "Solo beneficio positivo",
        "import_helper.profitable_only_help": (
            "Oculta articulos cuyo precio local no supera el Jita sell."
        ),
        "import_helper.min_capital_utilis": "Capital Utilis minimo",
        "import_helper.min_capital_utilis_help": (
            "0.10 significa al menos un 10 % de utilizacion de capital tras el envio."
        ),
        "import_helper.min_turnover_30d": "Rotacion minima 30D",
        "import_helper.min_turnover_30d_help": (
            "Oculta articulos cuya rotacion de 30D este por debajo de este valor."
        ),
        "import_helper.shipping_cost_per_m3": "Coste de envio por m3",
        "import_helper.shipping_cost_per_m3_help": (
            "Se usa para calcular el envio. El valor por defecto viene de settings.toml."
        ),
        "import_helper.markup_margin": "Margen",
        "import_helper.markup_margin_help": "Se usa para el RRP. 0.20 significa un 20 % sobre Jita sell.",
        "import_helper.metric_total_items": "Articulos Totales",
        "import_helper.metric_profitable_items": "Articulos Rentables",
        "import_helper.metric_avg_capital_utilis": "Capital Utilis Medio",
        "import_helper.column_item_help": "Nombre localizado del articulo cuando este disponible.",
        "import_helper.column_rrp_help": "Precio recomendado basado en Jita sell y el margen.",
        "import_helper.column_jita_sell_help": "Precio percentil de venta en Jita.",
        "import_helper.column_jita_buy_help": "Precio percentil de compra en Jita.",
        "import_helper.column_shipping_help": (
            "Se calcula como el volumen del articulo en m3 multiplicado por {shipping_cost_per_m3}."
        ),
        "import_helper.column_profit_30d_help": (
            "Se calcula como (precio local - Jita sell) multiplicado por el volumen diario medio y por 30."
        ),
        "import_helper.column_turnover_30d_help": (
            "Unidades vendidas en 30 dias multiplicadas por el precio Jita sell."
        ),
        "import_helper.column_volume_30d_help": (
            "Se calcula como el volumen diario medio multiplicado por 30."
        ),
        "import_helper.column_capital_utilis_help": (
            "Se calcula como ((precio local - Jita sell) - envio) dividido por Jita sell."
        ),
        "import_helper.column_rrp": "RRP",
        "import_helper.column_jita_sell": "Jita Sell",
        "import_helper.column_jita_buy": "Jita Buy",
        "import_helper.column_shipping": "Envio",
        "import_helper.column_profit_30d": "Beneficio 30D",
        "import_helper.column_turnover_30d": "Rotacion 30D",
        "import_helper.column_volume_30d": "Volumen 30D",
        "import_helper.column_capital_utilis": "Capital Utilis",
        "build_costs.title": "Herramienta de Costes de Fabricacion",
        "build_costs.category_label": "Selecciona una categoria",
        "build_costs.category_placeholder": "Nave",
        "build_costs.category_help": "Selecciona una categoria para filtrar grupos y articulos.",
        "build_costs.group_label": "Selecciona un grupo",
        "build_costs.item_label": "Selecciona un articulo",
        "build_costs.runs_label": "Runs",
        "build_costs.me_label": "ME",
        "build_costs.te_label": "TE",
        "build_costs.material_price_source_label": "Selecciona una fuente de precio de materiales",
        "build_costs.material_price_source_help": (
            "Fuente de precios de materiales usada en los calculos. ESI Average es el precio medio "
            "de CCP en la ventana de industria, Jita Sell es el precio minimo de venta en Jita y "
            "Jita Buy es el precio maximo de compra en Jita."
        ),
        "build_costs.price_source_esi_average": "Media ESI",
        "build_costs.price_source_jita_sell": "Venta Jita",
        "build_costs.price_source_jita_buy": "Compra Jita",
        "build_costs.structure_compare_expander": "Selecciona una estructura para comparar (opcional)",
        "build_costs.structure_compare_label": "Estructuras",
        "build_costs.structure_compare_placeholder": "Todas las estructuras",
        "build_costs.structure_compare_help": (
            "Selecciona una estructura para comparar el coste de fabricacion. Dejalo vacio para "
            "mostrar todas las estructuras."
        ),
        "build_costs.parameters_changed": (
            "⚠️ Los parametros han cambiado. Pulsa 'Recalcular' para actualizar los resultados."
        ),
        "build_costs.calculate": "Calcular",
        "build_costs.recalculate": "Recalcular",
        "build_costs.calculate_help": "Pulsa para calcular el coste del articulo seleccionado.",
        "build_costs.industry_indexes_last_updated": "Indices industriales actualizados por ultima vez: {timestamp}",
        "build_costs.progress_start": "Obteniendo datos de {total} estructuras...",
        "build_costs.progress_fetching": "Obteniendo {current} de {total} estructuras: {structure}",
        "build_costs.no_results": (
            "No se devolvieron resultados. Probablemente haya un problema con la API externa de "
            "datos industriales. Vuelve a intentarlo mas tarde."
        ),
        "build_costs.header": "Coste de fabricacion de {item_name}",
        "build_costs.summary": (
            "Coste de fabricacion de {item_name} con {runs} runs, {me} ME, {te} TE y "
            "{price_source} como fuente de precios de materiales (type_id: {type_id})"
        ),
        "build_costs.metric_build_cost_per_unit": "Coste por unidad",
        "build_costs.metric_build_cost_per_unit_help": "Basado en la estructura mas barata: {structure}",
        "build_costs.metric_total_build_cost": "Coste total de fabricacion",
        "build_costs.materials_job_cost": "**Materiales:** {materials} ISK | **Coste del job:** {job_cost} ISK",
        "build_costs.market_price_summary": (
            "**Precio en {market_name}:** <span style='color: orange;'>{price} ISK</span> "
            "(beneficio: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_market_price": "No se encontraron datos de precio de {market_name} para este articulo",
        "build_costs.jita_price_summary": (
            "**Precio en Jita:** <span style='color: orange;'>{price} ISK</span> "
            "(beneficio: {profit} ISK | {margin}%)"
        ),
        "build_costs.no_jita_price": "No se encontraron datos de precio de Jita para este articulo",
        "build_costs.super_note": (
            "<span style=\"font-weight: bold;\">Nota:</span> "
            "<span style=\"color: orange;\">Solo se muestran estructuras configuradas para "
            "construccion de supercapitales.</span>"
        ),
        "build_costs.material_breakdown": "Desglose de materiales",
        "build_costs.material_breakdown_for_structure": "Desglose de materiales: {structure}",
        "build_costs.material_breakdown_selector": "Selecciona una estructura para ver el desglose de materiales",
        "build_costs.material_breakdown_selector_help": (
            "Elige una estructura para ver cantidades y costes detallados de materiales."
        ),
        "build_costs.material_breakdown_missing": "No se encontraron datos para la estructura: {structure}",
        "build_costs.material_breakdown_summary": (
            "Coste de materiales de {item}: <span style='color: orange;'>**{cost} ISK**</span> "
            "(*{volume} m3*) - {price_source}"
        ),
        "build_costs.material_breakdown_tip": (
            "💡 **Consejo:** Puedes descargar estos datos como CSV con el icono de descarga (⬇️) "
            "en la esquina superior derecha de la tabla."
        ),
        "build_costs.selected_structure": "Estructura seleccionada",
        "build_costs.empty_subheader": "Herramienta de Costes de Fabricacion de WC Markets",
        "build_costs.empty_description": (
            "Selecciona una categoria, grupo y articulo en la barra lateral para calcular el coste "
            "de fabricacion. El calculo se hace para todas las estructuras de la base de datos y se "
            "ordena por coste total. Tambien puedes comparar con una estructura concreta y revisar "
            "el desglose de materiales."
        ),
        "build_costs.tool_description": """
    - <span style="font-weight: bold; color: orange;">Runs:</span> Numero de runs que quieres calcular.
    - <span style="font-weight: bold; color: orange;">ME:</span> Eficiencia material del plano. (por defecto 0)
    - <span style="font-weight: bold; color: orange;">TE:</span> Eficiencia temporal del plano. (por defecto 0)
    - <span style="font-weight: bold; color: orange;">Fuente de precio de materiales:</span> Fuente de precios usada en los calculos.
        - *Media ESI* - el precio medio de CCP en la ventana de industria.
        - *Venta Jita* - el precio minimo de venta en Jita.
        - *Compra Jita* - el precio maximo de compra en Jita.
    - <span style="font-weight: bold; color: orange;">Estructura:</span> Estructura para comparar el coste. (opcional)
    - <span style="font-weight: bold; color: orange;">Habilidades:</span> Se asume que todas las habilidades estan al nivel 5.
    """,
        "build_costs.no_buildable_items": (
            "No se encontraron articulos fabricables para el grupo {group_name}. Esto puede "
            "indicar que falta una tabla SDE como `industryActivityProducts`. Intenta sincronizar "
            "la base de datos o selecciona otro grupo."
        ),
        "build_costs.load_items_error": "No se pudieron cargar los articulos del grupo: {error}",
        "build_costs.invalid_selected_item": "El articulo seleccionado {item_name} no es fabricable",
        "build_costs.item_not_found": "No se encontro el articulo seleccionado {item_name} en la base de tipos",
        "build_costs.invalid_item": "Articulo invalido: {error}",
        "build_costs.select_valid_item": (
            "El articulo seleccionado {item_name} no es fabricable. Selecciona un articulo valido "
            "en la barra lateral."
        ),
        "build_costs.unknown_type": "Desconocido ({type_id})",
        "build_costs.special_group_sovereignty_hub": "Centro de soberania",
        "build_costs.column_structure": "Estructura",
        "build_costs.column_structure_help": "Nombre de la estructura.",
        "build_costs.column_structure_type": "Tipo",
        "build_costs.column_units": "Unidades",
        "build_costs.column_units_help": "Numero de unidades fabricadas.",
        "build_costs.column_total_cost": "Coste total",
        "build_costs.column_total_cost_help": "Coste total de fabricar esas unidades.",
        "build_costs.column_cost_per_unit": "Coste por unidad",
        "build_costs.column_cost_per_unit_help": "Coste de fabricacion por unidad del articulo.",
        "build_costs.column_material_cost": "Coste de materiales",
        "build_costs.column_material_cost_help": "Coste total de materiales.",
        "build_costs.column_total_job_cost": "Coste total del job",
        "build_costs.column_total_job_cost_help": (
            "Coste total del job, incluidos impuesto de instalacion, recargo SCC e indice del sistema."
        ),
        "build_costs.column_facility_tax": "Impuesto de instalacion",
        "build_costs.column_facility_tax_help": "Coste del impuesto de instalacion.",
        "build_costs.column_scc_surcharge": "Recargo SCC",
        "build_costs.column_scc_surcharge_help": "Coste del recargo SCC.",
        "build_costs.column_system_cost_index": "Indice de coste",
        "build_costs.column_rigs": "Rigs",
        "build_costs.column_rigs_help": "Rigs instalados en la estructura.",
        "build_costs.column_comparison_cost": "Coste comparativo",
        "build_costs.column_comparison_cost_help": "Diferencia frente al coste total de la estructura seleccionada.",
        "build_costs.column_comparison_cost_per_unit": "Coste comparativo por unidad",
        "build_costs.column_comparison_cost_per_unit_help": (
            "Diferencia frente al coste por unidad de la estructura seleccionada."
        ),
        "build_costs.column_material_help": "Nombre del material requerido.",
        "build_costs.column_quantity": "Cantidad",
        "build_costs.column_quantity_help": "Cantidad de material necesaria.",
        "build_costs.column_volume_per_unit": "Volumen/unidad",
        "build_costs.column_volume_per_unit_help": "Volumen por unidad de material (m3).",
        "build_costs.column_total_volume": "Volumen total",
        "build_costs.column_total_volume_help": "Volumen total de este material (m3).",
        "build_costs.column_unit_price": "Precio unitario",
        "build_costs.column_unit_price_help": "Coste por unidad de material (ISK).",
        "build_costs.column_total_cost_materials_help": "Coste total de este material (ISK).",
        "build_costs.column_percent_total": "% del total",
        "build_costs.column_percent_total_help": "Porcentaje del coste total de materiales.",
    },
}


def get_language_options() -> list[str]:
    """Return supported language codes."""
    return list(LANGUAGE_OPTIONS.keys())


def get_language_label(language_code: str) -> str:
    """Return the short label for a language code."""
    return LANGUAGE_OPTIONS.get(language_code, LANGUAGE_OPTIONS[DEFAULT_LANGUAGE])


def translate_text(language_code: str, key: str, **kwargs) -> str:
    """Translate a UI string with English fallback.

    Raises no exceptions — a typo in any translation template
    falls back to the English template, then to the raw key.
    """
    language_map = TRANSLATIONS.get(language_code, {})
    template = language_map.get(key)
    if template is None:
        template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key)
    if template is None:
        template = key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        import logging

        logging.getLogger(__name__).debug(
            "Translation format error for key=%r lang=%s, falling back to English",
            key,
            language_code,
        )
        en_template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
        try:
            return en_template.format(**kwargs)
        except (KeyError, IndexError):
            return key
