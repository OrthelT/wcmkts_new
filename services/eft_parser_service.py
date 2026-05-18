"""Small EFT fitting parser for admin doctrine edits.

EFT format expectations (per EVE Online's in-game EFT export):
- The first line is the header ``[Hull Name, Fit Name]``.
- Each subsequent body line is either:
    * ``Item Name`` — one of that item
    * ``Item Name xN`` — N stacked items (drones, charges placed in cargo)
    * ``Module Name, Charge Name`` — a module with a loaded charge
- Multi-comma body lines are anomalous (EVE items do not contain commas in
  their names). This parser splits at most one comma per body line so a
  malformed paste cannot silently fan out into three or more phantom items.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re


@dataclass(frozen=True)
class ParsedEFTFit:
    ship_name: str
    fit_name: str
    item_quantities: dict[str, int]


_COUNT_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<count>[1-9][0-9]*)$")

# Sanity bounds for admin-pasted input. A normal EFT export is well under any
# of these; the bounds exist so a clipboard mishap (entire log file, accidental
# tab dump, runaway expansion macro) cannot hang the parser or hold an open
# Turso transaction open while per-item SDE lookups iterate downstream.
_MAX_FITTING_CHARS = 100_000
_MAX_LINES = 500
_MAX_UNIQUE_ITEMS = 200

logger = logging.getLogger(__name__)


def parse_eft_fit(fitting_text: str) -> ParsedEFTFit:
    """Parse an EFT fitting block into hull, fit name, and item quantities."""
    if len(fitting_text) > _MAX_FITTING_CHARS:
        raise ValueError(
            f"EFT fitting is too large ({len(fitting_text)} chars > "
            f"{_MAX_FITTING_CHARS} cap). Paste only one fit at a time."
        )

    lines = [line.strip() for line in fitting_text.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) > _MAX_LINES:
        raise ValueError(
            f"EFT fitting has too many lines ({len(lines)} > {_MAX_LINES} cap). "
            "Paste only one fit at a time."
        )
    if not lines or not lines[0].startswith("[") or not lines[0].endswith("]"):
        raise ValueError("EFT fitting must start with a [Hull, Fit Name] header")

    header = lines[0][1:-1]
    if "," not in header:
        raise ValueError("EFT fitting header must include hull and fit name")

    ship_name, fit_name = [part.strip() for part in header.split(",", 1)]
    if not ship_name or not fit_name:
        raise ValueError("EFT fitting header must include hull and fit name")

    item_quantities: dict[str, int] = {}
    for line in lines[1:]:
        if line.count(",") > 1:
            logger.warning(
                "EFT body line has %d commas — only the first is treated as a "
                "module/charge separator: %r",
                line.count(","),
                line,
            )
        for part in line.split(",", 1):
            item_name, quantity = _parse_item_part(part.strip())
            if not item_name:
                continue
            item_quantities[item_name] = item_quantities.get(item_name, 0) + quantity
        if len(item_quantities) > _MAX_UNIQUE_ITEMS:
            raise ValueError(
                f"EFT fitting has too many distinct items "
                f"(>{_MAX_UNIQUE_ITEMS}). Paste only one fit at a time."
            )

    if not item_quantities:
        raise ValueError("EFT fitting does not contain any fitted items")

    return ParsedEFTFit(ship_name=ship_name, fit_name=fit_name, item_quantities=item_quantities)


def _parse_item_part(item_text: str) -> tuple[str, int]:
    match = _COUNT_SUFFIX_RE.match(item_text)
    if match is None:
        return item_text, 1
    return match.group("name").strip(), int(match.group("count"))
