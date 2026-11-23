"""Monte Carlo projected league tables for UPSL conferences.

Simulates every remaining (unplayed, non-playoff) fixture of the target
season N times using Dixon-Coles scoreline probability matrices, adds the
sampled results on top of the actual scraped standings, and aggregates:

  - average projected final points per team
  - probability of finishing in each position of its conference table

Newcomer handling (simulation only — the match-preview publishing gate in
dixon_coles.py is unaffected): teams without fitted params are assigned
their conference's average attack/defence. Conferences without any fitted
model fall back to a synthetic league-average model, which makes every
fixture in them a coin-flip at typical scoring rates.

Thin-history handling: every team's strengths are shrunk toward its
conference's median strengths with weight n/(n+SHRINK_K) on n career
matches, using the same helpers as match previews
(see dixon_coles.shrink_towards_conference). Fixtures involving a team
below MIN_PLAYED_MATCHES are still simulated here; they are omitted from
published match probabilities.

Usage (from pipeline/ with venv active):
    python -m upsl.simulate_standings
    python -m upsl.simulate_standings --season "2026 Fall" --sims 10000
    python -m upsl.simulate_standings --refit   # refit instead of params.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from upsl.dixon_coles import (
    MAX_GOALS,
    MIN_PLAYED_MATCHES,
    SHRINK_K,
    _as_bool_series,
    bridge_frame,
    build_rate_centers,
    dixon_coles_simulate_match,
    fit_models,
    load_all_matches,
    select_params,
    shrink_towards_conference,
    shrink_weight,
    training_frame,
)
from upsl.export_frontend import load_standings
from upsl.fetch import DATA_DIR, DEFAULT_DIVISION

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTIONS_OUT = REPO_ROOT / "public" / "upsl" / "projected-standings.json"
DEFAULT_SIMS = 10_000
DEFAULT_SEED = 42

# A conference's projections are flagged low-confidence when more than this
# share of its remaining fixtures needed the newcomer prior, or more than
# this share of its teams have fewer than MIN_PLAYED_MATCHES career matches.
LOW_CONFIDENCE_SHARE = 1 / 3

# Tie-break weights for ranking within a simulated conference table:
# Pts, then GD, then GF. Ranges are bounded (pts < 1e3, |gd| < 5e3,
# gf < 1e3) so the composite integer never collides across levels.
_PTS_W = 10_000_000
_GD_W = 1_000
_GD_SHIFT = 5_000


# ---------------------------------------------------------------------------
# Season / model selection
# ---------------------------------------------------------------------------

def _season_key(season: str) -> tuple[int, float]:
    """Sortable (year, term) key: Spring < Spring-Fall < Fall."""
    import re

    m = re.search(r"(20\d{2})\s*(Spring-Fall|Spring|Fall)?", str(season or ""), re.I)
    if not m:
        return (0, 0.0)
    term = (m.group(2) or "").lower()
    rank = {"spring": 1.0, "spring-fall": 1.5, "fall": 2.0}.get(term, 0.0)
    return (int(m.group(1)), rank)


def remaining_fixtures(matches: pd.DataFrame, season: str) -> pd.DataFrame:
    """Unplayed, non-playoff fixtures of one season (playoffs don't award
    league points, so they are excluded from table projections)."""
    m = matches.copy()
    played = _as_bool_series(m["played"])
    playoff = _as_bool_series(m["is_playoff"])
    m = m[(m["season"].astype(str) == season) & ~played & ~playoff]
    return m.reset_index(drop=True)


def played_counts(matches: pd.DataFrame) -> dict[str, int]:
    """Career played-match count per team across every scraped season."""
    played = matches[_as_bool_series(matches["played"])]
    counts: dict[str, int] = {}
    for col in ("home_team", "away_team"):
        for team, n in played[col].dropna().value_counts().items():
            counts[str(team)] = counts.get(str(team), 0) + int(n)
    return counts


def pick_target_season(matches: pd.DataFrame) -> str | None:
    """Most recent season that still has unplayed non-playoff fixtures."""
    played = _as_bool_series(matches["played"])
    playoff = _as_bool_series(matches["is_playoff"])
    seasons = matches.loc[~played & ~playoff, "season"].dropna().astype(str).unique()
    if not len(seasons):
        return None
    return max(seasons, key=_season_key)


def load_or_fit_models(division: str, refit: bool = False) -> dict:
    """Reuse the saved dixon_coles fit when available (fast path)."""
    params_path = DATA_DIR / division / "models" / "dixon_coles" / "params.json"
    if not refit and params_path.exists():
        print(f"Loading fitted models from {params_path}")
        return json.loads(params_path.read_text(encoding="utf-8"))
    print("Fitting Dixon-Coles models (no saved params or --refit given)…")
    matches = load_all_matches(division)
    train = training_frame(matches)
    bridges = bridge_frame(matches)
    return fit_models(train, bridges)


# ---------------------------------------------------------------------------
# Newcomer prior
# ---------------------------------------------------------------------------

def conference_means(params: dict) -> tuple[float, float]:
    """Average attack / defence across a conference model's teams."""
    atk = [float(v) for k, v in params.items() if k.startswith("attack_")]
    dfn = [float(v) for k, v in params.items() if k.startswith("defence_")]
    return float(np.mean(atk)), float(np.mean(dfn))


