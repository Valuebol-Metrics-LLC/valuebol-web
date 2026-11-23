"""UPSL Phase 1 Elo rating engine.

Methodology aligned with:
https://medium.com/@danielguerrerosantaren/how-to-calculate-elo-score-for-international-teams-using-python-66c136f01048

Phase 1 rules:
  - Baseline 1500 (2017 inaugural teams)
  - Expansion teams (first match after 2017): conference average of active peers
  - E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))
  - K = 25 regular, K = 40 playoff
  - S = 1 / 0.5 / 0 (no MoV, no HFA, no offseason reversion)
  - R' = R + K * (S - E)

Usage (from pipeline/ with venv active):
    python -m upsl.elo
    python -m upsl.elo --division premier --from-year 2017
    python -m upsl.elo --prev-from-git   # seed rank_delta vs last commit
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from upsl.export_frontend import (
    MATCH_TEAM_COLUMNS,
    _as_bool,
    _match_id,
    _to_iso_date,
    dedupe_matches,
)
from upsl.fetch import DATA_DIR, DEFAULT_DIVISION, slugify
from upsl.team_aliases import canonicalize_teams

REPO_ROOT = Path(__file__).resolve().parents[2]
RANKINGS_OUT = REPO_ROOT / "public" / "upsl" / "elo-rankings.json"
RANKINGS_GIT_PATH = "public/upsl/elo-rankings.json"

BASELINE = 1500.0
K_REGULAR = 25.0
K_PLAYOFF = 40.0
DEFAULT_FROM_YEAR = 2017
INAUGURAL_END = pd.Timestamp("2017-12-31")


def expected_score(rating_a: float, rating_b: float) -> float:
    """P(A beats B) under classic Elo logistic."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def actual_score(goals_for: int, goals_against: int) -> float:
    if goals_for > goals_against:
        return 1.0
    if goals_for < goals_against:
        return 0.0
    return 0.5


def load_all_matches(division: str) -> pd.DataFrame:
    root = DATA_DIR / division
    frames = []
    for path in sorted(root.glob("season=*/matches.parquet")):
        frames.append(pd.read_parquet(path))
    if not frames:
        for path in sorted(root.glob("season=*/matches.csv")):
            frames.append(pd.read_csv(path))
    if not frames:
        raise FileNotFoundError(f"No matches under {root}/season=*/")
    df = canonicalize_teams(pd.concat(frames, ignore_index=True), MATCH_TEAM_COLUMNS)
    return dedupe_matches(df)


