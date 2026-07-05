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
    showApp(); renderProfiles(); loadOutfit();
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
  if (dash.tokens[p]) { dash.active = p; renderProfiles(); loadOutfit(); }
  else { showLock(p); }
}

// The closet publishes today's look here (same-origin) — mirror it so adjusting reflects instantly.
function readToday(profile) { try { return JSON.parse(localStorage.getItem("wc.today." + profile)); } catch { return null; } }
function prefsFor(profile) { try { return JSON.parse(localStorage.getItem("wc.prefs." + profile)) || {}; } catch { return {}; } }

async function loadOutfit() {
  const active = dash.active;
  const cached = readToday(active);
  if (cached && cached.date === todayISO() && cached.result) { renderResult(cached.result); return; }
  loading(true);
  try {
    const r = await api("/api/outfit", { prefs: prefsFor(active), day: {} }, dash.tokens[active]);
    try { localStorage.setItem("wc.today." + active, JSON.stringify({ date: r.date, result: r })); } catch (e) {}
    renderResult(r);
  } catch (e) {
    if (e.message === "locked") { const t = { ...dash.tokens }; delete t[active]; dash.tokens = t; showLock(active); }
    else $("#d-headline").textContent = "Couldn't load — try again.";
  } finally { loading(false); }
}

function renderResult(r) {
  const d = r.date ? new Date(r.date + "T00:00:00") : new Date();
  $("#d-date").textContent = d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  $("#d-headline").textContent = r.headline || "";
  $("#d-reason").textContent = r.reason || "";
  renderWeather(r.weather);
  renderLook(r.pieces);
}

function renderWeather(w) {
  const el = $("#d-weather"), bars = $("#d-bars");
  if (!w) { el.textContent = ""; bars.hidden = true; return; }
  const cond = (w.summary || "").split(", ").slice(1).join(", ") || (w.condition || "").replace(/_/g, " ");
  el.textContent = `${fmtTemp(w.high)}  ${cond}${w.place ? " · " + w.place : ""}`.toUpperCase();
  const hrs = w.hourly || [];
  if (!hrs.length) { bars.hidden = true; bars.innerHTML = ""; return; }
  const temps = hrs.map((h) => h.temp).filter((t) => t != null);
  const lo = temps.length ? Math.min(...temps) : w.low, hi = temps.length ? Math.max(...temps) : w.high;
  const peak = hrs.reduce((a, b) => (b.pop > a.pop ? b : a), hrs[0]);
  const n = hrs.length, tickAt = new Set([0, Math.round(n / 3), Math.round((2 * n) / 3), n - 1]);
  const barHtml = hrs.map((h) => `<span class="wbar${h.pop >= 50 ? " wet" : h.pop >= 25 ? " damp" : ""}" style="--p:${Math.max(6, h.pop)}%"></span>`).join("");
  const ticks = hrs.map((h, i) => tickAt.has(i) ? `<span class="wtick"><b>${fmtTemp(h.temp)}</b><i>${fmtHour(h.hour)}</i></span>` : `<span class="wtick"></span>`).join("");
  bars.innerHTML =
    `<div class="wbars-head"><span class="wbars-range">${lo != null && hi != null ? `${fmtTemp(lo)}–${fmtTemp(hi)}` : ""}</span>` +
    `<span class="wbars-cap">${peak.pop >= 20 ? `rain ~${peak.pop}% · ${fmtHour(peak.hour)}` : "dry through the day"}</span></div>` +
    `<div class="wbars-row">${barHtml}</div><div class="wticks">${ticks}</div>`;
  bars.hidden = false;
}

function renderLook(pieces) {
  const look = $("#d-look"); look.innerHTML = "";
  const rows = { top: document.createElement("div"), bottom: document.createElement("div") };
  rows.top.className = rows.bottom.className = "look-row";
  (pieces || []).forEach((p) => {
    if (!p.url) return;
    const fig = document.createElement("figure");
    fig.className = "look-item cat-" + (p.category || "other");
    fig.innerHTML = `<img src="${p.url}" alt=""><figcaption>${p.name || ""}</figcaption>`;
    (TOP_ROW.has(p.category) ? rows.top : rows.bottom).appendChild(fig);
  });
  if (rows.top.children.length) look.appendChild(rows.top);
  if (rows.bottom.children.length) look.appendChild(rows.bottom);
}

// Inline adjust: load the full closet in an iframe, pointed at the active profile.
function openOverlay() {
  const active = dash.active;
  if (!dash.tokens[active]) { showLock(active); return; }
  localStorage.setItem("wc.token", dash.tokens[active]);
  localStorage.setItem("wc.profile", active);
  $("#d-overlay-title").textContent = `${cap(active)}'s closet`;
  $("#d-frame").src = "/?embed=1";
  $("#d-overlay").hidden = false;
}
function closeOverlay() {
  $("#d-overlay").hidden = true;
  $("#d-frame").src = "about:blank";
  loadOutfit();   // mirror whatever the closet last showed
}

function init() {
  $("#d-unlock").onclick = unlock;
  $("#d-pin").addEventListener("keydown", (e) => { if (e.key === "Enter") unlock(); });
  $("#d-outfit").onclick = openOverlay;
  $("#d-close").onclick = closeOverlay;
  $("#d-overlay").addEventListener("click", (e) => { if (e.target === $("#d-overlay")) closeOverlay(); });
  // refresh when the screen wakes / tab refocuses (kiosk mornings)
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !$("#d-app").hidden) loadOutfit(); });

  renderProfiles();
  const active = dash.active;
  if (dash.tokens[active]) { showApp(); loadOutfit(); } else { showLock(active); }
}
init();
