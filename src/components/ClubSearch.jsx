import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from '../lib/router.jsx';
import { getAllClubs, clubPath } from '../lib/data.js';
import Crest from './Crest.jsx';
import { SearchIcon, CloseIcon } from './Icons.jsx';

const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

/** Full-screen club finder. Opened from the header, the tab bar, or by pressing "/". */
export function ClubSearchDialog({ open, onClose }) {
  const { navigate } = useRouter();
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const input = useRef(null);
  const clubs = useMemo(getAllClubs, []);

  const results = useMemo(() => {
    const n = norm(q.trim());
    if (!n) return clubs.slice(0, 8);
    return clubs
      .filter((c) => norm(c.name).includes(n) || (c.conference && norm(c.conference).includes(n)))
      .sort((a, b) => norm(a.name).indexOf(n) - norm(b.name).indexOf(n))
      .slice(0, 10);
  }, [q, clubs]);

  useEffect(() => { if (open) { setQ(''); setActive(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);
  useEffect(() => setActive(0), [q]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  const go = (c) => { onClose(); navigate(clubPath(c.name)); };
  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === 'Enter' && results[active]) go(results[active]);
  };

  return (
    <div className="search-overlay" role="dialog" aria-modal="true" aria-label="Find a club" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="search-panel">
        <div className="search-field">
          <SearchIcon />
          <input
            ref={input}
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Find a club or conference"
            aria-label="Club name"
            role="combobox"
            aria-expanded="true"
            aria-controls="club-results"
            aria-activedescendant={results[active] ? `club-opt-${active}` : undefined}
            autoComplete="off"
          />
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close search"><CloseIcon /></button>
        </div>
        <p className="search-hint">{q.trim() ? `${results.length} match${results.length === 1 ? '' : 'es'}` : 'Top clubs right now'}</p>
        <ul id="club-results" role="listbox" className="search-results">
          {results.map((c, i) => (
            <li key={c.name} id={`club-opt-${i}`} role="option" aria-selected={i === active}>
              <button type="button" onClick={() => go(c)} onMouseEnter={() => setActive(i)} className={i === active ? 'active' : ''}>
                <Crest name={c.name} size={34} />
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: 'block', fontWeight: 700 }}>{c.name}</span>
                  <span className="muted small">{c.conference ?? 'UPSL'}</span>
                </span>
                {c.rank && <span className="num muted" style={{ fontSize: 20 }}>#{c.rank}</span>}
              </button>
            </li>
          ))}
          {!results.length && <li className="muted" style={{ padding: '18px 12px' }}>No club by that name yet. We add clubs as their results come in.</li>}
        </ul>
      </div>
    </div>
  );
}

/** Header trigger that looks like a search field on wide screens and an icon on small ones. */
export function SearchTrigger({ onOpen }) {
  return (
    <button type="button" className="search-trigger" onClick={onOpen} aria-label="Find a club">
      <SearchIcon width={18} height={18} />
      <span className="search-trigger-text">Find a club</span>
      <kbd>/</kbd>
    </button>
  );
}
