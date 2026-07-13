"use strict";

const $ = (s) => document.querySelector(s);
const TOP_ROW = new Set(["outerwear", "midlayer", "top", "blouse", "knit", "cardigan", "dress"]);
const PROFILES = ["joseph", "evangeline"];   // shown as a switch; each unlocks with its own PIN

const dash = {
  get tokens() { try { return JSON.parse(localStorage.getItem("dash.tokens")) || {}; } catch { return {}; } },
  set tokens(v) { localStorage.setItem("dash.tokens", JSON.stringify(v)); },
  get active() { return localStorage.getItem("dash.active") || PROFILES[0]; },
  set active(v) { localStorage.setItem("dash.active", v); },
  get units() { return localStorage.getItem("wc.units") || "C"; },   // shared with the closet
};

const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const fmtTemp = (c) => (c == null ? "" : dash.units === "F" ? `${Math.round(c * 9 / 5 + 32)}°` : `${Math.round(c)}°`);
const fmtHour = (h) => `${((h + 11) % 12) + 1}${h < 12 ? "am" : "pm"}`;

let pendingProfile = null;   // profile awaiting a PIN in the lock screen

function loading(on) { $("#d-loading").hidden = !on; }
function showLock(profile) {
  pendingProfile = profile;
  $("#d-lock-sub").textContent = `Enter ${cap(profile)}'s PIN.`;
  $("#d-lock-error").hidden = true;
  $("#d-pin").value = "";
  $("#d-lock").hidden = false; $("#d-app").hidden = true;
}
function showApp() { $("#d-lock").hidden = true; $("#d-app").hidden = false; }

async function api(path, body, token) {
  const opts = { method: body ? "POST" : "GET", headers: {} };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  if (token) opts.headers["Authorization"] = "Bearer " + token;
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(res.status === 401 ? "locked" : "request failed");
  return res.json();
}

async function unlock() {
  $("#d-lock-error").hidden = true;
  try {
    const r = await api("/api/unlock", { pin: $("#d-pin").value });
    const tokens = { ...dash.tokens, [r.profile]: r.token };
    dash.tokens = tokens; dash.active = r.profile;
    localStorage.setItem("wc.menswear." + r.profile, r.menswear ? "1" : "");
    day = freshDay(); activeOccasion = null;
    showApp(); renderProfiles(); loadOutfit(); loadBrief();
  } catch { $("#d-lock-error").hidden = false; }
}

function renderProfiles() {
  const wrap = $("#d-profiles"); wrap.innerHTML = "";
  PROFILES.forEach((p) => {
    const b = document.createElement("button");
    b.className = "d-prof" + (p === dash.active ? " on" : "");
    b.textContent = cap(p);
    b.onclick = () => switchProfile(p);
    wrap.appendChild(b);
  });
}

function switchProfile(p) {
  if (p === dash.active) return;
  if (dash.tokens[p]) { dash.active = p; day = freshDay(); activeOccasion = null; renderProfiles(); loadOutfit(); loadBrief(); }
  else { showLock(p); }
}

// ── Per-profile state (shared with the closet PWA via wc.* localStorage) ──
const REASONS = ["too warm", "too cold", "doesn't fit", "not feeling it"];
const OCCASIONS = ["Casual", "Weekend", "Work", "Dressy", "Going out", "Cozy home"];
const K = (base) => `wc.${base}.${dash.active}`;
const getJSON = (key, dflt) => { try { const v = JSON.parse(localStorage.getItem(key)); return v == null ? dflt : v; } catch { return dflt; } };
const prefs = () => getJSON(K("prefs"), {});
const recent = () => getJSON(K("recent"), []);
const setRecent = (v) => localStorage.setItem(K("recent"), JSON.stringify(v.slice(0, 25)));
const occStore = () => getJSON(K("occ"), {});
const setOcc = (o) => localStorage.setItem(K("occ"), JSON.stringify(o));

function freshDay() { return { occasion: null, temp_step: 0, dress_step: 0, anchor: null, anchors: [], wish: "", variety: false, rejections: [], date: null, location: null }; }
let day = freshDay();
let lastResult = null, currentPieces = {}, activeOccasion = null;

