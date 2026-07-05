"use strict";

const $ = (s) => document.querySelector(s);
const TOP_ROW = new Set(["outerwear", "midlayer", "top", "blouse", "knit", "cardigan", "dress"]);
const OCCASIONS = ["Casual", "Weekend", "Work", "Dressy", "Going out", "Cozy home"];
const REASONS = ["too cold", "too warm", "too small / doesn't fit", "wrong for the occasion", "not feeling it"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const store = {
  get token() { return localStorage.getItem("wc.token"); },
  set token(v) { v ? localStorage.setItem("wc.token", v) : localStorage.removeItem("wc.token"); },
  get profile() { return localStorage.getItem("wc.profile") || ""; },
  set profile(v) { v ? localStorage.setItem("wc.profile", v) : localStorage.removeItem("wc.profile"); },
  // Prefs and recency are per-profile, so switching closets never mixes them.
  _k(base) { return `wc.${base}.${this.profile || "_"}`; },
  get prefs() { try { return JSON.parse(localStorage.getItem(this._k("prefs"))) || {}; } catch { return {}; } },
  set prefs(v) { localStorage.setItem(this._k("prefs"), JSON.stringify(v)); },
  get recent() { try { return JSON.parse(localStorage.getItem(this._k("recent"))) || []; } catch { return []; } },
  set recent(v) { localStorage.setItem(this._k("recent"), JSON.stringify(v.slice(0, 15))); },
  get units() { return localStorage.getItem("wc.units") || "C"; },   // shared display pref
  set units(v) { localStorage.setItem("wc.units", v); },
  get locked() { try { return JSON.parse(localStorage.getItem(this._k("locked"))) || {}; } catch { return {}; } },
  set locked(v) { localStorage.setItem(this._k("locked"), JSON.stringify(v)); },
  get occasions() { try { return JSON.parse(localStorage.getItem(this._k("occ"))) || {}; } catch { return {}; } },
  set occasions(v) { localStorage.setItem(this._k("occ"), JSON.stringify(v)); },
};

const FRESH_DAY = () => ({ occasion: null, temp_step: 0, dress_step: 0, anchor: null, anchors: [], wish: "", variety: false, rejections: [], date: null, location: null });
let lastWeather = null;
let lastResult = null;
function todayISO() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function fmtTemp(c) { if (c == null) return ""; return store.units === "F" ? `${Math.round(c * 9 / 5 + 32)}°` : `${Math.round(c)}°`; }

let day = FRESH_DAY();
let activeOccasion = null;
let currentPieces = {};
let editingPiece = null;

async function api(path, body) {
  const opts = { method: body ? "POST" : "GET", headers: {} };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  if (store.token) opts.headers["Authorization"] = "Bearer " + store.token;
  const res = await fetch(path, opts);
  if (res.status === 401) { showLock(); throw new Error("locked"); }
  if (!res.ok) throw new Error("request failed");
  return res.json();
}

function showLock() { $("#lock").hidden = false; $("#app").hidden = true; }
function showApp() { $("#lock").hidden = true; $("#app").hidden = false; }
function loading(on) { $("#loading").hidden = !on; }

async function unlock() {
  $("#lock-error").hidden = true;
  try {
    const r = await api("/api/unlock", { pin: $("#pin").value });
    store.token = r.token; store.profile = r.profile || "";
    localStorage.setItem("wc.menswear." + store.profile, r.menswear ? "1" : "");
    $("#pin").value = "";
    showApp();
    await afterLogin(r.name || cap(store.profile));
    fetchOutfit();
  } catch { $("#lock-error").hidden = false; }
}

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
function setWhoami(name) { const el = $("#whoami"); if (el) el.textContent = name ? `${name}’s closet` : ""; }
function wardrobeIcon() { return localStorage.getItem("wc.menswear." + store.profile) ? "👔" : "👗"; }
function updateUnitToggle() { const b = $("#unit-toggle"); if (b) b.textContent = store.units === "F" ? "°F" : "°C"; }

async function afterLogin(name) {
  setWhoami(name);
  day = FRESH_DAY();
  $("#wish").value = "";
  $("#wardrobe-btn").textContent = `${wardrobeIcon()} Browse & edit my wardrobe`;
  updateUnitToggle();
  await pullState();                       // adopt locked outfits + prefs synced from other devices
  day.location = store.prefs.location || null;
}

async function pullState() {
  if (!store.token) return;
  try {
    const s = await api("/api/state");
    if (s && s.synced) {
      if (s.locked) store.locked = { ...store.locked, ...s.locked };
      if (s.occasions) store.occasions = { ...store.occasions, ...s.occasions };
      if (s.prefs) store.prefs = s.prefs;
    }
  } catch { /* offline / no store — keep local state */ }
}

function pushState() {
  if (!store.token) return;
  api("/api/state", { locked: store.locked, prefs: store.prefs, occasions: store.occasions }).catch(() => {});
}

function signOut() {
  store.token = null; store.profile = null;
  setWhoami(""); $("#pin").value = ""; $("#wish").value = "";
  day = FRESH_DAY();
  showLock();
}

function renderOccasions() {
  const wrap = $("#occasions"); wrap.innerHTML = "";
  OCCASIONS.forEach((o) => {
    const b = document.createElement("button");
    b.className = "chip" + (o.toLowerCase() === (activeOccasion || "").toLowerCase() ? " on" : "");
    b.textContent = o;
    b.onclick = () => {
      const key = day.date || todayISO();
      day.occasion = o; day.rejections = []; activeOccasion = o;
      store.occasions = { ...store.occasions, [key]: o };   // remember what you picked for this day
      pushState();
      renderOccasions(); fetchOutfit();
    };
    wrap.appendChild(b);
  });
}

function renderLook(pieces) {
  const look = $("#look"); look.innerHTML = "";
  currentPieces = {};
  const rows = { top: document.createElement("div"), bottom: document.createElement("div") };
  rows.top.className = rows.bottom.className = "look-row";
  const anchors = new Set(day.anchors || []);
  let any = false;
  (pieces || []).forEach((p) => {
    if (!p.url) return; any = true;
    currentPieces[p.name] = p;
    const anchored = p.id && anchors.has(p.id);
    const fig = document.createElement("figure");
    fig.className = "look-item cat-" + (p.category || "other") + (anchored ? " anchored" : "");
    fig.innerHTML = `<img src="${p.url}" alt=""><figcaption>${p.name || ""}</figcaption>` +
      (anchored ? `<button class="unanchor" data-id="${p.id}" title="Anchored — tap to release">🔒</button>` : "");
    fig.onclick = (e) => {
      if (e.target.closest(".unanchor")) { e.stopPropagation(); unanchor(p.id); return; }
      openReason(p);
    };
    (TOP_ROW.has(p.category) ? rows.top : rows.bottom).appendChild(fig);
  });
  if (rows.top.children.length) look.appendChild(rows.top);
  if (rows.bottom.children.length) look.appendChild(rows.bottom);
  $("#look-hint").hidden = !any;
}

function unanchor(id) {
  day.anchors = (day.anchors || []).filter((x) => x !== id);
  day.anchor = day.anchors[0] || null;
  fetchOutfit();
}

function renderResult(r) {
  lastResult = r;
  activeOccasion = r.occasion || activeOccasion; renderOccasions();
  $("#headline").textContent = r.headline || "";
  $("#reason").textContent = r.reason || "";
  $("#place").textContent = r.place || "";
  renderWeather(r.weather);
  const d = r.date ? new Date(r.date + "T00:00:00") : new Date();
  $("#date-label").textContent = d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  renderLook(r.pieces);
  updateLockButton();
  // Publish today's look so the dashboard can mirror it (same-origin, instant reflect).
  try { localStorage.setItem("wc.today." + store.profile, JSON.stringify({ date: r.date, result: r })); } catch (e) {}
}

async function fetchOutfit() {
  const key = day.date || todayISO();
  const lk = store.locked[key];
  if (lk && lk.anchors) {                 // pinned day: keep its pieces, still allow warmer etc.
    day.anchors = lk.anchors; day.anchor = lk.anchors[0] || null;
  } else if (lk && lk.pieces) {           // legacy frozen snapshot
    renderResult(lk); return;
  }
  const occ = store.occasions[key];       // a day you explicitly set overrides office-day defaults
  if (occ) { day.occasion = occ; activeOccasion = occ; }
  loading(true);
  try {
    day.recent = store.recent;
    const r = await api("/api/outfit", { prefs: store.prefs, day });
    const names = (r.pieces || []).map((p) => p.name).filter(Boolean);
    store.recent = [...names, ...store.recent.filter((n) => !names.includes(n))];
    renderResult(r);
  } catch (e) {
    if (e.message !== "locked") $("#reason").textContent = "Couldn't load — try again.";
  } finally {
    day.variety = false;  // one-shot
    loading(false);
  }
}

function shiftDay(delta) {
  const t = todayISO();
  const d = new Date((day.date || t) + "T00:00:00"); d.setDate(d.getDate() + delta);
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const max = new Date(t + "T00:00:00"); max.setDate(max.getDate() + 6);
  if (iso < t || d > max) return;                       // Open-Meteo window: today..+6
  day.date = iso === t ? null : iso;
  day.occasion = null; activeOccasion = null;           // let the new weekday set the occasion
  fetchOutfit();
}

function updateLockButton() {
  const b = $("#lock-day"); if (!b) return;
  const on = !!store.locked[day.date || todayISO()];
  b.innerHTML = on ? "🔒 Locked" : "🔓 Lock";
  b.classList.toggle("on", on);
  b.title = on ? "Locked for the day — tap to unlock" : "Lock this outfit for the day";
  document.querySelector(".outfit").classList.toggle("locked", on);
}

function currentIds() {
  return Object.values(currentPieces).map((p) => p.id).filter(Boolean);
}

function toggleLock() {
  const key = day.date || todayISO();
  const locked = { ...store.locked };
  if (locked[key]) {
    delete locked[key]; store.locked = locked;
    day.anchors = []; day.anchor = null;
  } else {
    const ids = currentIds();
    locked[key] = { anchors: ids }; store.locked = locked;
    day.anchors = ids; day.anchor = ids[0] || null;
  }
  updateLockButton();
  if (lastResult) renderResult(lastResult);   // refresh badges without regenerating
  pushState();
}

// Keep a locked day's stored anchors in step when pieces are kept/released.
function syncLockAnchors() {
  const key = day.date || todayISO();
  if (store.locked[key]) {
    store.locked = { ...store.locked, [key]: { anchors: day.anchors || [] } };
    pushState();
  }
}

function fmtHour(h) {
  const ap = h < 12 ? "am" : "pm";
  return `${((h + 11) % 12) + 1}${ap}`;
}

let wxHours = [];

function renderWeather(w) {
  lastWeather = w || null;
  const el = $("#weather");
  if (!w) { if (el) el.textContent = ""; renderWeatherBars(null); return; }
  const cond = (w.summary || "").split(", ").slice(1).join(", ") || (w.condition || "").replace(/_/g, " ");
  if (el) el.textContent = `${fmtTemp(w.high)}  ${cond}`.trim().toUpperCase();
  renderWeatherBars(w);
}

function renderWeatherBars(w) {
  const el = $("#weather-bars");
  if (!el) return;
  const pop = $("#wx-pop"); if (pop) pop.hidden = true;
  const hrs = (w && w.hourly) || []; wxHours = hrs;
  if (!hrs.length) { el.hidden = true; el.innerHTML = ""; return; }
  const temps = hrs.map((h) => h.temp).filter((t) => t != null);
  const lo = temps.length ? Math.min(...temps) : w.low;
  const hi = temps.length ? Math.max(...temps) : w.high;
  const peak = hrs.reduce((a, b) => (b.pop > a.pop ? b : a), hrs[0]);
  const n = hrs.length;
  const tickAt = new Set([0, Math.round(n / 3), Math.round((2 * n) / 3), n - 1]);
  const bars = hrs.map((h, i) => {
    const cls = h.pop >= 50 ? "wbar wet" : h.pop >= 25 ? "wbar damp" : "wbar";
    return `<span class="${cls}" data-i="${i}" style="--p:${Math.max(6, h.pop)}%"></span>`;
  }).join("");
  const ticks = hrs.map((h, i) => tickAt.has(i)
    ? `<span class="wtick"><b>${fmtTemp(h.temp)}</b><i>${fmtHour(h.hour)}</i></span>`
    : `<span class="wtick"></span>`).join("");
  const range = (lo != null && hi != null) ? `${fmtTemp(lo)}–${fmtTemp(hi)}` : "";
  const rain = peak.pop >= 20 ? `rain ~${peak.pop}% · ${fmtHour(peak.hour)}` : "dry through the day";
  el.innerHTML =
    `<div class="wbars-head"><span class="wbars-range">${range}</span><span class="wbars-cap">${rain}</span></div>` +
    `<div class="wbars-row">${bars}</div>` +
    `<div class="wticks">${ticks}</div>`;
  el.hidden = false;
}

function showWxPop(i) {
  const h = wxHours[i]; const pop = $("#wx-pop"); if (!h || !pop) return;
  pop.innerHTML =
    `<b>${fmtHour(h.hour)}</b><span>${fmtTemp(h.temp)}</span>` +
    `<span>🌧 ${h.pop}%</span>` + (h.wind != null ? `<span>🌬 ${h.wind} km/h</span>` : "");
  pop.hidden = false;
}

function openZoom(url) {
  if (!url) return;
  $("#zoom-img").src = url;
  $("#zoom").hidden = false;
}

function otherIds(name) {
  return Object.values(currentPieces).filter((p) => p.id && p.name !== name).map((p) => p.id);
}

// Swap = keep every other piece pinned for THIS regeneration only, replacing just this
// slot. The temporary pins are released afterwards so the rest aren't stuck locked.
function swapPiece(name, reason) {
  const userAnchors = day.anchors || [];
  const keep = otherIds(name);
  day.anchors = [...new Set([...userAnchors, ...keep])];
  day.anchor = day.anchors[0] || null;
  day.rejections.push({ item: name, reason });
  $("#reason-modal").hidden = true;
  fetchOutfit().then(() => {
    day.anchors = userAnchors; day.anchor = userAnchors[0] || null;
    if (lastResult) renderResult(lastResult);   // clear the transient anchor badges
  });
}

function openReason(piece) {
  const name = piece.name;
  const anchored = piece.id && (day.anchors || []).includes(piece.id);
  $("#reason-title").textContent = "This piece";
  $("#reason-img").src = piece.url || "";
  $("#reason-img").onclick = () => openZoom(piece.url);
  $("#reason-name").textContent = name || "";
  $("#reason-chips").hidden = true;
  $("#keep-label").textContent = anchored ? "Release" : "Keep";
  $("#keep-sub").textContent = anchored ? "stop anchoring it" : "anchor this piece";
  const row = $("#reason-chip-row"); row.innerHTML = "";
  REASONS.forEach((reason) => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = reason;
    b.onclick = () => swapPiece(name, reason);
    row.appendChild(b);
  });
  $("#act-keep").onclick = () => {
    const set = new Set(day.anchors || []);
    if (piece.id) { set.has(piece.id) ? set.delete(piece.id) : set.add(piece.id); }
    day.anchors = [...set]; day.anchor = day.anchors[0] || null;
    syncLockAnchors();
    $("#reason-modal").hidden = true;
    if (lastResult) renderResult(lastResult);   // update badge, keep the outfit
  };
  $("#act-remove").onclick = () => {
    if (lastResult) lastResult.pieces = (lastResult.pieces || []).filter((p) => p.name !== name);
    day.rejections.push({ item: name, reason: "removed for today" });
    day.anchors = (day.anchors || []).filter((id) => id !== piece.id);
    syncLockAnchors();
    $("#reason-modal").hidden = true;
    if (lastResult) renderResult(lastResult);   // drop just this piece, keep the rest
  };
  $("#act-swap").onclick = () => { $("#reason-chips").hidden = false; };
  $("#edit-piece").onclick = () => { $("#reason-modal").hidden = true; openPieceEditor(piece, "look"); };
  $("#reason-modal").hidden = false;
}

