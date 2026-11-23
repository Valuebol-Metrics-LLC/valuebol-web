import { useEffect, useState } from 'react';
import { Link } from '../lib/router.jsx';
import { SectionHead, InstagramBand, useOpenSearch } from '../components/Layout.jsx';
import Crest from '../components/Crest.jsx';
import VideoCard, { MatchStream } from '../components/Video.jsx';
import { SearchIcon } from '../components/Icons.jsx';
import { useFollowed } from '../lib/follow.js';
import { heroVideo } from '../config.js';
import { getVideos, getCoverage, getFeaturedMatches, getModelValidation, getRankings, getTopScorers, getAllClubs, describeOdds, formatDate, clubPath, matchPath, youtubeUrl } from '../lib/data.js';

/** Muted looping match footage behind the hero, under a dark green wash. */
function HeroVideo() {
  const [play, setPlay] = useState(false);
  useEffect(() => {
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const saveData = navigator.connection?.saveData;
    if (!calm && !saveData) setPlay(true);
  }, []);
  const { youtubeId: id, start, mp4 } = heroVideo;
  const src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&loop=1&playlist=${id}&controls=0&disablekb=1&modestbranding=1&playsinline=1&rel=0&iv_load_policy=3&start=${start}`;
  return (
    <div className="hero-media" aria-hidden="true">
      <img src={`https://i.ytimg.com/vi/${id}/maxresdefault.jpg`} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
      {play && (mp4
        ? <video src={mp4} autoPlay muted loop playsInline />
        : <iframe src={src} title="Background video" tabIndex={-1} allow="autoplay; encrypted-media" />)}
      <div className="hero-wash" />
    </div>
  );
}

