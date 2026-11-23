# valuebol-web

The new Valuebol Metrics website: UPSL rankings, predictions and stats, written for fans and players, with the full math one tap away.

Same numbers and methods as the current site (ASI, match projections, conference simulations). What changes is how they're shown: every page leads with a plain-English answer, and a **Show the math** button opens the real method for the stats crowd.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build in dist/
```

Built with React + Vite, no other runtime dependencies. Deploys to Vercel as-is (`vercel.json` sends every route to `index.html`).

## Pages

| Route | Page |
| --- | --- |
| `/` | Home: this week's big matches with plain-English odds, top 5, Golden Boot, model accuracy, Instagram |
| `/videos` | UPSL videos from YouTube: live streams, full games and highlights, with thumbnails |
| `/matches` | Beat the model: pick home / draw / away, see if you agree with the model (picks saved in the browser) |
| `/rankings` | Power rankings: ASI explainer, movers, searchable table, follow clubs (saved in the browser) |
| `/who-wins` | Pick any two clubs: "X come out on top in about 7 of 10 meetings", upset stakes, Show the math |
| `/title-race` | Can we still win it? Florida West simulations: chances by club, what-if points calculator |
| `/about` | About us: mission, coverage, who it's for, what's next, Instagram |
| `/contact` | Contact form (opens the visitor's email app, addressed to the team), Instagram DM, email |
| `/methodology` | How the numbers work: each model in one sentence, full method underneath, validation table |
| `/legal` | Copyright & terms: ownership, sharing with credit, data sources and club marks, corrections |

## Live streams and live scores

Each match in the data can carry `stream` (YouTube link), `streamStatus` (`live`, `replay` or `scheduled`) and `liveScore` (`{ home, away, minute }`). Match cards show **Watch live** / **Watch the replay** and the score when those are set. Filling `liveScore` automatically means a backend job that reads the scoreboard from the stream; see the PR notes.

## Before launch

1. **Live numbers.** Rankings and predictions still come from the Nov 21 snapshot. Point `src/lib/data.js` at the real pipeline (see below).
2. **The domain.** The new site runs at valuebol-metrics-llc.github.io/valuebol-web. Moving valuebol-metrics.com onto it replaces the current site, so only do it once the numbers are live. Either add the domain in Vercel (import this repo) or in GitHub Pages settings, then update the DNS records where the domain is registered.

## Where the data comes from

All pages read through `src/lib/data.js`. Right now it returns a **snapshot** of the live site's figures (`src/data/snapshot.js`, as of Nov 21, 2026). To go live, change only `src/lib/data.js` to read from the real pipeline, for example Supabase tables pushed by the Python pipeline, the same pattern as `amateur-football-dashboard`. No page code needs to change.

## Design

- Light and dark mode, switched from the header and remembered per visitor (defaults to the device setting). Both themes live in `src/styles.css` as CSS variables.
- Valuebol LLC logo (option 04), with a white-B version for dark mode.
- Club crests: `src/components/Crest.jsx` shows a club's real logo when a `logoUrl` is provided, otherwise an initials badge.
- Fonts: Barlow Condensed (numbers, headings) and Inter (text), from Google Fonts.

## Next up

Live data from the pipeline, every conference in Title race, Crowd vs the Model voting, player profiles with Instagram share cards, and the community scouts program.

## Clubs, search and match pages

- Press `/` (or the search button / "Clubs" tab on phones) to find any club. Each club has a page at `/club-<name>`.
- Club websites, Instagram handles and UPSL pages live in `src/data/clubs.js`. Only add links you've checked; the page asks for missing ones.
- Each featured match has a preview at `/match-<home>-vs-<away>-<date>` with an add-to-calendar button (1-hour reminder) and share link.
- Homepage background video: set in `src/config.js` (`heroVideo`). Uses a muted YouTube embed now; put an `.mp4` in `public/` for a faster, cleaner loop.

## UPSL scraper (logos, links, rosters, results)

`scraper/upsl_scraper.py` follows the approach of egudino20/UPSL-Webscraper (club cards on
premier.upsl.com/teams, then each club page) and adds logos and social links for every club.

```
pip install -r scraper/requirements.txt
python scraper/upsl_scraper.py all --limit 20   # try 20 clubs first
python scraper/upsl_scraper.py all              # every club (~1,000 pages, about 20-30 min)
python scraper/test_scraper.py                  # offline tests
```

It writes `public/logos/*.png` and `src/data/upsl/{teams.json,rosters.json,results.csv}`. The site
picks up logos and links automatically; hand-checked entries in `src/data/clubs.js` win over scraped ones
(use `upslName` there when our name differs from UPSL's). The GitHub Action in
`.github/workflows/scrape-upsl.yml` runs it every Monday and on demand from the Actions tab.
