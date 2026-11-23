import { Link } from '../lib/router.jsx';

const NAV = [
  { to: '/', label: 'Home' },
  { to: '/rankings', label: 'Rankings' },
  { to: '/who-wins', label: 'Who wins?' },
  { to: '/methodology', label: 'How it works' },
];

export function Header() {
  return (
    <header className="site-header">
      <div className="container">
        <Link to="/" className="brand" aria-label="Valuebol LLC home">
          <img src="/logo.png" alt="" />
          <span>Valuebol LLC</span>
        </Link>
        <nav className="nav" aria-label="Main">
          {NAV.map((item) => (
            <Link key={item.to} to={item.to}>
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container">
        <span className="brand" style={{ flexDirection: 'row', gap: 10 }}>
          <img src="/logo.png" alt="" style={{ height: 22 }} />
          <span>Valuebol LLC</span>
        </span>
        <span>
          Data sourced from <a href="https://upsl.com">upsl.com</a> ·{' '}
          <Link to="/methodology">How the numbers work</Link>
        </span>
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