function YourClubs() {
  const [followed] = useFollowed();
  const openSearch = useOpenSearch();
  const all = getAllClubs();
  const mine = followed.map((n) => all.find((c) => c.name === n)).filter(Boolean);
  if (!mine.length) {
    return (
      <section className="card card-pad follow-nudge">
        <div style={{ flex: '1 1 300px' }}>
          <h2 className="display display-md">Follow your club</h2>
          <p className="muted small" style={{ margin: '4px 0 0' }}>Find your team, tap Follow, and it shows up here every time you visit.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={openSearch}><SearchIcon width={18} height={18} /> Find my club</button>
      </section>
    );
  }
  return (
    <section>
      <SectionHead title="Your clubs" action={<button type="button" className="link-arrow" style={{ background: 'none', border: 0, color: 'var(--accent-text)' }} onClick={openSearch}>Add a club +</button>} />
      <div className="club-chips">
        {mine.map((c) => (
          <Link key={c.name} to={clubPath(c.name)} className="club-chip">
            <Crest name={c.name} size={40} />
            <span style={{ minWidth: 0 }}>
              <span style={{ display: 'block', fontWeight: 700 }}>{c.name}</span>
              <span className="muted small">{c.rank ? `#${c.rank}` : 'Unranked'}{c.conference ? ` · ${c.conference}` : ''}</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

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
            <Link to={clubPath(name)} style={{ fontWeight: 700, color: 'var(--text)' }}>{name}</Link>
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
        <p className="muted small" style={{ margin: 0 }}>No prediction yet. One of these clubs hasn't played enough games.</p>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 'auto' }}>
        <MatchStream m={m} />
        <Link to={matchPath(m)} className="link-arrow">Preview →</Link>
      </div>
    </article>
  );
}

export default function Home() {
  const cov = getCoverage();
  const top = getRankings().slice(0, 5);
  const matches = getFeaturedMatches().slice(0, 4);
  const videos = getVideos().filter((v) => !v.featured).slice(0, 3);
  const model = getModelValidation();
  const scorers = getTopScorers();
  const openSearch = useOpenSearch();

  return (
    <>
      <section className="hero">
        <HeroVideo />
        <div className="container hero-inner">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1000 }}>
            <p className="eyebrow hero-eyebrow">UPSL analytics · Fall 2026</p>
            <h1 className="display hero-title">
              Bridging the gap between amateur and <span className="hero-accent">professional</span> football.
            </h1>
            <p className="lead hero-lead">Rankings, match predictions and stats for every club in the UPSL.</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              <button type="button" className="btn btn-primary" onClick={openSearch}><SearchIcon width={18} height={18} /> Find your club</button>
              <Link to="/rankings" className="btn btn-ghost">See the rankings</Link>
              <a href={youtubeUrl(heroVideo.youtubeId)} target="_blank" rel="noreferrer" className="btn btn-ghost">▶ Watch the final</a>
            </div>
          </div>
          <div className="stat-strip hero-stats">
            <div><div className="num">{cov.teams}</div><div className="stat-label">Teams tracked</div></div>
            <div><div className="num">{cov.conferences}</div><div className="stat-label">Conferences</div></div>
            <div><div className="num">{cov.matches}</div><div className="stat-label">Matches analysed</div></div>
            <div><div className="num">{cov.since}</div><div className="stat-label">Data since</div></div>
          </div>
        </div>
      </section>

      <div className="container page">
        <YourClubs />

        <section>
          <SectionHead title="This week's big matches" action={<Link to="/matches" className="link-arrow">Make your picks →</Link>} />
          <div className="grid grid-auto">
            {matches.map((m) => <MatchCard key={m.date + m.home} m={m} />)}
          </div>
        </section>

        <section className="row">
          <div className="grow">
            <SectionHead title="Power rankings" sub={`Top 5 of ${cov.activeClubs} active clubs`} action={<Link to="/rankings" className="link-arrow">Full rankings →</Link>} />
            <div className="card">
              {top.map((t, i) => (
                <Link key={t.name} to={clubPath(t.name)} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderTop: i ? '1px solid var(--border)' : 'none', color: 'var(--text)' }}>
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
            <SectionHead title="Golden boot" sub="Fall 2026" />
            <div className="card">
              {scorers.slice(0, 5).map((p, i) => (
                <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                  <span className="num muted" style={{ fontSize: 22, width: 18 }}>{i + 1}</span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: 'block', fontWeight: 700 }}>{p.name}</span>
                    <Link to={clubPath(p.club)} className="small">{p.club}</Link>
                  </span>
                  <span className="num" style={{ fontSize: 30 }}>{p.goals}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="panel-accent" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 32 }}>
          <div style={{ flex: '1 1 320px' }}>
            <p className="eyebrow" style={{ color: 'var(--on-accent-2)' }}>Model accuracy</p>
            <h2 className="display display-lg" style={{ marginTop: 8 }}>We pick the right result {model.accuracy}% of the time</h2>
            <p className="muted" style={{ margin: '10px 0 0' }}>Checked on {model.matchesTested.toLocaleString('en-US')} Spring 2026 league games the model hadn't seen. Going by league averages alone gets {model.baseline}%.</p>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 28 }}>
            <div><div className="num" style={{ fontSize: 'clamp(44px, 12vw, 64px)' }}>{model.accuracy}%</div><div className="small">Valuebol model</div></div>
            <div><div className="num" style={{ fontSize: 'clamp(44px, 12vw, 64px)', opacity: 0.7 }}>{model.baseline}%</div><div className="small">Baseline</div></div>
          </div>
          <Link to="/methodology" className="btn" style={{ background: 'transparent', color: '#fff', borderColor: 'var(--on-accent-2)' }}>How it works</Link>
        </section>

        <section>
          <SectionHead title="Latest videos" action={<Link to="/videos" className="link-arrow">All videos →</Link>} />
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 24 }}>
            {videos.map((v) => <VideoCard key={v.id} v={v} />)}
          </div>
        </section>

        <InstagramBand />
      </div>
    </>
  );
}
