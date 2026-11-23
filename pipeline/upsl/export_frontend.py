"""Export scraped UPSL matches to public/upsl/matches.json for the Matches tab.

Usage (from pipeline/ with venv active):
    python -m upsl.export_frontend
    python -m upsl.export_frontend --division premier --season "2026 Spring"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from upsl.fetch import DATA_DIR, DEFAULT_DIVISION, DEFAULT_SEASON, slugify
from upsl.team_aliases import canonicalize_teams

MATCH_TEAM_COLUMNS = ("home_team", "away_team")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "public" / "upsl" / "matches.json"
# Named conference-standings.json: Vite's SPA fallback incorrectly serves
# index.html for /upsl/standings.json (conflicts with the /standings app route).
DEFAULT_STANDINGS_OUT = REPO_ROOT / "public" / "upsl" / "conference-standings.json"


def _to_iso_date(value, *, date_sort=None, season: str = "") -> str | None:
    """Normalize UPSL dates; prefer date_sort when the HTML year is garbage."""
    iso_from_sort = None
    if date_sort is not None and not (isinstance(date_sort, float) and pd.isna(date_sort)):
        try:
            ts = pd.to_datetime(float(date_sort), unit="s", errors="coerce")
            if not pd.isna(ts):
                iso_from_sort = ts.strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return iso_from_sort
    text = str(value).strip()
    if not text:
        return iso_from_sort
    # Already ISO
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        year = int(text[:4])
        if 2000 <= year <= 2100:
            return text
        return iso_from_sort or text
    # MM/DD/YYYY from UPSL HTML (occasionally wrong year, e.g. 0206)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        month, day, year_s = m.groups()
        year = int(year_s)
        if not (2000 <= year <= 2100):
            # e.g. "0206" typo → use season year or date_sort
            season_year = None
            sm = re.search(r"(20\d{2})", season or "")
            if sm:
                season_year = int(sm.group(1))
            if iso_from_sort:
                return iso_from_sort
            if season_year:
                return f"{season_year}-{int(month):02d}-{int(day):02d}"
            return None
        return f"{year}-{int(month):02d}-{int(day):02d}"
    ts = pd.to_datetime(text, errors="coerce")
    if pd.isna(ts):
        return iso_from_sort
    return ts.strftime("%Y-%m-%d")


def _match_id(row: dict) -> str:
    url = str(row.get("match_url") or "").rstrip("/")
    if url:
        slug = url.split("/")[-1]
        if slug:
            return slug
    parts = [
        str(row.get("conference_slug") or slugify(str(row.get("conference") or "x"))),
        str(row.get("date") or ""),
        slugify(str(row.get("home_team") or "home")),
        slugify(str(row.get("away_team") or "away")),
    ]
    return "-".join(p for p in parts if p)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _as_goal(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_ts(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dedupe_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate fixtures (same match_url) from concatenated seasons.

    UPSL lists some playoff fixtures on more than one season schedule page
    (e.g. national semifinals appear under both Spring and Fall), so
    all-season concats can carry the same match twice. Keep one row per
    match_url, preferring a played copy over an unplayed placeholder.
    """
    if df.empty or "match_url" not in df.columns:
        return df
    url = df["match_url"].fillna("").astype(str).str.strip()
    played = (
        df["played"].map(_as_bool)
        if "played" in df.columns
        else pd.Series(False, index=df.index)
    )
    # Stable sort so played copies win their duplicate group.
    order = pd.DataFrame({"url": url, "unplayed": ~played}, index=df.index)
    order = order.sort_values("unplayed", kind="mergesort")
    dup = order["url"].duplicated(keep="first") & (order["url"] != "")
    drop_index = order.index[dup]
    if drop_index.empty:
        return df
    return df.drop(index=drop_index).reset_index(drop=True)


def _season_dir(division: str, season: str) -> Path:
    return DATA_DIR / division / f"season={slugify(season)}"


def load_matches(division: str, season: str | None = None) -> pd.DataFrame:
    """Load one season, or all seasons when season is None / 'all'."""
    if season and season.lower() != "all":
        base = _season_dir(division, season)
        parquet_path = base / "matches.parquet"
        csv_path = base / "matches.csv"
        if parquet_path.exists():
            return canonicalize_teams(pd.read_parquet(parquet_path), MATCH_TEAM_COLUMNS)
        if csv_path.exists():
            return canonicalize_teams(pd.read_csv(csv_path), MATCH_TEAM_COLUMNS)
        raise FileNotFoundError(
            f"No matches file under {base}. Run: python -m upsl.fetch "
            f'--division {division} --season "{season}"'
        )

    root = DATA_DIR / division
    frames = []
    for path in sorted(root.glob("season=*/matches.parquet")):
        frames.append(pd.read_parquet(path))
    if not frames:
        for path in sorted(root.glob("season=*/matches.csv")):
            frames.append(pd.read_csv(path))
    if not frames:
        raise FileNotFoundError(
            f"No matches under {root}/season=*/. Run: python -m upsl.fetch --all-seasons"
        )
    df = canonicalize_teams(pd.concat(frames, ignore_index=True), MATCH_TEAM_COLUMNS)
    return dedupe_matches(df)


