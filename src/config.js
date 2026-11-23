// Site-wide settings. Fill in the real handle and email before launch.
export const site = {
  name: 'Valuebol LLC',
  tagline: 'Bridging the gap between amateur and professional football.',
  // TODO: confirm the real Instagram handle (no @).
  instagramHandle: 'valuebol.llc',
  // The contact form opens the visitor's email app addressed here.
  contactEmail: 'egudinodegrote@valuebol-metrics.com',
};

export const instagramUrl = `https://www.instagram.com/${site.instagramHandle}/`;

// Homepage background video. Uses a muted, looping YouTube embed until Valuebol has its own clip;
// drop an .mp4 into public/ and set `mp4: 'hero.mp4'` to use that instead (loads faster, no YouTube UI).
export const heroVideo = {
  youtubeId: 'jkA4f8Gpgv0', // 2026 UPSL National Final highlights
  start: 20,
  mp4: null,
};