async function openWardrobe() {
  const groups = $("#wardrobe-groups"); groups.innerHTML = "Loading…"; $("#wardrobe-modal").hidden = false;
  try {
    const items = (await api("/api/wardrobe")).filter((i) => i.url);
    const byCat = {};
    items.forEach((i) => { (byCat[i.category || "other"] ||= []).push(i); });
    groups.innerHTML = "";
    Object.keys(byCat).sort().forEach((cat) => {
      const h = document.createElement("h4"); h.className = "group-head"; h.textContent = cat; groups.appendChild(h);
      const grid = document.createElement("div"); grid.className = "grid";
      byCat[cat].forEach((i) => {
        const cell = document.createElement("button"); cell.className = "pick";
        cell.innerHTML = `<img src="${i.url}" alt=""><span>${i.name || ""}</span>`;
        cell.onclick = () => { $("#wardrobe-modal").hidden = true; openPieceEditor(i, "wardrobe"); };
        grid.appendChild(cell);
      });
      groups.appendChild(grid);
    });
  } catch { groups.innerHTML = "Couldn't load wardrobe."; }
}

async function openPicker() {
  const groups = $("#picker-groups"); groups.innerHTML = "Loading…"; $("#picker").hidden = false;
  try {
    const items = (await api("/api/wardrobe")).filter((i) => i.url);
    const byCat = {};
    items.forEach((i) => { (byCat[i.category || "other"] ||= []).push(i); });
    groups.innerHTML = "";
    Object.keys(byCat).sort().forEach((cat) => {
      const h = document.createElement("h4"); h.className = "group-head"; h.textContent = cat; groups.appendChild(h);
      const grid = document.createElement("div"); grid.className = "grid";
      byCat[cat].forEach((i) => {
        const cell = document.createElement("button");
        cell.className = "pick" + ((day.anchors || []).includes(i.id) ? " on" : "");
        cell.innerHTML = `<img src="${i.url}" alt=""><span>${i.name || ""}</span>`;
        cell.onclick = () => {
          const set = new Set(day.anchors || []);
          set.has(i.id) ? set.delete(i.id) : set.add(i.id);
          day.anchors = [...set];
          day.anchor = day.anchors[0] || null;
          cell.classList.toggle("on");
        };
        grid.appendChild(cell);
      });
      groups.appendChild(grid);
    });
  } catch { groups.innerHTML = "Couldn't load wardrobe."; }
}

