"""Small EFT fitting parser for admin doctrine edits."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedEFTFit:
    ship_name: str
    fit_name: str
    item_quantities: dict[str, int]


_COUNT_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<count>[1-9][0-9]*)$")


def parse_eft_fit(fitting_text: str) -> ParsedEFTFit:
    """Parse an EFT fitting block into hull, fit name, and item quantities."""
    lines = [line.strip() for line in fitting_text.splitlines()]
    lines = [line for line in lines if line]
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
        for part in line.split(","):
            item_name, quantity = _parse_item_part(part.strip())
            if not item_name:
                continue
            item_quantities[item_name] = item_quantities.get(item_name, 0) + quantity

    if not item_quantities:
        raise ValueError("EFT fitting does not contain any fitted items")

    return ParsedEFTFit(ship_name=ship_name, fit_name=fit_name, item_quantities=item_quantities)


def _parse_item_part(item_text: str) -> tuple[str, int]:
    match = _COUNT_SUFFIX_RE.match(item_text)
    if match is None:
        return item_text, 1
    return match.group("name").strip(), int(match.group("count"))
