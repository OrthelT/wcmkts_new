"""
Parser Utilities for Pricer Feature

Pure functions for parsing EFT fittings and tab-separated multibuy lists.
No database dependencies - just text parsing.

Supports:
- EFT (Eve Fitting Tool) format with ship header and slot sections
- Tab-separated item lists in either "item\tqty" or "qty\titem" format

Design:
- Pure functions (no side effects, no database calls)
- Returns raw parsed data; resolution to type_id happens in PricerService
- Handles common input variations gracefully
"""

import re
from typing import Optional
from dataclasses import dataclass

from domain.pricer import InputFormat, SlotType


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class RawParsedItem:
    """
    Raw parsed item before SDE resolution.

    Contains just the name and quantity extracted from text.
    """
    name: str
    quantity: int
    slot_type: SlotType = SlotType.UNKNOWN


@dataclass
class EFTParseResult:
    """Result of parsing an EFT fitting."""
    ship_name: str
    fit_name: str
    items: list[RawParsedItem]
    errors: list[str]


@dataclass
class MultibuyParseResult:
    """Result of parsing a multibuy list."""
    items: list[RawParsedItem]
    errors: list[str]


# =============================================================================
# Format Detection
# =============================================================================

def detect_input_format(text: str) -> InputFormat:
    """
    Detect whether input is EFT fitting or tab-separated list.

    EFT format starts with [ShipName, FitName].
    Multibuy is tab-separated text.

    Args:
        text: User input text

    Returns:
        InputFormat enum value
    """
    if not text or not text.strip():
        return InputFormat.UNKNOWN

    lines = text.strip().split('\n')
    first_line = lines[0].strip()

    # EFT format: first line starts with [ and contains a comma
    if first_line.startswith('[') and ',' in first_line:
        return InputFormat.EFT

    # Tab-separated: contains tabs
    if '\t' in text:
        return InputFormat.MULTIBUY

    # Could still be EFT without header (just modules)
    # or simple newline-separated item list
    # Default to multibuy for simple lists
    return InputFormat.MULTIBUY


# =============================================================================
# EFT Parsing
# =============================================================================

# Regex for quantity suffix: "Item x10" or "Item x1590"
EFT_QTY_PATTERN = re.compile(r'\s+x(\d+)$', re.IGNORECASE)

# EFT slot section order (by blank line position)
EFT_SLOT_ORDER = [
    SlotType.LOW,
    SlotType.MEDIUM,
    SlotType.HIGH,
    SlotType.RIG,
    SlotType.SUBSYSTEM,
    SlotType.DRONE,
    SlotType.CARGO,
]


def parse_eft_fitting(text: str) -> EFTParseResult:
    """
    Parse EFT-format fitting text.

    EFT Format:
    - First line: [ShipName, FitName]
    - Blank lines separate slot sections (low -> med -> high -> rigs -> drones -> cargo)
    - Items can have quantities: "Item Name x10"
    - Items without quantity have qty=1

    Args:
        text: EFT fitting text

    Returns:
        EFTParseResult with ship name, fit name, items list, and any errors
    """
    lines = text.strip().split('\n')

    ship_name = ""
    fit_name = ""
    items: list[RawParsedItem] = []
    errors: list[str] = []

    if not lines:
        return EFTParseResult(ship_name, fit_name, items, errors)

    # Track current slot section (by blank line count)
    # Start at -1 because first blank line after header is just a separator
    section_index = -1
    in_header = True
    started_modules = False

    for line in lines:
        line = line.strip()

        # Skip empty lines but track section changes
        if not line:
            if started_modules:
                # Only increment section after we've started parsing modules
                section_index += 1
            continue

        # Parse ship header: [ShipName, FitName]
        if line.startswith('[') and line.endswith(']'):
            header_content = line[1:-1]  # Remove brackets
            parts = header_content.split(',', 1)
            ship_name = parts[0].strip()
            fit_name = parts[1].strip() if len(parts) > 1 else "Unnamed Fit"

            # Add ship as an item with hull slot type
            items.append(RawParsedItem(
                name=ship_name,
                quantity=1,
                slot_type=SlotType.HULL
            ))
            in_header = False
            continue

        in_header = False

        # First non-empty line after header starts LOW slot section
        if not started_modules:
            started_modules = True
            section_index = 0

        # Skip [Empty X slot] placeholders
        if line.startswith('[Empty'):
            continue

        # Determine current slot type
        current_slot = SlotType.UNKNOWN
        if section_index < len(EFT_SLOT_ORDER):
            current_slot = EFT_SLOT_ORDER[section_index]
        else:
            current_slot = SlotType.CARGO  # Default excess to cargo

        # Parse item line (may have quantity suffix)
        parsed_item = _parse_eft_item_line(line, current_slot)
        if parsed_item:
            items.append(parsed_item)
        else:
            errors.append(f"Could not parse line: {line}")

    # Aggregate duplicate items
    items = _aggregate_items(items)

    return EFTParseResult(ship_name, fit_name, items, errors)