def league_average_params(models: dict) -> dict:
    """Synthetic model for conferences with no fit of their own.

    Averages the per-conference mean strengths so both teams score at
    league-typical rates; rho/home_adv use medians for robustness against
    unstable fits (see ERRORS.md on sparse-conference artifacts).
    """
    atks, dfns, rhos, havs = [], [], [], []
    for params in (models.get("conferences") or {}).values():
        a, d = conference_means(params)
        atks.append(a)
        dfns.append(d)
        rhos.append(float(params["rho"]))
        havs.append(float(params["home_adv"]))
    if not atks:
        raise ValueError("No fitted conference models available")
    return {
        "attack": float(np.mean(atks)),
        "defence": float(np.mean(dfns)),
        "rho": float(np.median(rhos)),
        "home_adv": float(np.median(havs)),
    }


def fixture_params(models: dict, match: dict, league_avg: dict) -> tuple[dict, bool]:
    """Params for one fixture; second value is True when a prior was used.

    Order: normal dixon_coles selection (conference / bridge) → conference
    model with conference-mean strengths for unknown teams → synthetic
    league-average model when the conference has never been fitted.
    """
    params, _source = select_params(models, match)
    if params is not None:
        return params, False

    home = str(match["home_team"])
    away = str(match["away_team"])
    conferences = models.get("conferences") or {}
    home_conf = str(match.get("conference") or "")
    away_conf = str(match.get("away_conference") or home_conf)
    conf_params = conferences.get(home_conf) or conferences.get(away_conf)
    if conf_params:
        mean_atk, mean_dfn = conference_means(conf_params)
        out = dict(conf_params)
        for team in (home, away):
            out.setdefault(f"attack_{team}", mean_atk)
            out.setdefault(f"defence_{team}", mean_dfn)
        return out, True

    return league_average_fixture_params(home, away, league_avg), True


def league_average_fixture_params(home: str, away: str, league_avg: dict) -> dict:
    """Both teams at league-average strength."""
    return {
        f"attack_{home}": league_avg["attack"],
        f"defence_{home}": league_avg["defence"],
        f"attack_{away}": league_avg["attack"],
        f"defence_{away}": league_avg["defence"],
        "rho": league_avg["rho"],
        "home_adv": league_avg["home_adv"],
    }


# ---------------------------------------------------------------------------
# Baseline table + simulation
# ---------------------------------------------------------------------------

@dataclass
class SimFixture:
    home_idx: int
    away_idx: int
    matrix: np.ndarray  # (max_goals+1, max_goals+1) scoreline probabilities
    used_prior: bool
    conference: str  # home team's conference (for reporting)


