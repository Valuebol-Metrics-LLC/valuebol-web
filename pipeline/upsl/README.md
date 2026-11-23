# UPSL scrape (local parquet)

Scrapes UPSL **schedule** and **standings** into local parquet/CSV under `upsl/data/`.

Divisions use separate subdomains (`premier.upsl.com`, `division1.upsl.com`, …).

## Default scope

- Division: **Premier**
- Season: **2026 Spring**
- Conferences: **all** with matches that season

## Setup

```bash
cd pipeline
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
# All Premier conferences, 2026 Spring (default)
python -m upsl.fetch

# Explicit
python -m upsl.fetch --division premier --season "2026 Spring"

# Single conference (any supported division)
python -m upsl.fetch --division division1 --conference "Midwest Central" --season "2026 Spring"

# Force re-download (ignore HTML cache)
python -m upsl.fetch --refresh-cache

# All Premier seasons (matches; add standings by omitting --skip-standings)
python -m upsl.fetch --all-seasons --skip-standings
python -m upsl.fetch --all-seasons

# Fit Dixon–Coles (blog methodology + time decay) + write predictions.json
# Stage A: per-conference fits on intra-conference matches. Each match is
#   weighted 0.5 ** (age_days / 365) (HALF_LIFE_DAYS), measured from the latest
#   dated intra-conference match; undated rows get weight 0. The saved
#   params.json carries the decay into projected standings too.
# Stage B: conference offsets from tagged bridges (interlocking + national).
#   Offsets are fitted and stored; cross-conference λ applies
#   OFFSET_WEIGHT_CROSS (default 1.0). Intra-conference predictions do not
#   apply conference offsets (OFFSET_WEIGHT remains 0).
# Finals-weekend rounds (semis / final / third place) are treated as neutral
#   sites and get no home advantage.
# Team strengths shrink toward the conference median at n/(n+k), k=6, matching
#   projected standings. Min played: 3 for same-conference fixtures,
#   13 for cross-conference (either team). Rows failing publish gates (λ or
#   win % extremes) are omitted. Metadata in predictions.json documents
#   offset_weight_cross, min_played_matches_cross, and gate thresholds.
# Optional slow full-league fit: --fit-global
python -m upsl.dixon_coles

# Phase 1 Elo (2017+ chronological; K=25 regular / K=40 playoff)
# Writes public/upsl/elo-rankings.json + models/elo/*.parquet
python -m upsl.elo

# Export scraped matches + standings for the Matches / Preview tabs
# (public/upsl/matches.json, public/upsl/conference-standings.json)
python -m upsl.export_frontend

# Monte Carlo projected league tables (public/upsl/projected-standings.json)
# Simulates remaining non-playoff fixtures with Dixon–Coles matrices; loads
# the saved params.json (run dixon_coles first, or pass --refit).
# Team strengths shrink toward the conference median at weight n/(n+k) on
# career matches (default k=6; pass --shrink-k 0 to disable). Same k as
# published match probabilities.
python -m upsl.simulate_standings
python -m upsl.simulate_standings --season "2026 Fall" --sims 10000

# Teams tab profiles (public/upsl/teams.json): per-season record, league
# position, conference playoff finish, season-end ASI rank, home stadium and
# 3-letter abbreviations. Reads elo-rankings.json, so run after upsl.elo.
python -m upsl.export_teams
```

Full refresh order: `fetch` → `export_frontend` → `dixon_coles` →
`simulate_standings` → `elo` → `export_teams`.

## Output layout

```text
data/
  raw_html/                          # cached HTML (gitignored)
  premier/
    meta/
      conferences_2026-spring.parquet
      seasons.parquet
    season=2026-spring/
      matches.parquet (+ .csv)
      standings.parquet (+ .csv)
      validation.parquet (+ .csv)
      summary.json
```

Generated files under `data/` (except `.gitkeep`) are gitignored; re-run `python -m upsl.fetch` to rebuild.

Playoff rows include `playoff_scope` (`conference` | `national`) and optional
`playoff_stage` (e.g. `National Round of 16`, `East Region Final`). Conference
brackets (including interlocking Virginia / Mid-Atlantic games) stay under the
home conference; national/regional games are grouped by stage in the Matches tab
(national sections listed first).

Validation compares a reconstructed W/D/L table (completed non-playoff matches,
including **inter-conference** league games) to official standings **per conference**.

- Official **PTS** can differ when the league applies point deductions.
- Exit code `2` only if record-match rate is below 98% (GP/W/D/L/GF/GA).
- Small residuals (e.g. OK-AR 2026 Spring) can happen when voided/replayed
  fixtures remain on the schedule HTML.

## Notes

- One schedule request returns all conferences for the season; rows are filtered by `data-team-conference-id`.
- Standings are fetched per conference (rate-limited). Empty parent groups (e.g. “American” with no table) are skipped.
- Be polite: do not remove the request sleep or parallelize aggressively.
- Supabase load is intentionally deferred.
