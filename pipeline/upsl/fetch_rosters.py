"""Scrape current UPSL team rosters into data/<division>/rosters/rosters.parquet.

Only teams with a match (played or scheduled) in the last
ACTIVITY_WINDOW_MONTHS are fetched, the same rule as the Rankings tab. The
team page URL comes from the team's slug in its latest match URL
(`/matches/<home-slug-id>-vs-<away-slug-id>-MM-DD-YYYY/`). That slug is
sometimes stale (e.g. la-wolves vs l-a-wolves); on a 404 the team link on
the match page itself is used instead.

A team page only shows its latest roster. Appearances are the site's
cumulative count, not per season. Staff and Top Scorers are ignored.

Re-running replaces the rows of every team fetched in that run and keeps
the rest, so a --conference run updates just that conference.

Usage (from pipeline/ with venv active):
    python -m upsl.fetch_rosters
    python -m upsl.fetch_rosters --conference "SoCal North"
    python -m upsl.fetch_rosters --missing-only
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from upsl.export_frontend import _to_iso_date, load_matches
from upsl.export_teams import ACTIVITY_WINDOW_MONTHS
from upsl.fetch import DATA_DIR, DEFAULT_DIVISION, DIVISION_BASES, _get

# Stop instead of hammering the site when it starts refusing requests.
MAX_CONSECUTIVE_FAILURES = 5

_MATCH_SLUG_RE = re.compile(r"/matches/(.+?-\d+)-vs-(.+?-\d+)-\d{1,2}-\d{1,2}-\d{4}/?$")


def rosters_path(division: str) -> Path:
    return DATA_DIR / division / "rosters" / "rosters.parquet"


def team_slugs(match_url: str) -> tuple[str, str] | None:
    """(home_slug, away_slug) from a match URL, or None for unusual URLs."""
    m = _MATCH_SLUG_RE.search(str(match_url or ""))
    return (m.group(1), m.group(2)) if m else None


def active_teams(matches: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """One row per active team: team, conference, team_url (None if unresolved)."""
    m = matches.copy()
    m["iso_date"] = [
        _to_iso_date(r.get("date"), date_sort=r.get("date_sort"), season=str(r.get("season") or ""))
        for r in m.to_dict(orient="records")
    ]
    m = m[m["iso_date"].notna()]
    cutoff = (pd.Timestamp(now.date()) - pd.DateOffset(months=ACTIVITY_WINDOW_MONTHS)).strftime("%Y-%m-%d")
    recent = m[m["iso_date"] >= cutoff]
    active = sorted(set(recent["home_team"]) | set(recent["away_team"]))

    rows = []
    for side in ("home", "away"):
        conf_col = "conference" if side == "home" else "away_conference"
        part = m[["iso_date", f"{side}_team", conf_col, "match_url"]].rename(
            columns={f"{side}_team": "team", conf_col: "conference"}
        )
        part["side"] = side
        rows.append(part)
    appearances = pd.concat(rows, ignore_index=True)
    appearances = appearances[appearances["team"].isin(active)]
    appearances = appearances.sort_values("iso_date", ascending=False, kind="mergesort")

    out = []
    for team, grp in appearances.groupby("team", sort=True):
        latest = grp.iloc[0]
        team_slug = match_url = side = None
        for r in grp.to_dict(orient="records"):
            slugs = team_slugs(r["match_url"])
            if slugs:
                team_slug = slugs[0] if r["side"] == "home" else slugs[1]
                match_url, side = r["match_url"], r["side"]
                break
        out.append(
            {
                "team": team,
                "conference": str(latest["conference"] or ""),
                "team_slug": team_slug,
                "match_url": match_url,
                "side": side,
            }
        )
    return pd.DataFrame(out)


def team_link_from_match(match_url: str, side: str) -> str | None:
    """Team page link on the match page; its slug can differ from the match URL's."""
    soup = BeautifulSoup(_get(match_url), "html.parser")
    link = soup.select_one(f".single-match__header .single-match__{side} a[href*='/teams/']")
    return str(link["href"]) if link else None