def _played_mask(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.astype(str).str.lower().isin(["true", "1", "yes", "t", "y"])
    return series.astype(bool)


def prepare_matches(matches: pd.DataFrame, *, from_year: int) -> pd.DataFrame:
    """Played matches from from_year onward, sorted chronologically."""
    m = matches.copy()
    played = _played_mask(m["played"])
    m = m[played].copy()
    m = m.dropna(subset=["home_goals", "away_goals", "home_team", "away_team"])
    m["home_team"] = m["home_team"].astype(str).str.strip()
    m["away_team"] = m["away_team"].astype(str).str.strip()
    m["home_goals"] = m["home_goals"].astype(int)
    m["away_goals"] = m["away_goals"].astype(int)
    m["conference"] = m.get("conference", pd.Series("", index=m.index)).fillna("").astype(str)
    m["away_conference"] = (
        m["away_conference"].fillna(m["conference"]).astype(str)
        if "away_conference" in m.columns
        else m["conference"]
    )
    m["conference_id"] = (
        m["conference_id"].fillna("").astype(str) if "conference_id" in m.columns else ""
    )
    m["away_conference_id"] = (
        m["away_conference_id"].fillna(m["conference_id"]).astype(str)
        if "away_conference_id" in m.columns
        else m["conference_id"]
    )
    if "is_playoff" in m.columns:
        m["is_playoff"] = m["is_playoff"].map(_as_bool)
    else:
        m["is_playoff"] = False

    iso = []
    for raw in m.to_dict(orient="records"):
        iso.append(
            _to_iso_date(
                raw.get("date"),
                date_sort=raw.get("date_sort"),
                season=str(raw.get("season") or ""),
            )
        )
    m["iso_date"] = iso
    m = m[m["iso_date"].notna()].copy()
    m["match_ts"] = pd.to_datetime(m["iso_date"], errors="coerce")
    if "kickoff_ts" in m.columns:
        kt = pd.to_numeric(m["kickoff_ts"], errors="coerce")
        use_kt = kt.notna() & (kt > 0)
        m.loc[use_kt, "match_ts"] = pd.to_datetime(kt[use_kt], unit="s", errors="coerce")
    m = m[m["match_ts"].notna()].copy()
    cutoff = pd.Timestamp(f"{from_year}-01-01")
    m = m[m["match_ts"] >= cutoff].copy()
    m = m.sort_values(
        ["match_ts", "iso_date", "home_team", "away_team"], kind="mergesort"
    ).reset_index(drop=True)
    return m


def conference_average(
    ratings: dict[str, float],
    team_conference_id: dict[str, str],
    conference_id: str,
) -> float | None:
    """Mean Elo of teams currently tagged to this conference_id."""
    if not conference_id:
        return None
    vals = [
        ratings[t]
        for t, cid in team_conference_id.items()
        if cid == conference_id and t in ratings
    ]
    if not vals:
        return None
    return float(np.mean(vals))


def initial_rating(
    *,
    match_ts: pd.Timestamp,
    conference_id: str,
    ratings: dict[str, float],
    team_conference_id: dict[str, str],
) -> tuple[float, str]:
    """Return (rating, init_reason)."""
    if match_ts <= INAUGURAL_END or not ratings:
        return BASELINE, "baseline_inaugural"
    avg = conference_average(ratings, team_conference_id, conference_id)
    if avg is None:
        return BASELINE, "baseline_fallback"
    return avg, "conference_average"


def compute_elo(matches: pd.DataFrame) -> tuple[list[dict], dict[str, dict]]:
    """Process matches in order. Returns (history_rows, team_state)."""
    ratings: dict[str, float] = {}
    team_conference: dict[str, str] = {}
    team_conference_id: dict[str, str] = {}
    team_league: dict[str, str] = {}
    matches_tracked: dict[str, int] = {}
    highest: dict[str, float] = {}
    recent_changes: dict[str, list[float]] = {}
    history: list[dict] = []

    for raw in matches.to_dict(orient="records"):
        home = str(raw["home_team"])
        away = str(raw["away_team"])
        if not home or not away or home == away:
            continue
        match_ts = pd.Timestamp(raw["match_ts"])
        iso = str(raw["iso_date"])
        mid = _match_id({**raw, "date": iso})
        league = "UPSL"
        home_conf = str(raw.get("conference") or "")
        away_conf = str(raw.get("away_conference") or home_conf)
        home_cid = str(raw.get("conference_id") or "")
        away_cid = str(raw.get("away_conference_id") or home_cid)
        k = K_PLAYOFF if bool(raw.get("is_playoff")) else K_REGULAR
        hg = int(raw["home_goals"])
        ag = int(raw["away_goals"])

        for team, conf, cid in (
            (home, home_conf, home_cid),
            (away, away_conf, away_cid),
        ):
            if team not in ratings:
                elo0, reason = initial_rating(
                    match_ts=match_ts,
                    conference_id=cid,
                    ratings=ratings,
                    team_conference_id=team_conference_id,
                )
                ratings[team] = elo0
                highest[team] = elo0
                matches_tracked[team] = 0
                recent_changes[team] = []
                # Seed history so chart has a start point before first result.
                history.append(
                    {
                        "match_id": f"init:{slugify(team)}",
                        "team": team,
                        "team_id": slugify(team),
                        "league": league,
                        "conference": conf,
                        "conference_id": cid,
                        "date": iso,
                        "elo_before": elo0,
                        "elo_after": elo0,
                        "elo_change": 0.0,
                        "init": reason,
                    }
                )
            team_conference[team] = conf
            team_conference_id[team] = cid
            team_league[team] = league

        rh = float(ratings[home])
        ra = float(ratings[away])
        eh = expected_score(rh, ra)
        ea = expected_score(ra, rh)
        sh = actual_score(hg, ag)
        sa = actual_score(ag, hg)
        dh = k * (sh - eh)
        da = k * (sa - ea)
        rh2 = rh + dh
        ra2 = ra + da
        ratings[home] = rh2
        ratings[away] = ra2
        highest[home] = max(highest.get(home, rh2), rh2)
        highest[away] = max(highest.get(away, ra2), ra2)
        matches_tracked[home] = matches_tracked.get(home, 0) + 1
        matches_tracked[away] = matches_tracked.get(away, 0) + 1
        recent_changes.setdefault(home, []).append(dh)
        recent_changes.setdefault(away, []).append(da)

        for team, conf, cid, before, after, change in (
            (home, home_conf, home_cid, rh, rh2, dh),
            (away, away_conf, away_cid, ra, ra2, da),
        ):
            history.append(
                {
                    "match_id": mid,
                    "team": team,
                    "team_id": slugify(team),
                    "league": league,
                    "conference": conf,
                    "conference_id": cid,
                    "date": iso,
                    "elo_before": round(before, 4),
                    "elo_after": round(after, 4),
                    "elo_change": round(change, 4),
                }
            )

    state = {
        "ratings": ratings,
        "conference": team_conference,
        "conference_id": team_conference_id,
        "league": team_league,
        "matches_tracked": matches_tracked,
        "highest": highest,
        "recent_changes": recent_changes,
    }
    return history, state


def build_rankings(state: dict) -> list[dict]:
    ratings = state["ratings"]
    rows = []
    for team, elo in ratings.items():
        changes = state["recent_changes"].get(team) or []
        recent = float(sum(changes[-5:])) if changes else 0.0
        rows.append(
            {
                "team": team,
                "team_id": slugify(team),
                "league": state["league"].get(team, "UPSL"),
                "conference": state["conference"].get(team, ""),
                "conference_id": state["conference_id"].get(team, ""),
                "elo": round(float(elo), 2),
                "matches_tracked": int(state["matches_tracked"].get(team, 0)),
                "highest_elo": round(float(state["highest"].get(team, elo)), 2),
                "recent_delta": round(recent, 2),
            }
        )
    rows.sort(key=lambda r: (-r["elo"], r["team"]))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def ranks_from_payload(payload: dict) -> dict[str, int]:
    """Map team name → national ASI rank from a prior export."""
    out: dict[str, int] = {}
    for row in payload.get("rankings") or []:
        team = row.get("team")
        rank = row.get("rank")
        if not team or rank is None:
            continue
        try:
            out[str(team)] = int(rank)
        except (TypeError, ValueError):
            continue
    return out


def load_previous_ranks(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    try:
        return ranks_from_payload(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def load_previous_ranks_from_git(
    *,
    repo_root: Path = REPO_ROOT,
    rel_path: str = RANKINGS_GIT_PATH,
    git_ref: str = "HEAD",
) -> dict[str, int]:
    """Load team→rank from a committed rankings JSON (default: HEAD)."""
    try:
        proc = subprocess.run(
            ["git", "show", f"{git_ref}:{rel_path}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return {}
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return {}
    try:
        return ranks_from_payload(json.loads(proc.stdout))
    except (json.JSONDecodeError, TypeError):
        return {}


def attach_rank_deltas(rankings: list[dict], prev_ranks: dict[str, int]) -> None:
    """Mutate rankings with rank_delta = prev_rank - new_rank (positive = moved up)."""
    for row in rankings:
        prev = prev_ranks.get(row["team"])
        if prev is None:
            row["rank_delta"] = None
        else:
            row["rank_delta"] = int(prev) - int(row["rank"])


def history_by_team(history: list[dict]) -> dict[str, list[dict]]:
    """Compact per-team series for the chart (date + elo_after)."""
    by_team: dict[str, list[dict]] = {}
    for row in history:
        team = row["team"]
        # Skip pure init duplicates when a real match follows same day — keep init.
        by_team.setdefault(team, []).append(
            {
                "d": row["date"],
                "e": round(float(row["elo_after"]), 2),
                "m": row["match_id"],
            }
        )
    return by_team


def export_payload(
    rankings: list[dict],
    history: list[dict],
    *,
    division: str,
    from_year: int,
    match_count: int,
    out_path: Path = RANKINGS_OUT,
) -> Path:
    payload = {
        "model": "elo_phase1",
        "source": (
            "https://medium.com/@danielguerrerosantaren/"
            "how-to-calculate-elo-score-for-international-teams-using-python-66c136f01048"
        ),
        "league": "UPSL",
        "division": division,
        "baseline": BASELINE,
        "k_regular": K_REGULAR,
        "k_playoff": K_PLAYOFF,
        "from_year": from_year,
        "home_advantage": False,
        "margin_of_victory": False,
        "offseason_reversion": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "match_count": match_count,
        "team_count": len(rankings),
        "history_rows": len(history),
        "rankings": rankings,
        "history": history_by_team(history),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return out_path


def save_artifacts(
    history: list[dict],
    rankings: list[dict],
    *,
    division: str,
) -> Path:
    art = DATA_DIR / division / "models" / "elo"
    art.mkdir(parents=True, exist_ok=True)
    hist_df = pd.DataFrame(history)
    rank_df = pd.DataFrame(rankings)
    hist_path = art / "history.parquet"
    rank_path = art / "current.parquet"
    hist_df.to_parquet(hist_path, index=False)
    rank_df.to_parquet(rank_path, index=False)
    meta = {
        "baseline": BASELINE,
        "k_regular": K_REGULAR,
        "k_playoff": K_PLAYOFF,
        "history_rows": len(history),
        "teams": len(rankings),
    }
    (art / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return art


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute UPSL Phase 1 Elo ratings")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument("--from-year", type=int, default=DEFAULT_FROM_YEAR)
    parser.add_argument(
        "--out",
        type=Path,
        default=RANKINGS_OUT,
        help=f"Frontend JSON path (default: {RANKINGS_OUT})",
    )
    parser.add_argument(
        "--prev-from-git",
        action="store_true",
        help=(
            "Compare ranks to a git revision of the rankings JSON "
            "(use once after a working-tree overwrite to seed movement vs a commit)"
        ),
    )
    parser.add_argument(
        "--prev-git-ref",
        default="HEAD",
        help=(
            "Git ref for --prev-from-git (default: HEAD). "
            "Example: d6057af~1 for the publish before a bad rescrape commit."
        ),
    )
    args = parser.parse_args(argv)

    raw = load_all_matches(args.division)
    print(f"Loaded {len(raw)} match rows")
    matches = prepare_matches(raw, from_year=args.from_year)
    print(f"Elo queue ({args.from_year}+ played): {len(matches)} matches")
    if matches.empty:
        print("No matches to process.")
        return 1

    history, state = compute_elo(matches)
    rankings = build_rankings(state)

    if args.prev_from_git:
        try:
            rel = args.out.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            rel = RANKINGS_GIT_PATH
        prev_ranks = load_previous_ranks_from_git(
            rel_path=rel,
            git_ref=args.prev_git_ref,
        )
        prev_src = f"git {args.prev_git_ref}:{rel}"
    else:
        prev_ranks = load_previous_ranks(args.out)
        prev_src = str(args.out)
    attach_rank_deltas(rankings, prev_ranks)
    movers = sum(
        1
        for r in rankings
        if r.get("rank_delta") is not None and r["rank_delta"] != 0
    )
    print(f"Rank deltas vs {prev_src}: {len(prev_ranks)} prior teams, {movers} movers")

    art = save_artifacts(history, rankings, division=args.division)
    print(f"Wrote artifacts under {art}")
    out = export_payload(
        rankings,
        history,
        division=args.division,
        from_year=args.from_year,
        match_count=len(matches),
        out_path=args.out,
    )
    print(
        f"Wrote {out} ({len(rankings)} teams, {len(history)} history rows)"
    )
    if rankings:
        top = rankings[0]
        delta = top.get("rank_delta")
        delta_s = (
            f"  rank_delta={delta:+d}" if isinstance(delta, int) else ""
        )
        print(
            f"  #1 {top['team']}  Elo={top['elo']}  "
            f"({top['conference']}){delta_s}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
