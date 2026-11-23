"""Scrape goal scorers from UPSL match pages into per-season parquet.

Each played match with a `match_url` is fetched once. The match page lists
"Goals Scored" per side as "<player> <goals>" (no minutes). Each side has
two lists: list_index 0 holds match goals; list_index 1 holds penalty
shootout goals (player "-"), which are not match goals. Coverage is often
partial, so the report compares credited match goals with final scores.

Outputs under data/<division>/season=<slug>/:
  goals.parquet          one row per (match, side, scorer list entry)
  scorer_pages.parquet   one row per scraped match (incl. those with no scorers)

Incremental: matches already in scorer_pages.parquet are skipped unless
they were played within --recheck-days (scorers are often added late).
Match pages are not cached to disk (~17k pages).

Usage (from pipeline/ with venv active):
    python -m upsl.fetch_scorers --season "2026 Fall"
    python -m upsl.fetch_scorers --all-seasons
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from upsl.export_frontend import _as_bool, _season_dir, _to_iso_date, load_matches
from upsl.fetch import DEFAULT_DIVISION, _get
from upsl.simulate_standings import _season_key

DEFAULT_RECHECK_DAYS = 14
CHECKPOINT_EVERY = 100
# Stop instead of hammering the site when it starts refusing requests.
MAX_CONSECUTIVE_FAILURES = 5

GOALS_FILE = "goals.parquet"
PAGES_FILE = "scorer_pages.parquet"


def _clean_name(text: str) -> str:
    return " ".join(str(text or "").split())


def parse_scorers(html: str) -> dict[str, list[dict]]:
    """{'home': [...], 'away': [...]} scorer entries from a match page."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, list[dict]] = {"home": [], "away": []}
    for side in ("home", "away"):
        lists = soup.select(f"div.single-match__{side} ul.single-match__scorers")
        for list_index, ul in enumerate(lists):
            for li in ul.find_all("li"):
                spans = li.find_all("span")
                if not spans:
                    continue
                player = _clean_name(spans[0].get_text(" "))
                if not player:
                    continue
                count_text = spans[1].get_text(strip=True) if len(spans) > 1 else ""
                # A listed scorer without a number scored once.
                goals = int(count_text) if count_text.isdigit() else 1
                img = li.find("img")
                icon = Path(str(img.get("src") or "")).stem if img else ""
                out[side].append(
                    {"player": player, "goals": goals, "list_index": list_index, "icon": icon}
                )
    return out


def _played_matches(matches: pd.DataFrame) -> pd.DataFrame:
    m = matches.copy()
    m = m[m["played"].map(_as_bool)]
    m = m[m["match_url"].fillna("").astype(str).str.startswith("http")]
    m["iso_date"] = [
        _to_iso_date(r.get("date"), date_sort=r.get("date_sort"), season=str(r.get("season") or ""))
        for r in m.to_dict(orient="records")
    ]
    return m.drop_duplicates(subset=["match_url"], keep="last").reset_index(drop=True)