def fetch_team_page(base: str, team: dict) -> tuple[str, str]:
    """(url, html) for a team page, retrying via the match page link on a 404."""
    url = f"{base}/teams/{team['team_slug']}/"
    try:
        return url, _get(url)
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        fallback = team_link_from_match(team["match_url"], team["side"])
        if not fallback or fallback.rstrip("/") == url.rstrip("/"):
            raise
        return fallback, _get(fallback)


def parse_roster(html: str) -> list[dict] | None:
    """Players from the "Roster" section, or None when the page has none."""
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (
            h
            for h in soup.select("h3.single-team__heading")
            if h.get_text(" ", strip=True).lower().startswith("roster")
        ),
        None,
    )
    if heading is None:
        return None
    roster_list = heading.find_next_sibling("div", class_="single-team__roster-list")
    if roster_list is None:
        return None

    players = []
    for card in roster_list.select("div.single-team__roster-player"):
        name_el = card.select_one(".single-team__roster-player-name")
        if name_el is None:
            continue
        parts = [" ".join(p.split()) for p in name_el.get_text("\n").split("\n")]
        parts = [p for p in parts if p]
        if not parts:
            continue
        first, last = parts[0], " ".join(parts[1:])
        title_el = card.select_one(".single-team__roster-player-title")
        apps_raw = str(card.get("data-appearences") or "").strip()
        players.append(
            {
                "first_name": first,
                "last_name": last,
                "player": " ".join(f"{first} {last}".split()),
                "position": title_el.get_text(strip=True) if title_el else "",
                "appearances": int(apps_raw) if apps_raw.isdigit() else 0,
            }
        )
    return players


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape current UPSL team rosters")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument("--conference", default=None, help="Only teams in this conference")
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only teams with no players in the existing rosters file (retry 404s / empty rosters)",
    )
    args = parser.parse_args(argv)

    path = rosters_path(args.division)
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame()

    now = datetime.now(timezone.utc)
    teams = active_teams(load_matches(args.division, "all"), now)
    if args.conference:
        teams = teams[teams["conference"] == args.conference]
        if teams.empty:
            print(f"No active teams in conference {args.conference!r}")
            return 1
    if args.missing_only and len(old):
        teams = teams[~teams["team"].isin(set(old["team"]))]
    unresolved = teams[teams["team_slug"].isna()]
    teams = teams[teams["team_slug"].notna()]
    print(
        f"Active teams (last {ACTIVITY_WINDOW_MONTHS} months): "
        f"{len(teams) + len(unresolved)}; fetching {len(teams)}; "
        f"no team URL for {len(unresolved)}"
    )
    for name in unresolved["team"]:
        print(f"  no team URL: {name}")

    base = DIVISION_BASES[args.division]
    new_rows: list[dict] = []
    fetched: set[str] = set()
    no_roster: list[str] = []
    failures = 0
    exit_code = 0
    for i, t in enumerate(teams.to_dict(orient="records"), start=1):
        try:
            url, html = fetch_team_page(base, t)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            print(f"  ERROR {status} {t['team']} {exc.request.url if exc.request else ''}")
            failures = 0 if status == 404 else failures + 1
        except requests.RequestException as exc:
            failures += 1
            print(f"  ERROR {exc.__class__.__name__} {t['team']} ({t['team_slug']})")
        else:
            failures = 0
            fetched.add(t["team"])
            players = parse_roster(html)
            if not players:
                no_roster.append(t["team"])
            scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for p in players or []:
                new_rows.append(
                    {
                        "division": args.division,
                        "team": t["team"],
                        "conference": t["conference"],
                        "team_url": url,
                        **p,
                        "scraped_at": scraped_at,
                    }
                )
        if failures >= MAX_CONSECUTIVE_FAILURES:
            print(f"Aborting: {failures} consecutive failures")
            exit_code = 2
            break
        if i % 25 == 0:
            print(f"  {i}/{len(teams)}")

    if len(old):
        old = old[~old["team"].isin(fetched)]
    rosters = pd.concat([old, pd.DataFrame(new_rows)], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    rosters.to_parquet(path, index=False)

    print(
        f"Wrote {path}: {len(rosters)} players across {rosters['team'].nunique() if len(rosters) else 0} teams "
        f"(this run: {len(new_rows)} players, {len(fetched)} teams fetched, "
        f"{len(no_roster)} with empty roster)"
    )
    for name in no_roster:
        print(f"  empty roster: {name}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