def build_universe(
    standings: pd.DataFrame, fixtures: pd.DataFrame
) -> tuple[list[str], dict[str, int], dict[str, str], pd.DataFrame]:
    """Team list, index map, team→conference map, and baseline stats.

    Teams come from the season's scraped standings plus any fixture
    participants missing from them (all-zero baseline rows). The scraped
    conference is authoritative; fixtures fill the gaps.
    """
    team_conf: dict[str, str] = {}
    baseline_rows: dict[str, dict] = {}

    for _, row in standings.iterrows():
        team = str(row["team"])
        if team in baseline_rows:
            continue
        team_conf[team] = str(row.get("conference") or "")
        baseline_rows[team] = {
            col: int(pd.to_numeric(row.get(col), errors="coerce") or 0)
            for col in ["gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]
        }
        place = pd.to_numeric(row.get("place"), errors="coerce")
        baseline_rows[team]["place"] = int(place) if pd.notna(place) else None

    zero = {c: 0 for c in ["gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]}
    for _, row in fixtures.iterrows():
        home, away = str(row["home_team"]), str(row["away_team"])
        conf = str(row.get("conference") or "")
        away_conf = str(row.get("away_conference") or conf)
        team_conf.setdefault(home, conf)
        team_conf.setdefault(away, away_conf)
        baseline_rows.setdefault(home, {**zero, "place": None})
        baseline_rows.setdefault(away, {**zero, "place": None})

    teams = sorted(baseline_rows)
    index = {t: i for i, t in enumerate(teams)}
    baseline = pd.DataFrame([baseline_rows[t] for t in teams], index=teams)
    return teams, index, team_conf, baseline


def build_sim_fixtures(
    models: dict,
    fixtures: pd.DataFrame,
    index: dict[str, int],
    max_goals: int,
    history: dict[str, int],
    centers: dict[str, tuple[float, float]],
    k: float = SHRINK_K,
) -> list[SimFixture]:
    league_avg = league_average_params(models)
    out: list[SimFixture] = []
    for _, row in fixtures.iterrows():
        match = {
            "home_team": str(row["home_team"]),
            "away_team": str(row["away_team"]),
            "conference": str(row.get("conference") or ""),
            "away_conference": str(row.get("away_conference") or ""),
        }
        params, used_prior = fixture_params(models, match, league_avg)
        params = shrink_towards_conference(
            params, match["home_team"], match["away_team"], history, centers, k
        )
        matrix = dixon_coles_simulate_match(
            params, match["home_team"], match["away_team"], max_goals=max_goals
        )
        # A degenerate fit (overflowed λ) yields an all-zero matrix; simulate
        # the fixture at league-average strength instead of dropping it.
        if matrix.sum() <= 0:
            matrix = dixon_coles_simulate_match(
                league_average_fixture_params(
                    match["home_team"], match["away_team"], league_avg
                ),
                match["home_team"],
                match["away_team"],
                max_goals=max_goals,
            )
            used_prior = True
        out.append(
            SimFixture(
                home_idx=index[match["home_team"]],
                away_idx=index[match["away_team"]],
                matrix=matrix,
                used_prior=used_prior,
                conference=match["conference"],
            )
        )
    return out


def run_simulation(
    baseline: pd.DataFrame,
    sim_fixtures: list[SimFixture],
    n_sims: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized over simulations: sample every fixture n_sims times and
    accumulate points / goals onto the baseline. Returns (pts, gf, ga)
    arrays of shape (n_teams, n_sims)."""
    n_teams = len(baseline)
    pts = np.tile(baseline["pts"].to_numpy(dtype=np.int32)[:, None], (1, n_sims))
    gf = np.tile(baseline["gf"].to_numpy(dtype=np.int32)[:, None], (1, n_sims))
    ga = np.tile(baseline["ga"].to_numpy(dtype=np.int32)[:, None], (1, n_sims))

    for fx in sim_fixtures:
        weights = fx.matrix.ravel().astype(np.float64)
        total = weights.sum()
        if not np.isfinite(total) or total <= 0:
            continue
        weights = weights / total
        draws = rng.choice(weights.size, size=n_sims, p=weights)
        side = fx.matrix.shape[1]
        h = (draws // side).astype(np.int32)
        a = (draws % side).astype(np.int32)

        home_pts = np.where(h > a, 3, np.where(h == a, 1, 0)).astype(np.int32)
        away_pts = np.where(a > h, 3, np.where(h == a, 1, 0)).astype(np.int32)
        pts[fx.home_idx] += home_pts
        pts[fx.away_idx] += away_pts
        gf[fx.home_idx] += h
        ga[fx.home_idx] += a
        gf[fx.away_idx] += a
        ga[fx.away_idx] += h

    return pts, gf, ga


def finishing_positions(
    pts: np.ndarray, gf: np.ndarray, ga: np.ndarray, member_idx: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Per-conference position probabilities and mean projected points.

    Ranks by Pts > GD > GF in every simulation (further ties broken by
    stable order). Returns (probs[k, k], avg_pts[k]) for k member teams.
    """
    sub_pts = pts[member_idx].astype(np.int64)
    sub_gd = (gf[member_idx] - ga[member_idx]).astype(np.int64)
    sub_gf = gf[member_idx].astype(np.int64)
    score = sub_pts * _PTS_W + (sub_gd + _GD_SHIFT) * _GD_W + sub_gf

    k, n_sims = score.shape
    order = np.argsort(-score, axis=0, kind="stable")
    pos = np.empty_like(order)
    np.put_along_axis(pos, order, np.arange(k)[:, None], axis=0)

    probs = np.stack([np.bincount(pos[i], minlength=k) for i in range(k)])
    return probs / float(n_sims), sub_pts.mean(axis=1)


# ---------------------------------------------------------------------------
# Aggregation + export
# ---------------------------------------------------------------------------

def build_payload(
    *,
    division: str,
    season: str,
    teams: list[str],
    team_conf: dict[str, str],
    baseline: pd.DataFrame,
    history: dict[str, int],
    sim_fixtures: list[SimFixture],
    pts: np.ndarray,
    gf: np.ndarray,
    ga: np.ndarray,
    n_sims: int,
    seed: int,
    max_goals: int,
    k: float,
) -> dict:
    fixtures_by_conf: dict[str, int] = {}
    priors_by_conf: dict[str, int] = {}
    # Remaining fixtures per team index — projected GP is deterministic
    # (baseline GP + games left), so it needs no simulation.
    remaining_by_team: dict[int, int] = {}
    for fx in sim_fixtures:
        fixtures_by_conf[fx.conference] = fixtures_by_conf.get(fx.conference, 0) + 1
        if fx.used_prior:
            priors_by_conf[fx.conference] = priors_by_conf.get(fx.conference, 0) + 1
        for idx in (fx.home_idx, fx.away_idx):
            remaining_by_team[idx] = remaining_by_team.get(idx, 0) + 1

    conferences: dict[str, dict] = {}
    for conf in sorted(set(team_conf.values())):
        members = [t for t in teams if team_conf[t] == conf]
        if not members:
            continue
        member_idx = np.array([teams.index(t) for t in members])
        probs, avg_pts = finishing_positions(pts, gf, ga, member_idx)
        # gf/ga already carry the baseline, so their means are projected finals.
        avg_gf = gf[member_idx].mean(axis=1)
        avg_ga = ga[member_idx].mean(axis=1)

        rows = []
        for i, team in enumerate(members):
            base = baseline.loc[team]
            rows.append(
                {
                    "team": team,
                    "place": int(base["place"]) if pd.notna(base["place"]) else None,
                    "gp": int(base["gp"]),
                    "wins": int(base["wins"]),
                    "draws": int(base["draws"]),
                    "losses": int(base["losses"]),
                    "pts": int(base["pts"]),
                    "gf": int(base["gf"]),
                    "ga": int(base["ga"]),
                    "gd": int(base["gd"]),
                    "avg_proj_pts": round(float(avg_pts[i]), 2),
                    "proj_gp": int(base["gp"])
                    + remaining_by_team.get(int(member_idx[i]), 0),
                    "proj_gf": round(float(avg_gf[i]), 1),
                    "proj_ga": round(float(avg_ga[i]), 1),
                    "proj_gd": round(float(avg_gf[i] - avg_ga[i]), 1),
                    "career_matches": int(history.get(team, 0)),
                    "shrink_weight": round(shrink_weight(history.get(team, 0), k), 3),
                    "position_probs": [round(float(p), 4) for p in probs[i]],
                }
            )
        rows.sort(key=lambda r: (-r["avg_proj_pts"], r["team"]))

        n_fixtures = fixtures_by_conf.get(conf, 0)
        n_priors = priors_by_conf.get(conf, 0)
        limited = sum(
            1 for t in members if history.get(t, 0) < MIN_PLAYED_MATCHES
        )
        low_confidence = (
            n_fixtures > 0 and n_priors / n_fixtures > LOW_CONFIDENCE_SHARE
        ) or (limited / len(members) > LOW_CONFIDENCE_SHARE)
        conferences[conf] = {
            "remaining_fixtures": n_fixtures,
            "fixtures_with_prior": n_priors,
            "teams_with_limited_history": limited,
            "low_confidence": bool(low_confidence),
            "teams": rows,
        }

    return {
        "league": "UPSL",
        "division": division,
        "season": season,
        "model": "dixon_coles_monte_carlo",
        "n_sims": n_sims,
        "seed": seed,
        "max_goals": max_goals,
        "shrink_k": k,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "conference_count": len(conferences),
        "conferences": conferences,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument(
        "--season",
        default="auto",
        help='Target season (e.g. "2026 Fall"); "auto" picks the most recent '
        "season with unplayed fixtures",
    )
    parser.add_argument("--sims", type=int, default=DEFAULT_SIMS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-goals", type=int, default=MAX_GOALS)
    parser.add_argument(
        "--shrink-k",
        type=float,
        default=SHRINK_K,
        help="Career matches at which a team's own fitted strengths carry half "
        "the weight of its conference median; 0 disables shrinkage",
    )
    parser.add_argument(
        "--refit",
        action="store_true",
        help="Refit models instead of loading saved params.json",
    )
    parser.add_argument("--out", type=Path, default=PROJECTIONS_OUT)
    args = parser.parse_args(argv)

    matches = load_all_matches(args.division)
    season = args.season
    if not season or season.lower() == "auto":
        season = pick_target_season(matches)
        if not season:
            raise SystemExit("No unplayed non-playoff fixtures found in any season")
    print(f"Target season: {season}")

    fixtures = remaining_fixtures(matches, season)
    if fixtures.empty:
        raise SystemExit(f"No remaining fixtures for {season!r}")
    print(f"Remaining fixtures: {len(fixtures)}")

    try:
        standings = load_standings(args.division, season)
    except FileNotFoundError:
        standings = pd.DataFrame()
        print("No scraped standings for this season — baselines start at zero.")

    models = load_or_fit_models(args.division, refit=args.refit)
    teams, index, team_conf, baseline = build_universe(standings, fixtures)
    print(f"Teams in universe: {len(teams)} across {len(set(team_conf.values()))} conferences")

    history = played_counts(matches)
    centers = build_rate_centers(models, teams, team_conf)
    sim_fixtures = build_sim_fixtures(
        models, fixtures, index, args.max_goals, history, centers, args.shrink_k
    )
    n_prior = sum(fx.used_prior for fx in sim_fixtures)
    if n_prior:
        print(f"Fixtures using newcomer/conference-average prior: {n_prior}")
    n_shrunk = sum(
        1 for t in teams if shrink_weight(history.get(t, 0), args.shrink_k) < 0.5
    )
    print(
        f"Shrinkage k={args.shrink_k:g}: {n_shrunk} of {len(teams)} teams weighted "
        f"below half on their own fitted strengths"
    )

    rng = np.random.default_rng(args.seed)
    pts, gf, ga = run_simulation(baseline, sim_fixtures, args.sims, rng)

    payload = build_payload(
        division=args.division,
        season=season,
        teams=teams,
        team_conf=team_conf,
        baseline=baseline,
        history=history,
        sim_fixtures=sim_fixtures,
        pts=pts,
        gf=gf,
        ga=ga,
        n_sims=args.sims,
        seed=args.seed,
        max_goals=args.max_goals,
        k=args.shrink_k,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    for conf, block in payload["conferences"].items():
        top = block["teams"][0]
        print(
            f"  {conf}: {len(block['teams'])} teams, "
            f"{block['remaining_fixtures']} fixtures "
            f"(prior: {block['fixtures_with_prior']}) — "
            f"favourite: {top['team']} ({top['avg_proj_pts']:.1f} pts, "
            f"P(1st)={top['position_probs'][0]:.0%})"
            + (" [low confidence]" if block["low_confidence"] else "")
        )


if __name__ == "__main__":
    main()
