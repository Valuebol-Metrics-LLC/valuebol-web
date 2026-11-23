"""Export per-team squads to public/upsl/squads.json for the Teams > Squad tab.

Per team: the scraped roster grouped by position, each player's goals in
the team's latest season, and a 4-4-2 starting eleven.

Reads data/<division>/rosters/rosters.parquet (upsl.fetch_rosters) and the
per-season goals.parquet / scorer_pages.parquet (upsl.fetch_scorers):

    python -m upsl.fetch_rosters
    python -m upsl.fetch_scorers --season "2026 Fall"
    python -m upsl.export_squads

Definitions:
  - Apps: the site's cumulative appearances for the club (not per season).
  - Goals: match goals (shootout goals excluded) credited on match pages in
    the team's latest season with a played match. Scorers are linked to
    roster players by name, ignoring full stops, case and extra spaces.
    `goals` is null when that season's match pages have not been scraped.
  - Starting eleven: per position the players with the most apps, ties
    broken alphabetically. Positions with too few players stay short.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from upsl.export_frontend import _as_bool, load_matches
from upsl.fetch import DATA_DIR, DEFAULT_DIVISION
from upsl.fetch_rosters import rosters_path
from upsl.fetch_scorers import GOALS_FILE, PAGES_FILE
from upsl.simulate_standings import _season_key

REPO_ROOT = Path(__file__).resolve().parents[2]
SQUADS_OUT = REPO_ROOT / "public" / "upsl" / "squads.json"

FORMATION = "4-4-2"
# Some team pages render positions translated (Spanish / Portuguese / French).
POSITIONS = {
    "Goalkeeper": "gk", "Portero": "gk", "Goleiro": "gk",
    "Defense": "def", "Defensa": "def", "Defesa": "def",
    "Midfield": "mid", "Centro del campo": "mid",
    "Forward": "fwd", "Adelante": "fwd", "Avant": "fwd",
}
LINEUP_SLOTS = {"gk": 1, "def": 4, "mid": 4, "fwd": 2}
GROUPS = ("gk", "def", "mid", "fwd", "other")


def normalize_name(name: str) -> str:
    return " ".join(re.sub(r"\.", "", str(name or "")).lower().split())


def latest_played_season(matches: pd.DataFrame) -> dict[str, str]:
    """team → latest season in which it has a played match."""
    played = matches[matches["played"].map(_as_bool)]
    seasons: dict[str, list[str]] = {}
    for side in ("home_team", "away_team"):
        for team, season in zip(played[side].astype(str), played["season"].astype(str)):
            seasons.setdefault(team, []).append(season)
    return {team: max(set(s), key=_season_key) for team, s in seasons.items()}


def load_scorers(division: str) -> tuple[pd.DataFrame, set[str]]:
    """Match-goal scorer rows for all seasons, and the seasons with scraped pages."""
    root = DATA_DIR / division
    goals = [pd.read_parquet(p) for p in sorted(root.glob(f"season=*/{GOALS_FILE}"))]
    pages = [pd.read_parquet(p) for p in sorted(root.glob(f"season=*/{PAGES_FILE}"))]
    scraped = {str(s) for df in pages for s in df["season"].unique()}
    columns = ["season", "match_url", "side", "team", "player", "goals"]
    if not goals:
        return pd.DataFrame(columns=columns), scraped
    g = pd.concat(goals, ignore_index=True)
    g = g[g["list_index"] == 0]
    return g[columns], scraped


def build_team(
    roster: pd.DataFrame, season: str | None, season_goals: dict[str, int] | None
) -> dict:
    groups: dict[str, list[dict]] = {g: [] for g in GROUPS}
    for p in roster.to_dict(orient="records"):
        group = POSITIONS.get(str(p["position"]), "other")
        goals = None if season_goals is None else season_goals.get(normalize_name(p["player"]), 0)
        groups[group].append({"name": p["player"], "apps": int(p["appearances"]), "goals": goals})
    for players in groups.values():
        players.sort(key=lambda p: (-p["apps"], p["name"].lower()))

    first = roster.iloc[0]
    return {
        "goals_season": season,
        "team_url": first["team_url"],
        "scraped_at": first["scraped_at"],
        "lineup": {g: groups[g][:n] for g, n in LINEUP_SLOTS.items()},
        "roster": groups,
    }


def build_payload(
    rosters: pd.DataFrame,
    scorers: pd.DataFrame,
    scraped_seasons: set[str],
    team_seasons: dict[str, str],
    *,
    division: str,
    now: datetime,
) -> tuple[dict, dict]:
    goal_totals: dict[tuple[str, str], dict[str, int]] = {}
    for (season, team, key), total in (
        scorers.assign(key=scorers["player"].map(normalize_name))
        .groupby(["season", "team", "key"])["goals"]
        .sum()
        .items()
    ):
        goal_totals.setdefault((str(season), str(team)), {})[key] = int(total)

    teams: dict[str, dict] = {}
    stats = {"credited": 0, "matched": 0}
    for team, roster in rosters.groupby("team", sort=True):
        season = team_seasons.get(team)
        season_goals = None
        if season in scraped_seasons:
            season_goals = goal_totals.get((season, team), {})
            roster_keys = {normalize_name(p) for p in roster["player"]}
            stats["credited"] += sum(season_goals.values())
            stats["matched"] += sum(v for k, v in season_goals.items() if k in roster_keys)
        teams[team] = build_team(roster, season, season_goals)

    payload = {
        "league": "UPSL",
        "division": division,
        "generated_at": now.isoformat(timespec="seconds"),
        "formation": FORMATION,
        "team_count": len(teams),
        "teams": teams,
    }
    return payload, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export UPSL squads for the Teams > Squad tab")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument("--out", type=Path, default=SQUADS_OUT)
    args = parser.parse_args(argv)

    path = rosters_path(args.division)
    if not path.exists():
        raise FileNotFoundError(f"No rosters at {path}. Run: python -m upsl.fetch_rosters")
    rosters = pd.read_parquet(path)
    scorers, scraped = load_scorers(args.division)
    team_seasons = latest_played_season(load_matches(args.division, "all"))

    payload, stats = build_payload(
        rosters, scorers, scraped, team_seasons,
        division=args.division, now=datetime.now(timezone.utc),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    with_goals = sum(1 for t in payload["teams"].values() if t["goals_season"] in scraped)
    pct = stats["matched"] / stats["credited"] if stats["credited"] else 0.0
    print(
        f"Wrote {args.out} ({payload['team_count']} teams, "
        f"{args.out.stat().st_size / 1024:.0f} KB); goals available for {with_goals} teams; "
        f"scorer goals linked to roster players: {stats['matched']}/{stats['credited']} ({pct:.1%})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