async function buildFromAnchors() {
  const warn = $("#anchor-warn");
  if ((day.anchors || []).length) {
    try {
      const { warnings } = await api("/api/anchors/check", { anchors: day.anchors });
      if (warnings && warnings.length) {
        warn.innerHTML = warnings.map((w) => `<p>⚠ ${w}</p>`).join("") +
          `<button id="warn-proceed" class="chip">Build anyway</button>`;
        warn.hidden = false;
        $("#warn-proceed").onclick = () => { warn.hidden = true; $("#picker").hidden = true; fetchOutfit(); };
        return;
      }
    } catch { /* ignore check failures, just build */ }
  }
  warn.hidden = true;
  $("#picker").hidden = true;
  fetchOutfit();
}

function bindRange(id, valueId) {
  const input = $(id), value = $(valueId);
  const sync = () => { value.textContent = input.value; };
  input.oninput = sync; sync();
}

let pieceEditorOrigin = null;

function openPieceEditor(piece, origin) {
  editingPiece = piece;
  pieceEditorOrigin = origin || null;
  $("#piece-title").textContent = piece.name || "Edit piece";
  $("#piece-img").src = piece.url || "";
  $("#piece-img").onclick = () => openZoom(piece.url);
  $("#piece-warmth").value = piece.warmth || 3;
  $("#piece-polish").value = piece.polish || (piece.category === "bag" ? 3 : 2);
  $("#piece-comfort").value = piece.comfort || 3;
  $("#piece-wear").value = piece.wear_frequency || 3;
  $("#piece-home").checked = piece.home_ok !== false;
  $("#piece-office").checked = piece.office_ok === true;
  $("#piece-avoid").checked = piece.avoid_often === true;
  bindRange("#piece-warmth", "#warmth-value");
  bindRange("#piece-polish", "#polish-value");
  bindRange("#piece-comfort", "#comfort-value");
  bindRange("#piece-wear", "#wear-value");
  $("#piece-editor").hidden = false;
}

