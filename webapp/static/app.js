"use strict";

const $ = (s) => document.querySelector(s);
const TOP_ROW = new Set(["outerwear", "midlayer", "top", "blouse", "knit", "cardigan", "dress"]);
const OCCASIONS = ["Casual", "Work", "Dressy", "Going out", "Cozy home"];
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
};

let day = { occasion: null, temp_step: 0, dress_step: 0, anchor: null, anchors: [], wish: "", variety: false, rejections: [], date: null, location: null };
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
    setWhoami(r.name || cap(store.profile));
    $("#pin").value = "";
    showApp(); fetchOutfit();
  } catch { $("#lock-error").hidden = false; }
}

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }

function setWhoami(name) {
  const el = $("#whoami"); if (el) el.textContent = name ? `${name}’s closet` : "";
}

function signOut() {
  store.token = null; store.profile = null;
  setWhoami(""); $("#pin").value = "";
  showLock();
}

function renderOccasions() {
  const wrap = $("#occasions"); wrap.innerHTML = "";
  OCCASIONS.forEach((o) => {
    const b = document.createElement("button");
    b.className = "chip" + (o.toLowerCase() === (activeOccasion || "").toLowerCase() ? " on" : "");
    b.textContent = o;
    b.onclick = () => { day.occasion = o; day.rejections = []; activeOccasion = o; renderOccasions(); fetchOutfit(); };
    wrap.appendChild(b);
  });
}

function renderLook(pieces) {
  const look = $("#look"); look.innerHTML = "";
  currentPieces = {};
  const rows = { top: document.createElement("div"), bottom: document.createElement("div") };
  rows.top.className = rows.bottom.className = "look-row";
  let any = false;
  (pieces || []).forEach((p) => {
    if (!p.url) return; any = true;
    currentPieces[p.name] = p;
    const fig = document.createElement("figure");
    fig.className = "look-item cat-" + (p.category || "other");
    fig.innerHTML = `<img src="${p.url}" alt=""><figcaption>${p.name || ""}</figcaption>`;
    fig.onclick = () => openReason(p);
    (TOP_ROW.has(p.category) ? rows.top : rows.bottom).appendChild(fig);
  });
  if (rows.top.children.length) look.appendChild(rows.top);
  if (rows.bottom.children.length) look.appendChild(rows.bottom);
  $("#look-hint").hidden = !any;
}

async function fetchOutfit() {
  loading(true);
  try {
    day.recent = store.recent;
    const r = await api("/api/outfit", { prefs: store.prefs, day });
    const names = (r.pieces || []).map((p) => p.name).filter(Boolean);
    store.recent = [...names, ...store.recent.filter((n) => !names.includes(n))];
    activeOccasion = r.occasion || activeOccasion; renderOccasions();
    $("#headline").textContent = r.headline || "";
    $("#reason").textContent = r.reason || "";
    $("#weather").textContent = (r.weather && r.weather.summary) || "";
    renderWeatherBars(r.weather);
    const d = r.date ? new Date(r.date + "T00:00:00") : new Date();
    $("#date-label").textContent = d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
    renderLook(r.pieces);
  } catch (e) {
    if (e.message !== "locked") $("#reason").textContent = "Couldn't load — try again.";
  } finally {
    day.variety = false;  // one-shot
    loading(false);
  }
}

function fmtHour(h) {
  const ap = h < 12 ? "am" : "pm";
  return `${((h + 11) % 12) + 1}${ap}`;
}

