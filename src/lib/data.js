// Data access for every page. Pages only call these functions, so moving from the
// snapshot to live data (Supabase tables fed by the Python pipeline, like the
// amateur-football-dashboard project) means changing this file only.
import * as snap from '../data/snapshot.js';

export const getAsOf = () => snap.asOf;
export const getCoverage = () => snap.coverage;
export const getRankings = () => snap.rankings;
export const getRatingRange = () => snap.ratingRange;
export const getMovers = () => snap.movers;
export const getFeaturedMatches = () => snap.featuredMatches;
export const getModelValidation = () => snap.modelValidation;
export const getTopScorers = () => snap.topScorers;

/** ASI is Elo-based: expected score of A against B (a draw counts as half a win). */
export function eloExpected(ratingA, ratingB) {
  return 1 / (1 + Math.pow(10, (ratingB - ratingA) / 400));
}

/** ASI points a club gains for a win (or loses for a defeat), with K = 25 for league matches. */
export function eloStake(expected, k = 25) {
  return Math.round(k * (1 - expected));
}

/** Plain-English label for a home / draw / away split. */
export function describeOdds([h, , a]) {
  const fav = Math.max(h, a);
  const side = h >= a ? 'home' : 'away';
  if (fav >= 65) return `Big ${side} favourites`;
  if (fav >= 50) return `${side === 'home' ? 'Home' : 'Away'} side favoured`;
  if (Math.abs(h - a) <= 15) return `Coin flip, slight ${side} edge`;
  return `${side === 'home' ? 'Home' : 'Away'} side edges it`;
}

export function formatDate(iso) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [y, m, d] = iso.split('-').map(Number);
  const day = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${day}, ${months[m - 1]} ${d}`;
}
