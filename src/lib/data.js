// Data access for every page. Pages only call these functions, so moving from the
// snapshot to live data (Supabase tables fed by the Python pipeline, like the
// amateur-football-dashboard project) means changing this file only.
import * as snap from '../data/snapshot.js';
import { clubProfiles } from '../data/clubs.js';
// Written by scraper/upsl_scraper.py (logos, links, city for every UPSL club). Empty until the scraper runs.
import upslTeams from '../data/upsl/teams.json';

export const getAsOf = () => snap.asOf;
export const getCoverage = () => snap.coverage;
export const getRankings = () => snap.rankings;
export const getRatingRange = () => snap.ratingRange;
export const getMovers = () => snap.movers;
export const getFeaturedMatches = () => snap.featuredMatches;
export const getModelValidation = () => snap.modelValidation;
export const getTopScorers = () => snap.topScorers;
export const getConferenceRace = () => snap.conferenceRace;
export const getVideos = () => snap.videos;

export const youtubeThumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
export const youtubeUrl = (id) => `https://www.youtube.com/watch?v=${id}`;

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

// ---- Clubs & matches -------------------------------------------------------

export const slugify = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
export const clubPath = (name) => `/club-${slugify(name)}`;

const upslBySlug = new Map(upslTeams.map((t) => [t.slug, t]));
const LINK_FIELDS = ['city', 'website', 'instagram', 'facebook', 'twitter', 'youtube', 'upsl', 'logo'];

/** Scraped UPSL info for a club, with hand-checked entries in clubs.js taking priority. */
export function profileFor(name) {
  const manual = clubProfiles[name] ?? {};
  const scraped = upslBySlug.get(slugify(manual.upslName ?? name)) ?? {};
  const merged = {};
  LINK_FIELDS.forEach((k) => { if (scraped[k]) merged[k] = scraped[k]; });
  return { ...merged, ...manual };
}

export const logoFor = (name) => profileFor(name).logo ?? null;

/** Every club the site knows about (ranked, in a fixture, in the title race or in a video). */
export function getAllClubs() {
  const names = new Map();
  const add = (name, extra = {}) => { if (!names.has(name)) names.set(name, { name, ...extra }); };
  snap.rankings.forEach((r) => add(r.name, { rank: r.rank, conference: r.conference }));
  snap.featuredMatches.forEach((m) => { add(m.home, { rank: m.homeRank }); add(m.away, { rank: m.awayRank }); });
  snap.conferenceRace.clubs.forEach((c) => add(c.name, { conference: snap.conferenceRace.conference }));
  snap.videos.forEach((v) => v.clubs.forEach((c) => add(c)));
  upslTeams.forEach((t) => add(t.name, { conference: t.conference }));
  return [...names.values()].sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999) || a.name.localeCompare(b.name));
}

export const matchPath = (m) => `/match-${slugify(`${m.home} vs ${m.away} ${m.date}`)}`;

export function getMatchBySlug(slug) {
  return snap.featuredMatches.find((m) => matchPath(m) === `/match-${slug}`) ?? null;
}

/** Everything the club page needs, or null if the slug matches no club. */
export function getClub(slug) {
  const base = getAllClubs().find((c) => slugify(c.name) === slug);
  if (!base) return null;
  const { name } = base;
  const ranked = snap.rankings.find((r) => r.name === name) ?? null;
  const race = snap.conferenceRace.clubs.find((c) => c.name === name) ?? null;
  return {
    ...base,
    ...profileFor(name),
    ranked,
    race: race && { ...race, conference: snap.conferenceRace.conference, runs: snap.conferenceRace.runs },
    matches: snap.featuredMatches.filter((m) => m.home === name || m.away === name),
    videos: snap.videos.filter((v) => v.clubs.includes(name)),
    scorers: snap.topScorers.filter((p) => p.club === name),
  };
}

export const instagramFor = (handle) => `https://www.instagram.com/${handle}/`;
