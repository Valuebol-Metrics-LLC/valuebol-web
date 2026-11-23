"""Scrape UPSL schedule + standings into local parquet files.

Divisions live on separate subdomains (premier / division1 / …). Schedule pages
embed the full season table and filter client-side, so matches are parsed from
row markup (`data-team-conference-id`). Standings use
`?conference=&season=` and are usually server-scoped.

Default: all Premier conferences, 2026 Spring.

Usage (from pipeline/ with venv active):
    python -m upsl.fetch
    python -m upsl.fetch --division premier --season "2026 Spring"
    python -m upsl.fetch --division division1 --conference "Midwest Central"
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

DIVISION_BASES = {
    "premier": "https://premier.upsl.com",
    "division1": "https://division1.upsl.com",
    "division2": "https://division2.upsl.com",
    "women": "https://women.upsl.com",
    "academy": "https://academy.upsl.com",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DIVISION = "premier"
DEFAULT_SEASON = "2026 Spring"


@dataclass(frozen=True)
class Conference:
    conference: str
    conference_id: str
    slug: str


@dataclass(frozen=True)
class Season:
    season: str
    season_id: str


@dataclass(frozen=True)
class DivisionScope:
    division: str
    base_url: str
    season: Season
    conferences: tuple[Conference, ...]


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "x"


def _get(url: str, *, sleep_s: float = 0.75, cache_path: Path | None = None) -> str:
    if cache_path and cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    if sleep_s:
        time.sleep(sleep_s)
    resp = requests.get(url, headers=HEADERS, timeout=90)
    resp.raise_for_status()
    text = resp.text
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return text


def list_seasons(
    division: str,
    *,
    cache_dir: Path | None = None,
) -> list[Season]:
    """Return seasons advertised on the division schedule index (newest first)."""
    if division not in DIVISION_BASES:
        raise ValueError(
            f"Unknown division {division!r}; choose from {sorted(DIVISION_BASES)}"
        )
    base = DIVISION_BASES[division]
    schedule_url = f"{base}/schedule/"
    cache = (cache_dir / f"{division}_schedule_index.html") if cache_dir else None
    html = _get(schedule_url, cache_path=cache)
    soup = BeautifulSoup(html, "html.parser")
    seasons: list[Season] = []
    seen: set[str] = set()
    for el in soup.select("[data-season-id]"):
        sid = str(el.get("data-season-id") or "").strip()
        name = (el.get("data-season-name") or el.get_text(strip=True) or "").strip()
        if not sid or not name or sid in seen:
            continue
        seen.add(sid)
        seasons.append(Season(season=name, season_id=sid))
    return seasons


def discover_division_scope(
    division: str,
    season_name: str,
    *,
    conference_name: str | None = None,
    cache_dir: Path | None = None,
) -> DivisionScope:
    """Resolve season + conference list for a division subdomain."""
    if division not in DIVISION_BASES:
        raise ValueError(
            f"Unknown division {division!r}; choose from {sorted(DIVISION_BASES)}"
        )
    base = DIVISION_BASES[division]
    schedule_url = f"{base}/schedule/"
    cache = (cache_dir / f"{division}_schedule_index.html") if cache_dir else None
    html = _get(schedule_url, cache_path=cache)
    soup = BeautifulSoup(html, "html.parser")

    season_id = None
    for el in soup.select("[data-season-id]"):
        label = el.get("data-season-name") or el.get_text(strip=True)
        if label == season_name:
            season_id = el.get("data-season-id")
            break
    if not season_id:
        raise RuntimeError(f"Season not found on {schedule_url}: {season_name!r}")

    conferences: list[Conference] = []
    seen: set[str] = set()
    for el in soup.select("[data-conference-id][data-conference-name]"):
        cid = el.get("data-conference-id")
        name = el.get("data-conference-name")
        slug = el.get("data-conference") or ""
        if not cid or cid == "false" or not name or name == "*":
            continue
        if cid in seen:
            continue
        seen.add(cid)
        conferences.append(Conference(conference=name, conference_id=str(cid), slug=slug))

    if conference_name:
        conferences = [c for c in conferences if c.conference == conference_name]
        if not conferences:
            raise RuntimeError(
                f"Conference {conference_name!r} not found on {schedule_url}"
            )

    conferences.sort(key=lambda c: c.conference.lower())
    return DivisionScope(
        division=division,
        base_url=base,
        season=Season(season=season_name, season_id=str(season_id)),
        conferences=tuple(conferences),
    )


def _parse_score(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text or text in {"-", "—", "TBD", "tbd"}:
        return None
    if not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def _parse_kickoff_ts(td) -> int | None:
    """Kickoff unix seconds from schedule time cell (`attr-time`), if present."""
    raw = td.get("attr-time") if td is not None else None
    if raw is None:
        return None
    text = str(raw).strip()
    if not text.isdigit():
        return None
    return int(text)


def _resolve_played(
    home_goals: int | None,
    away_goals: int | None,
    *,
    kickoff_ts: int | None,
    date_sort: int | None,
    now_ts: float | None = None,
) -> tuple[bool, int | None, int | None]:
    """UPSL often puts placeholder 0-0 in score cells before kickoff.

    Treat 0-0 as unplayed when kickoff (or date_sort fallback) is still in the
    future; otherwise keep numeric scores as a completed result.
    """
    if home_goals is None or away_goals is None:
        return False, None, None

    now = time.time() if now_ts is None else now_ts
    event_ts = kickoff_ts if kickoff_ts is not None else date_sort
    if (
        home_goals == 0
        and away_goals == 0
        and event_ts is not None
        and event_ts > now
    ):
        return False, None, None

    return True, home_goals, away_goals


_PLAYOFF_URL_RE = re.compile(
    r"playoff|semi(?:[-_]?final)?|(?:^|/)(?:s1|s2|q\d|final)(?:-|/|$)",
    re.I,
)

# Post-conference national ladder (not interlocking conference brackets).
_NATIONAL_URL_RE = re.compile(
    r"(?:^|/)(?:r32|r16|r8)(?:[-/]|$)|(?:^|/)(?:east|west|central|southeast|southwest|"
    r"midwest|south|north)-region-final|"
    r"national-(?:final|championship|semifinal|quarterfinal)",
    re.I,
)
_NATIONAL_STAGE_RE = re.compile(
    r"national\s+round\s+of\s+\d+|national\s+(?:final|championship|semifinal|quarterfinal)|"
    r"(?:east|west|central|southeast|southwest|midwest|south|north)\s+region\s+final",
    re.I,
)


def _is_playoff(match_url: str, venue: str) -> bool:
    if _PLAYOFF_URL_RE.search(match_url or ""):
        return True
    return bool(re.search(r"playoff|semi(?:[- ]?final)?|\bfinal\b", venue or "", re.I))


def _venue_stage_suffix(venue: str) -> str | None:
    """UPSL often appends '| National Round of 16' / '| East Region Final'."""
    text = (venue or "").strip()
    if "|" not in text:
        return None
    suffix = text.rsplit("|", 1)[-1].strip()
    return suffix or None


def _stage_from_match_url(match_url: str) -> str | None:
    slug = (match_url or "").rstrip("/").split("/")[-1].lower()
    if not slug:
        return None
    if re.search(r"(?:^|-)r32(?:-|$)", slug):
        return "National Round of 32"
    if re.search(r"(?:^|-)r16(?:-|$)", slug):
        return "National Round of 16"
    if re.search(r"(?:^|-)r8(?:-|$)", slug):
        return "National Round of 8"
    m = re.search(
        r"(east|west|central|southeast|southwest|midwest|south|north)-region-final",
        slug,
    )
    if m:
        return f"{m.group(1).replace('-', ' ').title()} Region Final"
    if "national-final" in slug or "national-championship" in slug:
        return "National Final"
    return None


def _classify_playoff(
    match_url: str, venue: str, *, is_playoff: bool
) -> tuple[str | None, str | None]:
    """Return (playoff_scope, playoff_stage).

    - conference: in-conference / interlocking conference brackets
    - national: national rounds + region finals
    """
    if not is_playoff:
        return None, None

    suffix = _venue_stage_suffix(venue)
    if suffix and _NATIONAL_STAGE_RE.search(suffix):
        # Normalize spacing/casing from the venue label.
        return "national", " ".join(suffix.split())

    url_stage = _stage_from_match_url(match_url)
    if url_stage or _NATIONAL_URL_RE.search(match_url or ""):
        return "national", url_stage or suffix or "National Playoffs"

    return "conference", None


def scrape_schedule_all(
    scope: DivisionScope,
    *,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Parse all matches for the season from one schedule page.

    Keeps inter-conference league games (common in DMV / Virginia). Each row
    stores home and away conference ids; `conference` is the home team's.
    """
    url = f"{scope.base_url}/schedule/?season={scope.season.season_id}"
    cache = None
    if cache_dir:
        cache = cache_dir / f"{scope.division}_schedule_{scope.season.season_id}.html"
    html = _get(url, cache_path=cache)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_=re.compile(r"schedule"))
    if table is None:
        table = soup.find("table")
    if table is None:
        raise RuntimeError("No schedule table found in UPSL HTML")

    # If the user scoped to one conference, keep games involving that conference
    # (including inter-conference opponents) so standings reconstruction is complete.
    single = len(scope.conferences) == 1
    focus_id = scope.conferences[0].conference_id if single else None

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 7:
            continue

        home_a = tds[0].find("a", attrs={"data-team-conference-id": True})
        away_a = tds[1].find("a", attrs={"data-team-conference-id": True})
        if not home_a or not away_a:
            continue

        home_cid = str(home_a.get("data-team-conference-id") or "")
        away_cid = str(away_a.get("data-team-conference-id") or "")
        home_cname = home_a.get("data-team-conference") or ""
        away_cname = away_a.get("data-team-conference") or ""
        if not home_cid or not away_cid:
            continue

        if single and focus_id not in {home_cid, away_cid}:
            continue

        match_url = home_a.get("href") or away_a.get("href") or ""
        date_sort_raw = tds[2].get("data-sort")
        date_sort = (
            int(date_sort_raw)
            if date_sort_raw and str(date_sort_raw).isdigit()
            else None
        )
        kickoff_ts = _parse_kickoff_ts(tds[3])
        raw_home = _parse_score(tds[4].get_text(strip=True))
        raw_away = _parse_score(tds[5].get_text(strip=True))
        played, home_goals, away_goals = _resolve_played(
            raw_home,
            raw_away,
            kickoff_ts=kickoff_ts,
            date_sort=date_sort,
        )
        venue = tds[6].get_text(strip=True)
        is_playoff = _is_playoff(match_url, venue)
        playoff_scope, playoff_stage = _classify_playoff(
            match_url, venue, is_playoff=is_playoff
        )

        rows.append(
            {
                "division": scope.division,
                "season": scope.season.season,
                "season_id": scope.season.season_id,
                "conference": home_cname,
                "conference_id": home_cid,
                "conference_slug": slugify(home_cname) if home_cname else "",
                "away_conference": away_cname,
                "away_conference_id": away_cid,
                "is_interconference": home_cid != away_cid,
                "date": tds[2].get_text(strip=True),
                "date_sort": date_sort,
                "kickoff_ts": kickoff_ts,
                "time": tds[3].get_text(strip=True),
                "home_team": home_a.get_text(strip=True),
                "away_team": away_a.get_text(strip=True),
                "home_goals": home_goals,
                "away_goals": away_goals,
                "played": played,
                "venue": venue,
                "city": tds[8].get_text(strip=True) if len(tds) > 8 else "",
                "state": tds[9].get_text(strip=True) if len(tds) > 9 else "",
                "match_url": match_url,
                "is_playoff": is_playoff,
                "playoff_scope": playoff_scope,
                "playoff_stage": playoff_stage,
                "source_url": url,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    return df.sort_values(
        by=["conference", "date_sort", "date", "home_team", "away_team"],
        ascending=True,
        kind="mergesort",
    ).reset_index(drop=True)


def scrape_standings_one(
    scope: DivisionScope,
    conf: Conference,
    *,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Return standings for one conference, or empty if the page has no table."""
    url = (
        f"{scope.base_url}/standings/"
        f"?conference={conf.conference_id}&season={scope.season.season_id}"
    )
    cache = None
    if cache_dir:
        cache = (
            cache_dir
            / f"{scope.division}_standings_{conf.conference_id}_{scope.season.season_id}.html"
        )
    html = _get(url, cache_path=cache)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()

    raw = pd.read_html(io.StringIO(str(table)))[0].copy()
    rename = {
        "P": "place",
        "Team": "team",
        "GP": "gp",
        "W": "wins",
        "D": "draws",
        "L": "losses",
        "GF": "gf",
        "GA": "ga",
        "GD": "gd",
        "PTS": "pts",
        "PTSP": "pts",
    }
    raw = raw.rename(columns={c: rename.get(str(c).strip(), str(c).strip()) for c in raw.columns})
    keep = ["place", "team", "gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]
    missing = [c for c in keep if c not in raw.columns]
    if missing:
        raise RuntimeError(
            f"Standings missing columns {missing} for {conf.conference}; got {list(raw.columns)}"
        )

    out = raw[keep].copy()
    out.insert(0, "division", scope.division)
    out.insert(1, "season", scope.season.season)
    out.insert(2, "season_id", scope.season.season_id)
    out.insert(3, "conference", conf.conference)
    out.insert(4, "conference_id", conf.conference_id)
    out.insert(5, "conference_slug", conf.slug)
    out["source_url"] = url
    out = out[out["team"].notna() & (out["team"].astype(str).str.strip() != "")]
    return out.reset_index(drop=True)


def scrape_standings_all(
    scope: DivisionScope,
    *,
    conference_ids: set[str] | None = None,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    skipped: list[str] = []
    for conf in scope.conferences:
        if conference_ids is not None and conf.conference_id not in conference_ids:
            continue
        print(f"  standings: {conf.conference} ({conf.conference_id})")
        try:
            df = scrape_standings_one(scope, conf, cache_dir=cache_dir)
        except Exception as exc:
            print(f"    ERROR: {exc}")
            skipped.append(conf.conference)
            continue
        if df.empty:
            print("    (no table — skipped)")
            skipped.append(conf.conference)
            continue
        print(f"    teams={len(df)}")
        frames.append(df)

    if skipped:
        print(f"  skipped {len(skipped)} conferences with no/usable standings")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def reconstruct_table(matches: pd.DataFrame) -> pd.DataFrame:
    """Build W/D/L / GF/GA / PTS from completed non-playoff matches."""
    played = matches[matches["played"] & ~matches["is_playoff"]].copy()
    if played.empty:
        return pd.DataFrame(
            columns=["team", "gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]
        )

    teams = sorted(set(played["home_team"]) | set(played["away_team"]))
    rows = []
    for team in teams:
        home = played[played["home_team"] == team]
        away = played[played["away_team"] == team]
        gf = int(home["home_goals"].sum() + away["away_goals"].sum())
        ga = int(home["away_goals"].sum() + away["home_goals"].sum())
        wins = int(
            ((home["home_goals"] > home["away_goals"]).sum())
            + ((away["away_goals"] > away["home_goals"]).sum())
        )
        draws = int(
            ((home["home_goals"] == home["away_goals"]).sum())
            + ((away["away_goals"] == away["home_goals"]).sum())
        )
        losses = int(
            ((home["home_goals"] < home["away_goals"]).sum())
            + ((away["away_goals"] < away["home_goals"]).sum())
        )
        gp = wins + draws + losses
        rows.append(
            {
                "team": team,
                "gp": gp,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "gf": gf,
                "ga": ga,
                "gd": gf - ga,
                "pts": 3 * wins + draws,
            }
        )
    return pd.DataFrame(rows).sort_values(
        by=["pts", "gd", "gf", "team"], ascending=[False, False, False, True]
    ).reset_index(drop=True)


def matches_for_conference(matches: pd.DataFrame, conf_id: str) -> pd.DataFrame:
    """Matches that count for a conference (home or away team in that conference)."""
    conf_id = str(conf_id)
    if "away_conference_id" in matches.columns:
        return matches[
            (matches["conference_id"].astype(str) == conf_id)
            | (matches["away_conference_id"].astype(str) == conf_id)
        ].copy()
    return matches[matches["conference_id"].astype(str) == conf_id].copy()


def validate_against_standings(
    matches: pd.DataFrame, standings: pd.DataFrame
) -> pd.DataFrame:
    """Per-conference checksum of reconstructed records vs official standings."""
    if matches.empty or standings.empty:
        return pd.DataFrame()

    parts: list[pd.DataFrame] = []
    for conf_id, st in standings.groupby("conference_id", sort=False):
        conf_name = st["conference"].iloc[0]
        m = matches_for_conference(matches, str(conf_id))
        recon = reconstruct_table(m)
        official = st[
            ["team", "gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]
        ].copy()
        for col in ["gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]:
            official[col] = pd.to_numeric(official[col], errors="coerce").astype("Int64")
            if not recon.empty:
                recon[col] = pd.to_numeric(recon[col], errors="coerce").astype("Int64")

        # Left-join on official standings teams only (inter-conference opponents
        # should not appear as "missing" rows in this conference's checksum).
        merged = official.merge(
            recon, on="team", how="left", suffixes=("_official", "_recon")
        )
        for col in ["gp", "wins", "draws", "losses", "gf", "ga", "gd", "pts"]:
            merged[f"{col}_match"] = merged[f"{col}_official"] == merged[f"{col}_recon"]
        record_cols = ["gp", "wins", "draws", "losses", "gf", "ga", "gd"]
        merged["record_match"] = merged[[f"{c}_match" for c in record_cols]].all(axis=1)
        merged["all_match"] = merged["record_match"] & merged["pts_match"]
        merged["pts_delta"] = merged["pts_official"] - merged["pts_recon"]
        merged.insert(0, "conference", conf_name)
        merged.insert(1, "conference_id", conf_id)
        parts.append(merged)

    return pd.concat(parts, ignore_index=True).sort_values(
        ["conference", "team"]
    ).reset_index(drop=True)


def _coalesce_nonempty_frame(
    path: Path, new_df: pd.DataFrame, *, label: str
) -> tuple[pd.DataFrame, bool]:
    """Prefer new data; if empty, keep an existing non-empty parquet at path."""
    if new_df is not None and len(new_df) > 0:
        return new_df, False
    if path.exists():
        try:
            old = pd.read_parquet(path)
            if len(old) > 0:
                return old, True
        except Exception as exc:  # noqa: BLE001 — fall through to empty write
            print(f"  warning: could not read existing {label} at {path}: {exc}")
    if new_df is None:
        return pd.DataFrame(), False
    return new_df, False


def write_outputs(
    scope: DivisionScope,
    matches: pd.DataFrame,
    standings: pd.DataFrame,
    validation: pd.DataFrame,
) -> dict[str, Path]:
    season_slug = slugify(scope.season.season)
    root = DATA_DIR / scope.division / f"season={season_slug}"
    meta_dir = DATA_DIR / scope.division / "meta"
    root.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "matches": root / "matches.parquet",
        "standings": root / "standings.parquet",
        "validation": root / "validation.parquet",
        "matches_csv": root / "matches.csv",
        "standings_csv": root / "standings.csv",
        "validation_csv": root / "validation.csv",
        "conferences": meta_dir / f"conferences_{season_slug}.parquet",
        "seasons": meta_dir / "seasons.parquet",
    }

    matches.to_parquet(paths["matches"], index=False)
    matches.to_csv(paths["matches_csv"], index=False)

    # Never clobber good standings/validation with empty frames (e.g. --skip-standings).
    standings_out, standings_preserved = _coalesce_nonempty_frame(
        paths["standings"], standings, label="standings"
    )
    validation_out, _ = _coalesce_nonempty_frame(
        paths["validation"], validation, label="validation"
    )
    standings_out.to_parquet(paths["standings"], index=False)
    validation_out.to_parquet(paths["validation"], index=False)
    standings_out.to_csv(paths["standings_csv"], index=False)
    validation_out.to_csv(paths["validation_csv"], index=False)
    standings = standings_out
    validation = validation_out
    if standings_preserved:
        print(
            f"  preserved existing standings ({len(standings)} rows); "
            "refused empty overwrite"
        )

    conf_df = pd.DataFrame([asdict(c) for c in scope.conferences])
    conf_df.insert(0, "division", scope.division)
    conf_df.insert(1, "season", scope.season.season)
    conf_df.insert(2, "season_id", scope.season.season_id)
    conf_df.to_parquet(paths["conferences"], index=False)

    season_row = pd.DataFrame(
        [
            {
                "division": scope.division,
                "season": scope.season.season,
                "season_id": scope.season.season_id,
            }
        ]
    )
    seasons_path = paths["seasons"]
    if seasons_path.exists():
        prev = pd.read_parquet(seasons_path)
        season_row = (
            pd.concat([prev, season_row], ignore_index=True)
            .drop_duplicates(subset=["division", "season_id"], keep="last")
            .reset_index(drop=True)
        )
    season_row.to_parquet(seasons_path, index=False)

    summary = {
        "division": scope.division,
        "season": scope.season.season,
        "season_id": scope.season.season_id,
        "conferences_listed": len(scope.conferences),
        "matches": int(len(matches)),
        "played": int(matches["played"].sum()) if len(matches) else 0,
        "playoff_flagged": int(matches["is_playoff"].sum()) if len(matches) else 0,
        "standings_rows": int(len(standings)),
        "standings_conferences": int(standings["conference_id"].nunique())
        if len(standings)
        else 0,
    }
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths["summary"] = summary_path
    return paths


def run_scrape(
    *,
    division: str,
    season: str,
    conference: str | None = None,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
    skip_standings: bool = False,
) -> int:
    """Scrape one division/season. Returns process exit code (0/1/2)."""
    print(f"Discovering {division!r} / {season!r} …")
    scope = discover_division_scope(
        division,
        season,
        conference_name=conference,
        cache_dir=cache_dir,
    )
    print(
        f"  base={scope.base_url}  season_id={scope.season.season_id}  "
        f"conferences={len(scope.conferences)}"
    )
    for c in scope.conferences:
        print(f"    - {c.conference_id:>4}  {c.conference}")

    if refresh_cache and cache_dir:
        patterns = [
            f"{scope.division}_schedule_{scope.season.season_id}.html",
            f"{scope.division}_schedule_index.html",
        ]
        for conf in scope.conferences:
            patterns.append(
                f"{scope.division}_standings_{conf.conference_id}_{scope.season.season_id}.html"
            )
        for name in patterns:
            path = cache_dir / name
            if path.exists():
                path.unlink()

    print("Scraping schedule (all conferences in one page)…")
    matches = scrape_schedule_all(scope, cache_dir=cache_dir)
    active_ids: set[str] = set()
    if len(matches):
        active_ids |= set(matches["conference_id"].astype(str))
        if "away_conference_id" in matches.columns:
            active_ids |= set(matches["away_conference_id"].astype(str))
    inter = (
        int(matches["is_interconference"].sum())
        if len(matches) and "is_interconference" in matches.columns
        else 0
    )
    print(
        f"  matches={len(matches)}  played={int(matches['played'].sum()) if len(matches) else 0}  "
        f"playoff_flagged={int(matches['is_playoff'].sum()) if len(matches) else 0}  "
        f"interconference={inter}  conferences_with_matches={len(active_ids)}"
    )

    # Extend scope conferences with any ids discovered only on match rows
    # (e.g. DMV South) so standings can be fetched for them too.
    known = {c.conference_id: c for c in scope.conferences}
    if len(matches):
        for _, row in (
            matches[["conference_id", "conference", "conference_slug"]]
            .drop_duplicates()
            .iterrows()
        ):
            cid = str(row["conference_id"])
            if cid and cid not in known and row["conference"]:
                known[cid] = Conference(
                    conference=str(row["conference"]),
                    conference_id=cid,
                    slug=str(row.get("conference_slug") or slugify(str(row["conference"]))),
                )
        if "away_conference_id" in matches.columns:
            for _, row in (
                matches[["away_conference_id", "away_conference"]]
                .drop_duplicates()
                .iterrows()
            ):
                cid = str(row["away_conference_id"])
                name = str(row["away_conference"] or "")
                if cid and cid not in known and name:
                    known[cid] = Conference(
                        conference=name, conference_id=cid, slug=slugify(name)
                    )
    scope = DivisionScope(
        division=scope.division,
        base_url=scope.base_url,
        season=scope.season,
        conferences=tuple(sorted(known.values(), key=lambda c: c.conference.lower())),
    )

    if skip_standings:
        print("Skipping standings (--skip-standings)")
        standings = pd.DataFrame()
        validation = pd.DataFrame()
        n_record = n_tot = 0
    else:
        print("Scraping standings (per conference with matches)…")
        standings = scrape_standings_all(
            scope, conference_ids=active_ids or None, cache_dir=cache_dir
        )
        print(
            f"  standings rows={len(standings)}  "
            f"conferences={standings['conference_id'].nunique() if len(standings) else 0}"
        )

        print("Validating per conference…")
        validation = validate_against_standings(matches, standings)
        if validation.empty:
            print("  (no validation rows)")
            n_record = n_tot = 0
        else:
            n_record = int(validation["record_match"].fillna(False).sum())
            n_all = int(validation["all_match"].fillna(False).sum())
            n_tot = len(validation)
            print(f"  record match (W/D/L/GF/GA): {n_record}/{n_tot}")
            print(f"  full match (incl. PTS):     {n_all}/{n_tot}")

            by_conf = (
                validation.groupby("conference", sort=True)["record_match"]
                .agg(ok=lambda s: int(s.fillna(False).sum()), n="count")
                .reset_index()
            )
            by_conf["ok"] = by_conf["ok"].astype(int)
            bad_confs = by_conf[by_conf["ok"] != by_conf["n"]]
            if len(bad_confs):
                print("  conferences with record mismatches:")
                print(bad_confs.to_string(index=False))
                bad = validation[~validation["record_match"].fillna(False)]
                cols = [
                    "conference",
                    "team",
                    "gp_official",
                    "gp_recon",
                    "wins_official",
                    "wins_recon",
                    "pts_official",
                    "pts_recon",
                ]
                print(bad[cols].head(40).to_string(index=False))
            deductions = validation[
                validation["record_match"].fillna(False)
                & ~validation["pts_match"].fillna(False)
            ]
            if len(deductions):
                print(f"  point deltas (likely deductions): {len(deductions)} teams")
                print(
                    deductions[
                        ["conference", "team", "pts_official", "pts_recon", "pts_delta"]
                    ]
                    .head(20)
                    .to_string(index=False)
                )

    paths = write_outputs(scope, matches, standings, validation)
    print("Wrote:")
    for key, path in paths.items():
        print(f"  {key}: {path}")

    if skip_standings:
        return 0 if len(matches) else 1

    # Fail only when record mismatch rate is material. Small residuals can come
    # from voided/replayed fixtures still listed on the schedule (e.g. OK-AR).
    if n_tot == 0:
        return 1
    if n_record == n_tot:
        return 0
    pct = n_record / n_tot
    if pct >= 0.98:
        print(f"  warning: {n_tot - n_record} residual record mismatches ({pct:.1%} ok)")
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape UPSL schedule + standings")
    parser.add_argument(
        "--division",
        default=DEFAULT_DIVISION,
        choices=sorted(DIVISION_BASES),
        help="UPSL division subdomain (default: premier)",
    )
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument(
        "--all-seasons",
        action="store_true",
        help="Scrape every season listed on the schedule index",
    )
    parser.add_argument(
        "--conference",
        default=None,
        help="Optional single conference name; default is all conferences",
    )
    parser.add_argument(
        "--skip-standings",
        action="store_true",
        help="Only scrape schedule/matches (faster for historical bulk pulls)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore/overwrite cached HTML under data/raw_html/",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Delete matching cache files before fetching",
    )
    args = parser.parse_args(argv)

    cache_dir = None if args.no_cache else DATA_DIR / "raw_html"

    if args.all_seasons:
        seasons = list_seasons(args.division, cache_dir=cache_dir)
        print(f"All seasons ({len(seasons)}):")
        for s in seasons:
            print(f"  {s.season_id:>4}  {s.season}")
        worst = 0
        for s in seasons:
            code = run_scrape(
                division=args.division,
                season=s.season,
                conference=args.conference,
                cache_dir=cache_dir,
                refresh_cache=args.refresh_cache,
                skip_standings=args.skip_standings,
            )
            worst = max(worst, code)
            print(f"--- finished {s.season!r} exit={code} ---")
        return worst

    return run_scrape(
        division=args.division,
        season=args.season,
        conference=args.conference,
        cache_dir=cache_dir,
        refresh_cache=args.refresh_cache,
        skip_standings=args.skip_standings,
    )


if __name__ == "__main__":
    sys.exit(main())
