import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { loadLiveData } from './lib/data.js';
import './styles.css';

// Load the latest numbers first (a ~40 KB file), so every page renders with them.
// If it's slow or missing, the site renders with the built-in snapshot instead.
loadLiveData().finally(() => {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
