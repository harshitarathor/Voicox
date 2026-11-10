/* Shared state and helpers: translate, format, call the API, draw charts and tables. */
/* ============ helpers ============ */
const $ = s => document.querySelector(s);
let LANG = localStorage.getItem("vx_lang"); if (!T[LANG]) LANG = "en";
let THEME = localStorage.getItem("vx_theme") || "dark";
let LIVE = false, TODAY = null, VOICE = false, BENCH = null, LAST = null;   // LAST: the last answer, kept when language or theme changes
const t = (k, ...a) => { const v = T[LANG][k] ?? T.en[k] ?? k; return typeof v === "function" ? v(...a) : v; };
const kl = k => T[LANG]["k_" + k] ?? T.en["k_" + k] ?? k.replace(/_/g, " ");
const pn = p => (PN[LANG] && PN[LANG][p]) || p;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = n => Number(n).toLocaleString("en-IN", {maximumFractionDigits: 2});
const inr = n => "₹" + fmt(Math.round(n));
const cv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pct = x => (typeof x === "number" ? Math.round(x * 100) : null);
const PAGEKEYS = ["ask", "sales", "stock", "detective", "data", "quality"];
const PAGES = () => ["ask", "sales", "stock", "detective", "data"].concat(BENCH && BENCH.available ? ["quality"] : []);
const ICON = {
  cart:'<svg viewBox="0 0 24 24"><path d="M3 4h2l2.4 11h10.2L20 7H6.2"/><circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/></svg>',
  box:'<svg viewBox="0 0 24 24"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/></svg>',
  warn:'<svg viewBox="0 0 24 24"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18v.4"/></svg>',
  down:'<svg viewBox="0 0 24 24"><path d="M12 4v13M6 12l6 6 6-6"/></svg>'};
const SEND = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/></svg>';
const NAVIC = {sales:"M4 20V10M10 20V4M16 20v-7M22 20H2",stock:"M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",ask:"M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",detective:"M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5",data:"M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",quality:"M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4"};
const spark = (ys, c) => { if (!ys || ys.length < 2) return ""; const mn = Math.min(...ys), mx = Math.max(...ys), r = (mx - mn) || 1;
  return `<svg class="sp" viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true"><polyline points="${ys.map((y, i) => `${(i * 100 / (ys.length - 1)).toFixed(1)},${(36 - (y - mn) / r * 32).toFixed(1)}`).join(" ")}"/></svg>`; };
const chg = x => (typeof x === "number" && isFinite(x)) ? `<i class="${x >= 0 ? "up" : "dn"}">${esc(t("wk", x))}</i>` : "";
const MIC = '<svg viewBox="0 0 24 24"><path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-6a3.5 3.5 0 0 0-7 0v6A3.5 3.5 0 0 0 12 15Zm6-3.5a1 1 0 1 0-2 0 4 4 0 0 1-8 0 1 1 0 1 0-2 0 6 6 0 0 0 5 5.91V20H9a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.59A6 6 0 0 0 18 11.5Z"/></svg>';