// Outfit cache — key by profile+date, value carries a signature of the inputs that
// affect generation. Navigating back to an already-loaded day (or waking the kiosk)
// re-renders the cached look instead of paying for another AI call. Any real change
// (occasion, warmth, wish, swap, New outfit) shifts the signature → a fresh load.
const outfitCache = {};
const outfitSig = () => JSON.stringify([day.occasion, day.temp_step, day.dress_step, day.anchors, day.rejections, day.wish]);
const outfitKey = () => `${dash.active}:${day.date || todayISO()}`;

async function loadOutfit(force) {
  const active = dash.active;
  // Only TODAY keeps a manually-chosen occasion; any other day always starts from its
  // weekday default (office days -> Work) so it can never get stuck on a stale WFH.
  const savedOcc = day.date ? null : occStore()[todayISO()];
  if (savedOcc && !day.occasion) { day.occasion = savedOcc; activeOccasion = savedOcc; }
  const key = outfitKey(), sig = outfitSig();
  if (!force && outfitCache[key] && outfitCache[key].sig === sig) { renderResult(outfitCache[key].result); return; }
  loading(true);
  try {
    day.recent = recent();
    const r = await api("/api/outfit", { prefs: prefs(), day }, dash.tokens[active]);
    const names = (r.pieces || []).map((p) => p.name).filter(Boolean);
    setRecent([...names, ...recent().filter((n) => !names.includes(n))]);
    outfitCache[key] = { sig, result: r };
    renderResult(r);
  } catch (e) {
    if (e.message === "locked") { const t = { ...dash.tokens }; delete t[active]; dash.tokens = t; showLock(active); }
    else $("#d-headline").textContent = "Couldn't load — try again.";
  } finally { loading(false); day.variety = false; }
}

function renderFocus() {
  const el = $("#d-focus"); if (el) el.value = localStorage.getItem(K("focus")) || "";
}

function renderResult(r) {
  lastResult = r;
  renderFocus();
  activeOccasion = r.occasion || activeOccasion;
  renderQuote();
  const d = r.date ? new Date(r.date + "T00:00:00") : new Date();
  $("#d-date").textContent = d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  $("#d-headline").textContent = r.headline || "";
  $("#d-place").textContent = (r.weather && r.weather.place) || "";
  renderWeather(r.weather);
  renderLook(r.pieces);
  renderOccasions();
  try { localStorage.setItem("wc.today." + dash.active, JSON.stringify({ date: r.date, result: r })); } catch (e) {}
}

let wxHours = [];
function renderWeather(w) {
  const el = $("#d-weather"), bars = $("#d-bars"), pop = $("#d-wx-pop");
  if (pop) pop.hidden = true;
  if (!w) { el.textContent = ""; bars.hidden = true; wxHours = []; return; }
  const cond = (w.summary || "").split(", ").slice(1).join(", ") || (w.condition || "").replace(/_/g, " ");
  el.textContent = `${fmtTemp(w.high)}  ${cond}${w.place ? " · " + w.place : ""}`.toUpperCase();
  const hrs = w.hourly || []; wxHours = hrs;
  if (!hrs.length) { bars.hidden = true; bars.innerHTML = ""; return; }
  const temps = hrs.map((h) => h.temp).filter((t) => t != null);
  const lo = temps.length ? Math.min(...temps) : w.low, hi = temps.length ? Math.max(...temps) : w.high;
  const peak = hrs.reduce((a, b) => (b.pop > a.pop ? b : a), hrs[0]);
  const n = hrs.length, tickAt = new Set([0, Math.round(n / 3), Math.round((2 * n) / 3), n - 1]);
  const barHtml = hrs.map((h, i) => `<span class="wbar${h.pop >= 50 ? " wet" : h.pop >= 25 ? " damp" : ""}" data-i="${i}" style="--p:${Math.max(6, h.pop)}%"></span>`).join("");
  const ticks = hrs.map((h, i) => tickAt.has(i) ? `<span class="wtick"><b>${fmtTemp(h.temp)}</b><i>${fmtHour(h.hour)}</i></span>` : `<span class="wtick"></span>`).join("");
  bars.innerHTML =
    `<div class="wbars-head"><span class="wbars-range">${lo != null && hi != null ? `${fmtTemp(lo)}–${fmtTemp(hi)}` : ""}</span>` +
    `<span class="wbars-cap">${peak.pop >= 20 ? `rain ~${peak.pop}% · ${fmtHour(peak.hour)}` : "dry through the day"}</span></div>` +
    `<div class="wbars-row">${barHtml}</div><div class="wticks">${ticks}</div>`;
  bars.hidden = false;
}

