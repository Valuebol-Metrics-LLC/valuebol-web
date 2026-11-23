import { Link } from '../lib/router.jsx';
import { InstagramBand } from '../components/Layout.jsx';
import { getCoverage, getModelValidation } from '../lib/data.js';
import { site } from '../config.js';

const AUDIENCES = [
  ['Players', 'See your club’s ranking and your goals, and share your season.'],
  ['Clubs', 'See where you rank among 400+ active clubs.'],
  ['Fans', 'Make picks, compare clubs and follow the title races.'],
  ['Sponsors', 'Find clubs and audiences to back.'],
];

export default function About() {
  const cov = getCoverage();
  const model = getModelValidation();
  return (
    <div className="container page" style={{ maxWidth: 1040 }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p className="eyebrow">About us</p>
        <h1 className="display display-xl">{site.tagline}</h1>
        <p className="lead">
          Valuebol covers about {cov.teams.replace('+', '')} United Premier Soccer League clubs, with match data going back to {cov.since}. One place for teams, local fans and sponsors to explore matches, rankings and scoring stats, and to see projections for upcoming games and whole conference seasons.
        </p>
      </section>

      <section className="stat-strip">
        <div><div className="num">{cov.teams}</div><div className="stat-label">Teams covered</div></div>
        <div><div className="num">{cov.conferences}</div><div className="stat-label">Conferences</div></div>
        <div><div className="num">{cov.matches}</div><div className="stat-label">Matches</div></div>
        <div><div className="num accent">{model.accuracy}%</div><div className="stat-label">Results called correctly</div></div>
      </section>

      <section className="row" style={{ alignItems: 'stretch' }}>
        <div className="grow card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 className="display display-md">Why the UPSL</h2>
          <p style={{ margin: 0 }}>
            The UPSL, founded in 2011, is the largest and most competitive pro-development league in North America. Hundreds of clubs play in it, but there has been very little data on them.
          </p>
        </div>
        <div className="side card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 className="display display-md">How we work</h2>
          <p style={{ margin: 0 }}>We use proper statistical models and show the results in a way anyone can follow. The full methods are public.</p>
          <Link to="/methodology" className="link-arrow">How the numbers work →</Link>
        </div>
      </section>

      <section>
        <h2 className="display display-lg" style={{ marginBottom: 16 }}>Who it's for</h2>
        <div className="grid grid-auto">
          {AUDIENCES.map(([who, what]) => (
            <div key={who} className="card card-pad" style={{ borderTop: '3px solid var(--accent)' }}>
              <h3 style={{ margin: '0 0 6px', fontSize: 18 }}>{who}</h3>
              <p className="muted" style={{ margin: 0 }}>{what}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel-accent" style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'center' }}>
        <div style={{ flex: '1 1 420px' }}>
          <p className="eyebrow" style={{ color: 'var(--on-accent-2)' }}>What's next</p>
          <h2 className="display display-lg" style={{ marginTop: 8 }}>Sponsor dashboards</h2>
          <p className="muted" style={{ margin: '10px 0 0' }}>
            We're adding sponsor tracking and dedicated sponsor dashboards for under-represented teams in the US soccer ecosystem.
          </p>
        </div>
        <Link to="/contact" className="btn" style={{ background: 'transparent', color: '#fff', borderColor: 'var(--on-accent-2)' }}>Talk to us</Link>
      </section>

      <InstagramBand />
    </div>
  );
}