/* Any answer from the backend is JSON, including its error messages. null = could not reach it. */
/* Every call carries the chosen language (en, hi or hn), so the answer is written in it, not only the labels. */
async function api(path, body) {
  try {
    if (!body && path.startsWith("/") && /^\/(stock-gaps|low-stock)/.test(path)) path += (path.includes("?") ? "&" : "?") + "lang=" + LANG;
    if (body && path === "/ask") body = {lang: LANG, ...body};
    const r = await fetch(path, body ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)} : undefined);
    try { return await r.json(); } catch (e) { return null; }
  } catch (e) { return null; }
}
function plot(id, x, y, line) {
  if (typeof Plotly === "undefined" || !$("#" + id)) return;
  const neg = !line && y.some(v => v < 0);
  const trace = {x, y, type: line ? "scatter" : "bar", mode: line ? "lines" : undefined,
    marker:{color: line ? cv("--gold") : y.map(v => v < 0 ? cv("--red") : cv("--gold"))}, line:{color:cv("--gold"), width:3},
    fill: line ? "tozeroy" : undefined, fillcolor:"rgba(246,183,60,.12)"};
  if (!line) { trace.text = y.map(v => String(v)); trace.textposition = "outside"; trace.cliponaxis = false; trace.textfont = {color: cv("--text")}; }
  const lay = {margin:{t:line ? 6 : 28, r:8, b:44, l:52}, paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(0,0,0,0)", font:{family:"Mukta,sans-serif", color:cv("--mute")},
    xaxis:{gridcolor:cv("--line")}, yaxis:{gridcolor:cv("--line"), zerolinecolor:cv("--mute")}};
  if (line && id !== "tr") lay.height = 360;
  if (!line) { lay.height = y.length === 1 ? 230 : 320; lay.bargap = 0.6; if (y.length <= 2) trace.width = y.length === 1 ? 0.14 : 0.22; if (neg) lay.yaxis.range = [Math.min(...y) * 1.2, 0]; }
  if (lay.height) $("#" + id).style.height = lay.height + "px";   // fixed box, so a window resize can never stretch the chart back to the default 450px
  Plotly.newPlot(id, [trace], lay, {responsive:true, displayModeBar:false});
}
const tbl = rows => { const c = Object.keys(rows[0]), num = k => typeof rows[0][k] === "number";
  return `<div class="sc2"><table><tr>${c.map(k => `<th class="${num(k)?"n":""}">${esc(kl(k))}</th>`).join("")}</tr>` +
    rows.map(r => `<tr>${c.map(k => `<td class="${num(k)?"n":""}">${esc(num(k) ? fmt(r[k]) : (k === "label" || k === "product" ? pn(r[k]) : r[k]))}</td>`).join("")}</tr>`).join("") + "</table></div>"; };
/* number tiles: `display` is the ready-made figure (e.g. ₹4,20,000) and is shown once, never as a second tile */
const tiles = n => { if (!n) return "";
  if (n.display) return `<div class="tiles"><div class="tile"><small>${esc(t("m_" + n.metric))}${n.period ? " · " + esc(t("p_" + n.period)) : ""}</small><strong>${esc(n.display)}</strong></div></div>`;
  const a = Object.entries(n).filter(([k, v]) => v !== null && typeof v !== "object" && !/^(metric|period.*|display)$/.test(k));
  return a.length ? `<div class="tiles">${a.map(([k, v]) => `<div class="tile ${/gap|change/.test(k) && v < 0 ? "neg" : ""}"><small>${esc(kl(k))}</small><strong>${esc(k === "product" ? pn(v) : typeof v === "number" ? fmt(v) : v)}</strong></div>`).join("")}</div>` : ""; };
const causes = (cs, disc) => `<div class="card"><h3>${esc(t("causes"))}</h3>${cs.map((c, i) => { const p = Math.round(c.score * 100);
  return `<div class="cz"><div class="rk">${i+1}</div><div><b>${esc(c.headline)}</b></div><div class="sc">${p}%</div><div class="bd"><div class="mt"><i data-w="${p}"></i></div><p>${esc(c.detail)}</p><p class="nx"><b>${esc(t("next"))}</b>${esc(c.check_next)}</p></div></div>`; }).join("")}` + (disc ? `<p class="note">${esc(disc)}</p>` : "") + "</div>";
const fill = () => requestAnimationFrame(() => requestAnimationFrame(() => document.querySelectorAll(".mt i").forEach(i => i.style.width = i.dataset.w + "%")));
/* Trust Mode: what the app understood, in plain words, before the answer */
const understood = q => { if (!q) return ""; const c = [t("i_" + q.intent)];
  if (q.period && q.intent !== "low_stock" && q.intent !== "stock_gap" && q.intent !== "explain_gap") c.push(t("p_" + q.period));
  if (q.compare_period) c.push("vs " + t("p_" + q.compare_period));
  if (["total", "ranked", "trend", "compare"].includes(q.intent) && q.metric) c.push(t("m_" + q.metric));
  if (q.intent === "ranked") c.push((q.order === "asc" ? "↑ " : "↓ ") + "Top " + q.limit);
  if (q.product) c.push(pn(q.product)); if (q.category) c.push(q.category);
  return `<p class="und">${esc(t("und"))} ${c.map(x => `<span class="c">${esc(x)}</span>`).join("")}</p>`; };