async function savePieceEditor() {
  if (!editingPiece || !editingPiece.id) return;
  const vals = {
    warmth: +$("#piece-warmth").value,
    polish: +$("#piece-polish").value,
    comfort: +$("#piece-comfort").value,
    wear_frequency: +$("#piece-wear").value,
    home_ok: $("#piece-home").checked,
    office_ok: $("#piece-office").checked,
    avoid_often: $("#piece-avoid").checked,
  };
  const btn = $("#piece-save"); btn.disabled = true; btn.textContent = "Saving…";
  try {
    await api("/api/wardrobe/" + encodeURIComponent(editingPiece.id), vals);
  } finally { btn.disabled = false; btn.textContent = "Save ratings"; }
  Object.assign(editingPiece, vals);   // reflect locally; ratings apply to FUTURE outfits
  $("#piece-editor").hidden = true;
  const origin = pieceEditorOrigin; pieceEditorOrigin = null;
  if (origin === "wardrobe") openWardrobe();   // else: keep the current outfit untouched
}

async function applyPlan() {
  const t = todayISO();
  day.date = ($("#date").value && $("#date").value >= t) ? ($("#date").value === t ? null : $("#date").value) : null;
  day.occasion = null; activeOccasion = null;
  $("#plan").hidden = true;
  fetchOutfit();
}

