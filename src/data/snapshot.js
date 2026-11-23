// Snapshot of live Valuebol figures (valuebol-metrics.com, as of Nov 21, 2026).
// Used until src/lib/data.js is pointed at the real pipeline / Supabase tables.
// Shape mirrors what the live site shows, so swapping the source changes no page code.

export const asOf = '2026-11-21';

export const coverage = { teams: '900+', conferences: '80+', matches: '17K+', since: 2017, activeClubs: 442 };

// rank, name, conference, asi, matches, record (W-D-L, current season), last5 (net ASI over last 5), move (rank change)
export const rankings = [
  [1, 'NY Renegades FC', 'American North', 1957, 118, '9-0-1', 28.7, 0],
  [2, 'Tennessee Tempo FC', 'KY - TN', 1878, 139, '7-1-1', 17.2, 0],
  [3, 'Deportivo Rose City', 'Oregon', 1874, 119, '7-0-0', 17.3, 0],
  [4, 'SCU Heat', 'Mid-Atlantic South', 1864, 158, '7-3-0', -7.6, 0],
  [5, 'Miami United FC', 'Florida South - South', 1855, 95, '6-3-0', 0.3, 0],
  [6, 'Lakeland United', 'Florida West', 1804, 132, '11-1-0', 38.7, 0],
  [7, 'Soda City FC', 'Mid-Atlantic South', 1802, 170, '6-4-1', -28.1, 0],
  [8, 'Kalonji Pro-Profile', 'Georgia East', 1794, 152, '5-0-5', -75.5, 0],
  [9, 'Valley 559 FC', 'NorCal', 1788, 113, '6-0-3', -25.2, 1],
  [10, 'Lynchburg FC', 'Virginia South', 1783, 87, '8-2-0', 18.6, -1],
  [11, 'Chicago Nation FC', 'Midwest Central', 1780, 143, '7-2-0', 19.7, 0],
  [12, 'PCU Pelicans SC', 'Florida West', 1777, 27, '9-0-1', 16, 0],
  [13, 'Virginia Dream FC', 'DMV North', 1768, 85, '6-3-1', 3, 0],
  [14, 'BFC Lightning', 'Oregon', 1763, 60, '6-2-2', -17.5, 0],
  [15, 'Arlington SA', 'DMV North', 1759, 145, '6-1-3', -36.9, 0],
  [16, 'Next Level Soccer Premier', 'Arizona', 1753, 67, '8-0-2', 3.2, 0],
  [17, 'Los Toros', 'DMV North', 1742, 48, '6-3-1', 6.2, 0],
  [18, 'FC Folsom', 'NorCal North', 1742, 90, '8-2-0', -20.5, 0],
  [19, 'Provo Utah FC', 'Mountain West', 1739, 98, '7-2-0', -3, 6],
  [20, 'Fut Ohio SC', 'Ohio/Indy', 1735, 100, '4-5-1', -35.9, -1],
  [21, 'Red Hook Football Club', 'American North', 1733, 46, '7-1-2', -15.9, -1],
  [22, 'Olympians FC', 'Arizona', 1732, 104, '6-4-0', 1.9, -1],
  [23, 'Atlanta United Academy', 'Georgia West', 1730, 95, '7-2-1', 58.8, -1],
  [24, 'Brockton FC United', 'New England', 1726, 122, '7-2-1', -42.4, -1],
  [25, 'Lions Football Club', 'Ohio/Indy', 1726, 58, '6-0-4', 10.4, 0],
  [26, 'Georgia Revolution FC', 'Georgia West', 1725, 76, '8-0-2', -11, 0],
  [27, 'West Texas Rush', 'West Texas - New Mexico', 1723, 85, '6-2-0', 40.2, 0],
  [28, 'LA Sol Athletics', 'SoCal North', 1718, 17, '13-0-0', 28.6, 0],
  [29, 'DC Hyper', 'DMV North', 1718, 40, '4-2-4', 49.5, 0],
  [30, 'Bridge Sports Club', 'DMV North', 1707, 125, '4-2-4', 0.9, 0],
].map(([rank, name, conference, asi, matches, record, last5, move]) => ({ rank, name, conference, asi, matches, record, last5, move }));

export const ratingRange = { lowest: 1167, highest: 1957 };

export const movers = {
  climber: { name: 'BE PRO FC', rank: 213, conference: 'Las Vegas', move: 137 },
  hottest: { name: 'Manu Ledesma Academy', rank: 56, conference: 'Ohio/Indy', last5: 70.3 },
  drop: { name: 'Las Vegas Football Institute', rank: 334, conference: 'Las Vegas', move: -101 },
};

