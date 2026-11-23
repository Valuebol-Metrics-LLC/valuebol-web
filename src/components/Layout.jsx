import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Link, useRouter } from '../lib/router.jsx';
import { useTheme } from '../lib/theme.js';
import { site, instagramUrl } from '../config.js';
import { InstagramIcon, SunIcon, MoonIcon, MenuIcon, CloseIcon, HomeIcon, BallIcon, ListIcon, PlayIcon, SearchIcon } from './Icons.jsx';
import { ClubSearchDialog, SearchTrigger } from './ClubSearch.jsx';

const SearchContext = createContext(() => {});
export const useOpenSearch = () => useContext(SearchContext);

/** Holds the club-search dialog so the header, tab bar and pages can all open it. "/" opens it too. */
export function SearchProvider({ children }) {
  const [open, setOpen] = useState(false);
  const openSearch = useCallback(() => setOpen(true), []);
  const close = useCallback(() => setOpen(false), []);
  useEffect(() => {
    const onKey = (e) => {
      const t = e.target;
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
      if (e.key === '/' && !typing) { e.preventDefault(); setOpen(true); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
    <SearchContext.Provider value={openSearch}>
      {children}
      <ClubSearchDialog open={open} onClose={close} />
    </SearchContext.Provider>
  );
}

const NAV = [
  { to: '/', label: 'Home' },
  { to: '/matches', label: 'Matches' },
  { to: '/videos', label: 'Videos' },
  { to: '/rankings', label: 'Rankings' },
  { to: '/who-wins', label: 'Who wins?' },
  { to: '/title-race', label: 'Title race' },
];
const NAV_MORE = [
  { to: '/about', label: 'About' },
  { to: '/methodology', label: 'How the numbers work' },
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
  const openSearch = useOpenSearch();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  // On the homepage the header sits on top of the video until you scroll.
  const overHero = path === '/' && !scrolled && !open;

  return (
    <header className={`site-header${overHero ? ' over-hero' : ''}`}>
      <div className="container header-row">
        <Link to="/" className="brand-inline" aria-label={`${site.name} home`}>
          <Logo height={26} />
          <span>Valuebol</span>
        </Link>
        <nav className="nav-main" aria-label="Main">
          {NAV.map((item) => <Link key={item.to} to={item.to}>{item.label}</Link>)}
        </nav>
        <div className="header-tools">
          <SearchTrigger onOpen={openSearch} />
          <a className="icon-btn ig-btn" href={instagramUrl} target="_blank" rel="noreferrer" aria-label={`Instagram @${site.instagramHandle}`}>
            <InstagramIcon />
          </a>
          <button type="button" className="icon-btn" onClick={toggleTheme} aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
          <Link to="/contact" className="btn btn-primary btn-sm header-cta">Contact</Link>
          <button type="button" className="icon-btn menu-btn" aria-expanded={open} aria-controls="mobile-nav" aria-label="Menu" onClick={() => setOpen(!open)}>
            {open ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" className="nav-mobile container" aria-label="Mobile">
          {[...NAV, ...NAV_MORE].map((item) => <Link key={item.to} to={item.to}>{item.label}</Link>)}
        </nav>
      )}
    </header>
  );
}

const TABS = [
  { to: '/', label: 'Home', Icon: HomeIcon },
  { to: '/matches', label: 'Matches', Icon: BallIcon },
  { to: '/rankings', label: 'Rankings', Icon: ListIcon },
  { to: '/videos', label: 'Videos', Icon: PlayIcon },
];

/** Thumb-reach navigation on phones. */
export function TabBar() {
  const openSearch = useOpenSearch();
  return (
    <nav className="tab-bar" aria-label="Quick">
      {TABS.map(({ to, label, Icon }) => (
        <Link key={to} to={to}><Icon /><span>{label}</span></Link>
      ))}
      <button type="button" onClick={openSearch}><SearchIcon /><span>Clubs</span></button>
    </nav>
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
          <Link to="/rankings">All clubs</Link>
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
        <p className="muted" style={{ margin: 0 }}>New rankings, picks and player cards every week. Tag us when you post your stats.</p>
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
