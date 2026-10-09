// Scoreboard configuration.
//
// Live sync options (first one filled in wins):
//   1. appsScriptUrl: paste your Google Apps Script web app URL (ends in /exec). See README.
//   2. firebase:      a Firebase Realtime Database web config.
//   3. Neither:       uses server.py if the page is served by it, otherwise
//                     syncs only between windows of the same browser.
window.SB_CONFIG = {
  gameId: "fulton",   // change per game, or add ?game=xyz to both URLs
  appsScriptUrl: "https://script.google.com/macros/s/AKfycbxa0MS3w5602ahmVEMBmjAL3I0OwjTEk_qMH-cFCe9nsHQLqLmUja41q-eGbZdvTMVY/exec",
  pollMs: 1000,
  firebase: null
};
