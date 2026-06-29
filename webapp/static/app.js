"use strict";

const $ = (s) => document.querySelector(s);
const TOP_ROW = new Set(["outerwear", "midlayer", "top", "blouse", "knit", "cardigan", "dress"]);
const OCCASIONS = ["Casual", "Work", "Dressy", "Going out", "Cozy home"];

const store = {
  get token() { return localStorage.getItem("wc.token"); },
  set token(v) { v ? localStorage.setItem("wc.token", v) : localStorage.removeItem("wc.token"); },
  get prefs() { try { return JSON.parse(localStorage.getItem("wc.prefs")) || {}; } catch { return {}; } },
  set prefs(v) { localStorage.setItem("wc.prefs", JSON.stringify(v)); },
};

let day = { occasion: "Casual", temp_nudge: null, anchor: null, wish: "" };

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
    store.token = token;
    showApp();
    fetchOutfit();
  } catch {
    $("#lock-error").hidden = false;
  }
}

function renderOccasions() {
  const wrap = $("#occasions");
  wrap.innerHTML = "";
  OCCASIONS.forEach((o) => {
    const b = document.createElement("button");
    b.className = "chip" + (o === day.occasion ? " on" : "");
    b.textContent = o;
    b.onclick = () => { day.occasion = o; renderOccasions(); fetchOutfit(); };
    wrap.appendChild(b);
  });
}

function renderLook(pieces) {
  const look = $("#look");
  look.innerHTML = "";
  const rows = { top: document.createElement("div"), bottom: document.createElement("div") };
  rows.top.className = "look-row";
  rows.bottom.className = "look-row";
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

async function fetchOutfit() {
  loading(true);
  try {
    const r = await api("/api/outfit", { prefs: store.prefs, day });
    $("#headline").textContent = r.headline || "";
    $("#reason").textContent = r.reason || "";
    $("#weather").textContent = (r.weather && r.weather.summary) || "";
    $("#date").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
    renderLook(r.pieces);
  } catch (e) {
    if (e.message !== "locked") $("#reason").textContent = "Couldn't load — try again.";
  } finally {
    loading(false);
  }
}

async function openPicker() {
  const grid = $("#picker-grid");
  grid.innerHTML = "Loading…";
  $("#picker").hidden = false;
  try {
    const items = await api("/api/wardrobe");
    grid.innerHTML = "";
    items.filter((i) => i.url).forEach((i) => {
      const cell = document.createElement("button");
      cell.className = "pick";
      cell.innerHTML = `<img src="${i.url}" alt=""><span>${i.name || ""}</span>`;
      cell.onclick = () => { day.anchor = i.id; $("#picker").hidden = true; fetchOutfit(); };
      grid.appendChild(cell);
    });
  } catch { grid.innerHTML = "Couldn't load wardrobe."; }
}

function loadSettings() {
  const p = store.prefs;
  $("#runs-cold").checked = !!p.runs_cold;
  $("#style-notes").value = p.style_notes || "";
  $("#love-colors").value = (p.love_colors || []).join(", ");
  $("#avoid-colors").value = (p.avoid_colors || []).join(", ");
}

function saveSettings() {
  const split = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);
  store.prefs = {
    runs_cold: $("#runs-cold").checked,
    style_notes: $("#style-notes").value.trim(),
    love_colors: split($("#love-colors").value),
    avoid_colors: split($("#avoid-colors").value),
  };
  $("#settings").hidden = true;
  fetchOutfit();
}

function bind() {
  $("#unlock").onclick = unlock;
  $("#pin").addEventListener("keydown", (e) => { if (e.key === "Enter") unlock(); });
  $("#regen").onclick = () => { day.wish = $("#wish").value.trim(); fetchOutfit(); };
  $("#wish").addEventListener("keydown", (e) => { if (e.key === "Enter") { day.wish = $("#wish").value.trim(); fetchOutfit(); } });
  document.querySelectorAll("[data-nudge]").forEach((b) => {
    b.onclick = () => {
      day.temp_nudge = day.temp_nudge === b.dataset.nudge ? null : b.dataset.nudge;
      document.querySelectorAll("[data-nudge]").forEach((x) => x.classList.toggle("on", x.dataset.nudge === day.temp_nudge));
      fetchOutfit();
    };
  });
  $("#anchor-btn").onclick = openPicker;
  $("#picker-close").onclick = () => { $("#picker").hidden = true; };
  $("#settings-btn").onclick = () => { loadSettings(); $("#settings").hidden = false; };
  $("#settings-close").onclick = () => { $("#settings").hidden = true; };
  $("#settings-save").onclick = saveSettings;
}

function init() {
  bind();
  renderOccasions();
  if (store.token) { showApp(); fetchOutfit(); } else { showLock(); }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
}

init();
