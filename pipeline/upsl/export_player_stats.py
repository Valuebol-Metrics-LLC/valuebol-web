"""Export scraped goal scorers for the frontend.

  public/upsl/player-stats.json   team → season → top scorers (Teams > Player Stats)
  public/upsl/match-scorers.json  match id → home / away scorers (Match Summary)

Reads the per-season goals.parquet and scorer_pages.parquet written by
upsl.fetch_scorers:

    python -m upsl.fetch_scorers --season "2026 Fall"
    python -m upsl.export_player_stats

Goals are match goals only (shootout list excluded). A player's entries are
merged by name ignoring full stops, case and extra spaces; the most common
spelling is shown. Every scorer counts, including players no longer on the
current roster. `scraped_seasons` lists seasons whose match pages have been
scraped, so a team or match with no entry there simply had no credited
scorers. UPSL lists no goal minutes, so match scorers carry counts only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from upsl.export_frontend import _match_id
from upsl.export_squads import load_scorers, normalize_name
from upsl.fetch import DEFAULT_DIVISION
from upsl.simulate_standings import _season_key

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYER_STATS_OUT = REPO_ROOT / "public" / "upsl" / "player-stats.json"
MATCH_SCORERS_OUT = REPO_ROOT / "public" / "upsl" / "match-scorers.json"


def _keyed(scorers: pd.DataFrame) -> pd.DataFrame:
    s = scorers.assign(
        season=scorers["season"].astype(str),
        team=scorers["team"].astype(str),
        key=scorers["player"].map(normalize_name),
    )
    return s[s["key"] != ""]


def _merge_players(grp: pd.DataFrame) -> list[dict]:
    """[{name, goals}] per normalized name, most goals first, then name."""
    rows = []
    for _, player in grp.groupby("key"):
        spellings = player["player"].value_counts()
        top = spellings[spellings == spellings.max()].index
        rows.append({"name": sorted(top)[0], "goals": int(player["goals"].sum())})
    rows.sort(key=lambda r: (-r["goals"], r["name"].lower()))
    return rows


def top_scorers(scorers: pd.DataFrame) -> dict[str, dict[str, list[dict]]]:
    """team → season → [{name, goals}]."""
    out: dict[str, dict[str, list[dict]]] = {}
    for (team, season), grp in _keyed(scorers).groupby(["team", "season"], sort=True):
        out.setdefault(team, {})[season] = _merge_players(grp)
    return out


def match_scorers(scorers: pd.DataFrame) -> dict[str, dict[str, list[dict]]]:
    """match id (same as matches.json) → {'home': [...], 'away': [...]}."""
    out: dict[str, dict[str, list[dict]]] = {}
    for (url, side), grp in _keyed(scorers).groupby(["match_url", "side"], sort=True):
        entry = out.setdefault(_match_id({"match_url": url}), {"home": [], "away": []})
        entry[str(side)] = _merge_players(grp)
    return out


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export UPSL goal scorers for the frontend")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument("--out", type=Path, default=PLAYER_STATS_OUT)
    parser.add_argument("--match-out", type=Path, default=MATCH_SCORERS_OUT)
    args = parser.parse_args(argv)

    scorers, scraped = load_scorers(args.division)
    header = {
        "league": "UPSL",
        "division": args.division,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scraped_seasons": sorted(scraped, key=_season_key, reverse=True),
    }
    teams = top_scorers(scorers)
    matches = match_scorers(scorers)
    _write_json(args.out, {**header, "team_count": len(teams), "teams": teams})
    _write_json(args.match_out, {**header, "match_count": len(matches), "matches": matches})
    print(
        f"Wrote {args.out} ({len(teams)} teams, {args.out.stat().st_size / 1024:.0f} KB) and "
        f"{args.match_out} ({len(matches)} matches, {args.match_out.stat().st_size / 1024:.0f} KB); "
        f"scraped seasons: {', '.join(header['scraped_seasons']) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