def _parse_eft_item_line(line: str, slot_type: SlotType) -> Optional[RawParsedItem]:
    """
    Parse a single EFT item line.

    Handles:
    - "Module Name" -> qty=1
    - "Module Name x10" -> qty=10
    - "Module Name, Charge Name" -> two items

    Args:
        line: Single line from EFT fitting
        slot_type: Current slot type based on section position

    Returns:
        RawParsedItem or None if line couldn't be parsed
    """
    line = line.strip()
    if not line:
        return None

    # Handle offline modules: "Module Name /offline"
    line = line.replace('/offline', '').strip()

    # Check for quantity suffix: "Item x10"
    qty_match = EFT_QTY_PATTERN.search(line)
    if qty_match:
        quantity = int(qty_match.group(1))
        item_name = line[:qty_match.start()].strip()
    else:
        quantity = 1
        item_name = line

    if not item_name:
        return None

    return RawParsedItem(
        name=item_name,
        quantity=quantity,
        slot_type=slot_type
    )


def _aggregate_items(items: list[RawParsedItem]) -> list[RawParsedItem]:
    """
    Aggregate duplicate items by name, summing quantities.

    Preserves slot_type from first occurrence.

    Args:
        items: List of parsed items (may have duplicates)

    Returns:
        List with duplicates merged
    """
    aggregated: dict[str, RawParsedItem] = {}

    for item in items:
        key = item.name.lower()  # Case-insensitive matching
        if key in aggregated:
            # Add quantity to existing
            existing = aggregated[key]
            aggregated[key] = RawParsedItem(
                name=existing.name,  # Keep original case
                quantity=existing.quantity + item.quantity,
                slot_type=existing.slot_type  # Keep first slot type
            )
        else:
            aggregated[key] = item

    return list(aggregated.values())


# =============================================================================
# Multibuy Parsing
# =============================================================================

def parse_multibuy_text(text: str) -> MultibuyParseResult:
    """
    Parse tab-separated item list.

    Supports formats:
    - "ItemName\tQuantity\t..." (item first)
    - "Quantity\tItemName\t..." (quantity first)

    Detection: If first column of first data line is numeric, assumes qty first.

    Additional columns after the first two are ignored.
    Stops parsing at "Total:" line.

    Args:
        text: Tab-separated item list

    Returns:
        MultibuyParseResult with items and any errors
    """
    lines = text.strip().split('\n')
    items: list[RawParsedItem] = []
    errors: list[str] = []

    if not lines:
        return MultibuyParseResult(items, errors)

    # Detect format from first line
    qty_first = _detect_quantity_first(lines)

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Stop at Total: line
        if line.lower().startswith('total:'):
            break

        # Parse based on detected format
        parsed = _parse_multibuy_line(line, qty_first)
        if parsed:
            items.append(parsed)
        elif line:  # Non-empty line that couldn't be parsed
            errors.append(f"Could not parse line: {line}")

    # Aggregate duplicates
    items = _aggregate_items(items)

    return MultibuyParseResult(items, errors)


