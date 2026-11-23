import { useEffect, useMemo, useState } from 'react';
import { Link } from '../lib/router.jsx';
import Crest from '../components/Crest.jsx';
import ShowTheMath from '../components/ShowTheMath.jsx';
import { getAsOf, getCoverage, getMovers, getRankings, getRatingRange, formatDate } from '../lib/data.js';

const FOLLOW_KEY = 'valuebol.followedClubs';

function loadFollowed() {
  try { return JSON.parse(localStorage.getItem(FOLLOW_KEY) || '[]'); } catch { return []; }
}

function MoverCard({ label, tone, name, sub, value }) {
  return (
    <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <Crest name={name} size={52} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className={tone === 'down' ? 'down small' : 'up small'} style={{ letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</div>
        <div style={{ fontWeight: 700 }}>{name}</div>
        <div className="muted small">{sub}</div>
      </div>
      <span className={`num ${tone === 'down' ? 'down' : 'accent'}`} style={{ fontSize: 34 }}>{value}</span>
    </div>
  );
}

export default function Rankings() {
  const rows = getRankings();
  const range = getRatingRange();
  const movers = getMovers();
  const cov = getCoverage();
  const [query, setQuery] = useState('');
  const [onlyMine, setOnlyMine] = useState(false);
  const [followed, setFollowed] = useState([]);

  useEffect(() => setFollowed(loadFollowed()), []);

  const toggle = (name) => {
    const next = followed.includes(name) ? followed.filter((n) => n !== name) : [...followed, name];
    setFollowed(next);
    try { localStorage.setItem(FOLLOW_KEY, JSON.stringify(next)); } catch { /* storage unavailable */ }
  };

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => (!onlyMine || followed.includes(r.name)) && (!q || r.name.toLowerCase().includes(q) || r.conference.toLowerCase().includes(q)));
  }, [rows, query, onlyMine, followed]);

  return (
    <div className="container page">
      <section className="row" style={{ alignItems: 'stretch' }}>
        <div className="grow" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 12 }}>
          <p className="eyebrow">Amateur Soccer Index · {formatDate(getAsOf())}</p>
          <h1 className="display display-xl">Power rankings</h1>
          <p className="lead">{cov.activeClubs} active UPSL clubs, rated on every result since {cov.since}.</p>
        </div>
        <div className="side card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <h2 className="display display-md">What the ASI is</h2>
          <p style={{ margin: 0 }}>Every club has a rating. Win and you take points from the team you beat. Beat a better team and you take more. Lose to a weaker one and you lose more.</p>
          <div>
            <div aria-hidden="true" style={{ height: 10, borderRadius: 5, background: 'linear-gradient(90deg, var(--border), var(--accent))' }} />
            <div className="small muted" style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <span><b style={{ color: 'var(--text)' }}>{range.lowest.toLocaleString('en-US')}</b> lowest active</span>
              <span><b className="accent">{range.highest.toLocaleString('en-US')}</b> #1 today</span>
            </div>
          </div>
          <ShowTheMath>
            <p style={{ margin: 0 }}>ASI is an Elo rating updated after every match. The rating gap sets each club's expected score: <code>E = 1 / (1 + 10^((R2 − R1) / 400))</code>.</p>
            <p style={{ margin: 0 }}>After the match, ratings move by K × (result − E). K is 25 for league matches and 40 for playoffs. Margin of victory, home advantage and offseason reversion are not used.</p>
            <p className="muted small" style={{ margin: 0 }}>Clubs from 2017 start at 1,500; later entrants start at their conference average. <Link to="/methodology">Full methodology →</Link></p>
          </ShowTheMath>
        </div>
      </section>

      <section className="grid grid-auto">
        <MoverCard label="Biggest climber" name={movers.climber.name} sub={`Now #${movers.climber.rank} · ${movers.climber.conference}`} value={`▲${movers.climber.move}`} />
        <MoverCard label="Hottest form" name={movers.hottest.name} sub={`#${movers.hottest.rank} · ASI points over last 5`} value={`+${Math.round(movers.hottest.last5)}`} />
        <MoverCard label="Biggest drop" tone="down" name={movers.drop.name} sub={`Now #${movers.drop.rank} · ${movers.drop.conference}`} value={`▼${Math.abs(movers.drop.move)}`} />
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 260px' }}>
            <span className="stat-label">Find a club or conference</span>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Type a name" style={{ height: 44, border: '1px solid var(--border-strong)', borderRadius: 8, padding: '0 12px', font: 'inherit', background: 'var(--surface)', color: 'var(--text)' }} />
          </label>
          <button type="button" className={`btn ${onlyMine ? 'btn-primary' : ''}`} aria-pressed={onlyMine} onClick={() => setOnlyMine(!onlyMine)}>
            ★ My clubs ({followed.length})
          </button>
        </div>

        <div className="card table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th><span className="visually-hidden">Follow</span></th>
                <th>Rank</th>
                <th>Club</th>
                <th>Conference</th>
                <th className="center">Record</th>
                <th className="right">Form (last 5)</th>
                <th className="right">ASI</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => {
                const on = followed.includes(t.name);
                return (
                  <tr key={t.name}>
                    <td style={{ width: 52 }}>
                      <button type="button" aria-pressed={on} aria-label={`Follow ${t.name}`} onClick={() => toggle(t.name)} style={{ width: 44, height: 44, border: 0, background: 'transparent', fontSize: 20, color: on ? 'var(--accent-text)' : 'var(--text-3)' }}>
                        {on ? '★' : '☆'}
                      </button>
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <span className={`num ${t.rank <= 3 ? 'accent' : ''}`} style={{ fontSize: 22, display: 'inline-block', width: 34 }}>{t.rank}</span>
                      {t.move > 0 && <span className="up small">▲{t.move}</span>}
                      {t.move < 0 && <span className="down small">▼{-t.move}</span>}
                    </td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 12, fontWeight: 600 }}>
                        <Crest name={t.name} />
                        {t.name}
                      </span>
                    </td>
                    <td className="muted small" style={{ whiteSpace: 'nowrap' }}>{t.conference}</td>
                    <td className="center num" style={{ fontSize: 18, fontWeight: 700 }}>{t.record}</td>
                    <td className={`right num ${t.last5 >= 0 ? 'up' : 'down'}`} style={{ fontSize: 18 }}>{t.last5 > 0 ? '+' : ''}{t.last5}</td>
                    <td className="right num" style={{ fontSize: 22 }}>{t.asi.toLocaleString('en-US')}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {visible.length === 0 && (
            <p className="muted" style={{ padding: 32, textAlign: 'center', margin: 0 }}>
              {onlyMine ? 'Tap ☆ next to any club to add it to My clubs.' : 'No club matches that search.'}
            </p>
          )}
        </div>
        <p className="muted small" style={{ margin: 0 }}>Showing the top {rows.length}. Form = ASI points won or lost over a club's last five matches.</p>
      </section>
    </div>
  );
}
