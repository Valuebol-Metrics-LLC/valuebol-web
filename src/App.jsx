import { RouterProvider, useRouter, Link } from './lib/router.jsx';
import { Header, Footer } from './components/Layout.jsx';
import Home from './pages/Home.jsx';
import Rankings from './pages/Rankings.jsx';
import WhoWins from './pages/WhoWins.jsx';
import Methodology from './pages/Methodology.jsx';

const ROUTES = {
  '/': Home,
  '/rankings': Rankings,
  '/who-wins': WhoWins,
  '/methodology': Methodology,
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
  const Page = ROUTES[path.replace(/\/+$/, '') || '/'] ?? NotFound;
  return <Page />;
}

export default function App({ initialPath }) {
  return (
    <RouterProvider initialPath={initialPath}>
      <Header />
      <main>
        <Routes />
      </main>
      <Footer />
    </RouterProvider>
  );
}