function showWxPop(i) {
  const h = wxHours[i], pop = $("#d-wx-pop"); if (!h || !pop) return;
  pop.innerHTML = `<b>${fmtHour(h.hour)}</b><span>${fmtTemp(h.temp)}</span><span>🌧 ${h.pop}%</span>` +
    (h.wind != null ? `<span>🌬 ${h.wind} km/h</span>` : "");
  pop.hidden = false;
}

function shiftDay(delta) {
  const t = todayISO();
  const base = new Date((day.date || t) + "T00:00:00"); base.setDate(base.getDate() + delta);
  const iso = `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, "0")}-${String(base.getDate()).padStart(2, "0")}`;
  const max = new Date(t + "T00:00:00"); max.setDate(max.getDate() + 6);
  if (iso < t || base > max) return;                 // weather window: today..+6
  day = freshDay(); activeOccasion = null;
  day.date = iso === t ? null : iso;
  loadOutfit();
}

function renderLook(pieces) {
  const look = $("#d-look"); look.innerHTML = ""; currentPieces = {};
  const rows = { top: document.createElement("div"), bottom: document.createElement("div") };
  rows.top.className = rows.bottom.className = "look-row";
  const anchors = new Set(day.anchors || []);
  (pieces || []).forEach((p) => {
    if (!p.url) return;
    currentPieces[p.name] = p;
    const anchored = p.id && anchors.has(p.id);
    const fig = document.createElement("figure");
    fig.className = "look-item cat-" + (p.category || "other") + (anchored ? " anchored" : "");
    fig.innerHTML = `<img src="${p.url}" alt=""><figcaption>${p.name || ""}</figcaption>` +
      (anchored ? `<button class="unanchor" data-id="${p.id}" title="Anchored — tap to release">🔒</button>` : "");
    fig.onclick = (e) => {
      if (e.target.closest(".unanchor")) { e.stopPropagation(); keepPiece(p); return; }
      openPieceMenu(p);
    };
    (TOP_ROW.has(p.category) ? rows.top : rows.bottom).appendChild(fig);
  });
  if (rows.top.children.length) look.appendChild(rows.top);
  if (rows.bottom.children.length) look.appendChild(rows.bottom);
}

// Tap a piece -> one compact popover; one more tap acts (2 clicks total).
function openPieceMenu(piece) {
  const pop = $("#d-pop");
  const anchored = piece.id && (day.anchors || []).includes(piece.id);
  pop.innerHTML =
    `<div class="d-pop-card">` +
    `<div class="d-pop-head"><img src="${piece.url}" alt=""><b>${piece.name || ""}</b>` +
    `<button class="d-pop-x" aria-label="Close">✕</button></div>` +
    `<div class="d-pop-sub">Swap it — why?</div><div class="d-pop-reasons">` +
    REASONS.map((r) => `<button class="chip" data-reason="${r}">${r}</button>`).join("") +
    `<button class="chip" data-reason="">just swap</button></div>` +
    `<div class="d-pop-actions">` +
    `<button class="chip" data-act="remove">✕ Remove</button>` +
    `<button class="chip" data-act="keep">${anchored ? "🔓 Release" : "★ Keep"}</button>` +
    (piece.id ? `<button class="chip" data-act="edit">✎ Edit details</button>` : "") +
    `<button class="chip" data-act="zoom">⤢ Zoom</button></div></div>`;
  pop.hidden = false;
  pop.querySelector(".d-pop-x").onclick = closePop;
  pop.querySelectorAll("[data-reason]").forEach((b) => b.onclick = () => swapPiece(piece.name, b.dataset.reason));
  pop.querySelector('[data-act="remove"]').onclick = () => removePiece(piece);
  pop.querySelector('[data-act="keep"]').onclick = () => keepPiece(piece);
  const editBtn = pop.querySelector('[data-act="edit"]');
  if (editBtn) editBtn.onclick = () => { closePop(); openEditor("edit=" + encodeURIComponent(piece.id), piece.name || "Edit piece"); };
  pop.querySelector('[data-act="zoom"]').onclick = () => { closePop(); $("#d-zoom-img").src = piece.url; $("#d-zoom").hidden = false; };
}
function closePop() { $("#d-pop").hidden = true; }

