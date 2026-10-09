// Fulton Scoreboard sync API (Google Apps Script)
// Deploy: Deploy > New deployment > Web app > Execute as: Me, Who has access: Anyone
const KEY = "state_";

function game_(e) {
  return String((e && e.parameter && e.parameter.game) || "fulton").replace(/[^A-Za-z0-9_-]/g, "") || "fulton";
}

function read_(g) {
  const cache = CacheService.getScriptCache();
  let s = cache.get(KEY + g);
  if (s === null) {
    s = PropertiesService.getScriptProperties().getProperty(KEY + g) || "{}";
    cache.put(KEY + g, s, 21600);
  }
  return s;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function applyPatch_(obj, patch) {
  Object.keys(patch || {}).forEach(function (path) {
    const keys = path.split("/");
    let o = obj;
    for (let i = 0; i < keys.length - 1; i++) {
      if (typeof o[keys[i]] !== "object" || o[keys[i]] === null) o[keys[i]] = {};
      o = o[keys[i]];
    }
    o[keys[keys.length - 1]] = patch[path];
  });
}

function doGet(e) {
  return out_({ state: JSON.parse(read_(game_(e))), now: Date.now() });
}

function doPost(e) {
  const g = game_(e);
  const body = JSON.parse(e.postData.contents);
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  let s;
  try {
    let st = JSON.parse(read_(g));
    if (body.set) st = body.set;
    else applyPatch_(st, body.patch);
    s = JSON.stringify(st);
    CacheService.getScriptCache().put(KEY + g, s, 21600);
    try { PropertiesService.getScriptProperties().setProperty(KEY + g, s); } catch (err) {} // >9KB (uploaded logo) stays cache-only
  } finally {
    lock.releaseLock();
  }
  return out_({ ok: true, state: JSON.parse(s), now: Date.now() });
}
