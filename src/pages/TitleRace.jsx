import { useState } from 'react';
import Crest from '../components/Crest.jsx';
import ShowTheMath from '../components/ShowTheMath.jsx';
import { Link } from '../lib/router.jsx';
import { getConferenceRace } from '../lib/data.js';

const ORD = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th', '11th', '12th', '13th'];
const val = (v) => (v === -1 ? 0.5 : v);
const pct = (v) => (v === -1 ? '<1%' : `${v}%`);
const top4 = (f) => Math.min(100, val(f[0]) + val(f[1]) + val(f[2]) + val(f[3]));
const fmtPct = (x) => (x >= 99.5 ? '100%' : x > 0 && x < 1 ? '<1%' : `${Math.round(x)}%`);

export default function TitleRace() {
  const race = getConferenceRace();
  // Open on the first club that still has games left and a finish that isn't settled yet.
  const [sel, setSel] = useState(() => {
    const i = race.clubs.findIndex((o) => o.projGp > o.gp && Math.max(...o.finish.map(val)) < 99.5);
    return i >= 0 ? i : 0;
  });
  const [calls, setCalls] = useState({});
  const c = race.clubs[sel];
  const f = c.finish;
  const p1 = val(f[0]);
  const t4 = top4(f);
  let best = 0;
  f.forEach((v, i) => { if (val(v) > val(f[best])) best = i; });
  const left = Math.max(0, c.projGp - c.gp);

  let verdict; let tone = '';
  if (p1 >= 99.5) { verdict = 'Clinched 1st place.'; tone = 'accent'; }
  else if (p1 === 0) { verdict = 'Out of the title race.'; tone = 'down'; }
  else verdict = `${pct(f[0])} chance to win the conference.`;
  let detail;
  if (p1 >= 99.5) detail = `${c.name} finished first in all ${race.runs.toLocaleString('en-US')} simulations.`;
  else if (t4 >= 99.5) detail = `Top 4 is safe. Most likely finish: ${ORD[best]} (${Math.round(val(f[best]))}% of simulations).`;
  else if (t4 > 0) detail = `Top 4 in ${Math.round(t4)}% of simulations. Most likely finish: ${ORD[best]}.`;
  else detail = `No top 4 finish in any simulation. Most likely finish: ${ORD[best]} (${Math.round(val(f[best]))}%).`;

  const mine = calls[sel] || {};
  let add = 0; let called = 0;
  for (let g = 0; g < left; g++) { if (mine[g] === 'W') add += 3; if (mine[g] === 'D') add += 1; if (mine[g]) called++; }
  const total = c.pts + add;
  const beats = race.clubs.filter((o, j) => j !== sel && o.pts < total).length;
  const setCall = (g, k) => setCalls({ ...calls, [sel]: { ...mine, [g]: mine[g] === k ? undefined : k } });
  const maxV = Math.max(...f.map(val));

  return (
    <div className="container page">
      <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <p className="eyebrow">UPSL {race.conference} · {race.season}</p>
          <h1 className="display display-xl">Can we still win it?</h1>
        </div>
        <p className="muted" style={{ maxWidth: 380, margin: 0 }}>We simulate the rest of the season <b style={{ color: 'var(--text)' }}>{race.runs.toLocaleString('en-US')} times</b>. Pick a club to see where it finishes.</p>
      </section>

      <nav aria-label="Pick a club" style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 6, marginTop: -24 }}>
        {race.clubs.map((o, j) => (
          <button key={o.name} type="button" aria-pressed={j === sel} onClick={() => setSel(j)}
            style={{ flex: 'none', minHeight: 48, padding: '0 14px 0 6px', borderRadius: 999, border: `2px solid ${j === sel ? 'var(--accent)' : 'var(--border-strong)'}`, background: j === sel ? 'var(--accent-soft)' : 'var(--surface)', color: 'var(--text)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
            <Crest name={o.name} size={32} />{o.name}
          </button>
        ))}
      </nav>

      <section className="row" style={{ alignItems: 'stretch' }}>
        <div className="grow card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Crest name={c.name} size={68} />
            <div>
              <div className="display display-md">{c.name}</div>
              <div className="muted small">Now {ORD[c.pos - 1]} · {c.pts} pts · {left ? `${left} game${left > 1 ? 's' : ''} left` : 'season complete'}</div>
            </div>
          </div>
          <h2 className={`display ${tone}`} style={{ fontSize: 'clamp(32px, 4.5vw, 46px)', lineHeight: 0.98 }} aria-live="polite">{verdict}</h2>
          <p style={{ margin: 0, fontSize: 17 }}>{detail}</p>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
            {[['Win the conference', pct(f[0]), ''], ['Finish top 4', fmtPct(t4), 'accent'], ['Projected points', c.projPts.toFixed(1), '']].map(([l, v, cls]) => (
              <div key={l} style={{ background: 'var(--surface-2)', borderRadius: 12, padding: 16 }}>
                <div className="stat-label">{l}</div>
                <div className={`num ${cls}`} style={{ fontSize: 40 }}>{v}</div>
              </div>
            ))}
          </div>
          <div>
            <p className="stat-label" style={{ margin: '0 0 10px' }}>Finishing position, % of simulations</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, minmax(0,1fr))', gap: 6, alignItems: 'end', height: 150 }} aria-hidden="true">
              {f.map((v, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', gap: 4, height: 150 }}>
                  <span className="num small" style={{ fontWeight: 700, color: i === best ? 'var(--text)' : 'var(--text-2)' }}>{val(v) ? pct(v) : ''}</span>
                  <div style={{ width: '100%', borderRadius: '4px 4px 0 0', height: val(v) ? Math.max(4, Math.round((118 * val(v)) / maxV)) : 2, background: !val(v) ? 'var(--border)' : i < 4 ? 'var(--accent)' : 'var(--draw)' }} />
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, minmax(0,1fr))', gap: 6, borderTop: '1px solid var(--border-strong)', paddingTop: 6 }}>
              {f.map((_, i) => <span key={i} className="muted small center">{i + 1}</span>)}
            </div>
          </div>
        </div>

        <div className="side panel-accent" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p className="eyebrow" style={{ color: 'var(--on-accent-2)' }}>What if</p>
          <h3 className="display display-md" style={{ margin: 0 }}>Set results for the games left</h3>
          {left === 0 && <p style={{ margin: 0 }}>Their league season is finished. Final total: {c.pts} points.</p>}
          {Array.from({ length: left }, (_, g) => (
            <div key={g} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 12, padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ flex: 1, fontWeight: 700 }}>Game {g + 1}</span>
              {['W', 'D', 'L'].map((k) => (
                <button key={k} type="button" aria-pressed={mine[g] === k} aria-label={`Game ${g + 1}: ${k === 'W' ? 'win' : k === 'D' ? 'draw' : 'loss'}`} onClick={() => setCall(g, k)}
                  className="num" style={{ width: 48, height: 44, borderRadius: 8, border: '2px solid #fff', background: mine[g] === k ? '#fff' : 'transparent', color: mine[g] === k ? 'var(--accent)' : '#fff', fontSize: 20 }}>{k}</button>
              ))}
            </div>
          ))}
          <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 12, padding: 16 }} aria-live="polite">
            <div className="small" style={{ color: 'var(--on-accent-2)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>Points total</div>
            <div className="num" style={{ fontSize: 60 }}>{total} pts</div>
            <div className="small">{!left ? 'No games left to play.' : called < left ? `Call all ${left} game${left > 1 ? 's' : ''}. Max possible: ${c.pts + 3 * left} pts.` : `More than ${beats} clubs have right now.`}</div>
          </div>
          <p className="small" style={{ margin: 0, color: 'var(--on-accent-2)' }}>This only adds up points. The percentages come from the simulations.</p>
        </div>
      </section>

      <section className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2 className="display display-lg">The race for the top 4</h2>
        {race.clubs.map((o, j) => {
          const x = top4(o.finish);
          return (
            <button key={o.name} type="button" onClick={() => setSel(j)} style={{ display: 'grid', gridTemplateColumns: '28px 36px minmax(0,1fr) minmax(0,2fr) 56px', alignItems: 'center', gap: 12, padding: '8px 10px', borderRadius: 10, border: 0, background: j === sel ? 'var(--accent-soft)' : 'transparent', color: 'var(--text)', textAlign: 'left' }}>
              <span className="num muted" style={{ fontSize: 20 }}>{o.pos}</span>
              <Crest name={o.name} size={32} />
              <span style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.name}</span>
              <span aria-hidden="true" style={{ height: 10, borderRadius: 5, background: 'var(--border)', overflow: 'hidden' }}>
                <span style={{ display: 'block', height: 10, background: 'var(--accent)', width: `${x}%` }} />
              </span>
              <span className="num right" style={{ fontSize: 20 }}>{fmtPct(x)}</span>
            </button>
          );
        })}
        <ShowTheMath>
          <p style={{ margin: 0 }}>Every remaining league fixture is played out by drawing one scoreline in proportion to its modeled probability. Wins earn 3 points, draws 1; the table ranks on points, then goal difference, then goals scored. Repeated {race.runs.toLocaleString('en-US')} times; results already on the official table are kept, playoffs excluded.</p>
          <p className="muted small" style={{ margin: 0 }}>"Top 4" is used as an example cutoff. <Link to="/methodology">Full methodology →</Link></p>
        </ShowTheMath>
      </section>
    </div>
  );
}
