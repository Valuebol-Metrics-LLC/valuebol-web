import { useId, useState } from 'react';

/**
 * Collapsible box with the method behind a number. The simple answer stays on top.
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
          <p className="stat-label" style={{ margin: 0 }}>The details</p>
          {children}
        </div>
      )}
    </div>
  );
}
