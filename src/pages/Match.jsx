import { Link } from '../lib/router.jsx';
import Crest from '../components/Crest.jsx';
import ShareButton from '../components/Share.jsx';
import { MatchStream } from '../components/Video.jsx';
import { CalendarIcon } from '../components/Icons.jsx';
import { getMatchBySlug, getRankings, clubPath, matchPath, describeOdds, formatDate, eloExpected, eloStake } from '../lib/data.js';

/** Turns "7:00 PM" on 2026-11-27 into a calendar timestamp (local time, 2 hours long). */
function icsTimes(date, time) {
  const m = /^(\d{1,2}):(\d{2})\s*(AM|PM)(?:\s*(PT|MT|CT|ET))?$/i.exec(time ?? '');
  if (!m) return null;
  const zones = { PT: 'America/Los_Angeles', MT: 'America/Denver', CT: 'America/Chicago', ET: 'America/New_York' };
  let h = Number(m[1]) % 12;
  if (m[3].toUpperCase() === 'PM') h += 12;
  const d = date.replace(/-/g, '');
  const pad = (n) => String(n).padStart(2, '0');
  const end = h + 2;
  const endDay = end >= 24 ? String(Number(d) + 1) : d; // good enough for fixture times
  const tz = m[4] ? zones[m[4].toUpperCase()] : null;
  return [`${d}T${pad(h)}${m[2]}00`, `${endDay}T${pad(end % 24)}${m[2]}00`, tz];
}

function downloadIcs(m) {
  const t = icsTimes(m.date, m.time);
  if (!t) return;
  const url = new URL(window.location.href).href;
  const body = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Valuebol LLC//Match//EN', 'BEGIN:VEVENT',
    `UID:${m.date}-${m.home}-${m.away}@valuebol-metrics.com`.replace(/\s+/g, ''),
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}Z`,
    t[2] ? `DTSTART;TZID=${t[2]}:${t[0]}` : `DTSTART:${t[0]}`,
    t[2] ? `DTEND;TZID=${t[2]}:${t[1]}` : `DTEND:${t[1]}`,
    `SUMMARY:${m.home} vs ${m.away}`,
    `DESCRIPTION:${m.competition}. Preview: ${url}`,
    'BEGIN:VALARM', 'TRIGGER:-PT1H', 'ACTION:DISPLAY', 'DESCRIPTION:Kick-off in 1 hour', 'END:VALARM',
    'END:VEVENT', 'END:VCALENDAR',
  ].join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([body], { type: 'text/calendar' }));
  a.download = `${m.home}-vs-${m.away}.ics`.replace(/\s+/g, '-');
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function Side({ name, rank, pct, align }) {
  return (
    <Link to={clubPath(name)} className="match-side" style={{ textAlign: align, alignItems: align === 'right' ? 'flex-end' : 'flex-start' }}>
      <Crest name={name} size={84} />
      <span style={{ fontWeight: 800, fontSize: 20, lineHeight: 1.2, color: 'var(--text)' }}>{name}</span>
      <span className="muted small">{rank ? `Ranked #${rank}` : 'Unranked'}</span>
      {pct != null && <span className={`num ${align === 'right' ? 'down' : 'accent'}`} style={{ fontSize: 'clamp(44px, 10vw, 72px)' }}>{pct}%</span>}
    </Link>
  );
}

export default function Match({ slug }) {
  const m = getMatchBySlug(slug);
  if (!m) {
    return (
      <div className="container page">
        <h1 className="display display-xl">Match not found</h1>
        <p><Link to="/matches">See this week's matches</Link></p>
      </div>
    );
  }
  const ratings = Object.fromEntries(getRankings().map((r) => [r.name, r.asi]));
  const hasRatings = ratings[m.home] && ratings[m.away];
  const exp = hasRatings ? eloExpected(ratings[m.home], ratings[m.away]) : null;
  const canCalendar = !m.streamStatus && icsTimes(m.date, m.time);

  return (
    <div className="container page">
      <section style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
          <p className="eyebrow">{m.competition} · {formatDate(m.date)} · {m.time}</p>
          <Link to="/matches" className="link-arrow">All matches →</Link>
        </div>
        <div className="card card-pad match-board">
          <Side name={m.home} rank={m.homeRank} pct={m.probs?.[0]} align="left" />
          <div className="match-mid">
            {m.liveScore ? (
              <span className="num" style={{ fontSize: 56 }}>{m.liveScore.home}–{m.liveScore.away}</span>
            ) : (
              <span className="num muted" style={{ fontSize: 32 }}>VS</span>
            )}
            {m.probs && <span className="small muted">Draw {m.probs[1]}%</span>}
          </div>
          <Side name={m.away} rank={m.awayRank} pct={m.probs?.[2]} align="right" />
        </div>
        {m.probs ? (
          <div>
            <div className="prob" style={{ height: 12 }} aria-hidden="true">
              <div className="h" style={{ width: `${m.probs[0]}%` }} />
              <div className="d" style={{ width: `${m.probs[1]}%` }} />
              <div className="a" style={{ width: `${m.probs[2]}%` }} />
            </div>
            <p style={{ margin: '10px 0 0' }}><b>{describeOdds(m.probs)}.</b> <span className="muted">Valuebol's model, based on both clubs' results and goals.</span></p>
          </div>
        ) : (
          <p className="muted" style={{ margin: 0 }}>No prediction for this one. One of the clubs hasn't played enough games yet.</p>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <MatchStream m={m} />
          {canCalendar && (
            <button type="button" className="btn btn-sm" onClick={() => downloadIcs(m)}>
              <CalendarIcon width={16} height={16} /> Add to calendar
            </button>
          )}
          {!m.streamStatus && <Link to="/matches" className="btn btn-sm btn-primary">Make your pick</Link>}
          <ShareButton to={matchPath(m)} title={`${m.home} vs ${m.away}`} text={m.probs ? `${m.home} vs ${m.away}: ${describeOdds(m.probs).toLowerCase()} (${m.probs.join('/')})` : `${m.home} vs ${m.away}`} />
        </div>
      </section>

      {hasRatings && (
        <section className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 className="display display-md">What's at stake</h2>
          <p style={{ margin: 0 }}>
            A win is worth <b className="accent">+{eloStake(exp)}</b> ASI points to {m.home} and <b className="accent">+{eloStake(1 - exp)}</b> to {m.away}.
            {' '}The underdog gains more for an upset.
          </p>
          <p className="muted small" style={{ margin: 0 }}>Ratings now: {m.home} {ratings[m.home]}, {m.away} {ratings[m.away]}. <Link to="/methodology">How ratings work</Link></p>
        </section>
      )}

      <section className="row">
        <Link to={clubPath(m.home)} className="card card-pad grow" style={{ color: 'var(--text)' }}>More on {m.home} →</Link>
        <Link to={clubPath(m.away)} className="card card-pad side" style={{ color: 'var(--text)' }}>More on {m.away} →</Link>
      </section>
    </div>
  );
}
