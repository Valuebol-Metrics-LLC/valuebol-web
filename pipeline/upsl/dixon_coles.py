"""Dixon–Coles model for UPSL (blog implementation + time decay).

Follows the approach in:
https://urazakgul.github.io/datafc-blog/posts/en/post3/better-predictions-for-football-matches-how-does-the-dixon-coles-model-work.html

Fits:
  - Stage A: one model per conference (intra-conference, non-playoff)
  - Stage B: conference offsets from tagged cross-conference bridges
    (interlocking league games + national playoffs), with region-group tags

Cross-conference predictions apply conference offsets; hybrid param stitching is gone.

Stage A weights each match's log-likelihood by 0.5 ** (age_days / HALF_LIFE_DAYS),
with age measured back from the latest played match, so a match one year old
counts half as much as the most recent one.

Published match probabilities shrink each team's attack/defence toward its
conference median at n/(n+SHRINK_K). Fixtures with a team below
MIN_PLAYED_MATCHES (league) or MIN_PLAYED_MATCHES_CROSS (cross-conference) are
omitted from predictions.json (preview stays blank). Extreme λ or win % after
prediction are omitted via publish quality gates.

Usage (from pipeline/ with venv active):
    python -m upsl.dixon_coles
    python -m upsl.dixon_coles --division premier
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, minimize
from scipy.stats import poisson

from upsl.export_frontend import (
    MATCH_TEAM_COLUMNS,
    _match_id,
    _to_iso_date,
    dedupe_matches,
)
from upsl.fetch import DATA_DIR, DEFAULT_DIVISION
from upsl.region_groups import region_group
from upsl.team_aliases import canonicalize_teams

REPO_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_OUT = REPO_ROOT / "public" / "upsl" / "predictions.json"
MAX_GOALS = 10
# Soft L2 on conference offsets (keeps sparse conferences near 0).
OFFSET_L2 = 2.0
# Fraction of the fitted conference offset applied to cross-conference λ.
# 0.0 treats conferences as equal strength; 1.0 trusts the bridge fit fully.
# Offsets are still fitted and stored either way (see conference_offsets).
OFFSET_WEIGHT = 0.0
# Cross-conference only: full bridge offset on λ (intra stays OFFSET_WEIGHT = 0).
OFFSET_WEIGHT_CROSS = 1.0
# League / same-conference previews (unchanged).
MIN_PLAYED_MATCHES = 3
# Cross-conference / bridge: either team below this → no published prediction.
MIN_PLAYED_MATCHES_CROSS = 13
# Publish gates (row omitted from predictions.json if any fail).
PUBLISH_LAMBDA_MIN = 0.25
PUBLISH_LAMBDA_MAX = 4.0
PUBLISH_P_EXTREME_LO = 0.02
PUBLISH_P_EXTREME_HI = 0.98
# Career matches at which a team's fitted strengths carry half the weight of
# its conference's median strengths (see shrink_towards_conference).
SHRINK_K = 6.0
# Stage A time decay: a match this many days older than the latest played
# match carries half the weight in the fit.
HALF_LIFE_DAYS = 365.0
# Floor on a shrunk rate before taking logs, guarding log(0) for a team whose
# fitted parameter ran to -inf and whose conference median is also degenerate.
_MIN_RATE = 1e-6
# Finals-weekend stages played at a centralized host (no home advantage).
_NEUTRAL_STAGE_RE = re.compile(
    r"semi[-\s]?final|third[-\s]?place|national\s+(?:final|championship)",
    re.I,
)


def rho_correction(x, y, lambda_x, mu_y, rho):
    if x == 0 and y == 0:
        return max(1 - lambda_x * mu_y * rho, 1e-10)
    if x == 0 and y == 1:
        return 1 + lambda_x * rho
    if x == 1 and y == 0:
        return 1 + mu_y * rho
    if x == 1 and y == 1:
        return max(1 - rho, 1e-10)
    return 1.0


def dc_log_like(x, y, alpha_x, beta_x, alpha_y, beta_y, rho, gamma):
    lambda_x = np.exp(alpha_x + beta_y + gamma)
    mu_y = np.exp(alpha_y + beta_x)
    log_lambda_x = np.log(max(poisson.pmf(x, lambda_x), 1e-10))
    log_mu_y = np.log(max(poisson.pmf(y, mu_y), 1e-10))
    return (
        np.log(max(rho_correction(x, y, lambda_x, mu_y, rho), 1e-10))
        + log_lambda_x
        + log_mu_y
    )


def solve_parameters(
    dataset,
    init_vals=None,
    options=None,
    weights=None,
    **kwargs,
):
    """Maximize Dixon–Coles log-likelihood (blog `solve_parameters`).

    `weights` (one per row, default 1.0) scales each match's log-likelihood,
    which is how time decay enters the fit.
    """
    if options is None:
        options = {"disp": False, "maxiter": 200}

    teams = np.sort(
        list(set(dataset["home_team"].unique()) | set(dataset["away_team"].unique()))
    )
    n_teams = len(teams)
    if n_teams < 2 or len(dataset) < 5:
        raise ValueError("Need at least 2 teams and 5 matches to fit Dixon–Coles")

    if init_vals is None:
        avg_attack = (
            dataset.groupby("home_team")["home_score"]
            .mean()
            .reindex(teams)
            .fillna(1.0)
            .values
        )
        avg_defence = (
            -dataset.groupby("away_team")["away_score"]
            .mean()
            .reindex(teams)
            .fillna(1.0)
            .values
        )
        init_vals = np.concatenate([avg_attack, avg_defence, np.array([0.0, 1.0])])

    # Pre-index teams for a vectorized objective (same formulas as blog itertuples).
    team_index = {t: i for i, t in enumerate(teams)}
    home_idx = dataset["home_team"].map(team_index).to_numpy()
    away_idx = dataset["away_team"].map(team_index).to_numpy()
    home_scores = dataset["home_score"].to_numpy(dtype=int)
    away_scores = dataset["away_score"].to_numpy(dtype=int)
    match_weights = (
        np.ones(len(dataset), dtype=float)
        if weights is None
        else np.asarray(weights, dtype=float)
    )

    def estimate_parameters(params):
        attack = params[:n_teams]
        defence = params[n_teams : 2 * n_teams]
        rho, gamma = params[-2:]
        lambda_x = np.exp(attack[home_idx] + defence[away_idx] + gamma)
        mu_y = np.exp(attack[away_idx] + defence[home_idx])
        ll = (
            np.log(np.maximum(poisson.pmf(home_scores, lambda_x), 1e-10))
            + np.log(np.maximum(poisson.pmf(away_scores, mu_y), 1e-10))
        )
        # τ correction on low-scoring outcomes (same cases as rho_correction).
        tau = np.ones(len(dataset), dtype=float)
        m00 = (home_scores == 0) & (away_scores == 0)
        m01 = (home_scores == 0) & (away_scores == 1)
        m10 = (home_scores == 1) & (away_scores == 0)
        m11 = (home_scores == 1) & (away_scores == 1)
        tau[m00] = np.maximum(1 - lambda_x[m00] * mu_y[m00] * rho, 1e-10)
        tau[m01] = 1 + lambda_x[m01] * rho
        tau[m10] = 1 + mu_y[m10] * rho
        tau[m11] = np.maximum(1 - rho, 1e-10)
        ll = ll + np.log(np.maximum(tau, 1e-10))
        return -np.sum(match_weights * ll)

    bounds = Bounds(
        [-np.inf] * n_teams + [-np.inf] * n_teams + [-1, 0],
        [np.inf] * n_teams + [np.inf] * n_teams + [1, np.inf],
    )

    # Blog uses SLSQP + sum(attack)=n. That scales poorly past ~40 teams, so
    # large fits use L-BFGS-B with a soft attack-mean penalty, then re-center.
    use_slsqp = n_teams <= 40
    if use_slsqp:
        constraints = [{"type": "eq", "fun": lambda x, n=n_teams: sum(x[:n]) - n}]
        opt_output = minimize(
            estimate_parameters,
            init_vals,
            method="SLSQP",
            options=options,
            constraints=constraints,
            bounds=bounds,
            **kwargs,
        )
        x = opt_output.x
    else:
        def estimate_large(params):
            loss = estimate_parameters(params)
            # Soft identifiability: mean attack ≈ 1 (same as blog sum(attack)=n).
            penalty = 100.0 * (params[:n_teams].mean() - 1.0) ** 2
            return loss + penalty

        opt_output = minimize(
            estimate_large,
            init_vals,
            method="L-BFGS-B",
            options={**options, "maxiter": max(int(options.get("maxiter", 150)), 80)},
            bounds=bounds,
            **kwargs,
        )
        x = opt_output.x.copy()
        x[:n_teams] = x[:n_teams] - x[:n_teams].mean() + 1.0

    return dict(
        zip(
            [f"attack_{t}" for t in teams]
            + [f"defence_{t}" for t in teams]
            + ["rho", "home_adv"],
            x,
        )
    )


def dixon_coles_simulate_match(params_dict, home_team, away_team, max_goals=MAX_GOALS):
    def calc_means(param_dict, home_team, away_team):
        return [
            np.exp(
                param_dict["attack_" + home_team]
                + param_dict["defence_" + away_team]
                + param_dict["home_adv"]
            ),
            np.exp(
                param_dict["defence_" + home_team]
                + param_dict["attack_" + away_team]
            ),
        ]

    empty = np.zeros((max_goals + 1, max_goals + 1))
    team_avgs = calc_means(params_dict, home_team, away_team)
    # An overflowed λ has no usable score distribution. Return a zero matrix
    # so outcome_probs yields null: a NaN in predictions.json makes the
    # browser's JSON.parse reject the whole file.
    if not np.all(np.isfinite(team_avgs)):
        return empty
    team_pred = [
        [poisson.pmf(i, team_avg) for i in range(max_goals + 1)] for team_avg in team_avgs
    ]
    output_matrix = np.outer(np.array(team_pred[0]), np.array(team_pred[1]))
    correction_matrix = np.array(
        [
            [
                rho_correction(h, a, team_avgs[0], team_avgs[1], params_dict["rho"])
                for a in range(2)
            ]
            for h in range(2)
        ]
    )
    output_matrix[:2, :2] *= correction_matrix
    # Guard against negative mass from extreme ρ, and NaN/inf from the
    # low-score correction at extreme λ.
    output_matrix = np.nan_to_num(output_matrix, nan=0.0, posinf=0.0, neginf=0.0)
    output_matrix = np.maximum(output_matrix, 0.0)
    total = float(output_matrix.sum())
    if not np.isfinite(total) or total <= 0:
        return empty
    return output_matrix / total


def _json_float(value) -> float | None:
    """Float safe for JSON.parse (browsers reject NaN and Infinity)."""
    number = float(value)
    return number if np.isfinite(number) else None


def outcome_probs(matrix: np.ndarray) -> dict[str, float | None]:
    """P(home win), P(draw), P(away win) from score matrix [home_goals, away_goals]."""
    # rows = home goals, cols = away goals
    m = np.maximum(np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0), 0.0)
    total = float(m.sum())
    if not np.isfinite(total) or total <= 0:
        return {"home": None, "draw": None, "away": None}
    m = m / total
    p_home = float(np.tril(m, k=-1).sum())
    p_draw = float(np.trace(m))
    p_away = float(np.triu(m, k=1).sum())
    return {"home": p_home, "draw": p_draw, "away": p_away}


def load_all_matches(division: str) -> pd.DataFrame:
    root = DATA_DIR / division
    if not root.exists():
        raise FileNotFoundError(f"No data under {root}")
    frames = []
    for path in sorted(root.glob("season=*/matches.parquet")):
        frames.append(pd.read_parquet(path))
    if not frames:
        for path in sorted(root.glob("season=*/matches.csv")):
            frames.append(pd.read_csv(path))
    if not frames:
        raise FileNotFoundError(f"No matches parquet/csv under {root}/season=*/")
    df = canonicalize_teams(pd.concat(frames, ignore_index=True), MATCH_TEAM_COLUMNS)
    return dedupe_matches(df)


def _as_bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.astype(str).str.lower().isin(["true", "1", "yes", "t", "y"])
    return series.astype(bool)


def _score_columns(m: pd.DataFrame) -> pd.DataFrame:
    out = m.dropna(subset=["home_goals", "away_goals", "home_team", "away_team"]).copy()
    out["home_score"] = out["home_goals"].astype(int)
    out["away_score"] = out["away_goals"].astype(int)
    out["home_team"] = out["home_team"].astype(str)
    out["away_team"] = out["away_team"].astype(str)
    out["conference"] = out["conference"].astype(str)
    if "away_conference" in out.columns:
        out["away_conference"] = out["away_conference"].astype(str)
    else:
        out["away_conference"] = out["conference"]
    return out


def training_frame(matches: pd.DataFrame) -> pd.DataFrame:
    """Completed non-playoff matches with blog column names (all conferences)."""
    m = matches.copy()
    played = _as_bool_series(m["played"])
    playoff = _as_bool_series(m["is_playoff"])
    m = m[played & ~playoff]
    return _score_columns(m).reset_index(drop=True)


def intra_conference_frame(train: pd.DataFrame) -> pd.DataFrame:
    """Stage A: same home/away conference only."""
    return train[
        train["conference"].astype(str) == train["away_conference"].astype(str)
    ].reset_index(drop=True)


def match_dates(frame: pd.DataFrame) -> pd.Series:
    """Calendar date per row (same date normalisation as the frontend export)."""
    iso = [
        _to_iso_date(
            raw.get("date"),
            date_sort=raw.get("date_sort"),
            season=str(raw.get("season") or ""),
        )
        for raw in frame.to_dict(orient="records")
    ]
    return pd.to_datetime(pd.Series(iso, index=frame.index), errors="coerce")


def time_decay_weights(
    dates: pd.Series,
    reference: pd.Timestamp,
    half_life_days: float = HALF_LIFE_DAYS,
) -> np.ndarray:
    """0.5 ** (age_days / half_life_days); rows without a usable date get 0."""
    age_days = (reference - dates).dt.days.to_numpy(dtype=float)
    weights = np.power(0.5, np.clip(age_days, 0.0, None) / half_life_days)
    return np.where(np.isfinite(weights), weights, 0.0)


def bridge_frame(matches: pd.DataFrame) -> pd.DataFrame:
    """Stage B: played cross-conference + national playoff bridges."""
    m = matches.copy()
    played = _as_bool_series(m["played"])
    m = _score_columns(m[played])
    m["region_home"] = m["conference"].map(region_group)
    m["region_away"] = m["away_conference"].map(region_group)
    if "playoff_scope" in m.columns:
        scope = m["playoff_scope"].astype(str).str.lower()
    else:
        scope = pd.Series("", index=m.index)
    is_national = scope.eq("national")
    cross_conf = m["conference"] != m["away_conference"]
    cross_group = m["region_home"] != m["region_away"]
    bridges = m[is_national | cross_conf].copy()
    bridges["bridge_type"] = np.select(
        [
            is_national.loc[bridges.index].to_numpy(),
            cross_group.loc[bridges.index].to_numpy(),
        ],
        ["national", "cross_group"],
        default="interlocking",
    )
    return bridges.reset_index(drop=True)


def fit_models(
    train: pd.DataFrame,
    bridges: pd.DataFrame | None = None,
    *,
    fit_global: bool = False,
) -> dict:
    """Fit per-conference Dixon–Coles models, then region-group offsets."""
    models: dict = {
        "global": None,
        "conferences": {},
        "team_conference": {},
        "conference_offsets": {},
        "bridge_meta": {},
    }

    intra = intra_conference_frame(train)
    intra_dates = match_dates(intra)
    reference = intra_dates.max()
    if pd.isna(reference):
        raise ValueError("No dated intra-conference matches to fit")
    intra_weights = pd.Series(
        time_decay_weights(intra_dates, reference), index=intra.index
    )
    undated = int(intra_dates.isna().sum())
    models["time_decay"] = {
        "half_life_days": HALF_LIFE_DAYS,
        "reference_date": reference.strftime("%Y-%m-%d"),
        "undated_rows_excluded": undated,
    }
    print(
        f"Time decay: half-life {HALF_LIFE_DAYS:g} days from "
        f"{reference:%Y-%m-%d}" + (f" ({undated} undated rows weighted 0)" if undated else "")
    )
    # Most-recent home conference label per team.
    latest = (
        train.sort_values("season") if "season" in train.columns else train
    )
    for team, grp in latest.groupby("home_team"):
        models["team_conference"][str(team)] = str(grp.iloc[-1]["conference"])

    for conf, group in intra.groupby("conference"):
        conf = str(conf)
        if len(group) < 8:
            continue
        teams = set(group["home_team"]) | set(group["away_team"])
        if len(teams) < 3:
            continue
        if len(teams) > 40:
            print(f"Fitting {conf!r} with L-BFGS ({len(group)} matches, {len(teams)} teams)…")
            opts = {"disp": False, "maxiter": 60}
        else:
            print(f"Fitting {conf!r} ({len(group)} matches, {len(teams)} teams)…")
            opts = {"disp": False, "maxiter": 200}
        try:
            params = solve_parameters(
                group, options=opts, weights=intra_weights.loc[group.index]
            )
            models["conferences"][conf] = params
            print(f"  rho={params['rho']:.4f}  home_adv={params['home_adv']:.4f}")
        except Exception as exc:  # noqa: BLE001 — keep other conferences fitting
            print(f"  skip {conf!r}: {exc}")

    if bridges is None:
        bridges = pd.DataFrame()
    offsets, meta = fit_conference_offsets(models, bridges)
    models["conference_offsets"] = offsets
    models["bridge_meta"] = meta
    if offsets:
        print(f"Fitted conference offsets on {meta.get('bridge_rows', 0)} bridges:")
        ranked = sorted(offsets.items(), key=lambda kv: kv[1])
        for conf, val in ranked[:8]:
            print(f"  {conf}: {val:+.3f}")
        if len(ranked) > 16:
            print("  …")
        for conf, val in ranked[-8:]:
            print(f"  {conf}: {val:+.3f}")
    else:
        print("No conference offsets fitted (insufficient bridges).")

    if fit_global:
        print(
            f"Fitting global model on {len(train)} matches "
            f"({len(set(train['home_team']) | set(train['away_team']))} teams)…"
        )
        models["global"] = solve_parameters(
            train, options={"disp": True, "maxiter": 40}
        )
        print(
            f"  rho={models['global']['rho']:.4f}  "
            f"home_adv={models['global']['home_adv']:.4f}"
        )
    else:
        print("Skipping global fit (use --fit-global to enable).")

    return models


def _team_strengths(
    models: dict, team: str, conference: str
) -> tuple[float, float, dict] | None:
    """Return (attack, defence, source_params) for team from its conference model."""
    conferences = models.get("conferences") or {}
    conf = conference or (models.get("team_conference") or {}).get(team) or ""
    params = conferences.get(str(conf))
    if not params:
        # Fall back: search any conference model that has this team.
        for conf_name, p in conferences.items():
            if f"attack_{team}" in p and f"defence_{team}" in p:
                return float(p[f"attack_{team}"]), float(p[f"defence_{team}"]), p
        return None
    if f"attack_{team}" not in params or f"defence_{team}" not in params:
        return None
    return float(params[f"attack_{team}"]), float(params[f"defence_{team}"]), params


def fit_conference_offsets(
    models: dict, bridges: pd.DataFrame
) -> tuple[dict[str, float], dict]:
    """Estimate conference-level shifts from tagged bridge matches.

    Team attack/defence stay fixed from Stage A. Offsets enter as:
      λ_h = exp(α_h + β_a + γ + δ_home − δ_away)

    Region-group tags on bridges are kept for diagnostics only; the fitted
    parameters are per conference so same-region interlocking is informative.
    """
    if bridges is None or bridges.empty:
        return {}, {"bridge_rows": 0}

    rows = []
    for raw in bridges.to_dict(orient="records"):
        home = str(raw["home_team"])
        away = str(raw["away_team"])
        home_conf = str(raw.get("conference") or "")
        away_conf = str(raw.get("away_conference") or "")
        if not home_conf or not away_conf or home_conf == away_conf:
            continue
        hs = _team_strengths(models, home, home_conf)
        aws = _team_strengths(models, away, away_conf)
        if hs is None or aws is None:
            continue
        att_h, def_h, hp = hs
        att_a, def_a, ap = aws
        rows.append(
            {
                "att_h": att_h,
                "def_h": def_h,
                "att_a": att_a,
                "def_a": def_a,
                "home_adv": 0.5 * (float(hp["home_adv"]) + float(ap["home_adv"])),
                "rho": 0.5 * (float(hp["rho"]) + float(ap["rho"])),
                "conf_h": home_conf,
                "conf_a": away_conf,
                "region_h": str(raw.get("region_home") or region_group(home_conf)),
                "region_a": str(raw.get("region_away") or region_group(away_conf)),
                "home_score": int(raw["home_score"]),
                "away_score": int(raw["away_score"]),
            }
        )

    if len(rows) < 10:
        return {}, {"bridge_rows": len(rows)}

    df = pd.DataFrame(rows)
    conferences = sorted(set(df["conf_h"]) | set(df["conf_a"]))
    counts = pd.concat([df["conf_h"], df["conf_a"]]).value_counts()
    ref = str(counts.index[0])
    free = [c for c in conferences if c != ref]
    if not free:
        return {ref: 0.0}, {"bridge_rows": len(df), "ref_conference": ref}

    conf_index = {c: i for i, c in enumerate(free)}
    ch_idx = df["conf_h"].map(lambda c: conf_index.get(c, -1)).to_numpy()
    ca_idx = df["conf_a"].map(lambda c: conf_index.get(c, -1)).to_numpy()
    att_h = df["att_h"].to_numpy()
    def_h = df["def_h"].to_numpy()
    att_a = df["att_a"].to_numpy()
    def_a = df["def_a"].to_numpy()
    gamma = df["home_adv"].to_numpy()
    rho = df["rho"].to_numpy()
    hs = df["home_score"].to_numpy(dtype=int)
    aws = df["away_score"].to_numpy(dtype=int)
    n_free = len(free)

    def pack_delta(x):
        d_h = np.zeros(len(df))
        d_a = np.zeros(len(df))
        mask_h = ch_idx >= 0
        mask_a = ca_idx >= 0
        d_h[mask_h] = x[ch_idx[mask_h]]
        d_a[mask_a] = x[ca_idx[mask_a]]
        return d_h, d_a

    def objective(x):
        d_h, d_a = pack_delta(x)
        lambda_x = np.exp(att_h + def_a + gamma + d_h - d_a)
        mu_y = np.exp(att_a + def_h + d_a - d_h)
        ll = (
            np.log(np.maximum(poisson.pmf(hs, lambda_x), 1e-10))
            + np.log(np.maximum(poisson.pmf(aws, mu_y), 1e-10))
        )
        tau = np.ones(len(df), dtype=float)
        m00 = (hs == 0) & (aws == 0)
        m01 = (hs == 0) & (aws == 1)
        m10 = (hs == 1) & (aws == 0)
        m11 = (hs == 1) & (aws == 1)
        tau[m00] = np.maximum(1 - lambda_x[m00] * mu_y[m00] * rho[m00], 1e-10)
        tau[m01] = 1 + lambda_x[m01] * rho[m01]
        tau[m10] = 1 + mu_y[m10] * rho[m10]
        tau[m11] = np.maximum(1 - rho[m11], 1e-10)
        ll = ll + np.log(np.maximum(tau, 1e-10))
        return -float(np.sum(ll)) + OFFSET_L2 * float(np.sum(x**2))

    opt = minimize(
        objective,
        np.zeros(n_free),
        method="L-BFGS-B",
        options={"disp": False, "maxiter": 250},
    )
    offsets = {ref: 0.0}
    for i, c in enumerate(free):
        offsets[c] = float(opt.x[i])
    meta = {
        "bridge_rows": int(len(df)),
        "ref_conference": ref,
        "n_conferences": len(conferences),
        "success": bool(opt.success),
        "by_type": (
            {str(k): int(v) for k, v in bridges["bridge_type"].value_counts().items()}
            if "bridge_type" in bridges.columns
            else {}
        ),
        "region_groups": sorted(set(df["region_h"]) | set(df["region_a"])),
    }
    return offsets, meta


def params_have_teams(params: dict, home: str, away: str) -> bool:
    return f"attack_{home}" in params and f"attack_{away}" in params


def cross_conference_params(
    models: dict, home: str, away: str, home_conf: str, away_conf: str
) -> dict | None:
    """Team strengths from each conference model + conference offsets.

    Offsets are scaled by OFFSET_WEIGHT_CROSS. Both conferences must still appear in
    the fitted offsets: presence is the check that bridge evidence linked them
    to the rest of the league at all, independent of how much of the estimated
    difference we apply.
    """
    hs = _team_strengths(models, home, home_conf)
    aws = _team_strengths(models, away, away_conf)
    if hs is None or aws is None:
        return None
    att_h, def_h, hp = hs
    att_a, def_a, ap = aws
    offsets = models.get("conference_offsets") or {}
    if home_conf not in offsets or away_conf not in offsets:
        return None
    w = OFFSET_WEIGHT_CROSS
    dh = float(offsets[home_conf]) * w
    da = float(offsets[away_conf]) * w
    rh = region_group(home_conf)
    ra = region_group(away_conf)
    # Bake δ into attack/defence so existing simulate_match formulas apply.
    return {
        f"attack_{home}": att_h + dh,
        f"defence_{home}": def_h - dh,
        f"attack_{away}": att_a + da,
        f"defence_{away}": def_a - da,
        "rho": float((float(hp["rho"]) + float(ap["rho"])) / 2.0),
        "home_adv": float((float(hp["home_adv"]) + float(ap["home_adv"])) / 2.0),
        "_region_home": rh,
        "_region_away": ra,
    }


def select_params(models: dict, match: dict) -> tuple[dict | None, str]:
    home = match["home_team"]
    away = match["away_team"]
    home_conf = str(
        match.get("conference")
        or (models.get("team_conference") or {}).get(home)
        or ""
    )
    away_conf = str(
        match.get("away_conference")
        or (models.get("team_conference") or {}).get(away)
        or home_conf
    )

    conf_params = (models.get("conferences") or {}).get(home_conf)
    if conf_params and params_have_teams(conf_params, home, away):
        return conf_params, f"conference:{home_conf}"

    # Same conference name but away missing from home model — try away model.
    away_params = (models.get("conferences") or {}).get(away_conf)
    if (
        home_conf == away_conf
        and away_params
        and params_have_teams(away_params, home, away)
    ):
        return away_params, f"conference:{away_conf}"

    if home_conf and away_conf and home_conf != away_conf:
        cross = cross_conference_params(models, home, away, home_conf, away_conf)
        if cross:
            rh = cross.pop("_region_home", region_group(home_conf))
            ra = cross.pop("_region_away", region_group(away_conf))
            return cross, f"bridge:{rh}+{ra}"

    global_params = models.get("global")
    if global_params and params_have_teams(global_params, home, away):
        return global_params, "global"
    return None, "unavailable"


def conference_rate_centers(params: dict) -> tuple[float, float]:
    """Median scoring / conceding multiplier (e^attack, e^defence) of a model.

    Median of rates rather than mean of log-parameters, because a team whose
    only match had zero goals for (or against) gets a parameter driven toward
    -inf by the fit. In log space one such team wrecks the centre, while as a
    rate it collapses to ~0 and the median ignores it outright.
    """
    atk = [np.exp(float(v)) for k, v in params.items() if k.startswith("attack_")]
    dfn = [np.exp(float(v)) for k, v in params.items() if k.startswith("defence_")]
    if not atk or not dfn:
        raise ValueError("Conference model has no team strengths")
    return float(np.median(atk)), float(np.median(dfn))


def build_rate_centers(
    models: dict, teams: list[str], team_conf: dict[str, str]
) -> dict[str, tuple[float, float]]:
    """Per-team shrinkage target: the median rates of its conference model.

    A team is attributed to the conference model it appears in; its scraped
    conference label wins when the team appears in several (clubs move between
    conferences across seasons). Teams whose conference was never fitted fall
    back to the median across conference centres.
    """
    conferences = models.get("conferences") or {}
    per_conf: dict[str, tuple[float, float]] = {}
    for name, params in conferences.items():
        try:
            per_conf[name] = conference_rate_centers(params)
        except ValueError:
            continue
    if not per_conf:
        raise ValueError("No fitted conference models available")
    league = (
        float(np.median([c[0] for c in per_conf.values()])),
        float(np.median([c[1] for c in per_conf.values()])),
    )

    owner: dict[str, str] = {}
    for name, params in conferences.items():
        if name not in per_conf:
            continue
        for key in params:
            if not key.startswith("attack_"):
                continue
            team = key[len("attack_") :]
            if team not in owner or team_conf.get(team) == name:
                owner[team] = name

    centers: dict[str, tuple[float, float]] = {}
    for team in teams:
        name = owner.get(team) or team_conf.get(team, "")
        centers[team] = per_conf.get(name, league)
    return centers


def shrink_weight(n_played: int, k: float = SHRINK_K) -> float:
    """Weight on a team's own fitted strengths: n/(n+k), so 0 games → 0.

    k <= 0 disables shrinkage: a team with any matches keeps full weight on
    its own params. A team with none still has nothing of its own to trust.
    """
    n = max(int(n_played), 0)
    if k <= 0:
        return 1.0 if n > 0 else 0.0
    return n / (n + k)


def shrink_towards_conference(
    params: dict,
    home: str,
    away: str,
    history: dict[str, int],
    centers: dict[str, tuple[float, float]],
    k: float = SHRINK_K,
) -> dict:
    """Blend both teams' strengths toward their conference medians.

    Blending happens on the rate scale (e^param) — the scale Poisson means are
    built from — then converts back to a log parameter so the existing
    simulate_match formulas are untouched. Conference-level rho and home_adv
    are shared across the whole model and are left alone.

    Cross-conference fixtures have the conference offset baked into attack and
    defence upstream (OFFSET_WEIGHT_CROSS), so shrink also pulls stitched
    strengths toward per-team conference medians.
    """
    if k <= 0:
        return params
    out = dict(params)
    for team in (home, away):
        center = centers.get(team)
        if center is None:
            continue
        w = shrink_weight(history.get(team, 0), k)
        for prefix, center_rate in (("attack", center[0]), ("defence", center[1])):
            key = f"{prefix}_{team}"
            if key not in out:
                continue
            rate = w * float(np.exp(float(out[key]))) + (1.0 - w) * center_rate
            out[key] = float(np.log(max(rate, _MIN_RATE)))
    return out


def _stage_label(match: dict) -> str:
    """Playoff stage label only — never the full venue string.

    Venue names such as 'Championship Soccer Stadium' would otherwise match
    the finals patterns below and mislabel ordinary hosted rounds.
    """
    stage = match.get("playoff_stage")
    if stage is not None and not pd.isna(stage) and str(stage).strip():
        return str(stage).strip()
    # UPSL appends the stage after a pipe, e.g. '… UCLA | National Semifinals'.
    # Third-place matches arrive untagged, so fall back to that suffix.
    venue = str(match.get("venue") or "")
    return venue.rsplit("|", 1)[-1].strip() if "|" in venue else ""


def is_neutral_site(match: dict) -> bool:
    """True for finals-weekend rounds, which UPSL hosts at one central venue.

    Earlier national rounds (R32/R16) are played at a participant's ground and
    keep home advantage. Region finals are left as hosted; their venues are
    not reliably neutral in the scraped data.
    """
    return bool(_NEUTRAL_STAGE_RE.search(_stage_label(match)))


def predict_match(
    models: dict,
    match: dict,
    max_goals: int = MAX_GOALS,
    *,
    history: dict[str, int] | None = None,
    centers: dict[str, tuple[float, float]] | None = None,
    k: float = SHRINK_K,
) -> dict | None:
    params, source = select_params(models, match)
    if params is None:
        return None
    if history is not None and centers is not None:
        params = shrink_towards_conference(
            params, match["home_team"], match["away_team"], history, centers, k
        )
    neutral = is_neutral_site(match)
    if neutral:
        params = {**params, "home_adv": 0.0}
    matrix = dixon_coles_simulate_match(
        params, match["home_team"], match["away_team"], max_goals=max_goals
    )
    probs = outcome_probs(matrix)
    return {
        "model": source,
        "p_home": probs["home"],
        "p_draw": probs["draw"],
        "p_away": probs["away"],
        "lambda_home": _json_float(
            np.exp(
                params["attack_" + match["home_team"]]
                + params["defence_" + match["away_team"]]
                + params["home_adv"]
            )
        ),
        "lambda_away": _json_float(
            np.exp(
                params["defence_" + match["home_team"]]
                + params["attack_" + match["away_team"]]
            )
        ),
        "rho": _json_float(params["rho"]),
        "home_adv": _json_float(params["home_adv"]),
        "neutral_site": neutral,
        "matrix": matrix.tolist(),
    }


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}

def _match_conferences(
    raw: dict, models: dict, *, home: str, away: str
) -> tuple[str, str]:
    home_conf = str(
        raw.get("conference")
        or (models.get("team_conference") or {}).get(home)
        or ""
    )
    away_conf = str(
        raw.get("away_conference")
        or (models.get("team_conference") or {}).get(away)
        or home_conf
    )
    return home_conf, away_conf


def is_cross_conference_fixture(
    raw: dict, models: dict, *, home: str, away: str
) -> bool:
    home_conf, away_conf = _match_conferences(raw, models, home=home, away=away)
    return bool(home_conf and away_conf and home_conf != away_conf)


def min_played_required(
    raw: dict, models: dict, *, home: str, away: str
) -> int:
    if is_cross_conference_fixture(raw, models, home=home, away=away):
        return MIN_PLAYED_MATCHES_CROSS
    return MIN_PLAYED_MATCHES


def prediction_passes_publish_gates(pred: dict) -> bool:
    for side in ("home", "away"):
        lam = pred.get(f"lambda_{side}")
        if lam is None or not np.isfinite(lam):
            return False
        if lam < PUBLISH_LAMBDA_MIN or lam > PUBLISH_LAMBDA_MAX:
            return False
    for key in ("p_home", "p_draw", "p_away"):
        p = pred.get(key)
        if p is None or not np.isfinite(p):
            return False
        if p < PUBLISH_P_EXTREME_LO or p > PUBLISH_P_EXTREME_HI:
            return False
    return True

def export_predictions(
    models: dict,
    matches: pd.DataFrame,
    *,
    out_path: Path = PREDICTIONS_OUT,
    max_goals: int = MAX_GOALS,
    k: float = SHRINK_K,
) -> Path:
    """Predict unplayed fixtures; also attach probs for played (optional audit)."""
    # Played-match counts per team: below min_played_required (league vs
    # cross-conference) → no published prediction (preview stays blank).
    # After predict_match, prediction_passes_publish_gates may omit extremes.
    # Teams that clear both gates still get n/(n+k) shrinkage, matching
    # projected standings.
    played_mask = matches["played"].map(_as_bool)
    played_rows = matches[played_mask]
    played_counts = (
        pd.concat([played_rows["home_team"], played_rows["away_team"]])
        .astype(str)
        .str.strip()
        .value_counts()
    )
    history = {str(t): int(n) for t, n in played_counts.items()}

    records = matches.to_dict(orient="records")
    team_conf: dict[str, str] = {}
    teams: list[str] = []
    seen: set[str] = set()
    for raw in records:
        home = str(raw.get("home_team") or "").strip()
        away = str(raw.get("away_team") or "").strip()
        conf = str(raw.get("conference") or "")
        away_conf = str(raw.get("away_conference") or conf)
        for team, label in ((home, conf), (away, away_conf)):
            if not team:
                continue
            team_conf.setdefault(team, label)
            if team not in seen:
                seen.add(team)
                teams.append(team)
    try:
        centers = build_rate_centers(models, teams, team_conf)
    except ValueError:
        centers = {}

    rows = []
    skipped_newcomer = 0
    skipped_quality = 0
    for raw in records:
        played = _as_bool(raw.get("played"))
        if played:
            continue
        home = str(raw.get("home_team") or "").strip()
        away = str(raw.get("away_team") or "").strip()
        min_required = min_played_required(
            raw, models, home=home, away=away
        )
        if (
            int(history.get(home, 0)) < min_required
            or int(history.get(away, 0)) < min_required
        ):
            skipped_newcomer += 1
            continue
        iso = _to_iso_date(
            raw.get("date"),
            date_sort=raw.get("date_sort"),
            season=str(raw.get("season") or ""),
        )
        mid = _match_id({**raw, "date": iso or raw.get("date")})
        pred = predict_match(
            models,
            {
                "home_team": home,
                "away_team": away,
                "conference": str(raw.get("conference") or ""),
                "away_conference": str(raw.get("away_conference") or ""),
                "playoff_stage": raw.get("playoff_stage"),
                "venue": raw.get("venue"),
            },
            max_goals=max_goals,
            history=history,
            centers=centers,
            k=k,
        )
        if pred is None:
            continue
        if not prediction_passes_publish_gates(pred):
            skipped_quality += 1
            continue
        rows.append({"id": mid, **pred})
    if skipped_newcomer:
        print(
            f"  skipped {skipped_newcomer} fixtures (min played: "
            f"{MIN_PLAYED_MATCHES} league, {MIN_PLAYED_MATCHES_CROSS} cross-conf)"
        )
    if skipped_quality:
        print(
            f"  skipped {skipped_quality} fixtures failing publish quality gates"
        )

    by_id = {r["id"]: r for r in rows}
    payload = {
        "model": "dixon_coles",
        "source": (
            "https://urazakgul.github.io/datafc-blog/posts/en/post3/"
            "better-predictions-for-football-matches-how-does-the-dixon-coles-model-work.html"
        ),
        "time_decay": True,
        "half_life_days": HALF_LIFE_DAYS,
        "time_decay_reference_date": (models.get("time_decay") or {}).get(
            "reference_date"
        ),
        "cross_conference": "conference_offsets_from_bridges",
        "offset_weight": OFFSET_WEIGHT,
        "offset_weight_cross": OFFSET_WEIGHT_CROSS,
        "shrink_k": k,
        "max_goals": max_goals,
        "min_played_matches": MIN_PLAYED_MATCHES,
        "min_played_matches_cross": MIN_PLAYED_MATCHES_CROSS,
        "publish_lambda_range": [PUBLISH_LAMBDA_MIN, PUBLISH_LAMBDA_MAX],
        "publish_p_extreme": [PUBLISH_P_EXTREME_LO, PUBLISH_P_EXTREME_HI],
        "prediction_count": len(by_id),
        "predictions": by_id,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    return out_path


def save_models(models: dict, path: Path) -> None:
    """JSON-serialize fitted params (no numpy types)."""
    def conv(obj):
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        return obj

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(conv(models), indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit UPSL Dixon–Coles models")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument("--max-goals", type=int, default=MAX_GOALS)
    parser.add_argument(
        "--fit-global",
        action="store_true",
        help="Also fit one large global model (slow; optional fallback)",
    )
    args = parser.parse_args(argv)

    matches = load_all_matches(args.division)
    print(
        f"Loaded {len(matches)} match rows across "
        f"{matches['season'].nunique() if 'season' in matches.columns else '?'} seasons"
    )
    train = training_frame(matches)
    bridges = bridge_frame(matches)
    intra_n = len(intra_conference_frame(train))
    print(f"Training rows (played, non-playoff): {len(train)}  intra: {intra_n}")
    print(
        f"Bridge rows (cross-conference / national): {len(bridges)}"
        + (
            f"  {bridges['bridge_type'].value_counts().to_dict()}"
            if len(bridges) and "bridge_type" in bridges.columns
            else ""
        )
    )
    if train.empty:
        print("No training data.")
        return 1

    models = fit_models(train, bridges, fit_global=args.fit_global)
    art_dir = DATA_DIR / args.division / "models" / "dixon_coles"
    save_models(models, art_dir / "params.json")
    print(f"Wrote {art_dir / 'params.json'}")
    print(f"  conferences fitted: {len(models['conferences'])}")
    print(f"  conference offsets: {len(models.get('conference_offsets') or {})}")

    pred_path = export_predictions(
        models,
        matches,
        out_path=PREDICTIONS_OUT,
        max_goals=args.max_goals,
        k=SHRINK_K,
    )
    print(f"Wrote {pred_path} ({json.loads(pred_path.read_text())['prediction_count']} upcoming)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
