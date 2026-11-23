// Followed clubs, kept in this browser. Shared by Rankings, club pages and Home.
import { useEffect, useState } from 'react';

const KEY = 'valuebol.followedClubs';
const EVENT = 'valuebol:follow';

const load = () => {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
};

export function useFollowed() {
  const [followed, setFollowed] = useState([]);
  useEffect(() => {
    setFollowed(load());
    const sync = () => setFollowed(load());
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  const toggle = (name) => {
    const cur = load();
    const next = cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name];
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage unavailable */ }
    setFollowed(next);
    window.dispatchEvent(new Event(EVENT));
  };
  return [followed, toggle];
}