// Editor overlay — embed the closet (same origin) so settings + per-garment editing
// reuse the closet's own modals. Sync the closet's token to the active profile first
// so the iframe is already signed in; on close, drop today's cache so edits take hold
// on the next look (no auto-regen — keeps loads minimal).
function openEditor(query, title) {
  const tok = dash.tokens[dash.active];
  if (!tok) { showLock(dash.active); return; }
  localStorage.setItem("wc.token", tok);
  localStorage.setItem("wc.profile", dash.active);
  $("#d-edit-title").textContent = title || "Edit";
  $("#d-frame").src = "/?embed&" + query;
  $("#d-edit").hidden = false;
}
function closeEditor() {
  $("#d-edit").hidden = true; $("#d-frame").src = "about:blank";
  delete outfitCache[outfitKey()];   // reflect any warmth/preference edits next load
}

// Swap keeps every other piece pinned for one regeneration, then releases them.
function swapPiece(name, reason) {
  const userAnchors = day.anchors || [];
  const keep = Object.values(currentPieces).filter((p) => p.id && p.name !== name).map((p) => p.id);
  day.anchors = [...new Set([...userAnchors, ...keep])]; day.anchor = day.anchors[0] || null;
  day.rejections.push({ item: name, reason: reason || "show me another" });
  closePop();
  loadOutfit().then(() => { day.anchors = userAnchors; day.anchor = userAnchors[0] || null; if (lastResult) renderLook(lastResult.pieces); });
}
function removePiece(piece) {
  if (lastResult) lastResult.pieces = (lastResult.pieces || []).filter((p) => p.name !== piece.name);
  day.rejections.push({ item: piece.name, reason: "removed for today" });
  day.anchors = (day.anchors || []).filter((id) => id !== piece.id);
  closePop();
  if (lastResult) renderLook(lastResult.pieces);
}
function keepPiece(piece) {
  const set = new Set(day.anchors || []);
  if (piece.id) { set.has(piece.id) ? set.delete(piece.id) : set.add(piece.id); }
  day.anchors = [...set]; day.anchor = day.anchors[0] || null;
  closePop();
  if (lastResult) renderLook(lastResult.pieces);
}

// ── Journal prompt — morning intention / evening reflection ──
// Drawn from well-known routines: Ivy Lee / The ONE Thing, the Five Minute Journal,
// Stoic morning & evening reviews (Marcus Aurelius, Seneca), Franklin's daily
// questions, Three Good Things (positive psychology), Eat That Frog.
const PROMPTS = {
  morning: [
    "What's the ONE thing today that makes everything else easier or unnecessary?",
    "What would make today great?",
    "What's within your control today — and what isn't?",
    "What good shall you do this day?",
    "Who do you want to be today, and what would that person do first?",
    "What's the hard thing you're avoiding? Can it go first?",
    "Name one thing you're genuinely looking forward to today.",
    "If today repeated 100 times, would it build the life you want? Adjust one thing.",
  ],
  evening: [
    "What went well today — and why?",
    "What did you do well? What could you improve? What did you learn?",
    "What good have you done today?",
    "What drained you, and what energized you?",
    "What's one thing you'd do differently tomorrow?",
    "Three things you're grateful for right now?",
    "Did today move you closer to what matters? How?",
    "What can you set down before sleep?",
  ],
};
// The "day" rolls over at 2am, not midnight — 12–2am is still the night before.
function logicalDoy() {
  const n = new Date(); n.setHours(n.getHours() - 2);
  const start = new Date(n.getFullYear(), 0, 0);
  return Math.floor((n - start) / 86400000);
}
function isEveningNow() { const h = new Date().getHours(); return h >= 17 || h < 2; }

