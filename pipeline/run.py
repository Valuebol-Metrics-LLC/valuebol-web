"""Run the whole UPSL pipeline in the order the dashboard repo uses.

The scraping and modelling code in pipeline/upsl/ is copied unchanged from
egudino20/amateur-football-dashboard. This file only decides which seasons to
refresh and runs the steps in his documented order:

    fetch -> fetch_rosters -> fetch_scorers -> export_frontend -> dixon_coles
          -> simulate_standings -> elo -> export_teams -> export_squads -> export_player_stats

Modes
    python pipeline/run.py full     every season since 2017 (first run: a few hours,
                                    mostly match pages for goal scorers)
    python pipeline/run.py update   re-download only the newest seasons, keep the rest
                                    from the cache, then rebuild every model and export

Options
    --seasons N       how many of the newest seasons "update" refreshes (default 2)
    --skip-scorers    skip match-page scraping (the slowest step)
    --division NAME   UPSL subdomain, default premier (the one the models are built for)

All website-facing output lands in public/upsl/*.json.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from upsl.fetch import DATA_DIR, list_seasons  # noqa: E402


def step(name: str, *args: str, allow_fail: bool = False, timeout: float | None = None) -> int:
    print(f"\n=== {name}: {' '.join(args)} ===", flush=True)
    t = time.time()
    try:
        code = subprocess.call([sys.executable, "-m", *args], cwd=HERE, timeout=timeout)
    except subprocess.TimeoutExpired:
        # fetch_scorers saves a checkpoint every 100 matches, so the next run resumes here.
        print(f"=== {name} stopped after {timeout / 60:.0f} min; the next run continues where it left off ===", flush=True)
        return 0
    print(f"=== {name} finished in {time.time() - t:.0f}s, exit {code} ===", flush=True)
    # fetch exits 2 when its rebuilt table disagrees with official standings for a few
    # clubs (point deductions, voided games). That is a warning, not a failure.
    if code not in (0, 2) and not allow_fail:
        sys.exit(f"{name} failed with exit code {code}")
    return code


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["full", "update"])
    p.add_argument("--seasons", type=int, default=2)
    p.add_argument("--skip-scorers", action="store_true")
    p.add_argument("--scorer-minutes", type=float, default=150,
                   help="time budget for goal-scorer scraping per run (default 150); it resumes next run")
    p.add_argument("--division", default="premier")
    a = p.parse_args()
    div = ["--division", a.division]
    cache = DATA_DIR / "raw_html"

    if a.mode == "full":
        step("Schedules + standings, every season", "upsl.fetch", *div, "--all-seasons")
    else:
        # Always re-read the season list so a new season is picked up.
        for f in cache.glob(f"{a.division}_schedule_index*.html"):
            f.unlink()
        seasons = list_seasons(a.division, cache_dir=cache)[: a.seasons]
        for s in seasons:
            step(f"Schedule + standings {s.season}", "upsl.fetch", *div, "--season", s.season, "--refresh-cache", allow_fail=True)

    step("Rosters (clubs active in the last months)", "upsl.fetch_rosters", *div, allow_fail=True)

    if not a.skip_scorers:
        # Newest seasons first so current numbers are right, then chip away at history.
        budget = a.scorer_minutes * 60
        if a.mode == "update":
            for s in seasons:
                step(f"Goal scorers {s.season}", "upsl.fetch_scorers", *div, "--season", s.season, allow_fail=True)
        step("Goal scorers, every season (resumable)", "upsl.fetch_scorers", *div, "--all-seasons",
             allow_fail=True, timeout=budget)

    step("Matches + standings JSON", "upsl.export_frontend", *div)
    step("Dixon-Coles predictions", "upsl.dixon_coles", *div)
    step("Projected standings (Monte Carlo)", "upsl.simulate_standings", *div)
    step("ASI (Elo) rankings", "upsl.elo", *div)
    step("Team profiles", "upsl.export_teams", *div)
    step("Squads", "upsl.export_squads", *div, allow_fail=True)
    step("Player stats", "upsl.export_player_stats", *div, allow_fail=True)
    print("\nDone. Website data is in public/upsl/.")


if __name__ == "__main__":
    main()
