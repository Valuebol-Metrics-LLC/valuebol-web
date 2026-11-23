import { useEffect, useState } from 'react';
import Crest from '../components/Crest.jsx';
import { MatchStream } from '../components/Video.jsx';
import ShowTheMath from '../components/ShowTheMath.jsx';
import { Link } from '../lib/router.jsx';
import { getFeaturedMatches, getModelValidation, describeOdds, formatDate, clubPath, matchPath } from '../lib/data.js';

const PICKS_KEY = 'valuebol.picks';
const LABEL = ['home win', 'draw', 'away win'];
const keyOf = (m) => `${m.date}|${m.home}|${m.away}`;
const modelPick = (p) => (p[0] >= p[1] && p[0] >= p[2] ? 0 : p[2] >= p[1] ? 2 : 1);

function MatchPick({ m, pick, onPick }) {
  const short = (n) => n.replace(/ (FC|SC)$/, '');
  const options = [short(m.home), 'Draw', short(m.away)];
  const closed = m.streamStatus === 'live' || m.streamStatus === 'replay';
  const mp = m.probs ? modelPick(m.probs) : null;
  let note = '';
  if (m.probs) {
    if (pick == null) note = `Model pick: ${LABEL[mp]}.`;
    else if (pick === mp) note = `Same as the model: ${LABEL[mp]}.`;
    else note = `Against the model. It has ${LABEL[mp]}.`;
  }
  return (
    <article className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 16, borderColor: pick != null ? 'var(--accent)' : undefined }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        <span>{formatDate(m.date)} · {m.time}</span>
        <span className="muted">{m.competition}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto minmax(0,1fr)', alignItems: 'center', gap: 10, textAlign: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <Crest name={m.home} size={52} />
          <Link to={clubPath(m.home)} style={{ fontWeight: 700, color: 'var(--text)' }}>{m.home}</Link><span className="muted small">ASI #{m.homeRank}</span>
        </div>
        <span className="num muted" style={{ fontSize: 22 }}>VS</span>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <Crest name={m.away} size={52} />
          <Link to={clubPath(m.away)} style={{ fontWeight: 700, color: 'var(--text)' }}>{m.away}</Link><span className="muted small">ASI #{m.awayRank}</span>
        </div>
      </div>
      {closed ? (
        <p className="muted small" style={{ margin: 0 }}>{m.streamStatus === 'live' ? 'Picks are closed. This game is on now.' : 'Picks are closed for this game.'}</p>
      ) : m.probs ? (
        <>
          <div role="group" aria-label="Your pick" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 8 }}>
            {options.map((label, i) => {
              const on = pick === i;
              return (
                <button key={label} type="button" aria-pressed={on} onClick={() => onPick(on ? null : i)}
                  style={{ minHeight: 64, borderRadius: 10, border: `2px solid ${on ? 'var(--accent)' : 'var(--border-strong)'}`, background: on ? 'var(--accent)' : 'var(--surface)', color: on ? 'var(--on-accent)' : 'var(--text)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{label}</span>
                  <span className="num" style={{ fontSize: 22 }}>{m.probs[i]}%</span>
                </button>
              );
            })}
          </div>
          <p className={pick != null && pick !== mp ? 'down small' : 'muted small'} style={{ margin: 0 }}>{describeOdds(m.probs)}. {note}</p>
        </>
      ) : (
        <p className="muted small" style={{ margin: 0, padding: 14, background: 'var(--surface-2)', borderRadius: 10, textAlign: 'center' }}>No prediction yet. One of these clubs hasn't played enough games.</p>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 'auto' }}>
        <MatchStream m={m} />
        <Link to={matchPath(m)} className="link-arrow">Preview →</Link>
      </div>
    </article>
  );
}

export default function Matches() {
  const matches = getFeaturedMatches();
  const model = getModelValidation();
  const [picks, setPicks] = useState({});

  useEffect(() => {
    try { setPicks(JSON.parse(localStorage.getItem(PICKS_KEY) || '{}')); } catch { /* ignore */ }
  }, []);

  const setPick = (m, value) => {
    const next = { ...picks };
    if (value == null) delete next[keyOf(m)]; else next[keyOf(m)] = value;
    setPicks(next);
    try { localStorage.setItem(PICKS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  };

  const pickable = matches.filter((m) => m.probs && !m.streamStatus);
  const made = pickable.filter((m) => picks[keyOf(m)] != null);
  const agree = made.filter((m) => picks[keyOf(m)] === modelPick(m.probs)).length;

  return (
    <>
      <section className="panel-accent" style={{ borderRadius: 0, padding: 0 }}>
        <div className="container" style={{ padding: '44px 24px', display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ flex: '1 1 480px' }}>
            <p className="eyebrow" style={{ color: 'var(--on-accent-2)' }}>Weekly picks</p>
            <h1 className="display display-xl" style={{ marginTop: 6 }}>Beat the model</h1>
            <p style={{ margin: '12px 0 0', fontSize: 17, color: 'var(--on-accent-2)', maxWidth: 560 }}>
              Pick a result for each of this week's big games and see how you do against our model. It gets {model.accuracy}% right.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 28, background: 'rgba(0,0,0,0.18)', borderRadius: 12, padding: '18px 26px' }} aria-live="polite">
            <div className="center"><div className="num" style={{ fontSize: 52 }}>{made.length}/{pickable.length}</div><div className="small">Your picks</div></div>
            <div className="center"><div className="num" style={{ fontSize: 52 }}>{agree}</div><div className="small">Same as model</div></div>
          </div>
        </div>
      </section>

      <div className="container page">
        <section className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {matches.map((m) => <MatchPick key={keyOf(m)} m={m} pick={picks[keyOf(m)]} onPick={(v) => setPick(m, v)} />)}
        </section>
        <section className="card card-pad">
          <ShowTheMath label="How the odds are made">
            <p style={{ margin: 0 }}>Each club has an attack and defense strength fitted to its results (recent matches count more, one-year half-life). The two are combined into expected goals, every scoreline gets a Poisson probability, and the home / draw / away odds are the sums.</p>
            <p className="muted small" style={{ margin: 0 }}>Your picks are saved in this browser only. <Link to="/methodology">Full methodology →</Link></p>
          </ShowTheMath>
        </section>
      </div>
    </>
  );
}
