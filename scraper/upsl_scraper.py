"""UPSL scraper for the Valuebol site.

Built on the approach in egudino20/UPSL-Webscraper: read every club card on
premier.upsl.com/teams/, then visit each club's page. On top of rosters and
results it collects each club's logo and its website / Instagram / Facebook / X
links, and covers every conference instead of one.

Plain requests + BeautifulSoup is tried first (fast, works in GitHub Actions).
Pass --selenium to load pages in Chrome instead if upsl.com starts rendering
with JavaScript.

Usage
  python scraper/upsl_scraper.py teams       # club list + logos + links
  python scraper/upsl_scraper.py rosters     # players per club
  python scraper/upsl_scraper.py results     # every result on every club page
  python scraper/upsl_scraper.py all         # all of the above
Options
  --limit N        only the first N clubs (for testing)
  --only premier   only clubs on that UPSL subdomain (premier, division1, women, ...)
  --refresh        re-download pages and logos even if cached
  --selenium       use Chrome via Selenium instead of requests

Outputs (paths relative to the repo root)
  public/logos/<slug>.png         square 256 px logos, transparent padding
  src/data/upsl/teams.json        one record per club, read by the site
  src/data/upsl/rosters.json      players per club
  src/data/upsl/results.csv       one row per match (deduplicated)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scraper" / ".cache"
LOGO_DIR = ROOT / "public" / "logos"
DATA_DIR = ROOT / "src" / "data" / "upsl"
TEAMS_URL = "https://premier.upsl.com/teams/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DELAY = 0.8  # seconds between requests, to be polite to upsl.com
LOGO_SIZE = 256
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR".split())

# Handles that belong to the league or to post links, not to a club.
LEAGUE_HANDLES = {"upslsoccer", "upsl", "upslwomen", "upslacademy", "p", "reel", "reels", "explore", "accounts", "stories", "tv"}
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com", "tiktok.com", "youtube.com", "youtu.be")
NOT_A_WEBSITE = SOCIAL_HOSTS + ("upsl.com", "upslsoccer", "google.", "goo.gl", "apple.com", "wa.me", "mailto:", "tel:", "linktr.ee/upsl")


# ---------------------------------------------------------------- helpers

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fix_upsl_url(url: str) -> str:
    """Some club links on upsl.com are missing the dot (division1upsl.com, premierupsl.com)."""
    return re.sub(r"//(premier|division1|women|academy|academyboys|academygirls)upsl\.com", r"//\1.upsl.com", url)


def subdomain(url: str) -> str:
    host = urlparse(url).netloc
    return host.split(".")[0] if host.endswith("upsl.com") else host


class Fetcher:
    def __init__(self, use_selenium: bool = False, refresh: bool = False):
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        self.driver = None
        if use_selenium:
            from selenium import webdriver  # imported only when asked for
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_argument("--headless=new")
            opts.add_argument(f"user-agent={UA}")
            self.driver = webdriver.Chrome(options=opts)
        CACHE.mkdir(parents=True, exist_ok=True)
        self._last = 0.0

    def _wait(self):
        gap = time.time() - self._last
        if gap < DELAY:
            time.sleep(DELAY - gap)
        self._last = time.time()

    def html(self, url: str) -> str:
        key = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")
        if key.exists() and not self.refresh:
            return key.read_text(encoding="utf-8", errors="ignore")
        self._wait()
        if self.driver:
            self.driver.get(url)
            time.sleep(2)
            text = self.driver.page_source
        else:
            for attempt in range(3):
                try:
                    r = self.session.get(url, timeout=30)
                    r.raise_for_status()
                    text = r.text
                    break
                except requests.RequestException as e:
                    if attempt == 2:
                        raise
                    print(f"  retry {url}: {e}", file=sys.stderr)
                    time.sleep(3 * (attempt + 1))
        key.write_text(text, encoding="utf-8")
        return text

    def binary(self, url: str) -> bytes | None:
        self._wait()
        try:
            r = self.session.get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            print(f"  logo download failed {url}: {e}", file=sys.stderr)
            return None

    def close(self):
        if self.driver:
            self.driver.quit()


# ---------------------------------------------------------------- parsing

def img_url(tag, base: str) -> str | None:
    """Best image URL from an <img> (handles lazy-loading and srcset) or a CSS background."""
    if tag is None:
        return None
    if tag.name == "img":
        srcset = tag.get("data-srcset") or tag.get("srcset")
        if srcset:
            # pick the widest candidate
            best = max(
                (c.strip().split(" ") for c in srcset.split(",") if c.strip()),
                key=lambda p: int(re.sub(r"\D", "", p[1]) or 0) if len(p) > 1 else 0,
            )
            return urljoin(base, best[0])
        for attr in ("data-src", "data-lazy-src", "data-original", "src"):
            v = tag.get(attr)
            if v and not v.startswith("data:"):
                return urljoin(base, v)
    style = tag.get("style") or ""
    m = re.search(r"url\(['\"]?([^'\")]+)", style)
    return urljoin(base, m.group(1)) if m else None


def parse_team_cards(html: str, base: str = TEAMS_URL) -> list[dict]:
    """Club cards on the /teams/ page (same selectors as UPSL-Webscraper)."""
    soup = BeautifulSoup(html, "html.parser")
    teams = []
    for card in soup.select("div.teams__card--container"):
        name = (card.get("data-team-name") or "").strip()
        a = card.find("a", href=True)
        if not name or not a:
            continue
        logo_tag = card.find("img") or card.find(style=re.compile("background-image"))
        teams.append({
            "id": (card.get("data-team-id") or "").strip(),
            "name": name,
            "conference": (card.get("data-team-conference") or "").strip(),
            "upsl": fix_upsl_url(urljoin(base, a["href"])),
            "card_logo": img_url(logo_tag, base),
        })
    return teams


def _header_region(soup):
    """The part of a club page that describes the club (not the site header/footer)."""
    for sel in ("[class*='single-team__header']", "[class*='single-team__hero']", "[class*='single-team__info']",
                "[class*='single-team__top']", "[class*='single-team']"):
        el = soup.select_one(sel)
        if el:
            return el
    return soup.find("main") or soup.body or soup


def parse_team_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    region = _header_region(soup)

    # Logo: an image marked as the logo/crest, then the first image in the club header, then og:image.
    logo = None
    for el in region.select("[class*='logo'], [class*='crest'], [class*='badge']"):
        cand = el if el.name == "img" else el.find("img") or el
        logo = img_url(cand, url)
        if logo:
            break
    if not logo:
        logo = img_url(region.find("img"), url)
    if not logo:
        og = soup.find("meta", property="og:image")
        logo = og["content"] if og and og.get("content") else None

    # Links: look in the club header first; fall back to the page minus site chrome.
    scope = region
    anchors = scope.find_all("a", href=True)
    if not any(h in a["href"] for a in anchors for h in SOCIAL_HOSTS):
        for chrome in soup.select("header, footer, nav"):
            chrome.decompose()
        anchors = soup.find_all("a", href=True)

    links: dict[str, str] = {}
    for a in anchors:
        href = a["href"].strip()
        low = href.lower()
        if "instagram.com" in low and "instagram" not in links:
            m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", href)
            if m and m.group(1).lower().strip(".") not in LEAGUE_HANDLES:
                links["instagram"] = m.group(1).strip(".")
        elif ("facebook.com" in low or "fb.com" in low) and "facebook" not in links and "upsl" not in low:
            links["facebook"] = href
        elif re.search(r"//(www\.)?(twitter|x)\.com/", low) and "twitter" not in links and "upsl" not in low:
            links["twitter"] = href
        elif ("youtube.com" in low or "youtu.be" in low) and "youtube" not in links and "upsl" not in low:
            links["youtube"] = href
        elif low.startswith("http") and "website" not in links and not any(x in low for x in NOT_A_WEBSITE):
            links["website"] = href

    # Location line, if the page shows one (e.g. "Portland, OR").
    city = None
    loc = region.select_one("[class*='location'], [class*='city']")
    if loc:
        city = " ".join(loc.get_text(" ", strip=True).split()) or None
    if not city:  # club pages print it as its own short line, e.g. "Portland,\nOR"
        for el in region.find_all(True):
            txt = " ".join(el.get_text(" ", strip=True).split())
            m = re.fullmatch(r"([A-Za-z.'\- ]{2,30}?)\s*,\s*([A-Z]{2})", txt)
            if m and m.group(2) in US_STATES:
                city = f"{m.group(1).strip()}, {m.group(2)}"
                break

    return {"logo": logo, "city": city, **links}


def parse_roster(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    names = soup.select("span.single-team__roster-player-name")
    pos = soup.select("span.single-team__roster-player-title")
    apps = soup.select("span.single-team__roster-player-appearances")
    out = []
    for i, n in enumerate(names):
        a = apps[i].get_text(" ", strip=True) if i < len(apps) else ""
        out.append({
            "player": " ".join(n.get_text(" ", strip=True).split()),
            "position": pos[i].get_text(strip=True) if i < len(pos) else None,
            "appearances": int(re.sub(r"\D", "", a.split(":")[-1]) or 0) if a else 0,
        })
    return out


def parse_results(html: str) -> list[dict]:
    """Rows of #single-team-schedule. Columns are matched by header name, because the
    table has been Home | Away | Date | H | A | Venue (UPSL-Webscraper, 2024) and
    Home | Away | Date | Time | H | A | Venue (2026). Played games carry upsl__show__results."""
    soup = BeautifulSoup(html, "html.parser")
    season = None
    opts = soup.select("#single__select-season option")
    for o in sorted(opts, key=lambda o: o.has_attr("selected"), reverse=True):  # selected first
        t = o.get_text(strip=True)
        if re.search(r"\d{4}", t):
            season = t
            break
    table = soup.select_one("#single-team-schedule")
    if not table:
        return []
    heads = [th.get_text(" ", strip=True).lower() for th in table.select("thead th")]
    names = {"home": "home", "away": "away", "date": "date", "time": "time", "h": "home_score", "a": "away_score", "venue": "venue"}
    colmap = {i: names[h] for i, h in enumerate(heads) if h in names}
    if not colmap:  # no header: guess from the row length
        layout = ["home", "away", "date", "time", "home_score", "away_score", "venue"]
        sample = table.select_one("tbody tr")
        n = len(sample.find_all("td")) if sample else 0
        if n in (6, 7) and n != 8:
            layout = ["home", "away", "date", "home_score", "away_score", "venue"]
        colmap = dict(enumerate(layout))
    rows = []
    for tr in table.select("tbody tr"):
        td = tr.find_all("td")
        if len(td) < 5:
            continue
        rec = {"season": season, "date": None, "time": None, "home": None, "away": None,
               "home_score": None, "away_score": None, "venue": None}
        for i, field in colmap.items():
            if i < len(td):
                rec[field] = " ".join(td[i].get_text(" ", strip=True).split()) or None
        marker = " ".join(tr.get("class", [])) + " " + " ".join(" ".join(c.get("class", [])) + " " + c.get_text(" ", strip=True) for c in td)
        rec["played"] = "show__results" in marker or ("show__schedule" not in marker and rec["home_score"] not in (None, ""))
        if not rec["played"]:
            rec["home_score"] = rec["away_score"] = None
        if rec["home"] and rec["away"]:
            rows.append(rec)
    return rows


# ---------------------------------------------------------------- logos

def save_logo(data: bytes, dest: Path) -> bool:
    """Square PNG, logo centred on transparent padding. Returns False if it isn't a usable image."""
    try:
        from PIL import Image
    except ImportError:  # Pillow missing: keep the original bytes
        dest.write_bytes(data)
        return True
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return False
    im = im.convert("RGBA")
    if min(im.size) < 24:
        return False
    im.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (LOGO_SIZE, LOGO_SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((LOGO_SIZE - im.width) // 2, (LOGO_SIZE - im.height) // 2), im)
    canvas.save(dest, "PNG", optimize=True)
    return True


# ---------------------------------------------------------------- commands

def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def select(teams, args):
    if getattr(args, "name", None):
        wanted = [n.lower() for n in args.name]
        teams = [t for t in teams if any(w in t["name"].lower() for w in wanted)]
    if args.only:
        teams = [t for t in teams if subdomain(t["upsl"]) == args.only]
    return teams[: args.limit] if args.limit else teams


def cmd_teams(f: Fetcher, args):
    cards = parse_team_cards(f.html(TEAMS_URL))
    if not cards:
        sys.exit("No club cards found on upsl.com/teams. The page layout may have changed, or it now needs --selenium.")
    print(f"{len(cards)} clubs listed on upsl.com")
    old = {t["upsl"]: t for t in load_json(DATA_DIR / "teams.json", [])}
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    out, logo_hashes = [], Counter()

    for i, c in enumerate(select(cards, args), 1):
        print(f"[{i}] {c['name']}")
        try:
            page = parse_team_page(f.html(c["upsl"]), c["upsl"])
        except Exception as e:  # keep going; one bad page shouldn't stop the run
            print(f"  page failed: {e}", file=sys.stderr)
            page = {}
        slug = slugify(c["name"])
        rec = {
            "id": c["id"], "name": c["name"], "slug": slug, "conference": c["conference"],
            "division": subdomain(c["upsl"]), "upsl": c["upsl"],
            **{k: v for k, v in page.items() if k != "logo" and v},
        }
        dest = LOGO_DIR / f"{slug}.png"
        sources = [u for u in dict.fromkeys([page.get("logo"), c.get("card_logo")]) if u]
        if sources and (args.refresh or not dest.exists()):
            for src in sources:  # club page logo first, then the smaller card logo
                data = f.binary(src)
                if data and save_logo(data, dest):
                    rec["logo_source"] = src
                    break
        elif dest.exists():
            rec["logo_source"] = old.get(c["upsl"], {}).get("logo_source", sources[0] if sources else None)
        if dest.exists():
            rec["logo"] = f"logos/{slug}.png"
            logo_hashes[hashlib.md5(dest.read_bytes()).hexdigest()] += 1
        out.append(rec)

    # The same image on many clubs is UPSL's placeholder, not a real logo: drop it.
    placeholders = {h for h, n in logo_hashes.items() if n >= 5}
    dropped = 0
    for rec in out:
        p = ROOT / "public" / rec.get("logo", "-")
        if rec.get("logo") and p.exists() and hashlib.md5(p.read_bytes()).hexdigest() in placeholders:
            p.unlink()
            rec.pop("logo")
            rec.pop("logo_source", None)
            dropped += 1

    # Keep clubs from earlier runs that this (possibly --limit) run didn't touch.
    seen = {r["upsl"] for r in out}
    out += [t for u, t in old.items() if u not in seen]
    out.sort(key=lambda r: (r["conference"], r["name"]))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "teams.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    n_logo = sum(1 for r in out if r.get("logo"))
    n_ig = sum(1 for r in out if r.get("instagram"))
    n_web = sum(1 for r in out if r.get("website"))
    print(f"Saved {len(out)} clubs: {n_logo} logos ({dropped} placeholders dropped), {n_ig} Instagram, {n_web} websites")


def cmd_rosters(f: Fetcher, args):
    teams = select(load_json(DATA_DIR / "teams.json", []), args)
    rosters = load_json(DATA_DIR / "rosters.json", {})
    for i, t in enumerate(teams, 1):
        print(f"[{i}/{len(teams)}] roster {t['name']}")
        try:
            players = parse_roster(f.html(t["upsl"]))
        except Exception as e:
            print(f"  failed: {e}", file=sys.stderr)
            continue
        if players:
            rosters[t["slug"]] = {"club": t["name"], "players": players}
    (DATA_DIR / "rosters.json").write_text(json.dumps(rosters, indent=1, ensure_ascii=False))
    print(f"Saved rosters for {len(rosters)} clubs")


RESULT_COLS = ["division", "conference", "season", "date", "time", "home", "away", "home_score", "away_score", "venue", "played", "source"]


def cmd_results(f: Fetcher, args):
    teams = select(load_json(DATA_DIR / "teams.json", []), args)
    path = DATA_DIR / "results.csv"
    rows: dict[tuple, dict] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows[(r["date"], r["home"], r["away"])] = r
    for i, t in enumerate(teams, 1):
        print(f"[{i}/{len(teams)}] results {t['name']}")
        try:
            games = parse_results(f.html(t["upsl"]))
        except Exception as e:
            print(f"  failed: {e}", file=sys.stderr)
            continue
        for g in games:
            key = (g["date"], g["home"], g["away"])
            # a played row replaces a scheduled one for the same fixture
            if key in rows and rows[key].get("played") in (True, "True") and not g["played"]:
                continue
            rows[key] = {"division": t["division"], "conference": t["conference"], "source": t["upsl"], **g}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: (r["date"] or "", r["home"])):
            w.writerow(r)
    print(f"Saved {len(rows)} matches to {path.relative_to(ROOT)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["teams", "rosters", "results", "all"])
    p.add_argument("--limit", type=int)
    p.add_argument("--only", help="UPSL subdomain, e.g. premier or division1")
    p.add_argument("--name", action="append", help="only clubs whose name contains this (repeatable)")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--selenium", action="store_true")
    args = p.parse_args(argv)

    f = Fetcher(use_selenium=args.selenium, refresh=args.refresh)
    try:
        if args.command in ("teams", "all"):
            cmd_teams(f, args)
            args.refresh = False  # club pages are cached now; reuse them below
            f.refresh = False
        if args.command in ("rosters", "all"):
            cmd_rosters(f, args)
        if args.command in ("results", "all"):
            cmd_results(f, args)
    finally:
        f.close()


if __name__ == "__main__":
    main()
