import { Link } from '../lib/router.jsx';
import { site } from '../config.js';

const YEAR = 2026;

const SECTIONS = [
  {
    title: 'Copyright',
    body: [
      `© ${YEAR} ${site.name}. All rights reserved.`,
      `The Valuebol name and logo, the Amateur Soccer Index (ASI), the match projections, conference simulations and other ratings, plus the site's design, text and graphics are owned by ${site.name}. You may not copy, republish or sell them without written permission.`,
    ],
  },
  {
    title: 'Sharing',
    body: [
      'Players, clubs and fans may share Valuebol pages, rankings, stat cards and ranking badges on social media and club websites, as long as the content is not changed and Valuebol is credited (for example "via Valuebol" or a tag of our Instagram account).',
    ],
  },
  {
    title: 'Data sources and third-party marks',
    body: [
      'Match results and schedules come from publicly available information on upsl.com. Valuebol is independent and is not affiliated with or endorsed by the United Premier Soccer League.',
      'Club names, crests and logos belong to their clubs and are shown only to identify them. Videos linked from this site belong to their owners.',
    ],
  },
  {
    title: 'Using the site',
    body: [
      'Ratings and predictions are estimates for information and entertainment. They are not guarantees and must not be used for betting.',
      'Picks, followed clubs and your theme choice are saved only in your own browser. We do not run user accounts yet.',
    ],
  },
  {
    title: 'Corrections and takedown requests',
    body: [
      'If a result is wrong, or you believe something on this site uses your work without permission, contact us and we will review it promptly.',
    ],
  },
];

export default function Legal() {
  return (
    <div className="container page" style={{ maxWidth: 860 }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p className="eyebrow">Legal</p>
        <h1 className="display display-xl">Copyright &amp; terms</h1>
        <p className="lead">What you can and can't do with the content on this site.</p>
      </section>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {SECTIONS.map((s) => (
          <section key={s.title} className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 className="display display-md">{s.title}</h2>
            {s.body.map((p) => <p key={p.slice(0, 30)} style={{ margin: 0 }}>{p}</p>)}
          </section>
        ))}
      </div>
      <p className="muted small" style={{ margin: 0 }}>
        Questions? <Link to="/contact">Contact us</Link> or email <a href={`mailto:${site.contactEmail}`}>{site.contactEmail}</a>. Last updated November {YEAR}.
      </p>
    </div>
  );
}