// Featured upcoming matches with Valuebol's home / draw / away probabilities (null = not enough history).
export const featuredMatches = [
  { date: '2026-11-27', time: '8:00 PM', competition: 'UPSL Florida West', home: 'PCU Pelicans SC', homeRank: 12, away: 'West Florida Flames', awayRank: 81, probs: [72, 16, 12] },
  { date: '2026-11-28', time: '4:00 PM', competition: 'UPSL National Round of 16', home: 'DC Hyper', homeRank: 29, away: 'Cosmos B', awayRank: 72, probs: [65, 23, 12] },
  { date: '2026-11-29', time: '4:00 PM', competition: 'UPSL National Round of 16', home: 'NY Renegades FC', homeRank: 1, away: 'Boston Emeralds FC', awayRank: 41, probs: null },
  { date: '2026-11-29', time: '7:00 PM', competition: 'UPSL Florida West', home: 'PCU Pelicans SC', homeRank: 12, away: 'Inter City FC', awayRank: 33, probs: [46, 21, 32] },
];

// Model validation (held-out Spring 2026 league matches).
export const modelValidation = {
  matchesTested: 1675,
  accuracy: 56.5,
  baseline: 45.7,
  models: [
    { name: 'Joint + shrinkage + time weighting', logLoss: 0.942, brier: 0.557, correct: 56.5, chosen: true },
    { name: 'Joint + shrinkage', logLoss: 0.945, brier: 0.559, correct: 56.0 },
    { name: 'Ratio + shrinkage + time weighting', logLoss: 0.95, brier: 0.564, correct: 55.3 },
    { name: 'Ratio + shrinkage', logLoss: 0.956, brier: 0.568, correct: 54.7 },
    { name: 'Joint', logLoss: 0.956, brier: 0.56, correct: 57.0 },
    { name: 'Ratio + time weighting', logLoss: 1.041, brier: 0.572, correct: 56.4 },
    { name: 'Ratio', logLoss: 1.044, brier: 0.578, correct: 55.6 },
    { name: 'League-average baseline', logLoss: 1.01, brier: 0.614, correct: 45.7 },
  ],
};

export const topScorers = [
  { name: 'Junior Rosero', club: 'NY Renegades FC', goals: 12 },
  { name: 'Sebastian Ruiz Restrepo', club: 'NY Renegades FC', goals: 8 },
  { name: 'Mauricio J Puerto', club: 'NY Renegades FC', goals: 7 },
];

// Florida West, Fall 2026: projected table from 10,000 simulated seasons.
// pts/gp = official table now; projGp = games after the remaining fixtures; finish = % of runs in each place (1st..13th), -1 = under 1%.
export const conferenceRace = {
  conference: 'Florida West',
  season: 'Fall 2026',
  runs: 10000,
  clubs: [
    { name: 'Lakeland United', pos: 1, pts: 34, gp: 12, projGp: 12, projPts: 34.0, finish: [100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
    { name: 'PCU Pelicans SC', pos: 2, pts: 27, gp: 10, projGp: 12, projPts: 30.9, finish: [0, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
    { name: 'Inter City FC', pos: 3, pts: 19, gp: 9, projGp: 11, projPts: 22.7, finish: [0, 0, 96, 4, -1, 0, 0, 0, 0, 0, 0, 0, 0] },
    { name: 'Sarasota Paradise', pos: 5, pts: 16, gp: 10, projGp: 12, projPts: 19.2, finish: [0, 0, 4, 65, 18, 4, 6, 4, 0, 0, 0, 0, 0] },
    { name: 'West Florida Flames', pos: 4, pts: 17, gp: 11, projGp: 12, projPts: 17.5, finish: [0, 0, -1, 10, 36, 51, 2, 0, 0, 0, 0, 0, 0] },
    { name: 'Shock City FC', pos: 6, pts: 16, gp: 11, projGp: 12, projPts: 17.3, finish: [0, 0, 0, 12, 37, 11, 15, 25, 0, 0, 0, 0, 0] },
    { name: 'Benfica Residential Academy', pos: 7, pts: 16, gp: 12, projGp: 12, projPts: 16.0, finish: [0, 0, 0, 0, 1, 30, 65, 4, 0, 0, 0, 0, 0] },
    { name: 'FC Tampa Rangers', pos: 8, pts: 15, gp: 12, projGp: 12, projPts: 15.0, finish: [0, 0, 0, 0, 0, 0, 0, 56, 44, -1, 0, 0, 0] },
    { name: 'Florida Premier FC', pos: 9, pts: 10, gp: 9, projGp: 12, projPts: 14.4, finish: [0, 0, 0, 9, 8, 4, 12, 12, 45, 11, 1, 0, 0] },
    { name: 'Clearwater Chargers SC', pos: 10, pts: 9, gp: 10, projGp: 12, projPts: 11.2, finish: [0, 0, 0, 0, 0, 0, 0, -1, 10, 64, 18, 8, -1] },
    { name: 'Cape Coral City FC', pos: 11, pts: 7, gp: 11, projGp: 12, projPts: 8.5, finish: [0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 44, 35, 12] },
    { name: 'Florida Celtic SC', pos: 12, pts: 4, gp: 9, projGp: 12, projPts: 7.3, finish: [0, 0, 0, 0, 0, 0, 0, 0, 1, 10, 18, 24, 48] },
    { name: 'SWFL SC', pos: 13, pts: 3, gp: 8, projGp: 11, projPts: 6.9, finish: [0, 0, 0, 0, 0, 0, 0, 0, 1, 6, 19, 33, 40] },
  ],
};
