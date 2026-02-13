"""
Doctrine Display Names

Maps raw database doctrine names to user-friendly display names.
The mapping is explicit because many names are not algorithmically
derivable (e.g., "WC Armor DPS NAPOC v1.0" -> "Apocalypse Navy").

Usage:
    get_doctrine_display_name("SUBS - WC AHACs")  # -> "AHACs"
    get_doctrine_display_name("Unknown")           # -> "Unknown" (fallback)
"""

DOCTRINE_DISPLAY_NAMES: dict[str, str] = {
    "SUBS - WC Hurricane / WC飓风": "Hurricane",
    "SUBS - WC Tackle": "Tackle",
    "SUBS - WC AHACs": "AHACs",
    "SUBS - WC Nightmare": "Nightmare",
    "SUBS - WC-EN Retributions 2404": "Retributions",
    "SUBS - WCEN Uprising Harpy Fleet": "Harpy",
    "SUBS - WC-EN AB Kikimora Fleet": "Kikimora (AB)",
    "SUBS - WCEN Uprising Torpedo Bombers": "Bombers (Torpedo)",
    "SUBS - WCEN Uprising Tempest Fleet Issue": "Tempest Fleet Issue",
    "WC Armor DPS NAPOC v1.0": "Apocalypse Navy",
    "SUBS - WC-EN Cyclone Fleet Issues": "Cyclone Fleet Issue",
    "SUBS - WC Rokhs": "Rokhs",
    "SUBS - WC-EN Tornados": "Tornados",
    "SUBS - WC-EN Bombing Bombers": "Bombers (Bombing)",
    "SUBS - Newbro Friendly Ships": "Newbro Friendly",
    "SUBS - WC-EN Vulture/Ferox Navy Issue Fleet": "Vulture/Ferox Navy",
    "SUBS - WC-EN Exequror Navy": "Exequror Navy",
    "SUBS - WC-EN Moas": "Moas",
    "SUBS - WC-EN Hurricane Fleet Issue": "Hurricane Fleet Issue",
    "WC-EN Shield DPS Maelstrom v1.0": "Maelstrom",
    "special fits": "Special Fits",
    "SUBS - WCEN Entosis": "Entosis",
    "SUBS - WC Raven Navy Issues": "Raven Navy Issue",
    "SUBS - WC-EN Ferox": "Ferox",

}


def get_doctrine_display_name(raw_name: str) -> str:
    """Return user-friendly display name for a doctrine, or the raw name if unknown."""
    display_name = DOCTRINE_DISPLAY_NAMES.get(raw_name, raw_name)
    return display_name
