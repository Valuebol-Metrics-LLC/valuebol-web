import { RouterProvider, useRouter, Link } from './lib/router.jsx';
import { Header, Footer, TabBar, SearchProvider } from './components/Layout.jsx';
import Club from './pages/Club.jsx';
import Match from './pages/Match.jsx';
import Home from './pages/Home.jsx';
import Rankings from './pages/Rankings.jsx';
import WhoWins from './pages/WhoWins.jsx';
import Methodology from './pages/Methodology.jsx';
import Matches from './pages/Matches.jsx';
import TitleRace from './pages/TitleRace.jsx';
import About from './pages/About.jsx';
import Contact from './pages/Contact.jsx';
import Legal from './pages/Legal.jsx';
import Videos from './pages/Videos.jsx';

const ROUTES = {
  '/': Home,
  '/rankings': Rankings,
  '/who-wins': WhoWins,
  '/methodology': Methodology,
  '/matches': Matches,
  '/title-race': TitleRace,
  '/about': About,
  '/contact': Contact,
  '/legal': Legal,
  '/videos': Videos,
};

function NotFound() {
  return (
    <div className="container page">
      <h1 className="display display-xl">Page not found</h1>
      <p><Link to="/">Back to the homepage</Link></p>
    </div>
  );
}

function Routes() {
  const { path } = useRouter();
  const clean = path.replace(/\/+$/, '') || '/';
  if (clean.startsWith('/club-')) return <Club slug={clean.slice(6)} />;
  if (clean.startsWith('/match-')) return <Match slug={clean.slice(7)} />;
  const Page = ROUTES[clean] ?? NotFound;
  return <Page />;
}

export default function App({ initialPath }) {
  return (
    <RouterProvider initialPath={initialPath}>
      <SearchProvider>
        <Header />
        <main>
          <Routes />
        </main>
        <Footer />
        <TabBar />
      </SearchProvider>
    </RouterProvider>
  );
}
