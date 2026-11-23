"""Export per-team profiles to public/upsl/teams.json for the Teams tab.

Per team: 3-letter abbreviation, current conference, current ASI (Elo),
home stadium, and one row per season (record, league position, ASI rank,
conference playoff finish, inferred playoff spots).

Reads the scraped parquet (matches + standings) and the published
public/upsl/elo-rankings.json, so run it after `upsl.elo`:

    python -m upsl.export_frontend
    python -m upsl.elo
    python -m upsl.export_teams

Definitions:
  - ASI rank (completed season): rank by Elo as of the season's last played
    match, among teams that played a match that season.
  - ASI rank (ongoing season): rank by current Elo among clubs with a match
    played or scheduled in the last ACTIVITY_WINDOW_MONTHS (same rule as the
    Team Rankings tab).
  - Playoff finish: conference playoffs only. A team's exit round comes from
    how many more playoff matches the opponent that eliminated it went on to
    play (1 → semifinal, 2 → quarterfinal), because older match URLs carry no
    round label.
  - Playoff spots: teams from the conference that played its playoffs that
    season; the ongoing season uses the most recent earlier count.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

from upsl.elo import RANKINGS_OUT
from upsl.export_frontend import (
    _as_bool,
    _to_iso_date,
    clean_venue,
    load_matches,
    load_standings,
)
from upsl.fetch import DEFAULT_DIVISION
from upsl.simulate_standings import _season_key

REPO_ROOT = Path(__file__).resolve().parents[2]
TEAMS_OUT = REPO_ROOT / "public" / "upsl" / "teams.json"
# Must match ACTIVITY_WINDOW_MONTHS in src/utils/rankings.js.
ACTIVITY_WINDOW_MONTHS = 6
COUNTRY = "USA"

# Words skipped when building initials ("NY Renegades FC" → NYR).
_ABBR_STOPWORDS = {
    "fc", "sc", "ac", "cf", "afc", "fa", "sa", "cd", "club", "football",
    "soccer", "the", "de", "of", "and",
}
# Hand-picked codes that win over the generated ones.
_ABBR_OVERRIDES: dict[str, str] = {}


def team_abbreviation(name: str) -> str:
    """Three-letter code from a team name.

    Initials of the significant words (an all-caps word such as "NY"
    contributes all its letters), padded with the following letters of the
    last word, then the first word, when fewer than three are available.
    """
    if name in _ABBR_OVERRIDES:
        return _ABBR_OVERRIDES[name]
    words = re.findall(r"[A-Za-z0-9]+", name.replace("'", "").replace("’", ""))
    significant = [w for w in words if w.lower() not in _ABBR_STOPWORDS] or words
    if not significant:
        return name[:3].upper()

    letters = ""
    for word in significant:
        if word.isupper() and 2 <= len(word) <= 3:
            letters += word
        else:
            letters += word[0]
    for filler in (significant[-1][1:], significant[0][1:]):
        if len(letters) >= 3:
            break
        letters += filler[: 3 - len(letters)]
    return letters[:3].upper()


def prepare_matches(matches: pd.DataFrame) -> pd.DataFrame:
    m = matches.copy()
    m["home_team"] = m["home_team"].astype(str).str.strip()
    m["away_team"] = m["away_team"].astype(str).str.strip()
    m["season"] = m["season"].astype(str)
    m["played"] = m["played"].map(_as_bool)
    m["is_playoff"] = m["is_playoff"].map(_as_bool)
    m["iso_date"] = [
        _to_iso_date(r.get("date"), date_sort=r.get("date_sort"), season=str(r.get("season") or ""))
        for r in m.to_dict(orient="records")
    ]
    m = m[m["iso_date"].notna()].copy()
    m["kickoff"] = pd.to_numeric(m.get("kickoff_ts"), errors="coerce").fillna(0)
    m["scope"] = m["playoff_scope"].fillna("").astype(str).str.lower()
    return m.sort_values(["iso_date", "kickoff"], kind="mergesort").reset_index(drop=True)


def pick_standing_rows(standings: pd.DataFrame) -> dict[tuple[str, str], dict]:
    """One standings row per (team, season); the one with most games played wins."""
    out: dict[tuple[str, str], dict] = {}
    for raw in standings.to_dict(orient="records"):
        team = str(raw.get("team") or "").strip()
        season = str(raw.get("season") or "").strip()
        if not team or not season:
            continue
        gp = int(pd.to_numeric(raw.get("gp"), errors="coerce") or 0)
        cur = out.get((team, season))
        if cur is None or gp > cur["gp"]:
            out[(team, season)] = {
                "conference": str(raw.get("conference") or "").strip(),
                "place": _int_or_none(raw.get("place")),
                "gp": gp,
                "gf": _int_or_none(raw.get("gf")) or 0,
                "ga": _int_or_none(raw.get("ga")) or 0,
                "wins": _int_or_none(raw.get("wins")) or 0,
                "draws": _int_or_none(raw.get("draws")) or 0,
                "losses": _int_or_none(raw.get("losses")) or 0,
                "pts": _int_or_none(raw.get("pts")) or 0,
            }
    return out


def _int_or_none(value) -> int | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else int(number)


def ongoing_season(matches: pd.DataFrame) -> str | None:
    """Most recent season that still has any unplayed fixture (incl. playoffs)."""
    seasons = matches.loc[~matches["played"], "season"].unique()
    return max(seasons, key=_season_key) if len(seasons) else None


# ---------------------------------------------------------------------------
# ASI ranks
# ---------------------------------------------------------------------------

def rating_as_of(points: list[dict], iso_date: str) -> float | None:
    """Elo after the last history point on or before iso_date."""
    rating = None
    for p in points:
        if p["d"] > iso_date:
            break
        rating = float(p["e"])
    return rating


def rank_map(ratings: dict[str, float]) -> dict[str, int]:
    """1 = highest rating; ties broken by name (same order as the Rankings tab)."""
    order = sorted(ratings, key=lambda t: (-ratings[t], t))
    return {team: i + 1 for i, team in enumerate(order)}


def season_asi_ranks(
    matches: pd.DataFrame, history: dict[str, list[dict]]
) -> dict[str, dict[str, int]]:
    """season → team → ASI rank as of that season's last played match."""
    played = matches[matches["played"]]
    out: dict[str, dict[str, int]] = {}
    for season, grp in played.groupby("season"):
        end = str(grp["iso_date"].max())
        teams = set(grp["home_team"]) | set(grp["away_team"])
        ratings = {}
        for team in teams:
            r = rating_as_of(history.get(team) or [], end)
            if r is not None:
                ratings[team] = r
        out[str(season)] = rank_map(ratings)
    return out


