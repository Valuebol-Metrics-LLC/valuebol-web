import { Link } from '../lib/router.jsx';
import { SectionHead, InstagramBand } from '../components/Layout.jsx';
import Crest from '../components/Crest.jsx';
import { getCoverage, getFeaturedMatches, getModelValidation, getRankings, getTopScorers, describeOdds, formatDate } from '../lib/data.js';

function MatchCard({ m }) {
  return (
    <article className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        <span>{formatDate(m.date)} · {m.time}</span>
        <span className="muted">{m.competition}</span>
      </div>
      {[[m.home, m.homeRank, 0], [m.away, m.awayRank, 2]].map(([name, rank, i]) => (
        <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Crest name={name} size={40} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700 }}>{name}</div>
            <div className="muted small">ASI #{rank}</div>
          </div>
          {m.probs && <span className={`num ${i === 0 ? 'accent' : 'down'}`} style={{ fontSize: 26 }}>{m.probs[i]}%</span>}
        </div>
      ))}
      {m.probs ? (
        <div>
          <div className="prob" aria-hidden="true">
            <div className="h" style={{ width: `${m.probs[0]}%` }} />
            <div className="d" style={{ width: `${m.probs[1]}%` }} />
            <div className="a" style={{ width: `${m.probs[2]}%` }} />
          </div>
          <p className="small" style={{ margin: '8px 0 0' }}>
            <b>{describeOdds(m.probs)}</b> <span className="muted">· draw {m.probs[1]}%</span>
          </p>
        </div>
      ) : (
        <p className="muted small" style={{ margin: 0 }}>No prediction yet: one club needs more match history.</p>
      )}
    </article>
  );
}

export default function Home() {
  const cov = getCoverage();
  const top = getRankings().slice(0, 5);
  const matches = getFeaturedMatches();
  const model = getModelValidation();
  const scorers = getTopScorers();

  return (
    <>
      <section style={{ borderBottom: '1px solid var(--border-strong)', background: 'var(--bg-band)' }}>
        <div className="container" style={{ padding: '64px 24px 48px', display: 'flex', flexDirection: 'column', gap: 36 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 780 }}>
            <p className="eyebrow">UPSL analytics · Fall 2026</p>
            <h1 className="display display-xl">
              Bridging the gap between amateur and <span className="accent">professional</span> football.
            </h1>
            <p className="lead">Rankings, predictions and player stats for every UPSL club, in plain English, with the math one tap away.</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              <Link to="/who-wins" className="btn btn-primary">Who wins? Try it</Link>
              <Link to="/rankings" className="btn">See the rankings</Link>
            </div>
          </div>
          <div className="stat-strip">
            <div><div className="num" >{cov.teams}</div><div className="stat-label">Teams tracked</div></div>
            <div><div className="num">{cov.conferences}</div><div className="stat-label">Conferences</div></div>
            <div><div className="num">{cov.matches}</div><div className="stat-label">Matches analysed</div></div>
            <div><div className="num">{cov.since}</div><div className="stat-label">Data since</div></div>
          </div>
        </div>
      </section>

      <div className="container page">
        <section>
          <SectionHead kicker="01" title="This week's big matches" action={<Link to="/matches" className="link-arrow">Make your picks →</Link>} />
          <div className="grid grid-auto">
            {matches.map((m) => <MatchCard key={m.date + m.home} m={m} />)}
          </div>
        </section>

        <section className="row">
          <div className="grow">
            <SectionHead kicker="02" title="Power rankings" sub="Top 5 of 442 active clubs" action={<Link to="/rankings" className="link-arrow">Full rankings →</Link>} />
            <div className="card">
              {top.map((t, i) => (
                <Link key={t.name} to="/rankings" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderTop: i ? '1px solid var(--border)' : 'none', color: 'var(--text)' }}>
                  <span className={`num ${t.rank <= 3 ? 'accent' : ''}`} style={{ fontSize: 28, width: 28 }}>{t.rank}</span>
                  <Crest name={t.name} />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: 'block', fontWeight: 700 }}>{t.name}</span>
                    <span className="muted small">{t.conference} · {t.record}</span>
                  </span>
                  <span className="num" style={{ fontSize: 26 }}>{t.asi.toLocaleString('en-US')}</span>
                </Link>
              ))}
            </div>
          </div>
          <div className="side">
            <SectionHead kicker="03" title="Golden boot" sub="Fall 2026" />
            <div className="card">
              {scorers.map((p, i) => (
                <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                  <span className="num muted" style={{ fontSize: 22, width: 18 }}>{i + 1}</span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: 'block', fontWeight: 700 }}>{p.name}</span>
                    <span className="muted small">{p.club}</span>
                  </span>
                  <span className="num" style={{ fontSize: 30 }}>{p.goals}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="panel-accent" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 32 }}>
          <div style={{ flex: '1 1 320px' }}>
            <p className="eyebrow" style={{ color: 'var(--on-accent-2)' }}>04 · Can you trust the model?</p>
            <h2 className="display display-lg" style={{ marginTop: 8 }}>It calls {model.accuracy}% of results</h2>
            <p className="muted" style={{ margin: '10px 0 0' }}>Tested on {model.matchesTested.toLocaleString('en-US')} Spring 2026 league matches it had never seen. Guessing from league averages gets {model.baseline}%.</p>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 28 }}>
            <div><div className="num" style={{ fontSize: 'clamp(44px, 12vw, 64px)' }}>{model.accuracy}%</div><div className="small">Valuebol model</div></div>
            <div><div className="num" style={{ fontSize: 'clamp(44px, 12vw, 64px)', opacity: 0.7 }}>{model.baseline}%</div><div className="small">Baseline</div></div>
          </div>
          <Link to="/methodology" className="btn" style={{ background: 'transparent', color: '#fff', borderColor: 'var(--on-accent-2)' }}>How it works</Link>
        </section>

        <InstagramBand />
      </div>
    </>
  );
}