async function resolveSuburb() {
  // Turn the suburb box into a location when it changed; keep the previous one on miss.
  const q = $("#suburb").value.trim();
  const curLabel = (store.prefs.location && store.prefs.location.label) || "";
  if (q === curLabel) return store.prefs.location || null;
  if (!q) return null;
  $("#suburb-status").textContent = "Finding location…";
  try {
    const loc = await api("/api/geocode?q=" + encodeURIComponent(q));
    $("#suburb-status").textContent = "Set to " + (loc.label || q);
    return loc;
  } catch {
    $("#suburb-status").textContent = "Couldn't find that place — keeping previous.";
    return store.prefs.location || null;
  }
}

function renderOfficeDays() {
  const wrap = $("#office-days"); wrap.innerHTML = "";
  const set = new Set(store.prefs.office_days || [1, 3]);
  WEEKDAYS.forEach((d, i) => {
    const b = document.createElement("button"); b.type = "button";
    b.className = "wd" + (set.has(i) ? " on" : ""); b.textContent = d;
    b.onclick = () => { b.classList.toggle("on"); }; b.dataset.i = i;
    wrap.appendChild(b);
  });
}

function loadSettings() {
  const p = store.prefs;
  $("#runs-cold").checked = !!p.runs_cold;
  $("#style-notes").value = p.style_notes || "";
  $("#love-colors").value = (p.love_colors || []).join(", ");
  $("#avoid-colors").value = (p.avoid_colors || []).join(", ");
  $("#suburb").value = (p.location && p.location.label) || "";
  $("#suburb-status").textContent = "";
  renderOfficeDays();
}