def current_asi_ranks(
    matches: pd.DataFrame, rankings: list[dict], now: datetime
) -> dict[str, int]:
    """Rank among clubs active in the rolling window, by current Elo."""
    cutoff = (pd.Timestamp(now.date()) - pd.DateOffset(months=ACTIVITY_WINDOW_MONTHS)).strftime("%Y-%m-%d")
    recent = matches[matches["iso_date"] >= cutoff]
    active = set(recent["home_team"]) | set(recent["away_team"])
    ratings = {r["team"]: float(r["elo"]) for r in rankings if r["team"] in active}
    return rank_map(ratings)


# ---------------------------------------------------------------------------
# Playoffs
# ---------------------------------------------------------------------------

def _round_label(match: dict) -> str | None:
    """'final' / 'semi' / 'quarter' from the match URL or venue stage suffix.

    Recent seasons tag rounds (e.g. dmv-north-s1-06-20-2026); older ones don't.
    """
    slug = str(match.get("match_url") or "").rstrip("/").split("/")[-1].lower()
    stage = str(match.get("venue") or "").lower()
    stage = stage.rsplit("|", 1)[-1] if "|" in stage else ""
    if re.search(r"(?:^|-)s\d(?:-|$)|semi", slug) or "semi" in stage:
        return "semi"
    if re.search(r"(?:^|-)q\d(?:-|$)|quarter", slug) or "quarter" in stage:
        return "quarter"
    if re.search(r"(?:^|-)final(?:-|$)", slug) or re.search(r"\bfinal\b", stage):
        return "final"
    return None