function renderWeatherBars(w) {
  const el = $("#weather-bars");
  if (!el) return;
  const hrs = (w && w.hourly) || [];
  if (!hrs.length) { el.hidden = true; el.innerHTML = ""; return; }
  const temps = hrs.map((h) => h.temp).filter((t) => t != null);
  const lo = temps.length ? Math.min(...temps) : w.low;
  const hi = temps.length ? Math.max(...temps) : w.high;
  const peak = hrs.reduce((a, b) => (b.pop > a.pop ? b : a), hrs[0]);
  const n = hrs.length;
  const tickAt = new Set([0, Math.round(n / 3), Math.round((2 * n) / 3), n - 1]);
  const bars = hrs.map((h) => {
    const cls = h.pop >= 50 ? "wbar wet" : h.pop >= 25 ? "wbar damp" : "wbar";
    const t = h.temp != null ? ` ${h.temp}°` : "";
    return `<span class="${cls}" style="--p:${Math.max(6, h.pop)}%" title="${fmtHour(h.hour)}${t} · rain ${h.pop}%"></span>`;
  }).join("");
  const ticks = hrs.map((h, i) => tickAt.has(i)
    ? `<span class="wtick"><b>${h.temp != null ? h.temp + "°" : ""}</b><i>${fmtHour(h.hour)}</i></span>`
    : `<span class="wtick"></span>`).join("");
  const range = (lo != null && hi != null) ? `${lo}°–${hi}°` : "";
  const rain = peak.pop >= 20 ? `rain ~${peak.pop}% · ${fmtHour(peak.hour)}` : "dry through the day";
  el.innerHTML =
    `<div class="wbars-head"><span class="wbars-range">${range}</span><span class="wbars-cap">${rain}</span></div>` +
    `<div class="wbars-row">${bars}</div>` +
    `<div class="wticks">${ticks}</div>`;
  el.hidden = false;
}

function openReason(piece) {
  const name = piece.name;
  $("#reason-title").textContent = "This piece";
  $("#reason-img").src = piece.url || "";
  $("#reason-name").textContent = name || "";
  $("#reason-chips").hidden = true;
  const row = $("#reason-chip-row"); row.innerHTML = "";
  REASONS.forEach((reason) => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = reason;
    b.onclick = () => { day.rejections.push({ item: name, reason }); $("#reason-modal").hidden = true; fetchOutfit(); };
    row.appendChild(b);
  });
  $("#act-remove").onclick = () => {
    day.rejections.push({ item: name, reason: "removed for today" });
    $("#reason-modal").hidden = true; fetchOutfit();
  };
  $("#act-swap").onclick = () => { $("#reason-chips").hidden = false; };
  $("#edit-piece").onclick = () => { $("#reason-modal").hidden = true; openPieceEditor(piece); };
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
        cell.onclick = () => { $("#wardrobe-modal").hidden = true; openPieceEditor(i); };
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

function openPieceEditor(piece) {
  editingPiece = piece;
  $("#piece-title").textContent = piece.name || "Edit piece";
  $("#piece-img").src = piece.url || "";
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
  await api("/api/wardrobe/" + encodeURIComponent(editingPiece.id), {
    warmth: +$("#piece-warmth").value,
    polish: +$("#piece-polish").value,
    comfort: +$("#piece-comfort").value,
    wear_frequency: +$("#piece-wear").value,
    home_ok: $("#piece-home").checked,
    office_ok: $("#piece-office").checked,
    avoid_often: $("#piece-avoid").checked,
  });
  $("#piece-editor").hidden = true;
  fetchOutfit();
}

async function applyPlan() {
  day.date = $("#date").value || null;
  const city = $("#city").value.trim();
  if (city) {
    try { day.location = await api("/api/geocode?q=" + encodeURIComponent(city)); }
    catch { day.location = null; }
  } else { day.location = null; }
  $("#plan").hidden = true;
  fetchOutfit();
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
  renderOfficeDays();
}

function saveSettings() {
  const split = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);
  const office = [...document.querySelectorAll("#office-days .wd.on")].map((b) => +b.dataset.i);
  store.prefs = {
    runs_cold: $("#runs-cold").checked,
    style_notes: $("#style-notes").value.trim(),
    love_colors: split($("#love-colors").value),
    avoid_colors: split($("#avoid-colors").value),
    office_days: office,
  };
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
  $("#piece-close").onclick = () => { $("#piece-editor").hidden = true; };
  $("#piece-save").onclick = savePieceEditor;
  $("#plan-btn").onclick = () => { $("#plan").hidden = !$("#plan").hidden; };
  $("#plan-apply").onclick = applyPlan;
  $("#settings-btn").onclick = () => { loadSettings(); $("#settings").hidden = false; };
  $("#settings-close").onclick = () => { $("#settings").hidden = true; };
  $("#settings-save").onclick = saveSettings;
  $("#signout-btn").onclick = signOut;
}

function init() {
  bind(); renderOccasions();
  if (store.token) { setWhoami(cap(store.profile)); showApp(); fetchOutfit(); } else { showLock(); }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
}
init();