def load_standings(division: str, season: str | None = None) -> pd.DataFrame:
    """Load one season's standings, or all seasons when season is None / 'all'."""
    if season and season.lower() != "all":
        base = _season_dir(division, season)
        parquet_path = base / "standings.parquet"
        csv_path = base / "standings.csv"
        if parquet_path.exists():
            return canonicalize_teams(pd.read_parquet(parquet_path), ("team",))
        if csv_path.exists():
            return canonicalize_teams(pd.read_csv(csv_path), ("team",))
        raise FileNotFoundError(
            f"No standings file under {base}. Run: python -m upsl.fetch "
            f'--division {division} --season "{season}"'
        )

    root = DATA_DIR / division
    frames = []
    for path in sorted(root.glob("season=*/standings.parquet")):
        frames.append(pd.read_parquet(path))
    if not frames:
        for path in sorted(root.glob("season=*/standings.csv")):
            frames.append(pd.read_csv(path))
    if not frames:
        raise FileNotFoundError(
            f"No standings under {root}/season=*/. Run: python -m upsl.fetch --all-seasons"
        )
    return canonicalize_teams(pd.concat(frames, ignore_index=True), ("team",))


def _optional_str(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


_FIELD_SUFFIX_RE = re.compile(r"\s*[-–]\s*(?:field|fld|pitch)\b.*$", re.I)


def clean_venue(venue: str) -> str:
    """Stadium name without the 'Playoff' prefix, stage suffix or field number."""
    text = str(venue or "").strip()
    if text.startswith("Playoff"):
        text = text[len("Playoff"):].strip()
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    return _FIELD_SUFFIX_RE.sub("", text).strip()


def export_matches(
    *,
    division: str = DEFAULT_DIVISION,
    season: str = "all",
    out_path: Path = DEFAULT_OUT,
) -> Path:
    df = load_matches(division, season)
    rows = []
    for raw in df.to_dict(orient="records"):
        iso = _to_iso_date(
            raw.get("date"),
            date_sort=raw.get("date_sort"),
            season=season,
        )
        if not iso:
            continue
        played = _as_bool(raw.get("played"))
        home_goals = _as_goal(raw.get("home_goals"))
        away_goals = _as_goal(raw.get("away_goals"))
        # Trust scraper `played`. UPSL uses placeholder 0-0 before kickoff;
        # those rows are exported with null scores and played=false.
        if not played:
            home_goals = None
            away_goals = None
        division_label = str(raw.get("division") or division).strip()
        conference = str(raw.get("conference") or "").strip() or "Unknown"
        row = {
            "id": _match_id({**raw, "date": iso}),
            "league": "UPSL",
            "division": division_label.title() if division_label.islower() else division_label,
            "season": _optional_str(raw.get("season")) or (
                season if season and season.lower() != "all" else None
            ),
            "conference": conference,
            "conference_id": str(raw.get("conference_id") or ""),
            "away_conference": _optional_str(raw.get("away_conference")),
            "away_conference_id": _optional_str(raw.get("away_conference_id")),
            "date": iso,
            "time": str(raw.get("time") or "").strip(),
            "kickoff_ts": _as_ts(raw.get("kickoff_ts")),
            "home_team": str(raw.get("home_team") or "").strip(),
            "away_team": str(raw.get("away_team") or "").strip(),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "played": played,
            "venue": str(raw.get("venue") or "").strip(),
            "venue_name": _optional_str(clean_venue(raw.get("venue"))),
            "city": _optional_str(raw.get("city")),
            "state": _optional_str(raw.get("state")),
            "is_playoff": _as_bool(raw.get("is_playoff")),
            "playoff_scope": _optional_str(raw.get("playoff_scope")),
            "playoff_stage": _optional_str(raw.get("playoff_stage")),
            "is_interconference": _as_bool(raw.get("is_interconference")),
            "match_url": str(raw.get("match_url") or "").strip(),
        }
        rows.append(row)

    rows.sort(key=lambda r: (r["date"], r["time"], r["home_team"], r["away_team"]))
    payload = {
        "league": "UPSL",
        "division": division,
        "season": season,
        "match_count": len(rows),
        "matches": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def export_standings(
    *,
    division: str = DEFAULT_DIVISION,
    season: str = "all",
    out_path: Path = DEFAULT_STANDINGS_OUT,
) -> Path:
    df = load_standings(division, season)
    rows = []
    for raw in df.to_dict(orient="records"):
        team = _optional_str(raw.get("team"))
        if not team:
            continue
        row_season = _optional_str(raw.get("season"))
        if not row_season and season and str(season).lower() != "all":
            row_season = season
        rows.append(
            {
                "league": "UPSL",
                "division": division,
                "season": row_season or "Unknown",
                "conference": _optional_str(raw.get("conference")) or "Unknown",
                "conference_id": str(raw.get("conference_id") or ""),
                "place": _as_goal(raw.get("place")),
                "team": team,
                "gp": _as_goal(raw.get("gp")) or 0,
                "wins": _as_goal(raw.get("wins")) or 0,
                "draws": _as_goal(raw.get("draws")) or 0,
                "losses": _as_goal(raw.get("losses")) or 0,
                "gf": _as_goal(raw.get("gf")) or 0,
                "ga": _as_goal(raw.get("ga")) or 0,
                "gd": _as_goal(raw.get("gd")) or 0,
                "pts": _as_goal(raw.get("pts")) or 0,
            }
        )
    rows.sort(
        key=lambda r: (
            r["conference"],
            r["place"] if r["place"] is not None else 999,
            r["team"],
        )
    )
    payload = {
        "league": "UPSL",
        "division": division,
        "season": season,
        "row_count": len(rows),
        "standings": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export UPSL matches for the frontend")
    parser.add_argument("--division", default=DEFAULT_DIVISION)
    parser.add_argument(
        "--season",
        default="all",
        help='Season name, or "all" (default) for every scraped season',
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSON path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)
    path = export_matches(division=args.division, season=args.season, out_path=args.out)
    standings_path = export_standings(division=args.division, season=args.season)
    print(f"Wrote {path}")
    print(f"Wrote {standings_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
