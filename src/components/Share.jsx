import { useState } from 'react';
import { hrefFor } from '../lib/router.jsx';
import { ShareIcon } from './Icons.jsx';

/** Share a page: the phone's share sheet where there is one, otherwise copy the link. */
export default function ShareButton({ to, title, text, label = 'Share' }) {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    const url = new URL(hrefFor(to), window.location.href).href;
    if (navigator.share) {
      try { await navigator.share({ title, text, url }); return; } catch { /* closed or not allowed */ }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { window.prompt('Copy this link', url); }
  };
  return (
    <button type="button" className="btn btn-sm" onClick={onClick}>
      <ShareIcon width={16} height={16} /> {copied ? 'Link copied' : label}
    </button>
  );
}