def playoff_finishes(
    matches: pd.DataFrame, ongoing: str | None
) -> dict[tuple[str, str], str | None]:
    """(team, season) → conference playoff finish label (None while still alive)."""
    conf_po = matches[matches["is_playoff"] & (matches["scope"] == "conference")]
    national = matches[matches["is_playoff"] & (matches["scope"] == "national")]
    national_teams = {
        str(s): set(g["home_team"]) | set(g["away_team"])
        for s, g in national.groupby("season")
    }
    out: dict[tuple[str, str], str | None] = {}
    for season, grp in conf_po.groupby("season"):
        season = str(season)
        records = grp.to_dict(orient="records")  # already in date order
        by_team: dict[str, list[int]] = {}
        for i, r in enumerate(records):
            by_team.setdefault(r["home_team"], []).append(i)
            by_team.setdefault(r["away_team"], []).append(i)

        for team, idxs in by_team.items():
            if any(not records[i]["played"] for i in idxs):
                out[(team, season)] = None  # next round still to play
                continue
            last = records[idxs[-1]]
            is_home = last["home_team"] == team
            opponent = last["away_team"] if is_home else last["home_team"]
            gf = int(last["home_goals"] if is_home else last["away_goals"])
            ga = int(last["away_goals"] if is_home else last["home_goals"])
            later = sum(1 for i in by_team.get(opponent, []) if i > idxs[-1])
            label = _round_label(last)

            if label in ("semi", "quarter"):
                # A labelled early round as the last match: a loss/draw is the
                # exit; a win with nothing after it means later rounds are
                # missing (or unscheduled), so the finish is unknown.
                out[(team, season)] = (
                    None if gf > ga else ("Semi Finalist" if label == "semi" else "Quarter Finalist")
                )
            elif label == "final" or later == 0:
                if label is None and season == ongoing:
                    out[(team, season)] = None  # next round not scheduled yet
                    continue
                if gf > ga:
                    out[(team, season)] = "Champion"
                elif gf < ga:
                    out[(team, season)] = "Finalist"
                else:
                    # Drawn final (decided on penalties): the national
                    # qualifier is the champion when only one side advanced.
                    nat = national_teams.get(season, set())
                    won = team in nat and opponent not in nat
                    out[(team, season)] = "Champion" if won else "Finalist"
            elif later == 1:
                out[(team, season)] = "Semi Finalist"
            elif later == 2:
                out[(team, season)] = "Quarter Finalist"
            else:
                out[(team, season)] = "Playoffs"
    return out


def playoff_spots(
    matches: pd.DataFrame,
    standing_rows: dict[tuple[str, str], dict],
    ongoing: str | None,
) -> dict[tuple[str, str], int | None]:
    """(conference, season) → number of playoff places."""
    conf_po = matches[matches["is_playoff"] & (matches["scope"] == "conference")]
    counts: dict[tuple[str, str], int] = {}
    for season, grp in conf_po.groupby("season"):
        season = str(season)
        teams = set(grp["home_team"]) | set(grp["away_team"])
        per_conf = Counter(
            standing_rows[(t, season)]["conference"]
            for t in teams
            if (t, season) in standing_rows
        )
        for conf, n in per_conf.items():
            counts[(conf, season)] = n

    seasons = sorted({s for _, s in standing_rows}, key=_season_key)
    conferences = {row["conference"] for row in standing_rows.values()}
    out: dict[tuple[str, str], int | None] = {}
    for conf in conferences:
        for i, season in enumerate(seasons):
            if season == ongoing:
                earlier = [counts[(conf, s)] for s in seasons[:i] if (conf, s) in counts]
                out[(conf, season)] = earlier[-1] if earlier else counts.get((conf, season))
            else:
                out[(conf, season)] = counts.get((conf, season))
    return out


# ---------------------------------------------------------------------------
# Stadium
# ---------------------------------------------------------------------------

def home_stadiums(matches: pd.DataFrame) -> dict[str, dict]:
    """Most-used non-playoff home venue in each team's latest season at home."""
    home = matches[~matches["is_playoff"]].copy()
    home["venue_clean"] = home["venue"].map(clean_venue)
    home = home[home["venue_clean"] != ""]
    out: dict[str, dict] = {}
    for team, grp in home.groupby("home_team"):
        latest = max(grp["season"].unique(), key=_season_key)
        rows = grp[grp["season"] == latest]
        venue = rows["venue_clean"].value_counts().index[0]
        at_venue = rows[rows["venue_clean"] == venue]
        city = _mode(at_venue.get("city"))
        state = _mode(at_venue.get("state"))
        query = ", ".join(p for p in (venue, city, state, COUNTRY) if p)
        out[str(team)] = {
            "name": venue,
            "city": city,
            "state": state,
            "country": COUNTRY,
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
        }
    return out


