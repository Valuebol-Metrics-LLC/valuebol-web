import { useState } from 'react';
import Crest, { initials, crestColor } from '../components/Crest.jsx';
import ShowTheMath from '../components/ShowTheMath.jsx';
import { Link } from '../lib/router.jsx';
import { getRankings, eloExpected, eloStake } from '../lib/data.js';

const short = (n) => n.replace(/ (FC|SC|SA)$/, '');

function Picker({ label, clubs, value, onChange }) {
  const club = clubs[value];
  return (
    <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, textAlign: 'center' }}>
      <Crest name={club.name} size={96} />
      <label style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="stat-label">{label}</span>
        <select value={value} onChange={(e) => onChange(Number(e.target.value))} style={{ height: 48, border: '1px solid var(--border-strong)', borderRadius: 8, padding: '0 12px', font: 'inherit', fontWeight: 600, background: 'var(--surface)' }}>
          {clubs.map((c, i) => <option key={c.name} value={i}>#{c.rank}  {c.name}</option>)}
        </select>
      </label>
      <span className="muted small">Ranked <b style={{ color: 'var(--text)' }}>#{club.rank}</b> · ASI {club.asi.toLocaleString('en-US')}</span>
    </div>
  );
}

export default function WhoWins() {
  const clubs = getRankings();
  const [a, setA] = useState(0);
  const [b, setB] = useState(1);
  const A = clubs[a];
  const B = clubs[b];
  const same = a === b;

  const eA = eloExpected(A.asi, B.asi);
  const nA = Math.round(eA * 10);
  const fav = eA >= 0.5 ? A : B;
  const dog = eA >= 0.5 ? B : A;
  const eFav = Math.max(eA, 1 - eA);

  let headline;
  if (same) headline = 'Pick two different clubs';
  else if (nA === 5) headline = 'Too close to call. About 5 wins each out of 10';
  else headline = `${short(fav.name)} win about ${Math.max(nA, 10 - nA)} out of 10`;

  return (
    <div className="container page" style={{ maxWidth: 1080 }}>
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <p className="eyebrow">Head to head</p>
        <h1 className="display display-xl">Who wins?</h1>
        <p className="lead">Pick two clubs and see how a game between them would likely go.</p>
      </div>

      <section className="versus">
        <Picker label="Club 1" clubs={clubs} value={a} onChange={setA} />
        <span className="num muted vs" style={{ fontSize: 40 }}>VS</span>
        <Picker label="Club 2" clubs={clubs} value={b} onChange={setB} />
      </section>

      <section className="card" style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 24 }}>
        <p className="eyebrow">Prediction</p>
        <h2 className="display" style={{ fontSize: 'clamp(34px, 5vw, 52px)', lineHeight: 0.95 }} aria-live="polite">{headline}</h2>
        {!same && (
          <>
            <div>
              <div aria-hidden="true" style={{ display: 'grid', gridTemplateColumns: 'repeat(10, minmax(0,1fr))', gap: 8 }}>
                {Array.from({ length: 10 }, (_, i) => {
                  const club = i < nA ? A : B;
                  return (
                    <span key={i} className="crest" style={{ aspectRatio: '1', background: crestColor(club.name), fontSize: 'clamp(10px, 2vw, 18px)' }}>
                      {initials(club.name)}
                    </span>
                  );
                })}
              </div>
              <p className="muted small" style={{ margin: '12px 0 0' }}>If they played 10 times (draws counted as half a win).</p>
            </div>
            <div className="grid grid-auto">
              <div style={{ background: 'var(--surface-2)', borderRadius: 12, padding: 20 }}>
                <div className="down small" style={{ letterSpacing: '0.08em', textTransform: 'uppercase' }}>Upset watch: {short(dog.name)}</div>
                <p style={{ margin: '6px 0 0', fontSize: 16 }}>A win would be worth <b>+{Math.round(25 * eFav)} ASI points</b> to {short(dog.name)}, and cost {short(fav.name)} the same.</p>
              </div>
              <div style={{ background: 'var(--surface-2)', borderRadius: 12, padding: 20 }}>
                <div className="up small" style={{ letterSpacing: '0.08em', textTransform: 'uppercase' }}>If the favorite wins</div>
                <p style={{ margin: '6px 0 0', fontSize: 16 }}>{short(fav.name)} would gain just <b>+{eloStake(eFav)} points</b>. Beating a weaker team doesn't move the rating much.</p>
              </div>
            </div>
            <ShowTheMath>
              <p style={{ margin: 0 }}>ASI is an Elo rating. The rating gap sets each club's expected score: <code>E = 1 / (1 + 10^((R2 − R1) / 400))</code></p>
              <div className="grid grid-auto">
                <div><div className="stat-label">Rating gap</div><div className="num" style={{ fontSize: 30 }}>{Math.abs(A.asi - B.asi)} pts</div></div>
                <div><div className="stat-label">Expected score, {short(A.name)}</div><div className="num" style={{ fontSize: 30 }}>{eA.toFixed(2)}</div></div>
                <div><div className="stat-label">Expected score, {short(B.name)}</div><div className="num" style={{ fontSize: 30 }}>{(1 - eA).toFixed(2)}</div></div>
                <div><div className="stat-label">K-factor (league)</div><div className="num" style={{ fontSize: 30 }}>25</div></div>
              </div>
              <p className="muted small" style={{ margin: 0 }}>Expected score counts a draw as half a win. Match-day win / draw / loss odds come from the separate attack-and-defense scoreline model. <Link to="/methodology">Full methodology →</Link></p>
            </ShowTheMath>
          </>
        )}
      </section>
    </div>
  );
}
