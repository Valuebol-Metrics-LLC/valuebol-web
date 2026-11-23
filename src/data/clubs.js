// Club profiles: official links and home city. Only links that were checked against a
// source are filled in; everything else is left empty and the club page asks the club
// (or a fan) to send it. Add `logo: 'logos/<file>.png'` once Joel's logos are in public/logos/.
//
// website   - the club's own site
// instagram - handle without the @
// upsl      - the club's page on upsl.com (schedule and results)
// checked   - where the link was confirmed, so it can be re-checked later
export const clubProfiles = {
  'Tennessee Tempo FC': {
    city: 'Murfreesboro, TN',
    website: 'https://www.tennesseetempofc.com',
    checked: 'Wikipedia infobox, Nov 2026',
  },
  'Deportivo Rose City': {
    city: 'Portland, OR',
    upsl: 'https://premier.upsl.com/teams/deportivo-rose-city',
    checked: 'upsl.com team page, Nov 2026',
  },
  'SCU Heat': {
    city: 'Columbia, SC',
    website: 'https://www.southcarolinaunitedfc.com',
    checked: 'South Carolina United FC (parent club) site, Nov 2026',
  },
  'Miami United FC': {
    city: 'Miami, FL',
    website: 'https://www.miamiunitedsoccer.com',
    checked: 'Club site, Nov 2026',
  },
  'Miami FC U20': {
    city: 'Miami, FL',
    instagram: 'miamifcusla',
    checked: 'miamifc.com news post, Nov 2026',
  },
  'Lakeland United': { city: 'Lakeland, FL' },
  'Soda City FC': {
    city: 'Columbia, SC',
    website: 'https://sodacitysoccer.com',
    checked: 'Sponsor announcement linking the official site, Nov 2026',
  },
  'Lynchburg FC': {
    city: 'Lynchburg, VA',
    website: 'https://lynchburgfc.sportzstudio.com',
    upsl: 'https://premier.upsl.com/teams/lynchburg-fc-33621/',
    checked: 'Club site and upsl.com team page, Nov 2026',
  },
  'Chicago Nation FC': {
    city: 'Chicago, IL',
    website: 'https://chicagonationfc.com',
    instagram: 'chicagonationfc',
    upsl: 'https://premier.upsl.com/teams/chicago-nation-fc-430068',
    checked: 'Club Instagram posts linking chicagonationfc.com, upsl.com, Nov 2026',
  },
};
