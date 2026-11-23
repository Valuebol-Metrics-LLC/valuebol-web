import { Link } from '../lib/router.jsx';
import Crest from '../components/Crest.jsx';
import VideoCard from '../components/Video.jsx';
import ShareButton from '../components/Share.jsx';
import { SectionHead } from '../components/Layout.jsx';
import { useFollowed } from '../lib/follow.js';
import { InstagramIcon, GlobeIcon, StarIcon } from '../components/Icons.jsx';
import { getClub, getRatingRange, clubPath, matchPath, instagramFor, formatDate, describeOdds } from '../lib/data.js';

function Stat({ value, label, tone }) {
  return (
    <div>
      <div className={`num ${tone ?? ''}`} style={{ fontSize: 'clamp(34px, 7vw, 48px)' }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function FinishChart({ race, name }) {
  const max = Math.max(...race.finish.map((p) => Math.max(p, 0)), 1);
  return (
    <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <h3 className="display display-md">Where they finish</h3>
        <p className="muted small" style={{ margin: '4px 0 0' }}>
          {race.conference}, from {race.runs.toLocaleString('en-US')} simulated seasons. Now {race.pts} pts from {race.gp} games.
        </p>
      </div>
      <div className="finish-bars" role="img" aria-label={`${name} finishing position chances`}>
        {race.finish.map((p, i) => (
          <div key={i} className="finish-col">
            <span className="small muted">{p > 0 ? `${p}%` : p < 0 ? '<1' : ''}</span>
            <div className="finish-bar" style={{ height: `${(Math.max(p, p < 0 ? 0.5 : 0) / max) * 100}%` }} />
            <span className="small">{i + 1}</span>
          </div>
        ))}
      </div>
      <Link to="/title-race" className="link-arrow">Play out the title race →</Link>
    </div>
  );
}

export default function Club({ slug }) {
  const club = getClub(slug);
  const [followed, toggle] = useFollowed();

  if (!club) {
    return (
      <div className="container page">
        <h1 className="display display-xl">Club not found</h1>
        <p>We couldn't find that club. Try the search, or <Link to="/rankings">browse the rankings</Link>.</p>
      </div>
    );
  }

  const { name, ranked, race } = club;
  const isFollowed = followed.includes(name);
  const range = getRatingRange();
  const pct = ranked ? Math.round(((ranked.asi - range.lowest) / (range.highest - range.lowest)) * 100) : null;
  const hasLinks = club.website || club.instagram || club.upsl;

  return (
    <>
      <section className="club-hero">
        <div className="container club-hero-row">
          <Crest name={name} logoUrl={club.logo} size={112} />
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p className="eyebrow">{[club.conference, club.city].filter(Boolean).join(' · ') || 'UPSL'}</p>
            <h1 className="display display-xl">{name}</h1>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button type="button" className={`btn btn-sm${isFollowed ? ' btn-primary' : ''}`} aria-pressed={isFollowed} onClick={() => toggle(name)}>
                <StarIcon width={16} height={16} filled={isFollowed} /> {isFollowed ? 'Following' : 'Follow'}
              </button>
              {club.website && <a className="btn btn-sm" href={club.website} target="_blank" rel="noreferrer"><GlobeIcon width={16} height={16} /> Website</a>}
              {club.instagram && <a className="btn btn-sm" href={instagramFor(club.instagram)} target="_blank" rel="noreferrer"><InstagramIcon width={16} height={16} /> @{club.instagram}</a>}
              {club.upsl && <a className="btn btn-sm" href={club.upsl} target="_blank" rel="noreferrer">UPSL page</a>}
              <ShareButton to={clubPath(name)} title={`${name} on Valuebol`} text={ranked ? `${name} are #${ranked.rank} in the UPSL power rankings.` : name} />
            </div>
          </div>
        </div>
      </section>

      <div className="container page">
        {ranked ? (
          <section className="stat-strip" style={{ borderTop: 'none' }}>
            <Stat value={`#${ranked.rank}`} label="Power ranking" tone="accent" />
            <Stat value={ranked.asi.toLocaleString('en-US')} label="ASI rating" />
            <Stat value={ranked.record} label="Fall 2026 W-D-L" />
            <Stat value={`${ranked.last5 > 0 ? '+' : ''}${ranked.last5}`} label="ASI, last 5 games" tone={ranked.last5 >= 0 ? 'up' : 'down'} />
          </section>
        ) : (
          <p className="muted" style={{ margin: 0 }}>Outside the top 30 right now. The full table for every club is coming to this page.</p>
        )}

        {ranked && (
          <section className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <b>Rating compared with the whole league</b>
              <span className="muted small">{ranked.matches} rated matches since 2017</span>
            </div>
            <div className="meter"><div style={{ width: `${pct}%` }} /></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }} className="small muted">
              <span>Lowest {range.lowest}</span><span>Highest {range.highest}</span>
            </div>
          </section>
        )}

        {club.matches.length > 0 && (
          <section>
            <SectionHead title="Coming up" />
            <div className="card">
              {club.matches.map((m, i) => {
                const home = m.home === name;
                const opp = home ? m.away : m.home;
                const win = m.probs ? m.probs[home ? 0 : 2] : null;
                return (
                  <Link key={m.date + opp} to={matchPath(m)} className="list-row" style={{ borderTop: i ? '1px solid var(--border)' : 'none' }}>
                    <Crest name={opp} size={36} />
                    <span style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ display: 'block', fontWeight: 700 }}>{home ? 'vs' : 'at'} {opp}</span>
                      <span className="muted small">{formatDate(m.date)} · {m.time} · {m.competition}</span>
                    </span>
                    {m.streamStatus === 'live' && <span className="live-pill">● Live</span>}
                    {win != null && <span className="num accent" style={{ fontSize: 24 }} title={describeOdds(m.probs)}>{win}%</span>}
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        <section className="row">
          {race && <div className="grow"><FinishChart race={race} name={name} /></div>}
          <div className={race ? 'side' : 'grow'} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {club.scorers.length > 0 && (
              <div className="card">
                <h3 className="display display-md" style={{ padding: '20px 20px 4px' }}>Top scorers</h3>
                {club.scorers.map((p) => (
                  <div key={p.name} className="list-row" style={{ borderTop: '1px solid var(--border)' }}>
                    <span style={{ flex: 1, fontWeight: 700 }}>{p.name}</span>
                    <span className="num" style={{ fontSize: 26 }}>{p.goals}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <h3 className="display display-md">{hasLinks ? 'Club links' : 'Missing club links'}</h3>
              {hasLinks ? (
                <p className="muted small" style={{ margin: 0 }}>Something out of date? Let us know and we'll fix it.</p>
              ) : (
                <p className="muted small" style={{ margin: 0 }}>We don't have a website or Instagram for {name} yet. If you play for or run the club, send them in.</p>
              )}
              <div><Link to="/contact" className="btn btn-sm">Send us the links</Link></div>
            </div>
          </div>
        </section>

        {club.videos.length > 0 && (
          <section>
            <SectionHead title="Watch" />
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 24 }}>
              {club.videos.map((v) => <VideoCard key={v.id} v={v} />)}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