def _detect_quantity_first(lines: list[str]) -> bool:
    """
    Detect if the multibuy format has quantity in first column.

    Checks if first column of first non-empty line is numeric.

    Args:
        lines: List of lines from input

    Returns:
        True if quantity appears to be first column
    """
    for line in lines:
        line = line.strip()
        if not line or line.lower().startswith('total:'):
            continue

        # Split by tab
        cols = line.split('\t')
        if not cols:
            continue

        first_col = cols[0].strip()
        # Check if first column is numeric (after removing thousands separators)
        cleaned = first_col.replace(',', '').replace('.', '').replace(' ', '')
        return cleaned.isdigit()

    return False  # Default: item name first


def _parse_multibuy_line(line: str, qty_first: bool) -> Optional[RawParsedItem]:
    """
    Parse a single multibuy line.

    Args:
        line: Tab-separated line
        qty_first: If True, format is "qty\tname", else "name\tqty"

    Returns:
        RawParsedItem or None if couldn't parse
    """
    cols = line.split('\t')

    if len(cols) < 2:
        # Single column - try to parse as item with qty=1
        if cols:
            name = cols[0].strip()
            if name and not _is_numeric(name):
                return RawParsedItem(name=name, quantity=1)
        return None

    if qty_first:
        qty_str = cols[0].strip()
        name = cols[1].strip()
    else:
        name = cols[0].strip()
        qty_str = cols[1].strip()

    if not name:
        return None

    # Parse quantity (handle thousands separators)
    quantity = _parse_quantity(qty_str)
    if quantity <= 0:
        quantity = 1  # Default to 1 if can't parse

    return RawParsedItem(
        name=name,
        quantity=quantity,
        slot_type=SlotType.UNKNOWN
    )


def _is_numeric(s: str) -> bool:
    """Check if string is numeric (after removing separators)."""
    cleaned = s.replace(',', '').replace('.', '').replace(' ', '')
    return cleaned.isdigit()


def _parse_quantity(qty_str: str) -> int:
    """
    Parse quantity string, handling thousands separators.

    Handles:
    - "1500" -> 1500
    - "1,500" -> 1500 (comma separator)
    - "1.500" -> 1500 (period separator, European)
    - "1 500" -> 1500 (space separator)

    Args:
        qty_str: Quantity string

    Returns:
        Integer quantity, or 0 if couldn't parse
    """
    if not qty_str:
        return 0

    # Remove common thousands separators
    cleaned = qty_str.strip()
    cleaned = cleaned.replace(',', '')
    cleaned = cleaned.replace(' ', '')

    # Handle period as thousands separator (European) vs decimal
    # If there's a period and the part after is 3 digits, it's likely thousands separator
    if '.' in cleaned:
        parts = cleaned.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            # Likely thousands separator
            cleaned = cleaned.replace('.', '')
        else:
            # Likely decimal - take integer part
            cleaned = parts[0]

    try:
        return int(cleaned)
    except ValueError:
        return 0


# =============================================================================
# Unified Parse Function
# =============================================================================

def parse_input(text: str) -> tuple[list[RawParsedItem], InputFormat, Optional[str], Optional[str], list[str]]:
    """
    Parse user input, auto-detecting format.

    Args:
        text: User input (EFT or multibuy format)

    Returns:
        Tuple of:
        - items: List of RawParsedItem
        - format: Detected InputFormat
        - ship_name: Ship name (EFT only, None otherwise)
        - fit_name: Fit name (EFT only, None otherwise)
        - errors: List of parse error messages
    """
    text = text.strip()
    if not text:
        return [], InputFormat.UNKNOWN, None, None, ["Empty input"]

    input_format = detect_input_format(text)

    if input_format == InputFormat.EFT:
        result = parse_eft_fitting(text)
        return result.items, InputFormat.EFT, result.ship_name, result.fit_name, result.errors
    else:
        result = parse_multibuy_text(text)
        return result.items, InputFormat.MULTIBUY, None, None, result.errors


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_item_name(name: str) -> str:
    """
    Normalize item name for database lookup.

    - Strips whitespace
    - Handles common typos/variations

    Args:
        name: Raw item name

    Returns:
        Normalized name for lookup
    """
    if not name:
        return ""

    # Strip whitespace
    name = name.strip()

    # Common variations
    # (could expand this with more mappings)

    return name
