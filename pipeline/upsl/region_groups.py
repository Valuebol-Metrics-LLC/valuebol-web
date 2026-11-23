"""Map UPSL conference names → region groups for Dixon–Coles bridge offsets.

Historical schedules rename conferences often (zones, sponsors). Aliases collapse
those labels so interlocking / national bridges share a stable group id.
"""

from __future__ import annotations

import re

# Explicit aliases (normalized key → region_group). Checked before prefix rules.
_ALIASES: dict[str, str] = {
    "arizona": "arizona",
    "colorado": "colorado",
    "dmv north": "dmv",
    "dmv south": "dmv",
    "dmv south-a": "dmv",
    "virginia north": "dmv",
    "virginia south": "dmv",
    "florida - central": "florida",
    "florida - central zone 1": "florida",
    "florida - central zone 2": "florida",
    "florida - south": "florida",
    "florida - west": "florida",
    "florida central - summer": "florida",
    "florida south zone 1": "florida",
    "florida south zone 2": "florida",
    "georgia": "georgia",
    "georgia north": "georgia",
    "georgia south": "georgia",
    "georgia zone 1": "georgia",
    "georgia zone 2": "georgia",
    "ky - tn": "ky_tn",
    "mid-atlantic": "mid_atlantic",
    "mid-atlantic north": "mid_atlantic",
    "mid-atlantic south": "mid_atlantic",
    "midwest central": "midwest",
    "midwest central - north": "midwest",
    "midwest central - south": "midwest",
    "midwest east": "midwest",
    "midwest south": "midwest",
    "midwest west": "midwest",
    "mountain west": "mountain_west",
    "ne-sd-ia": "ne_sd_ia",
    "new england": "new_england",
    "new england north": "new_england",
    "new england south": "new_england",
    "norcal": "norcal",
    "norcal north": "norcal",
    "norcal south": "norcal",
    "norcal zone a": "norcal",
    "american": "northeast",
    "american north": "northeast",
    "american south": "northeast",
    "northeast - american": "northeast",
    "northeast american": "northeast",
    "northeast american (north)": "northeast",
    "northeast american (south)": "northeast",
    "ok - ar": "ok_ar",
    "ohio": "ohio",
    "ohio/indy": "ohio",
    "ohio/indy north": "ohio",
    "ohio/indy south": "ohio",
    "oregon": "pacific_nw",
    "pacific northwest": "pacific_nw",
    "washington": "pacific_nw",
    "del real foods socal central": "socal",
    "socal central": "socal",
    "socal central coast": "socal",
    "socal north": "socal",
    "socal south": "socal",
    "cricket wireless texas central": "texas",
    "cricket wireless texas south": "texas",
    "texas central": "texas",
    "texas central - austin": "texas",
    "texas central - san antonio": "texas",
    "texas north": "texas",
    "texas south": "texas",
    "west texas - new mexico": "west_texas",
    "western ny": "western_ny",
    "western ny east": "western_ny",
    "western ny west": "western_ny",
    "gateway": "gateway",
}


def _norm(name: str) -> str:
    text = str(name or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def region_group(conference: str | None) -> str:
    """Return stable region group id for a conference display name."""
    key = _norm(conference or "")
    if not key or key in {"n/a", "none", "unknown"}:
        return "unknown"
    if key in _ALIASES:
        return _ALIASES[key]
    # Prefix fallbacks for future renames.
    if key.startswith("florida"):
        return "florida"
    if key.startswith("georgia"):
        return "georgia"
    if key.startswith("dmv") or key.startswith("virginia"):
        return "dmv"
    if key.startswith("mid-atlantic"):
        return "mid_atlantic"
    if key.startswith("midwest"):
        return "midwest"
    if key.startswith("new england"):
        return "new_england"
    if key.startswith("norcal"):
        return "norcal"
    if key.startswith("socal") or "socal" in key:
        return "socal"
    if key.startswith("texas") or "texas central" in key or "texas south" in key:
        return "texas"
    if key.startswith("west texas"):
        return "west_texas"
    if key.startswith("western ny"):
        return "western_ny"
    if key.startswith("ohio"):
        return "ohio"
    if "american" in key or key.startswith("northeast"):
        return "northeast"
    return f"other:{key}"
