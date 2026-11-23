// Tiny client-side router (no dependency). vercel.json rewrites every path to index.html.
import { createContext, useContext, useEffect, useState } from 'react';

const RouterContext = createContext({ path: '/', navigate: () => {} });

// Hash routing (#rankings) is used only for static previews built with __HASH_ROUTER__ = true.
// The real site (Vite + Vercel) uses clean paths.
// eslint-disable-next-line no-undef
const HASH = typeof __HASH_ROUTER__ !== 'undefined' && __HASH_ROUTER__;
const readPath = () => {
  if (!HASH) return window.location.pathname;
  const h = window.location.hash.replace(/^#/, '');
  return !h || h === 'home' ? '/' : `/${h}`;
};
export const hrefFor = (to) => (HASH ? `#${to === '/' ? 'home' : to.slice(1)}` : to);

export function RouterProvider({ children, initialPath }) {
  const [path, setPath] = useState(
    initialPath ?? (typeof window !== 'undefined' ? readPath() : '/'),
  );

  useEffect(() => {
    const onPop = () => setPath(readPath());
    window.addEventListener(HASH ? 'hashchange' : 'popstate', onPop);
    return () => window.removeEventListener(HASH ? 'hashchange' : 'popstate', onPop);
  }, []);

  const navigate = (to) => {
    if (to === path) return;
    if (HASH) window.location.hash = hrefFor(to);
    else window.history.pushState({}, '', to);
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
    <a href={hrefFor(to)} onClick={onClick} aria-current={path === to ? 'page' : undefined} {...rest}>
      {children}
    </a>
  );
}
