import { useState } from 'react';
import { getModelValidation } from '../lib/data.js';

// Full method text is carried over from the current Valuebol Data & Models page, unchanged in substance.
const SECTIONS = [
  {
    id: 'projections',
    title: 'Match projections',
    plain: 'Every club gets an attack and a defense strength from its results. We combine the two clubs into expected goals, then work out the chance of every scoreline. Add them up and you get home, draw and away odds.',
    method: [
      'Every club is assigned an attack and defense strength, estimated by solving for the parameters that maximize the likelihood of the historical results within its conference.',
      'Recent matches are weighted more heavily, with weights decaying by a one-year half-life.',
      'Strengths are shrunk toward the conference average. Teams with minimal history are pulled closer to the conference average, while teams with a longer history more closely reflect their own attack and defense strengths.',
      'The strengths of the two clubs in a matchup are combined into expected home and away goals, with an adjustment for home advantage.',
      'For every scoreline, the probability is the product of the two independent Poisson probabilities at those expected goals.',
      'The match outcome probabilities are the sums of the scoreline probabilities, capped at 10 goals a side and rescaled to 100%.',
      'For matches within conferences, probabilities are displayed only when both clubs have at least three completed matches.',
      'For matches between conferences, probabilities are displayed only when both clubs have at least thirteen completed matches.',
      'In matches between conferences, each club keeps the attack and defense strengths from its own conference. These strengths are adjusted based on historical inter-conference results: a conference with relatively better results has its strengths adjusted favorably, and one with worse results the other way.',
      'The home-advantage adjustment is the average of the home advantage estimated for each club’s conference. National semifinals, the national final and the third-place match are not adjusted for home advantage.',
      'Data: strengths are estimated from the live archive of completed UPSL matches since 2017 and refreshed as new matches are played; current strengths are applied to every upcoming fixture.',
    ],
  },
  {
    id: 'simulations',
    title: 'Conference simulations',
    plain: 'We play out the rest of every conference season 10,000 times using those scoreline odds. How often a club finishes 1st, 2nd and so on is its chance of finishing there.',
    method: [
      'The same scoreline probabilities are used to project each conference table. Every remaining league fixture in the current season is played out by drawing one scoreline in proportion to its modeled probability.',
      'Each run awards three points for a win and one for a draw, and adds the goals to each club’s total. The simulated table is ranked on points, then goal difference, then goals scored.',
      'Repeating this 10,000 times gives the share of runs in which each club finished in each position, along with its average projected points and goals.',
      'For ongoing seasons, results already on the official table are kept. Only games still to be played are simulated. Playoff fixtures are currently excluded.',
      'Clubs without a fitted strength use their conference’s typical attack and defense as a proxy. A conference that has never been fit is simulated at league-wide average scoring rates. Clubs with a short record are shrunk the same way as in match projections.',
      'A conference is marked low-confidence when more than a third of its remaining fixtures used a typical-strength prior, or more than a third of its clubs have fewer than three career matches.',
    ],
  },
  {
    id: 'asi',
    title: 'Amateur Soccer Index (ASI)',
    plain: 'A rating for every club, like chess ratings. Win and you take points from the club you beat. Beating a stronger club earns more; losing to a weaker one costs more.',
    method: [
      'ASI is a league-wide rating system updated after each match using an Elo-based framework. Before a match, the rating gap between the two clubs is used to calculate each side’s expected score.',
      'Afterward, each club’s rating is adjusted based on how the actual result compares to that expectation. The size of the adjustment is set by a K-factor of 25 for league matches and 40 for playoffs.',
      'Margin of victory, home advantage and offseason reversion are not factored into the update.',
      'Clubs whose first match falls in the inaugural 2017 season start at 1,500. A club entering later starts at the average rating of the clubs in its conference; clubs in a new conference with no rated clubs start at 1,500.',
      'Rankings are updated weekly after each league weekend. The rating uses every played match on the UPSL website since 2017, including playoffs and inter-conference matches. The live table shows clubs with a match in the last six months; clubs that left the league stay in the historical series.',
    ],
  },
];

function MethodSection({ s }) {
  const [open, setOpen] = useState(false);
  return (
    <section id={s.id} className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <h2 className="display display-md">{s.title}</h2>
      <p style={{ margin: 0, fontSize: 17 }}>{s.plain}</p>
      <div>
        <button type="button" className="btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? 'Hide full method' : 'Full method'}
        </button>
      </div>
      {open && (
        <ul className="math" style={{ margin: 0, paddingLeft: 20 }}>
          {s.method.map((m) => <li key={m.slice(0, 40)} style={{ marginBottom: 6 }}>{m}</li>)}
        </ul>
      )}
    </section>
  );
}

export default function Methodology() {
  const v = getModelValidation();
  return (
    <div className="container page" style={{ maxWidth: 960 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p className="eyebrow">Data &amp; models</p>
        <h1 className="display display-xl">How the numbers work</h1>
        <p className="lead">Valuebol runs on three models. Here's what each one does, with the full method underneath.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {SECTIONS.map((s) => <MethodSection key={s.id} s={s} />)}
      </div>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 className="display display-lg">How accurate is it?</h2>
        <p style={{ margin: 0, fontSize: 17 }}>
          On {v.matchesTested.toLocaleString('en-US')} Spring 2026 league matches the model never saw, it called the right result <b>{v.accuracy}%</b> of the time. Guessing from league-average home / draw / away rates gets {v.baseline}%.
        </p>
        <div className="card table-wrap">
          <table className="data">
            <thead>
              <tr><th>Model</th><th className="right">Log loss</th><th className="right">Brier</th><th className="right">Correct result</th></tr>
            </thead>
            <tbody>
              {v.models.map((m) => (
                <tr key={m.name} style={m.chosen ? { background: 'var(--accent-soft)' } : undefined}>
                  <td style={{ fontWeight: m.chosen ? 700 : 400 }}>{m.name}{m.chosen ? ' (used)' : ''}</td>
                  <td className="right">{m.logLoss.toFixed(3)}</td>
                  <td className="right">{m.brier.toFixed(3)}</td>
                  <td className="right">{m.correct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small" style={{ margin: 0 }}>
          Lower log loss and Brier score are better. Correct result = how often the most likely of home, draw or away happened. Not every test match could use both clubs' own history: 8.4% used the baseline alone, 37.3% blended about one-third model with two-thirds baseline, and 54.3% used both clubs' fitted strengths (log loss 0.915 on that group).
        </p>
      </section>
    </div>
  );
}
