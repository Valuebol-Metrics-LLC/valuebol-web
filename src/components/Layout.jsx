import { useEffect, useState } from 'react';
import { Link, useRouter } from '../lib/router.jsx';
import { useTheme } from '../lib/theme.js';
import { site, instagramUrl } from '../config.js';
import { InstagramIcon, SunIcon, MoonIcon, MenuIcon, CloseIcon } from './Icons.jsx';

const NAV = [
  { to: '/', label: 'Home' },
  { to: '/matches', label: 'Matches' },
  { to: '/rankings', label: 'Rankings' },
  { to: '/who-wins', label: 'Who wins?' },
  { to: '/title-race', label: 'Title race' },
  { to: '/about', label: 'About' },
  { to: '/contact', label: 'Contact' },
];

function Logo({ height = 30 }) {
  return (
    <>
      <img className="logo-light" src="logo.png" alt="" style={{ height, width: 'auto', display: 'block' }} />
      <img className="logo-dark" src="logo-dark.png" alt="" style={{ height, width: 'auto' }} />
    </>
  );
}

export function Header() {
  const [theme, toggleTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const { path } = useRouter();
  useEffect(() => setOpen(false), [path]);

  return (
    <header className="site-header">
      <div className="container">
        <Link to="/" className="brand" aria-label={`${site.name} home`}>
          <Logo />
          <span>{site.name}</span>
        </Link>
        <nav id="main-nav" className={`nav${open ? ' open' : ''}`} aria-label="Main">
          {NAV.map((item) => (
            <Link key={item.to} to={item.to}>{item.label}</Link>
          ))}
        </nav>
        <div className="header-tools">
          <a className="icon-btn" href={instagramUrl} target="_blank" rel="noreferrer" aria-label={`Valuebol on Instagram, @${site.instagramHandle}`}>
            <InstagramIcon />
          </a>
          <button type="button" className="icon-btn" onClick={toggleTheme} aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
          <button type="button" className="icon-btn menu-btn" aria-expanded={open} aria-controls="main-nav" aria-label="Menu" onClick={() => setOpen(!open)}>
            {open ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container" style={{ alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span className="brand" style={{ alignItems: 'flex-start' }}>
            <Logo height={26} />
            <span>{site.name}</span>
          </span>
          <span>Data sourced from <a href="https://upsl.com">upsl.com</a></span>
          <span>© 2026 {site.name}. All rights reserved.</span>
        </div>
        <nav aria-label="Footer" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 20px' }}>
          <Link to="/about">About us</Link>
          <Link to="/contact">Contact</Link>
          <Link to="/methodology">How the numbers work</Link>
          <Link to="/legal">Copyright &amp; terms</Link>
          <a href={instagramUrl} target="_blank" rel="noreferrer">Instagram @{site.instagramHandle}</a>
        </nav>
      </div>
    </footer>
  );
}

export function SectionHead({ kicker, title, sub, action }) {
  return (
    <div className="section-head">
      <div>
        {kicker && <p className="kicker">{kicker}</p>}
        <h2 className="display display-lg">{title}</h2>
        {sub && <p className="muted small" style={{ margin: '6px 0 0' }}>{sub}</p>}
      </div>
      {action}
    </div>
  );
}

/** Instagram follow band used on Home and About. */
export function InstagramBand() {
  const week = [
    ['Mon', 'Power rankings'],
    ['Thu', 'Matchday call-up'],
    ['Fri', 'Beat the model picks'],
    ['Sun', 'Results + movers'],
  ];
  return (
    <section className="card card-pad" style={{ display: 'flex', flexWrap: 'wrap', gap: 28, alignItems: 'center' }}>
      <div style={{ flex: '1 1 320px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <p className="eyebrow">On Instagram</p>
        <h2 className="display display-lg">Follow @{site.instagramHandle}</h2>
        <p className="muted" style={{ margin: 0 }}>Rankings, picks and player cards every week. Tag us when you post your stats.</p>
        <div><a className="btn btn-primary" href={instagramUrl} target="_blank" rel="noreferrer"><InstagramIcon /> Follow on Instagram</a></div>
      </div>
      <div style={{ flex: '1 1 320px', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        {week.map(([d, what]) => (
          <div key={d} style={{ background: 'var(--surface-2)', borderRadius: 10, padding: '12px 14px' }}>
            <div className="num accent" style={{ fontSize: 22 }}>{d}</div>
            <div style={{ fontWeight: 600 }}>{what}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
