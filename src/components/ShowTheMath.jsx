import { useId, useState } from 'react';

/**
 * Every fan-facing answer gets one of these: the plain-English answer stays on top,
 * the real method sits one tap away for the stats crowd.
 */
export default function ShowTheMath({ children, label = 'Show the math' }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div>
      <button type="button" className="btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        {open ? 'Hide the math' : label}
      </button>
      {open && (
        <div id={id} className="math" style={{ marginTop: 16 }}>
          <p className="stat-label" style={{ margin: 0 }}>For the stats crowd</p>
          {children}
        </div>
      )}
    </div>
  );
}
