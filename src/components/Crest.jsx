// Club crest. Uses the club's logo (scraped from upsl.com or added by hand) when there is one;
// otherwise an initials badge in a stable colour per club, so every page looks finished.
import { useState } from 'react';
import { logoFor } from '../lib/data.js';

const COLORS = ['#B42318', '#1F6F4A', '#6D28D9', '#C2410C', '#0E7490', '#9D174D', '#3F3F46', '#854D0E', '#155E75', '#7E22CE', '#166534', '#9A3412'];
const SKIP = new Set(['FC', 'SC', 'SA', 'CF', 'AFC']);

export function initials(name) {
  let words = name.replace(/[^A-Za-z0-9 ]/g, ' ').split(' ').filter((w) => w && !SKIP.has(w.toUpperCase()));
  if (!words.length) words = name.split(' ');
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.slice(0, 3).map((w) => w[0]).join('').toUpperCase();
}

export function crestColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return COLORS[h % COLORS.length];
}

export default function Crest({ name, logoUrl, size = 34 }) {
  const src = logoUrl ?? logoFor(name);
  const [failed, setFailed] = useState(false);
  if (src && !failed) {
    return (
      <img
        className="crest crest-logo"
        src={src}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        onError={() => setFailed(true)}
        style={{ width: size, height: size, padding: Math.round(size * 0.1) }}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className="crest"
      style={{ width: size, height: size, background: crestColor(name), fontSize: Math.round(size * 0.38) }}
    >
      {initials(name)}
    </span>
  );
}