async function saveSettings() {
  const split = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);
  const office = [...document.querySelectorAll("#office-days .wd.on")].map((b) => +b.dataset.i);
  const location = await resolveSuburb();
  store.prefs = {
    ...store.prefs,
    runs_cold: $("#runs-cold").checked,
    style_notes: $("#style-notes").value.trim(),
    love_colors: split($("#love-colors").value),
    avoid_colors: split($("#avoid-colors").value),
    office_days: office,
    location,
  };
  day.location = location;
  pushState();
  $("#settings").hidden = true; fetchOutfit();
}

function bind() {
  $("#unlock").onclick = unlock;
  $("#pin").addEventListener("keydown", (e) => { if (e.key === "Enter") unlock(); });
  $("#regen").onclick = () => { day.wish = $("#wish").value.trim(); fetchOutfit(); };
  $("#wish").addEventListener("keydown", (e) => { if (e.key === "Enter") { day.wish = $("#wish").value.trim(); fetchOutfit(); } });
  document.querySelectorAll("[data-warm]").forEach((b) => b.onclick = () => { day.temp_step += +b.dataset.warm; fetchOutfit(); });
  document.querySelectorAll("[data-dress]").forEach((b) => b.onclick = () => { day.dress_step += +b.dataset.dress; fetchOutfit(); });
  $("#variety-btn").onclick = () => { day.variety = true; fetchOutfit(); };
  $("#anchor-btn").onclick = openPicker;
  $("#picker-close").onclick = () => { $("#picker").hidden = true; };
  $("#picker-apply").onclick = buildFromAnchors;
  $("#wardrobe-btn").onclick = openWardrobe;
  $("#wardrobe-close").onclick = () => { $("#wardrobe-modal").hidden = true; };
  $("#reason-close").onclick = () => { $("#reason-modal").hidden = true; };
  document.querySelectorAll(".modal").forEach((m) => {
    m.addEventListener("click", (e) => { if (e.target === m) m.hidden = true; });
  });
  $("#piece-close").onclick = () => {
    $("#piece-editor").hidden = true;
    const origin = pieceEditorOrigin; pieceEditorOrigin = null;
    if (origin === "wardrobe") openWardrobe();
  };
  $("#piece-save").onclick = savePieceEditor;
  $("#plan-btn").onclick = () => { $("#plan").hidden = !$("#plan").hidden; };
  $("#plan-apply").onclick = applyPlan;
  $("#settings-btn").onclick = () => { loadSettings(); $("#settings").hidden = false; };
  $("#settings-close").onclick = () => { $("#settings").hidden = true; };
  $("#settings-save").onclick = saveSettings;
  $("#signout-btn").onclick = signOut;
  $("#day-prev").onclick = () => shiftDay(-1);
  $("#day-next").onclick = () => shiftDay(1);
  $("#lock-day").onclick = toggleLock;
  $("#unit-toggle").onclick = () => { store.units = store.units === "F" ? "C" : "F"; updateUnitToggle(); if (lastWeather) renderWeather(lastWeather); };
  const bars = $("#weather-bars");
  bars.addEventListener("click", (e) => { const b = e.target.closest(".wbar"); if (b) showWxPop(+b.dataset.i); });
  bars.addEventListener("mousemove", (e) => { const b = e.target.closest(".wbar"); if (b) showWxPop(+b.dataset.i); });
  $("#zoom").onclick = () => { $("#zoom").hidden = true; };
}

const EMBED = new URLSearchParams(location.search).has("embed");
function readTodayLocal() {
  try { const t = JSON.parse(localStorage.getItem("wc.today." + store.profile)); return (t && t.result) || null; } catch { return null; }
}

function init() {
  bind(); renderOccasions(); updateUnitToggle();
  if (EMBED) document.body.classList.add("embed");
  if (store.token) {
    showApp();
    afterLogin(cap(store.profile)).then(() => {
      const current = EMBED && readTodayLocal();
      if (current) renderResult(current);   // edit the look already on screen; don't regenerate
      else fetchOutfit();
    });
  } else { showLock(); }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
}
init();
