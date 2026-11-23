import { useState } from 'react';
import VideoCard from '../components/Video.jsx';
import { getVideos } from '../lib/data.js';
import { Link } from '../lib/router.jsx';

const FILTERS = [
  ['all', 'All'],
  ['live', 'Live'],
  ['highlights', 'Highlights'],
  ['full', 'Full games'],
];

export default function Videos() {
  const all = getVideos();
  const [filter, setFilter] = useState('all');
  const featured = all.find((v) => v.featured);
  const list = all.filter((v) => (filter === 'all' ? !v.featured : v.kind === filter));
  const liveCount = all.filter((v) => v.kind === 'live').length;

  return (
    <div className="container page">
      <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <p className="eyebrow">UPSL on YouTube</p>
          <h1 className="display display-xl">Videos</h1>
          <p className="lead">Highlights, full games and live streams from around the league.</p>
        </div>
        <div className="segmented" role="group" aria-label="Filter videos">
          {FILTERS.map(([k, label]) => (
            <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)}>
              {label}{k === 'live' && liveCount ? ` (${liveCount})` : ''}
            </button>
          ))}
        </div>
      </section>

      {filter === 'all' && featured && (
        <section className="card card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24, alignItems: 'center' }}>
          <VideoCard v={featured} big />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p className="eyebrow">Featured</p>
            <h2 className="display display-lg">2026 National Final</h2>
            <p style={{ margin: 0 }}>Deportivo Rose City and Miami United FC played for the national title in Los Angeles. Both are still in our top 5.</p>
          </div>
        </section>
      )}

      <section className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 24 }}>
        {list.map((v) => <VideoCard key={v.id} v={v} />)}
      </section>
      {list.length === 0 && <p className="muted">Nothing here right now.</p>}

      <p className="muted small" style={{ margin: 0 }}>Videos open on YouTube and belong to the channels that posted them. Want your club's games here? <Link to="/contact">Send us your channel</Link>.</p>
    </div>
  );
}
