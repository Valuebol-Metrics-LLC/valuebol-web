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
| `/matches` | Beat the model: pick home / draw / away, see if you agree with the model (picks saved in the browser) |
| `/rankings` | Power rankings: ASI explainer, movers, searchable table, follow clubs (saved in the browser) |
| `/who-wins` | Pick any two clubs: "X come out on top in about 7 of 10 meetings", upset stakes, Show the math |
| `/title-race` | Can we still win it? Florida West simulations: chances by club, what-if points calculator |
| `/about` | About us: mission, coverage, who it's for, what's next, Instagram |
| `/contact` | Contact form (opens the visitor's email app, addressed to the team), Instagram DM, email |
| `/methodology` | How the numbers work: each model in one sentence, full method underneath, validation table |
| `/legal` | Copyright & terms: ownership, sharing with credit, data sources and club marks, corrections |

## Before launch

Set the real Instagram handle in `src/config.js` (still a placeholder). The contact email is set.

## Where the data comes from

All pages read through `src/lib/data.js`. Right now it returns a **snapshot** of the live site's figures (`src/data/snapshot.js`, as of Nov 21, 2026). To go live, change only `src/lib/data.js` to read from the real pipeline, for example Supabase tables pushed by the Python pipeline, the same pattern as `amateur-football-dashboard`. No page code needs to change.

## Design

- Light and dark mode, switched from the header and remembered per visitor (defaults to the device setting). Both themes live in `src/styles.css` as CSS variables.
- Valuebol LLC logo (option 04), with a white-B version for dark mode.
- Club crests: `src/components/Crest.jsx` shows a club's real logo when a `logoUrl` is provided, otherwise an initials badge.
- Fonts: Barlow Condensed (numbers, headings) and Inter (text), from Google Fonts.

## Next up

Live data from the pipeline, every conference in Title race, Crowd vs the Model voting, player profiles with Instagram share cards, and the community scouts program.