let journalStep = 0;
function renderJournal() {
  const evening = isEveningNow();
  const set = evening ? PROMPTS.evening : PROMPTS.morning;
  $("#d-journal-title").textContent = evening ? "Evening reflection" : "Morning intention";
  $("#d-journal-prompt").textContent = set[(logicalDoy() + journalStep) % set.length];
}

// Daily quote, themed to the day: focus for work days, calm for weekend/home, else general.
const QUOTES = {
  work: [
    "“Amateurs sit and wait for inspiration, the rest of us just get up and go to work.” — Stephen King",
    "“The secret of getting ahead is getting started.” — Mark Twain",
    "“It’s not always that we need to do more but rather that we need to focus on less.” — Nathan W. Morris",
    "“Well done is better than well said.” — Benjamin Franklin",
    "“Do the hard jobs first. The easy jobs will take care of themselves.” — Dale Carnegie",
    "“Action is the foundational key to all success.” — Pablo Picasso",
    "“You don’t have to see the whole staircase, just take the first step.” — Martin Luther King Jr.",
  ],
  calm: [
    "“Almost everything will work again if you unplug it for a few minutes — including you.” — Anne Lamott",
    "“Rest and self-care are so important. You cannot serve from an empty vessel.” — Eleanor Brownn",
    "“Nature does not hurry, yet everything is accomplished.” — Lao Tzu",
    "“Take rest; a field that has rested gives a bountiful crop.” — Ovid",
    "“Slow down and enjoy life. It’s not only the scenery you miss by going too fast.” — Eddie Cantor",
    "“Adopt the pace of nature: her secret is patience.” — Ralph Waldo Emerson",
    "“Enjoy the little things, for one day you may look back and realise they were the big things.” — Robert Brault",
  ],
  general: [
    "“Whether you think you can or you think you can’t, you’re right.” — Henry Ford",
    "“The best way to predict the future is to create it.” — Peter Drucker",
    "“What you do every day matters more than what you do once in a while.” — Gretchen Rubin",
    "“Little by little, one travels far.” — J.R.R. Tolkien",
    "“Happiness is not something ready made. It comes from your own actions.” — Dalai Lama",
    "“Start where you are. Use what you have. Do what you can.” — Arthur Ashe",
    "“How we spend our days is, of course, how we spend our lives.” — Annie Dillard",
  ],
};
function renderQuote() {
  const el = $("#d-quote"); if (!el) return;
  const occ = (activeOccasion || "").toLowerCase();
  const pool = occ === "work" ? QUOTES.work
    : (occ === "weekend" || occ === "cozy home") ? QUOTES.calm : QUOTES.general;
  el.textContent = pool[logicalDoy() % pool.length];
}

// ── Brief blocks (schedule + priorities), published by the local job ──
async function loadBrief() {
  renderJournal();   // always shown (framework prompt, no backend needed)
  try {
    const b = await api("/api/brief", null, dash.tokens[dash.active]);
    if (b && b.synced) { renderSchedule(b.schedule || []); renderPriorities(b.priorities || []); }
  } catch { /* keep the journal + any prior brief */ }
}
function renderSchedule(items) {
  const el = $("#d-schedule");
  el.innerHTML = items.length
    ? items.map((e) => `<div class="d-sched"><span class="d-sched-t">${e.time || ""}</span>` +
        `<span class="d-sched-x"><b>${e.title || ""}</b>${e.location ? `<i>${e.location}</i>` : ""}</span></div>`).join("")
    : `<p class="d-empty">Nothing scheduled.</p>`;
}
function renderPriorities(items) {
  const block = $("#d-priorities-block"), el = $("#d-priorities");
  block.hidden = !items.length;
  el.innerHTML = items.map((p) =>
    `<div class="d-prio d-prio-${p.urgency || "today"}"><b>${p.title || ""}</b>` +
    `${p.summary ? `<span>${p.summary}</span>` : ""}<i>${p.source || ""}</i></div>`).join("");
}

