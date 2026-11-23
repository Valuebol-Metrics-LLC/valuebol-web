import { useState } from 'react';
import { youtubeThumb, youtubeUrl } from '../lib/data.js';
import Crest from './Crest.jsx';

const KIND = { highlights: 'Highlights', full: 'Full game', live: 'Live' };

/** YouTube thumbnail; falls back to a drawn cover with both crests if the image can't load. */
function Thumb({ v, big }) {
  const [failed, setFailed] = useState(false);
  return (
    <div style={{ position: 'relative', aspectRatio: '16 / 9', borderRadius: 10, overflow: 'hidden', background: 'linear-gradient(135deg, #12301c, #0a140d)' }}>
      {!failed ? (
        <img src={youtubeThumb(v.id)} alt="" loading="lazy" onError={() => setFailed(true)} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
      ) : (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: big ? 120 : 76 }}>
          {v.clubs.slice(0, 2).map((c) => <Crest key={c} name={c} size={big ? 84 : 48} />)}
        </div>
      )}
      <span style={{ position: 'absolute', left: 10, top: 10, padding: '3px 8px', borderRadius: 6, fontSize: 12, fontWeight: 700, background: v.kind === 'live' ? '#c62828' : 'rgba(0,0,0,0.75)', color: '#fff' }}>
        {v.kind === 'live' ? '● LIVE' : KIND[v.kind]}
      </span>
      <span aria-hidden="true" style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: big ? 72 : 52, height: big ? 72 : 52, borderRadius: '50%', background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width={big ? 30 : 22} height={big ? 30 : 22} viewBox="0 0 24 24" fill="#fff"><path d="M8 5v14l11-7z" /></svg>
      </span>
    </div>
  );
}

export default function VideoCard({ v, big = false }) {
  return (
    <a href={youtubeUrl(v.id)} target="_blank" rel="noreferrer" className="video-card" style={{ display: 'flex', flexDirection: 'column', gap: 10, color: 'var(--text)' }}>
      <Thumb v={v} big={big} />
      <div>
        <div style={{ fontWeight: 700, fontSize: big ? 20 : 15, lineHeight: 1.3 }}>{v.title}</div>
        <div className="muted small" style={{ marginTop: 4 }}>{v.channel} · {v.when}</div>
      </div>
    </a>
  );
}

/** Watch-live / replay link and live score for a match card. */
export function MatchStream({ m }) {
  if (!m.stream) return null;
  const live = m.streamStatus === 'live';
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
      {live && m.liveScore && (
        <span className="num" style={{ fontSize: 22 }} aria-label={`Live score ${m.liveScore.home} to ${m.liveScore.away}, minute ${m.liveScore.minute}`}>
          {m.liveScore.home}–{m.liveScore.away} <span className="small muted">{m.liveScore.minute}'</span>
        </span>
      )}
      <a className="btn btn-sm" href={m.stream} target="_blank" rel="noreferrer" style={live ? { background: '#c62828', borderColor: '#c62828', color: '#fff' } : undefined}>
        {live ? '● Watch live' : 'Watch the replay'}
      </a>
    </div>
  );
}
