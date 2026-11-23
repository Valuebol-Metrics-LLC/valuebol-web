// Club crest. Shows the club's logo when `logoUrl` is set; otherwise an initials badge
// in a stable colour per club, so pages look finished before every logo arrives.
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
  if (logoUrl) {
    return <img src={logoUrl} alt="" width={size} height={size} style={{ borderRadius: '50%', objectFit: 'cover', flex: 'none' }} />;
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