function newOutfit() { day.anchors = []; day.anchor = null; day.rejections = []; day.variety = true; loadOutfit(true); }
function submitWish() { day.wish = $("#d-wish").value.trim(); loadOutfit(); }

function renderOccasions() {
  const wrap = $("#d-occasions"); if (!wrap) return; wrap.innerHTML = "";
  OCCASIONS.forEach((o) => {
    const b = document.createElement("button");
    b.className = "chip" + (o.toLowerCase() === (activeOccasion || "").toLowerCase() ? " on" : "");
    b.textContent = o;
    b.onclick = () => {
      day.occasion = o; day.rejections = []; activeOccasion = o;
      if (!day.date) setOcc({ ...occStore(), [todayISO()]: o });   // persist for today only
      renderOccasions(); loadOutfit();
    };
    wrap.appendChild(b);
  });
}

// Kiosk auto-auth: a signed token in the URL (?k=<joseph token>, or ?joseph=…&evangeline=…)
// seeds this device so the morning display never asks for a PIN.
function seedKioskTokens() {
  const qp = new URLSearchParams(location.search);
  const seed = { joseph: qp.get("joseph") || qp.get("k"), evangeline: qp.get("evangeline") };
  let seeded = null;
  const toks = { ...dash.tokens };
  for (const p of PROFILES) { if (seed[p]) { toks[p] = seed[p]; seeded = seeded || p; } }
  if (seeded) {
    dash.tokens = toks; dash.active = seeded;
    history.replaceState(null, "", location.pathname);   // drop the token from the URL
  }
}

function init() {
  seedKioskTokens();
  $("#d-unlock").onclick = unlock;
  $("#d-pin").addEventListener("keydown", (e) => { if (e.key === "Enter") unlock(); });
  $("#d-regen").onclick = newOutfit;
  $("#d-wish").addEventListener("keydown", (e) => { if (e.key === "Enter") submitWish(); });
  $("#d-adv-toggle").onclick = () => {
    const a = $("#d-advanced"); a.hidden = !a.hidden;
    $("#d-adv-toggle").textContent = a.hidden ? "Advanced ⌄" : "Advanced ⌃";
  };
  document.querySelectorAll("[data-warm]").forEach((b) => b.onclick = () => { day.temp_step += +b.dataset.warm; loadOutfit(); });
  document.querySelectorAll("[data-dress]").forEach((b) => b.onclick = () => { day.dress_step += +b.dataset.dress; loadOutfit(); });
  $("#d-pop").addEventListener("click", (e) => { if (e.target === $("#d-pop")) closePop(); });
  $("#d-zoom").onclick = () => { $("#d-zoom").hidden = true; };
  $("#d-prev").onclick = () => shiftDay(-1);
  $("#d-next").onclick = () => shiftDay(1);
  $("#d-focus").addEventListener("input", (e) => localStorage.setItem(K("focus"), e.target.value));
  $("#d-journal").onclick = () => { journalStep++; renderJournal(); };   // tap for another prompt
  $("#d-settings").onclick = () => openEditor("panel=settings", "Preferences");   // prefs overlay, no page jump
  $("#d-edit-done").onclick = closeEditor;
  $("#d-edit").addEventListener("click", (e) => { if (e.target === $("#d-edit")) closeEditor(); });
  const bars = $("#d-bars");
  bars.addEventListener("click", (e) => { const b = e.target.closest(".wbar"); if (b) showWxPop(+b.dataset.i); });
  bars.addEventListener("mousemove", (e) => { const b = e.target.closest(".wbar"); if (b) showWxPop(+b.dataset.i); });
  // fresh look when the kiosk wakes / tab refocuses
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !$("#d-app").hidden) { day = freshDay(); loadOutfit(); loadBrief(); } });

  renderProfiles();
  const active = dash.active;
  if (dash.tokens[active]) {
    showApp(); loadOutfit(); loadBrief();
    setTimeout(loadBrief, 12000);   // catch the fresh brief the launcher publishes on wake
  } else { showLock(active); }
}
init();
