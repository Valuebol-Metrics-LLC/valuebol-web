"""Build public/upsl/site.json: the small file the website loads on every visit.

The pipeline's own exports (matches.json alone is ~15 MB) are too heavy for a
phone, so this keeps only what the pages show, in the same shapes as
src/data/snapshot.js: rankings for active clubs, movers, the biggest upcoming
matches with predictions, this season's top scorers and one live title race.

Run after the rest of the pipeline:  python pipeline/export_site.py
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "upsl"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def pct(p: float) -> int:
    """Whole percent; a real but tiny chance shows as -1 ("<1%") rather than 0."""
    v = round(p * 100)
    return -1 if v == 0 and p > 0 else v


def short_count(n: int) -> str:
    if n >= 1000:
        return f"{n // 1000}K+"
    return f"{(n // 10) * 10}+" if n >= 100 else str(n)


def main() -> None:
    elo = load("elo-rankings.json")
    teams = load("teams.json")
    preds = load("predictions.json")["predictions"]
    proj = load("projected-standings.json")
    players = load("player-stats.json")
    matches = load("matches.json")["matches"]

    season = teams["ongoing_season"] or teams["latest_season"]
    profiles = teams["teams"]
    today = date.today().isoformat()

    def season_row(name: str):
        for s in profiles.get(name, {}).get("seasons", []):
            if s["season"] == season:
                return s
        return None

    # --- rankings: clubs that played this season, ranked by ASI ---------------------------
    active = [r for r in elo["rankings"] if season_row(r["team"])]
    active.sort(key=lambda r: -r["elo"])
    rankings = []
    for i, r in enumerate(active, 1):
        s = season_row(r["team"])
        rankings.append({
            "rank": i,
            "name": r["team"],
            "conference": s["conference"] if s else r["conference"],
            "asi": round(r["elo"]),
            "matches": r["matches_tracked"],
            "record": f'{s["wins"]}-{s["draws"]}-{s["losses"]}',
            "last5": round(r.get("recent_delta") or 0, 1),
            "move": r.get("rank_delta") or 0,
        })
    rank_of = {r["name"]: r["rank"] for r in rankings}

    # Rank change over the last two weeks, from the rating history (elo.py only fills
    # rank_delta when it has a previous run to compare with).
    if all(not r["move"] for r in rankings):
        cutoff = (date.fromisoformat(elo["generated_at"][:10]) - timedelta(days=14)).isoformat()
        hist = elo.get("history", {})

        def elo_at(name):
            past = [h["e"] for h in hist.get(name, []) if h["d"] <= cutoff]
            return past[-1] if past else None

        before = sorted(((elo_at(r["name"]), r["name"]) for r in rankings if elo_at(r["name"]) is not None), reverse=True)
        old_rank = {name: i for i, (_, name) in enumerate(before, 1)}
        for r in rankings:
            if r["name"] in old_rank:
                r["move"] = old_rank[r["name"]] - r["rank"]

    def pick(key, best):
        cand = [r for r in rankings if r[key] is not None]
        r = best(cand, key=lambda x: x[key]) if cand else None
        return r and {"name": r["name"], "rank": r["rank"], "conference": r["conference"], key: r[key]}

    movers = {"climber": pick("move", max), "hottest": pick("last5", max), "drop": pick("move", min)}

    # --- upcoming matches with predictions ------------------------------------------------
    upcoming = [m for m in matches if not m["played"] and m["date"] >= today and m["season"] == season]

    def stage(m):
        if m.get("is_playoff"):
            scope = "National" if m.get("playoff_scope") == "national" else m["conference"]
            return f"UPSL {scope} playoffs" + (f" · {m['playoff_stage']}" if m.get("playoff_stage") else "")
        return f"UPSL {m['conference']}"

    def fmt_time(t):
        return "TBD" if not t or t.upper() == "TBD" else t.replace(" pm", " PM").replace(" am", " AM")

    featured = []
    for m in upcoming:
        p = preds.get(m["id"])
        featured.append({
            "id": m["id"],
            "date": m["date"],
            "time": fmt_time(m.get("time")),
            "competition": stage(m),
            "home": m["home_team"], "homeRank": rank_of.get(m["home_team"]),
            "away": m["away_team"], "awayRank": rank_of.get(m["away_team"]),
            "probs": [round(p["p_home"] * 100), round(p["p_draw"] * 100), round(p["p_away"] * 100)] if p else None,
            "venue": m.get("venue_name") if m.get("venue_name") not in (None, "TBD") else None,
            "matchUrl": m.get("match_url"),
        })
    # biggest games first: both clubs ranked, best combined rank, then by date
    featured.sort(key=lambda f: ((f["homeRank"] or 999) + (f["awayRank"] or 999), f["date"]))
    featured = sorted(featured[:12], key=lambda f: (f["date"], f["time"]))

    # --- this season's top scorers -------------------------------------------------------------
    scorers = []
    for club, seasons in players["teams"].items():
        for p in seasons.get(season, []):
            scorers.append({"name": p["name"].title() if p["name"].isupper() else p["name"], "club": club, "goals": p["goals"]})
    scorers.sort(key=lambda p: (-p["goals"], rank_of.get(p["club"], 999)))
    # Goal scorers come from match pages and fill in over several runs. Until most active
    # clubs are covered, publish nothing so the site keeps its last checked list.
    covered = sum(1 for r in rankings if season in players["teams"].get(r["name"], {}))
    scorer_coverage = covered / max(len(rankings), 1)
    top_scorers = scorers[:10] if scorer_coverage >= 0.9 else None

    # --- one live title race: the conference with the most games left ----------------------------
    confs = proj["conferences"]
    live = {k: v for k, v in confs.items() if v["remaining_fixtures"] > 0 and not v["low_confidence"]}
    name = max(live, key=lambda k: live[k]["remaining_fixtures"]) if live else next(iter(confs))
    race = {
        "conference": name,
        "season": season.split(" ")[1] + " " + season.split(" ")[0] if " " in season else season,
        "runs": proj["n_sims"],
        "clubs": [{
            "name": t["team"], "pos": t["place"], "pts": t["pts"], "gp": t["gp"],
            "projGp": t["proj_gp"], "projPts": round(t["avg_proj_pts"], 1),
            "finish": [pct(x) for x in t["position_probs"]],
        } for t in confs[name]["teams"]],
    }

    elos = [r["asi"] for r in rankings]
    conf_count = len({r["conference"] for r in rankings})
    site = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asOf": elo["generated_at"][:10],
        "season": season,
        "coverage": {
            "teams": short_count(elo["team_count"]),
            "conferences": str(conf_count),
            "matches": short_count(elo["match_count"]),
            "since": elo["from_year"],
            "activeClubs": len(rankings),
        },
        "rankings": rankings,
        "ratingRange": {"lowest": min(elos), "highest": max(elos)},
        "movers": movers,
        "featuredMatches": featured,
        "topScorers": top_scorers,
        "scorerCoverage": round(scorer_coverage, 2),
        "conferenceRace": race,
    }
    path = OUT / "site.json"
    path.write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB): {len(rankings)} active clubs, "
          f"{len(featured)} featured matches, race = {name}, scorer coverage {scorer_coverage:.0%}")


if __name__ == "__main__":
    main()
