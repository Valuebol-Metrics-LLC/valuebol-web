"""Map variant UPSL team spellings to one canonical name.

UPSL schedules occasionally change a club's spelling between seasons (e.g.
capitalisation). Without an alias, Elo, Dixon–Coles and standings treat the
variants as separate teams and the club loses its match history.
"""

from __future__ import annotations

import pandas as pd

# Variant spelling → canonical spelling (the club's current UPSL name).
_ALIASES: dict[str, str] = {
    "Tenfifteen FC": "TenFifteen FC",
}


def canonical_team(name):
    """Return the canonical spelling for one team name."""
    if not isinstance(name, str):
        return name
    return _ALIASES.get(name.strip(), name)


def canonicalize_teams(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Replace variant spellings in the given columns (missing columns are skipped)."""
    for col in columns:
        if col in df.columns:
            df[col] = df[col].map(canonical_team)
    return df
