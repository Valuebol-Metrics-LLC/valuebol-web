// Tiny client-side router (no dependency). vercel.json rewrites every path to index.html.
import { createContext, useContext, useEffect, useState } from 'react';

const RouterContext = createContext({ path: '/', navigate: () => {} });

export function RouterProvider({ children, initialPath }) {
  const [path, setPath] = useState(
    initialPath ?? (typeof window !== 'undefined' ? window.location.pathname : '/'),
  );

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = (to) => {
    if (to === path) return;
    window.history.pushState({}, '', to);
    setPath(to);
    window.scrollTo(0, 0);
  };

  return <RouterContext.Provider value={{ path, navigate }}>{children}</RouterContext.Provider>;
}

export function useRouter() {
  return useContext(RouterContext);
}

/** Internal link: plain <a> for accessibility, intercepted for client-side navigation. */
export function Link({ to, children, ...rest }) {
  const { path, navigate } = useRouter();
  const onClick = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(to);
  };
  return (
    <a href={to} onClick={onClick} aria-current={path === to ? 'page' : undefined} {...rest}>
      {children}
    </a>
  );
}