def _read_existing(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def _write(
    season_dir: Path,
    old_goals: pd.DataFrame,
    old_pages: pd.DataFrame,
    new_goals: list[dict],
    new_pages: list[dict],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replace rows for re-scraped matches and write both files."""
    refreshed = {p["match_url"] for p in new_pages}
    if len(old_goals):
        old_goals = old_goals[~old_goals["match_url"].isin(refreshed)]
    if len(old_pages):
        old_pages = old_pages[~old_pages["match_url"].isin(refreshed)]
    goals = pd.concat([old_goals, pd.DataFrame(new_goals)], ignore_index=True)
    pages = pd.concat([old_pages, pd.DataFrame(new_pages)], ignore_index=True)
    season_dir.mkdir(parents=True, exist_ok=True)
    goals.to_parquet(season_dir / GOALS_FILE, index=False)
    pages.to_parquet(season_dir / PAGES_FILE, index=False)
    return goals, pages


def scrape_season(
    division: str,
    season: str,
    matches: pd.DataFrame,
    *,
    recheck_days: int,
    limit: int | None,
    now: datetime,
) -> int:
    """Scrape one season's match pages. Returns 0, or 2 if aborted on errors."""
    season_dir = _season_dir(division, season)
    old_goals = _read_existing(season_dir / GOALS_FILE)
    old_pages = _read_existing(season_dir / PAGES_FILE)
    done = set(old_pages["match_url"]) if len(old_pages) else set()
    cutoff = (now - timedelta(days=recheck_days)).strftime("%Y-%m-%d")

    played = _played_matches(matches)
    todo = played[
        ~played["match_url"].isin(done) | (played["iso_date"].fillna("") >= cutoff)
    ]
    if limit is not None:
        todo = todo.head(limit)
    print(
        f"{season}: played={len(played)} already_scraped={len(done)} "
        f"to_fetch={len(todo)} (recheck since {cutoff})"
    )

    new_goals: list[dict] = []
    new_pages: list[dict] = []
    failures = 0
    exit_code = 0
    try:
        for i, row in enumerate(todo.to_dict(orient="records"), start=1):
            url = str(row["match_url"])
            try:
                html = _get(url)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status == 404:
                    print(f"  404 {url}")
                    failures = 0
                    continue
                failures += 1
                print(f"  ERROR {status} {url}")
            except requests.RequestException as exc:
                failures += 1
                print(f"  ERROR {exc.__class__.__name__} {url}")
            else:
                failures = 0
                scorers = parse_scorers(html)
                scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                for side in ("home", "away"):
                    team = row[f"{side}_team"]
                    for entry in scorers[side]:
                        new_goals.append(
                            {
                                "division": division,
                                "season": season,
                                "match_url": url,
                                "iso_date": row["iso_date"],
                                "side": side,
                                "team": team,
                                **entry,
                            }
                        )
                new_pages.append(
                    {
                        "division": division,
                        "season": season,
                        "match_url": url,
                        "iso_date": row["iso_date"],
                        "home_team": row["home_team"],
                        "away_team": row["away_team"],
                        "home_goals": int(row["home_goals"]),
                        "away_goals": int(row["away_goals"]),
                        "scraped_at": scraped_at,
                    }
                )

            if failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"  aborting {season}: {failures} consecutive failures")
                exit_code = 2
                break
            if i % CHECKPOINT_EVERY == 0:
                old_goals, old_pages = _write(season_dir, old_goals, old_pages, new_goals, new_pages)
                new_goals, new_pages = [], []
                print(f"  {i}/{len(todo)} checkpoint saved")
    finally:
        goals, pages = _write(season_dir, old_goals, old_pages, new_goals, new_pages)

    report(season, goals, pages)
    return exit_code


def report(season: str, goals: pd.DataFrame, pages: pd.DataFrame) -> None:
    if pages.empty:
        print(f"  {season}: no scraped matches")
        return
    pages = pages.copy()
    match_goals = goals[goals["list_index"] == 0] if len(goals) else goals
    for side in ("home", "away"):
        per_match = (
            match_goals[match_goals["side"] == side].groupby("match_url")["goals"].sum()
            if len(match_goals)
            else pd.Series(dtype="int64")
        )
        pages[f"{side}_credited"] = pages["match_url"].map(per_match).fillna(0).astype(int)
    final = int(pages["home_goals"].sum() + pages["away_goals"].sum())
    credited = int(pages["home_credited"].sum() + pages["away_credited"].sum())
    any_scorer = int(((pages["home_credited"] + pages["away_credited"]) > 0).sum())
    complete = int(
        (
            (pages["home_credited"] == pages["home_goals"])
            & (pages["away_credited"] == pages["away_goals"])
        ).sum()
    )
    over = int(
        (
            (pages["home_credited"] > pages["home_goals"])
            | (pages["away_credited"] > pages["away_goals"])
        ).sum()
    )
    pct = credited / final if final else 0.0
    print(
        f"  {season}: matches={len(pages)} with_scorers={any_scorer} "
        f"fully_credited={complete} over_credited={over} "
        f"goals credited {credited}/{final} ({pct:.1%})"
    )
    if len(goals):
        by_list = goals.groupby(["list_index", "icon"])["goals"].agg(["count", "sum"])
        print("  scorer entries by list/icon:")
        print("   " + by_list.to_string().replace("\n", "\n   "))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape UPSL goal scorers from match pages")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--season", help='e.g. "2026 Fall"')
    scope.add_argument("--all-seasons", action="store_true")
    parser.add_argument(
        "--recheck-days",
        type=int,
        default=DEFAULT_RECHECK_DAYS,
        help="Re-fetch already scraped matches played within this many days",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max pages per season")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    if args.all_seasons:
        all_matches = load_matches(args.division, "all")
        seasons = sorted(
            all_matches["season"].dropna().astype(str).unique(), key=_season_key, reverse=True
        )
        worst = 0
        for season in seasons:
            season_matches = all_matches[all_matches["season"].astype(str) == season]
            code = scrape_season(
                args.division, season, season_matches,
                recheck_days=args.recheck_days, limit=args.limit, now=now,
            )
            worst = max(worst, code)
            if code:
                break
        return worst

    matches = load_matches(args.division, args.season)
    return scrape_season(
        args.division, args.season, matches,
        recheck_days=args.recheck_days, limit=args.limit, now=now,
    )


if __name__ == "__main__":
    sys.exit(main())
