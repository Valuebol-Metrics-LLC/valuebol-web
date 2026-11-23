import { useEffect, useState } from 'react';

const KEY = 'valuebol.theme';

function current() {
  if (typeof document === 'undefined') return 'light';
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

/** Light / dark theme, applied as data-theme on <html> and remembered in the browser. */
export function useTheme() {
  const [theme, setTheme] = useState(current);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem(KEY, theme); } catch { /* storage unavailable */ }
  }, [theme]);

  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))];
}
