import { useState } from 'react';
import { site, instagramUrl } from '../config.js';
import { InstagramIcon, MailIcon } from '../components/Icons.jsx';

const ROLES = ['Fan', 'Player', 'Coach', 'Club', 'Sponsor', 'Media'];
const TOPICS = [
  'General question',
  'Fix a stat or result',
  'Get my club’s ranking badge',
  'Sponsorship',
  'Partnership or press',
];

export default function Contact() {
  const [role, setRole] = useState('Fan');
  const [topic, setTopic] = useState(TOPICS[0]);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const submit = (e) => {
    e.preventDefault();
    if (!name.trim() || !email.includes('@') || message.trim().length < 5) {
      setError('Add your name, a valid email and a short message.');
      return;
    }
    setError('');
    const subject = `[${topic}] from ${name} (${role})`;
    const body = `${message}\n\n${name}\n${email}\nI am a: ${role}`;
    // No server yet: hand the message to the visitor's email app, addressed to the team.
    window.location.href = `mailto:${site.contactEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    setSent(true);
  };

  return (
    <div className="container page" style={{ maxWidth: 1040 }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p className="eyebrow">Contact us</p>
        <h1 className="display display-xl">Talk to Valuebol</h1>
        <p className="lead">Spotted a wrong result? Want your club's badge? Interested in sponsoring? We read everything.</p>
      </section>

      <section className="row" style={{ alignItems: 'stretch' }}>
        <form className="grow card card-pad" onSubmit={submit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="field">
            <span>I am a</span>
            <div className="segmented" role="group" aria-label="I am a">
              {ROLES.map((r) => (
                <button key={r} type="button" aria-pressed={role === r} onClick={() => setRole(r)}>{r}</button>
              ))}
            </div>
          </div>
          <label className="field">
            <span>What is it about?</span>
            <select className="input" value={topic} onChange={(e) => setTopic(e.target.value)}>
              {TOPICS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <label className="field"><span>Name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
            <label className="field"><span>Email</span><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label>
          </div>
          <label className="field">
            <span>Message</span>
            <textarea className="input" value={message} onChange={(e) => setMessage(e.target.value)} placeholder={topic === 'Fix a stat or result' ? 'Which match, and what should it say?' : 'How can we help?'} />
          </label>
          {error && <p role="alert" className="down" style={{ margin: 0 }}>{error}</p>}
          {sent && !error && <p role="status" className="up" style={{ margin: 0 }}>Your email app should open with the message ready. Hit send there and we'll get back to you.</p>}
          <div><button type="submit" className="btn btn-primary"><MailIcon /> Send message</button></div>
        </form>

        <aside className="side" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <a className="card card-pad" href={instagramUrl} target="_blank" rel="noreferrer" style={{ display: 'flex', gap: 14, alignItems: 'center', color: 'var(--text)' }}>
            <span className="icon-btn" style={{ background: 'var(--accent)', color: 'var(--on-accent)', borderColor: 'var(--accent)' }}><InstagramIcon /></span>
            <span>
              <span style={{ display: 'block', fontWeight: 700 }}>DM us on Instagram</span>
              <span className="muted small">@{site.instagramHandle} · fastest reply</span>
            </span>
          </a>
          <a className="card card-pad" href={`mailto:${site.contactEmail}`} style={{ display: 'flex', gap: 14, alignItems: 'center', color: 'var(--text)' }}>
            <span className="icon-btn"><MailIcon /></span>
            <span>
              <span style={{ display: 'block', fontWeight: 700 }}>Email</span>
              <span className="muted small">{site.contactEmail}</span>
            </span>
          </a>
          <div className="card card-pad">
            <h2 style={{ margin: '0 0 8px', fontSize: 17 }}>Clubs: get your badge</h2>
            <p className="muted small" style={{ margin: 0 }}>Every ranked club can get an official ASI ranking badge for Instagram and its website. Pick "Get my club's ranking badge" in the form.</p>
          </div>
        </aside>
      </section>
    </div>
  );
}
