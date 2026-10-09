// Shared scoreboard state. Uses Firebase Realtime Database when configured,
// otherwise BroadcastChannel + localStorage (same browser only).
(function () {
  const CFG = window.SB_CONFIG || {};
  const params = new URLSearchParams(location.search);
  const GAME = (params.get("game") || CFG.gameId || "fulton").replace(/[^a-zA-Z0-9_-]/g, "") || "fulton";
  const ROOT = new URL("../", (document.currentScript && document.currentScript.src) || location.href);

  const QLEN = 12 * 60 * 1000; // high school quarters: 12 minutes

  const DEFAULT = {
    title: "FULTON HIGH SCHOOL FOOTBALL",
    away: {
      name: "Morrison", mascot: "Mustangs", abbr: "MOR", record: "0-0",
      primary: "#1C46A6", secondary: "#D7141E", logo: "assets/morrison.png",
      score: 0, timeouts: 3
    },
    home: {
      name: "Fulton", mascot: "Steamers", abbr: "FUL", record: "0-0",
      primary: "#C8102E", secondary: "#111111", logo: "assets/steamers.png",
      score: 0, timeouts: 3
    },
    quarter: "1",
    clock: { running: false, remaining: QLEN, startedAt: 0, length: QLEN },
    play: { running: false, remaining: 40000, startedAt: 0, show: false },
    down: 1, distance: "10",
    ballOn: { side: "home", yard: "" },
    possession: "home",
    showDown: true,
    flag: false,
    banner: { text: "", team: "", ts: 0 },
    info: { text: "", show: false }
  };

  const clone = (o) => JSON.parse(JSON.stringify(o));
  function merge(base, over) {
    if (!over || typeof over !== "object") return base;
    for (const k of Object.keys(over)) {
      const v = over[k];
      if (v && typeof v === "object" && base[k] && typeof base[k] === "object") merge(base[k], v);
      else base[k] = v;
    }
    return base;
  }
  function applyPatch(obj, patch) {
    for (const [path, val] of Object.entries(patch)) {
      const keys = path.split("/");
      let o = obj;
      for (let i = 0; i < keys.length - 1; i++) {
        if (typeof o[keys[i]] !== "object" || o[keys[i]] === null) o[keys[i]] = {};
        o = o[keys[i]];
      }
      o[keys[keys.length - 1]] = val;
    }
  }

  let state = clone(DEFAULT);
  let offset = 0;
  let status = "connecting";
  const listeners = [];
  const statusListeners = [];
  const notify = () => listeners.forEach((f) => { try { f(state); } catch (e) { console.error(e); } });
  const setStatus = (s) => { status = s; statusListeners.forEach((f) => f(s)); };

  function localBackend() {
    const KEY = "sb:" + GAME;
    let bc = null;
    try { bc = new BroadcastChannel(KEY); } catch (e) {}
    const load = (raw) => { state = merge(clone(DEFAULT), JSON.parse(raw)); notify(); };
    try { const s = localStorage.getItem(KEY); if (s) state = merge(clone(DEFAULT), JSON.parse(s)); } catch (e) {}
    if (bc) bc.onmessage = (e) => load(e.data);
    window.addEventListener("storage", (e) => { if (e.key === KEY && e.newValue) load(e.newValue); });
    const persist = () => {
      const raw = JSON.stringify(state);
      try { localStorage.setItem(KEY, raw); } catch (e) {}
      if (bc) bc.postMessage(raw);
    };
    setTimeout(() => { setStatus("local"); window.SB.loaded = true; notify(); });
    return {
      update(p) { applyPatch(state, p); persist(); notify(); },
      set(s) { state = merge(clone(DEFAULT), s); persist(); notify(); }
    };
  }

  function firebaseBackend() {
    const V = "10.12.2";
    const load = (src) => new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = src; s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
    let ref = null;
    const pending = [];
    load(`https://www.gstatic.com/firebasejs/${V}/firebase-app-compat.js`)
      .then(() => load(`https://www.gstatic.com/firebasejs/${V}/firebase-database-compat.js`))
      .then(() => {
        if (!firebase.apps.length) firebase.initializeApp(CFG.firebase);
        const db = firebase.database();
        db.ref(".info/serverTimeOffset").on("value", (s) => { offset = s.val() || 0; });
        db.ref(".info/connected").on("value", (s) => setStatus(s.val() ? "live" : "offline"));
        ref = db.ref("scoreboards/" + GAME);
        ref.on("value", (snap) => { state = merge(clone(DEFAULT), snap.val() || {}); window.SB.loaded = true; notify(); },
          () => setStatus("error"));
        pending.splice(0).forEach((f) => f());
      })
      .catch(() => setStatus("error"));
    const run = (f) => (ref ? f() : pending.push(f));
    return {
      update(p) { applyPatch(state, p); notify(); run(() => ref.update(p)); },
      set(s) { state = merge(clone(DEFAULT), s); notify(); run(() => ref.set(state)); }
    };
  }

  // Local server (server.py on the Mac running OBS): live sync via Server-Sent Events
  function serverBackend() {
    const api = (p) => new URL(`api/${p}?game=${encodeURIComponent(GAME)}`, ROOT).href;
    let pending = 0, latest = null;
    let chain = Promise.resolve();
    const receive = (msg) => {
      offset = msg.now - Date.now();
      latest = msg.state;
      if (pending === 0) { state = merge(clone(DEFAULT), latest); notify(); }
    };
    const post = (path, body) => {
      pending++;
      chain = chain
        .then(() => fetch(api(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }))
        .catch(() => setStatus("offline"))
        .then(() => {
          if (--pending === 0 && latest) { state = merge(clone(DEFAULT), latest); notify(); }
        });
    };
    const es = new EventSource(api("events"));
    es.onopen = () => setStatus("live");
    es.onmessage = (e) => { setStatus("live"); receive(JSON.parse(e.data)); };
    es.onerror = () => setStatus("offline");
    return {
      update(p) { applyPatch(state, p); notify(); post("update", p); },
      set(s) { state = merge(clone(DEFAULT), s); notify(); post("set", state); }
    };
  }

  // Google Apps Script web app: controller POSTs patches, displays poll for state
  function appsScriptBackend() {
    const base = CFG.appsScriptUrl + (CFG.appsScriptUrl.includes("?") ? "&" : "?") + "game=" + encodeURIComponent(GAME);
    let pending = 0, lastWrite = 0, bestRtt = Infinity, lastJson = "";
    let chain = Promise.resolve();
    const take = (msg, t0) => {
      const t1 = Date.now(), rtt = t1 - t0;
      if (rtt <= bestRtt * 1.25) { bestRtt = Math.min(bestRtt, rtt); offset = msg.now - (t0 + t1) / 2; }
      setStatus("live");
      if (pending || t0 < lastWrite) return; // stale: a write happened after this read began
      const j = JSON.stringify(msg.state || {});
      if (j === lastJson && window.SB.loaded) return;
      lastJson = j;
      state = merge(clone(DEFAULT), msg.state || {});
      window.SB.loaded = true;
      notify();
    };
    const poll = () => {
      const t0 = Date.now();
      fetch(base + "&t=" + t0, { cache: "no-store" })
        .then((r) => r.json())
        .then((m) => take(m, t0))
        .catch(() => setStatus("offline"))
        .finally(() => setTimeout(poll, CFG.pollMs || 1000));
    };
    const post = (body) => {
      pending++;
      chain = chain
        .then(() => {
          const t0 = Date.now();
          return fetch(base, { method: "POST", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify(body) })
            .then((r) => r.json())
            .then((m) => { pending--; lastWrite = Date.now(); take(m, t0); });
        })
        .catch(() => { pending--; lastWrite = Date.now(); setStatus("offline"); });
    };
    poll();
    return {
      update(p) { applyPatch(state, p); notify(); post({ patch: p }); },
      set(s) { state = merge(clone(DEFAULT), s); notify(); post({ set: state }); }
    };
  }

  let mode = "local";
  let backend = null;
  const queued = [];
  const use = (m, b) => { mode = m; backend = b; window.SB.mode = m; queued.splice(0).forEach(([k, v]) => backend[k](v)); };

  const now = () => Date.now() + offset;
  const timerMs = (t) => (t.running ? Math.max(0, t.remaining - (now() - t.startedAt)) : t.remaining);
  const call = (k, v) => (backend ? backend[k](v) : queued.push([k, v]));

  window.SB = {
    game: GAME,
    mode,
    loaded: false,
    DEFAULT: clone(DEFAULT),
    get: () => state,
    update: (p) => call("update", p),
    set: (s) => call("set", s),
    onChange: (f) => { listeners.push(f); f(state); },
    onStatus: (f) => { statusListeners.push(f); f(status); },
    now,
    fullName: (t) => (String(t.name).toLowerCase() === String(t.mascot).toLowerCase() ? t.name : `${t.name} ${t.mascot}`).toUpperCase(),
    timerMs,
    asset: (p) => (!p ? "" : /^(https?:|data:|blob:)/.test(p) ? p : new URL(p, ROOT).href)
  };

  if (CFG.appsScriptUrl) use("google", appsScriptBackend());
  else if (CFG.firebase && CFG.firebase.databaseURL) use("firebase", firebaseBackend());
  else if (!/^https?:$/.test(location.protocol)) use("local", localBackend());
  else {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 2000);
    fetch(new URL(`api/state?game=${GAME}`, ROOT).href, { signal: ctl.signal, cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((msg) => {
        if (!msg || typeof msg.now !== "number") throw 0;
        offset = msg.now - Date.now();
        state = merge(clone(DEFAULT), msg.state); window.SB.loaded = true; notify();
        use("server", serverBackend());
      })
      .catch(() => use("local", localBackend()))
      .finally(() => clearTimeout(t));
  }
})();