def _mode(series: pd.Series | None) -> str | None:
    if series is None:
        return None
    values = series.dropna().astype(str).str.strip()
    values = values[values != ""]
    return str(values.value_counts().index[0]) if len(values) else None


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

def build_payload(
    matches: pd.DataFrame,
    standings: pd.DataFrame,
    elo: dict,
    *,
    division: str,
    now: datetime,
) -> dict:
    standing_rows = pick_standing_rows(standings)
    ongoing = ongoing_season(matches)
    rankings = elo.get("rankings") or []
    history = elo.get("history") or {}
    elo_by_team = {r["team"]: float(r["elo"]) for r in rankings}

    season_ranks = season_asi_ranks(matches, history)
    current_ranks = current_asi_ranks(matches, rankings, now)
    finishes = playoff_finishes(matches, ongoing)
    spots = playoff_spots(matches, standing_rows, ongoing)
    stadiums = home_stadiums(matches)

    all_seasons = sorted({s for _, s in standing_rows}, key=_season_key)
    latest_season = all_seasons[-1] if all_seasons else None

    seasons_by_team: dict[str, list[str]] = {}
    for team, season in standing_rows:
        seasons_by_team.setdefault(team, []).append(season)

    teams: dict[str, dict] = {}
    for team, seasons in seasons_by_team.items():
        seasons = sorted(seasons, key=_season_key, reverse=True)
        rows = []
        for season in seasons:
            st = standing_rows[(team, season)]
            is_ongoing = season == ongoing
            rows.append(
                {
                    "season": season,
                    "conference": st["conference"],
                    "ongoing": is_ongoing,
                    "asi_rank": (
                        current_ranks.get(team) if is_ongoing else season_ranks.get(season, {}).get(team)
                    ),
                    "gp": st["gp"],
                    "gf": st["gf"],
                    "ga": st["ga"],
                    "wins": st["wins"],
                    "draws": st["draws"],
                    "losses": st["losses"],
                    "pts": st["pts"],
                    "place": st["place"],
                    "playoff_finish": finishes.get((team, season)),
                    "playoff_spots": spots.get((st["conference"], season)),
                }
            )
        elo_now = elo_by_team.get(team)
        teams[team] = {
            "team": team,
            "abbr": team_abbreviation(team),
            "conference": rows[0]["conference"],
            "latest_season": rows[0]["season"],
            "elo": round(elo_now, 2) if elo_now is not None else None,
            "asi_rank": current_ranks.get(team),
            "stadium": stadiums.get(team),
            "seasons": rows,
        }

    # Opponents that never appear in standings still need a code for the
    # previous-matches strip.
    abbreviations = {
        t: team_abbreviation(t)
        for t in sorted(set(matches["home_team"]) | set(matches["away_team"]))
    }

    conferences: dict[str, list[str]] = {}
    if latest_season:
        for (team, season), st in standing_rows.items():
            if season == latest_season and st["conference"]:
                conferences.setdefault(st["conference"], []).append(team)
    for conf, members in conferences.items():
        members.sort(key=lambda t: (-(elo_by_team.get(t) or float("-inf")), t))

    ranked = [t for t in current_ranks if t in teams]
    top_team = min(ranked, key=lambda t: current_ranks[t]) if ranked else None

    return {
        "league": "UPSL",
        "division": division,
        "generated_at": now.isoformat(timespec="seconds"),
        "latest_season": latest_season,
        "ongoing_season": ongoing,
        "activity_window_months": ACTIVITY_WINDOW_MONTHS,
        "top_team": top_team,
        "conferences": dict(sorted(conferences.items())),
        "abbreviations": abbreviations,
        "team_count": len(teams),
        "teams": dict(sorted(teams.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export UPSL team profiles for the Teams tab")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument("--elo", type=Path, default=RANKINGS_OUT)
    parser.add_argument("--out", type=Path, default=TEAMS_OUT)
    args = parser.parse_args(argv)

    matches = prepare_matches(load_matches(args.division, "all"))
    standings = load_standings(args.division, "all")
    elo = json.loads(args.elo.read_text(encoding="utf-8"))
    payload = build_payload(
        matches, standings, elo, division=args.division, now=datetime.now(timezone.utc)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    print(
        f"Wrote {args.out} ({payload['team_count']} teams, "
        f"{args.out.stat().st_size / 1024:.0f} KB); ongoing season: {payload['ongoing_season']}; "
        f"top ASI team: {payload['top_team']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
