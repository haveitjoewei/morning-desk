"use strict";

const $ = (s) => document.querySelector(s);
const TOP_ROW = new Set(["outerwear", "midlayer", "top", "blouse", "knit", "cardigan", "dress"]);
const OCCASIONS = ["Casual", "Work", "Dressy", "Going out", "Cozy home"];
const REASONS = ["too cold", "too warm", "too small / doesn't fit", "wrong for the occasion", "not feeling it"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const store = {
  get token() { return localStorage.getItem("wc.token"); },
  set token(v) { v ? localStorage.setItem("wc.token", v) : localStorage.removeItem("wc.token"); },
  get prefs() { try { return JSON.parse(localStorage.getItem("wc.prefs")) || {}; } catch { return {}; } },
  set prefs(v) { localStorage.setItem("wc.prefs", JSON.stringify(v)); },
};

let day = { occasion: null, temp_step: 0, dress_step: 0, anchor: null, wish: "", variety: false, rejections: [], date: null, location: null };
let activeOccasion = null;

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
    const { token } = await api("/api/unlock", { pin: $("#pin").value });
    store.token = token; showApp(); fetchOutfit();
  } catch { $("#lock-error").hidden = false; }
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
  const rows = { top: document.createElement("div"), bottom: document.createElement("div") };
  rows.top.className = rows.bottom.className = "look-row";
  let any = false;
  (pieces || []).forEach((p) => {
    if (!p.url) return; any = true;
    const fig = document.createElement("figure");
    fig.className = "look-item cat-" + (p.category || "other");
    fig.innerHTML = `<img src="${p.url}" alt=""><figcaption>${p.name || ""}</figcaption>`;
    fig.onclick = () => openReason(p.name);
    (TOP_ROW.has(p.category) ? rows.top : rows.bottom).appendChild(fig);
  });
  if (rows.top.children.length) look.appendChild(rows.top);
  if (rows.bottom.children.length) look.appendChild(rows.bottom);
  $("#look-hint").hidden = !any;
}

async function fetchOutfit() {
  loading(true);
  try {
    const r = await api("/api/outfit", { prefs: store.prefs, day });
    activeOccasion = r.occasion || activeOccasion; renderOccasions();
    $("#headline").textContent = r.headline || "";
    $("#reason").textContent = r.reason || "";
    $("#weather").textContent = (r.weather && r.weather.summary) || "";
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

function openReason(name) {
  $("#reason-title").textContent = "Swap: " + name;
  const wrap = $("#reason-chips"); wrap.innerHTML = "";
  REASONS.forEach((reason) => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = reason;
    b.onclick = () => { day.rejections.push({ item: name, reason }); $("#reason-modal").hidden = true; fetchOutfit(); };
    wrap.appendChild(b);
  });
  $("#reason-modal").hidden = false;
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
        cell.className = "pick";
        cell.innerHTML = `<img src="${i.url}" alt=""><span>${i.name || ""}</span>`;
        cell.onclick = () => { day.anchor = i.id; $("#picker").hidden = true; fetchOutfit(); };
        grid.appendChild(cell);
      });
      groups.appendChild(grid);
    });
  } catch { groups.innerHTML = "Couldn't load wardrobe."; }
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
  $("#reason-close").onclick = () => { $("#reason-modal").hidden = true; };
  $("#plan-btn").onclick = () => { $("#plan").hidden = !$("#plan").hidden; };
  $("#plan-apply").onclick = applyPlan;
  $("#settings-btn").onclick = () => { loadSettings(); $("#settings").hidden = false; };
  $("#settings-close").onclick = () => { $("#settings").hidden = true; };
  $("#settings-save").onclick = saveSettings;
}

function init() {
  bind(); renderOccasions();
  if (store.token) { showApp(); fetchOutfit(); } else { showLock(); }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
}
init();
