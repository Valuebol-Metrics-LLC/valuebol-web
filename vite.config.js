import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// PAGES=1 builds the GitHub Pages copy: relative paths and #hash links,
// because GitHub Pages can't send every path to index.html the way Vercel does.
const pages = process.env.PAGES === '1';

export default defineConfig({
  plugins: [react()],
  base: pages ? './' : '/',
  define: { __HASH_ROUTER__: JSON.stringify(pages) },
});
