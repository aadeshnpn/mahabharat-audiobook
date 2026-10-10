// Mahabharata character mapper — vanilla JS + Cytoscape.js
const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (method, url, body, isForm) => {
  const opt = { method, headers: {} };
  if (body !== undefined) { if (isForm) opt.body = body; else { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); } }
  const r = await fetch(url, opt); const t = await r.text(); let d; try { d = JSON.parse(t); } catch { d = t; }
  if (!r.ok) { const msg = (d && d.detail) ? (typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail)) : r.statusText; toast("Error: " + msg); throw new Error(msg); }
  return d;
};
const toast = (m) => { const t = $("#toast"); t.textContent = m; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2600); };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const KIND_COLORS = { human: "#c17a3a", sage: "#f08c00", deity: "#e8b500", celestial: "#1098ad", naga: "#2f9e44", asura: "#862e9c", rakshasa: "#a61e4d", bird: "#74b816", animal: "#5c940d", chorus: "#868e96" };
let META, cy, chars = [], current = null, hiddenTypes = new Set(), pollTimer = null;

async function init() {
  META = await api("GET", "/api/meta");
  const typeOpts = Object.entries(META.relationship_types).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join("");
  $$("select[name=type]").forEach(s => s.innerHTML = typeOpts);
  $("#kinds").innerHTML = META.kinds.map(k => `<option value="${k}">`).join("");
  $("#kindFilter").innerHTML = `<option value="">All kinds</option>` + META.kinds.map(k => `<option>${k}</option>`).join("");
  buildLegend(); buildGraph(); await refresh();
  if (!META.voice_generation.available) { $("#btnGen").disabled = true; $("#btnGen").title = "VoxCPM2 environment not found"; }
  const h = location.hash.slice(1); if (h) select(h);
}

function buildLegend() {
  const rel = Object.entries(META.relationship_types).map(([k, v]) =>
    `<label><input type="checkbox" data-type="${k}" checked><span class="sw" style="background:${v.color}"></span>${v.label}</label>`).join("");
  const kinds = Object.entries(KIND_COLORS).map(([k, c]) => `<label title="node kind"><span class="kind" style="background:${c}"></span>${k}</label>`).join("");
  $("#legend").innerHTML = rel + `<span style="width:16px"></span>` + kinds + `<label title="has reference voice clip"><span class="kind" style="border:3px solid #111;background:#fff"></span>has voice</label>`;
  $$("#legend input[data-type]").forEach(cb => cb.onchange = () => { cb.checked ? hiddenTypes.delete(cb.dataset.type) : hiddenTypes.add(cb.dataset.type); applyFilters(); });
}

function buildGraph() {
  cy = cytoscape({
    container: $("#cy"), wheelSensitivity: 0.25, minZoom: 0.15, maxZoom: 3,
    style: [
      { selector: "node", style: { "label": "data(label)", "font-size": 11, "text-valign": "bottom", "text-margin-y": 3, "color": "#2b2118",
          "text-outline-color": "#faf7f0", "text-outline-width": 2, "background-color": (n) => KIND_COLORS[n.data("kind")] || "#adb5bd",
          "width": (n) => 14 + 5 * Math.log2(1 + (n.data("mentions") || 0)), "height": (n) => 14 + 5 * Math.log2(1 + (n.data("mentions") || 0)),
          "shape": (n) => n.data("gender") === "female" ? "diamond" : (["generic", "chorus"].includes(n.data("kind")) ? "hexagon" : "ellipse"),
          "border-width": (n) => n.data("has_voice") ? 3 : 0, "border-color": "#111" } },
      { selector: "edge", style: { "width": 1.6, "line-color": "data(color)", "target-arrow-color": "data(color)", "curve-style": "bezier",
          "target-arrow-shape": (e) => e.data("directed") ? "triangle" : "none", "arrow-scale": 0.8, "opacity": 0.75 } },
      { selector: "edge[type = 'spouse_of']", style: { "line-style": "dashed" } },
      { selector: "edge[type = 'enemy_of']", style: { "width": 2.2 } },
      { selector: ".faded", style: { "opacity": 0.12 } },
      { selector: "node:selected", style: { "border-width": 4, "border-color": "#b5651d" } },
      { selector: "edge.hl", style: { "label": "data(label)", "font-size": 9, "text-rotation": "autorotate", "text-background-color": "#fff", "text-background-opacity": .8, "opacity": 1, "width": 2.6 } },
    ],
  });
  cy.on("tap", "node", (e) => select(e.target.id()));
  cy.on("tap", (e) => { if (e.target === cy) { cy.elements().removeClass("faded hl"); } });
}

async function refresh(relayout = true) {
  chars = await api("GET", "/api/characters");
  $("#charList").innerHTML = chars.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  const g = await api("GET", "/api/graph");
  const pos = {}; cy.nodes().forEach(n => pos[n.id()] = n.position());
  cy.elements().remove(); cy.add([...g.nodes, ...g.edges]);
  const known = Object.keys(pos).length && cy.nodes().every(n => pos[n.id()]);
  if (!relayout && known) cy.nodes().forEach(n => n.position(pos[n.id()])); else runLayout();
  applyFilters(); renderTable(); renderStats(g);
  if (current) cy.$id(current).select();
}
function runLayout() { cy.layout({ name: "cose", animate: false, nodeRepulsion: 9000, idealEdgeLength: 70, gravity: 0.35, numIter: 2500, randomize: true }).run(); }

function applyFilters() {
  const q = $("#search").value.trim().toLowerCase(), kind = $("#kindFilter").value;
  cy.edges().forEach(e => e.style("display", hiddenTypes.has(e.data("type")) ? "none" : "element"));
  cy.nodes().forEach(n => {
    const c = chars.find(x => x.id === n.id()); if (!c) return;
    const m = (!kind || c.kind === kind) && (!q || c.name.toLowerCase().includes(q) || c.aliases.some(a => a.toLowerCase().includes(q)) || c.role.toLowerCase().includes(q));
    n.style("display", m ? "element" : "none");
  });
  renderTable();
}

function renderStats(g) {
  const voiced = chars.filter(c => c.voice_clip).length, prov = chars.filter(c => c.provisional).length;
  const byProv = {}; chars.forEach(c => byProv[c.provenance || "hand"] = (byProv[c.provenance || "hand"] || 0) + 1);
  const spk = chars.filter(c => c.speaking_lines > 0).length;
  $("#stats").innerHTML = `<p><b>${chars.length}</b> characters (<b>${spk}</b> speaking) · <b>${g.edges.length}</b> relationships · <b>${voiced}</b> with voice clips · <b>${prov}</b> provisional</p>
  <p class="note">Provenance: ${Object.entries(byProv).map(([k, v]) => `${esc(k)} ${v}`).join(" · ")}</p>
  <p class="note">Node size ∝ log(mentions in Book 1). ◆ = female, ● = male, ⬢ = chorus / group voice. Black ring = has a reference voice.</p>`;
}

let sortKey = "mentions", sortDir = -1;
function renderTable() {
  if ($("#table").hidden) return;
  const q = $("#search").value.trim().toLowerCase(), kind = $("#kindFilter").value;
  const rows = chars.filter(c => (!kind || c.kind === kind) && (!q || c.name.toLowerCase().includes(q) || c.aliases.some(a => a.toLowerCase().includes(q))))
    .sort((a, b) => ((a[sortKey] > b[sortKey]) ? 1 : (a[sortKey] < b[sortKey]) ? -1 : 0) * sortDir);
  const cols = [["name", "Name"], ["kind", "Kind"], ["gender", "Gender"], ["role", "Role"], ["mentions", "Mentions"], ["speaking_lines", "Speech turns"], ["first_section", "First §"], ["provenance", "Provenance"], ["voice_clip", "Voice"]];
  $("#table").innerHTML = `<table><thead><tr>${cols.map(([k, l]) => `<th data-k="${k}">${l}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead><tbody>${rows.map(c => `<tr data-id="${c.id}"><td><b>${esc(c.name)}</b><br><small>${esc(c.respelling)}</small></td><td>${c.kind}${c.kind_detail ? `<br><small>${esc(c.kind_detail)}</small>` : ""}</td><td>${c.gender}</td><td>${esc(c.role)}</td><td>${c.mentions}</td><td>${c.speaking_lines}</td><td>${c.first_section ?? ""}</td><td>${esc(c.provenance || "")}</td><td>${c.voice_clip ? "🔊" : ""}</td></tr>`).join("")}</tbody></table>`;
  $$("#table th").forEach(th => th.onclick = () => { const k = th.dataset.k; sortDir = sortKey === k ? -sortDir : -1; sortKey = k; renderTable(); });
  $$("#table tr[data-id]").forEach(tr => tr.onclick = () => select(tr.dataset.id));
}

const LIST_FIELDS = ["aliases", "personality", "emotional_range"], NUM_LIST = ["key_sections", "sections"];
async function select(id) {
  let c; try { c = await api("GET", "/api/characters/" + encodeURIComponent(id)); } catch { return; }
  current = id; location.hash = id; $("#empty").hidden = true; $("#detail").hidden = false;
  $("#dName").textContent = c.name;
  $("#dBadges").innerHTML = `<span class="badge">${esc(c.kind)}${c.kind_detail ? " · " + esc(c.kind_detail) : ""}</span><span class="badge" title="provenance">${esc(c.provenance || "hand")}</span>${(c.flags || []).map(f => `<span class="badge warn">${esc(f.replace(/_/g, " "))}</span>`).join("")}${c.provisional ? '<span class="badge warn">provisional</span>' : ""}${c.voice_clip ? '<span class="badge ok">voice</span>' : ""}`;
  const f = $("#fProfile");
  for (const el of f.elements) {
    if (!el.name) continue; const v = c[el.name];
    if (el.type === "checkbox") el.checked = !!v;
    else if (LIST_FIELDS.includes(el.name) || NUM_LIST.includes(el.name)) el.value = (v || []).join(", ");
    else el.value = v ?? "";
  }
  const sbs = Object.entries(c.speech_by_section || {}).map(([s, n]) => `§${s}×${n}`).join(" ");
  $("#dSource").textContent = [c.source, c.narrative_sections && c.narrative_sections.length && (`Narrative sections: ${c.narrative_sections.length}`), sbs && ("Speech turns by section: " + sbs), c.count_notes && ("Count note: " + c.count_notes)].filter(Boolean).join(" · ");
  renderVoice(c); renderRels(c);
  cy.elements().removeClass("faded hl"); const n = cy.$id(id);
  if (n.nonempty()) { cy.$(":selected").unselect(); n.select(); const nb = n.closedNeighborhood(); cy.elements().not(nb).addClass("faded"); n.connectedEdges().addClass("hl"); cy.animate({ center: { eles: n }, duration: 250 }); }
}

function renderVoice(c) {
  $("#vClip").innerHTML = c.voice_clip ? `<audio controls preload="none" src="/${c.voice_clip}?t=${Date.now()}"></audio><div class="note">${esc(c.voice_clip)} · ${esc(c.voice_engine)}</div>` : `<p class="note">No reference clip yet.</p>`;
  $("#vPrompt").value = c.voice_prompt || c.voice_brief || ""; $("#vLine").value = c.sample_line || "";
  const grp = c.voice_group ? chars.find(x => x.id === c.voice_group) : null;
  $("#vNotes").innerHTML = (c.voice_group ? `<p class="note">Shares the group voice of <a data-go-voice="${esc(c.voice_group)}">${esc(grp ? grp.name : c.voice_group)}</a>${grp && grp.voice_clip ? ` · <audio controls preload="none" src="/${grp.voice_clip}"></audio>` : " (no clip yet)"}</p>` : "") + esc(c.voice_notes || "");
  $$("#vNotes a[data-go-voice]").forEach(a => a.onclick = () => select(a.dataset.goVoice));
  loadCands(); loadJobs();
}
async function loadCands() {
  const cands = await api("GET", `/api/characters/${current}/voice/candidates`);
  $("#vCands").innerHTML = cands.length ? cands.map(p => `<div class="cand"><span title="${p}">${p.split("/").pop()}</span><audio controls preload="none" src="/${p}"></audio><button data-p="${p}">Use</button></div>`).join("") : `<p class="note">No candidates. Generate one or attach a clip.</p>`;
  $$("#vCands button").forEach(b => b.onclick = async () => { await api("POST", `/api/characters/${current}/voice/select`, { file: b.dataset.p, prompt: $("#vPrompt").value }); toast("Reference voice updated"); await refresh(false); select(current); });
}
async function loadJobs() {
  const jobs = await api("GET", `/api/jobs?character=${current}`);
  $("#vJobs").innerHTML = jobs.length ? jobs.slice(0, 6).map(j => `<div class="job ${j.status}">#${j.id} ${j.status} · ${new Date(j.created * 1000).toLocaleTimeString()}${j.output ? " · " + esc(j.output) : ""}${j.log ? `<details><summary>log</summary><pre>${esc(j.log.slice(-800))}</pre></details>` : ""}</div>`).join("") : `<p class="note">No jobs.</p>`;
  const active = jobs.some(j => j.status === "queued" || j.status === "running");
  clearTimeout(pollTimer); if (active) pollTimer = setTimeout(() => { loadJobs(); loadCands(); }, 4000);
}

function renderRels(c) {
  const name = (id) => (chars.find(x => x.id === id) || { name: id }).name;
  $("#relBody").innerHTML = c.relationships.map(r => {
    const t = META.relationship_types[r.type] || { label: r.type, color: "#999" }; const out = r.source === c.id; const other = out ? r.target : r.source;
    const lab = t.directed ? (out ? t.label : `← ${t.label}`) : t.label;
    return `<tr><td><span class="badge" style="background:${t.color}22;color:${t.color}">${lab}</span>${r.provisional ? ' <small title="provisional">?</small>' : ""}</td><td><a data-go="${other}">${esc(name(other))}</a></td><td title="${esc(r.notes || "")}">${r.section ? "§" + r.section : ""}</td><td><button data-del="${r.id}" class="danger subtle" title="delete">✕</button></td></tr>`;
  }).join("") || `<tr><td colspan=4 class="note">No relationships.</td></tr>`;
  $$("#relBody a[data-go]").forEach(a => a.onclick = () => select(a.dataset.go));
  $$("#relBody button[data-del]").forEach(b => b.onclick = async () => { if (!confirm("Delete this relationship?")) return; await api("DELETE", "/api/relationships/" + b.dataset.del); toast("Relationship deleted"); await refresh(false); select(current); });
}

// ---- events ----
$$(".tabs button").forEach(b => b.onclick = () => { $$(".tabs button").forEach(x => x.classList.toggle("on", x === b)); $$(".tab").forEach(t => t.hidden = t.dataset.tab !== b.dataset.tab); });
$("#search").oninput = applyFilters; $("#kindFilter").onchange = applyFilters; $("#btnLayout").onclick = runLayout;
$("#btnView").onclick = () => { const t = $("#table"); t.hidden = !t.hidden; $("#btnView").textContent = t.hidden ? "☰ Table" : "◎ Graph"; renderTable(); if (t.hidden) cy.resize(); };
$("#fProfile").onsubmit = async (e) => {
  e.preventDefault(); const f = e.target, patch = {};
  for (const el of f.elements) {
    if (!el.name || el.disabled) continue;
    if (el.type === "checkbox") patch[el.name] = el.checked;
    else if (LIST_FIELDS.includes(el.name)) patch[el.name] = el.value.split(",").map(s => s.trim()).filter(Boolean);
    else if (NUM_LIST.includes(el.name)) patch[el.name] = el.value.split(/[ ,]+/).map(Number).filter(n => Number.isInteger(n) && n > 0);
    else if (el.type === "number") patch[el.name] = el.value === "" ? null : Number(el.value);
    else patch[el.name] = el.value;
  }
  const cur = chars.find(x => x.id === current);
  if (cur && cur.provenance === "text-extracted") patch.provenance = "text-extracted+hand-edited";
  await api("PATCH", "/api/characters/" + current, patch); toast("Saved"); await refresh(false); select(current);
};
$("#btnDelete").onclick = async () => {
  if (!confirm(`Delete ${current} and all of its relationships? (voice files are kept)`)) return;
  await api("DELETE", "/api/characters/" + current); toast("Deleted " + current); current = null; location.hash = "";
  $("#detail").hidden = true; $("#empty").hidden = false; await refresh(false);
};
$("#btnNew").onclick = () => $("#dlgNew").showModal();
$("#fNew").onsubmit = async (e) => {
  if (e.submitter && e.submitter.value === "cancel") return;
  const fd = Object.fromEntries(new FormData(e.target)); const c = await api("POST", "/api/characters", { ...fd, source: "manual (web UI)" });
  e.target.reset(); toast("Created " + c.id); await refresh(false); select(c.id);
};
$("#btnRel").onclick = () => { const f = $("#fRel"); if (current) f.source.value = current; $("#dlgRel").showModal(); };
$("#fRel").onsubmit = async (e) => {
  if (e.submitter && e.submitter.value === "cancel") return;
  const fd = Object.fromEntries(new FormData(e.target)); await api("POST", "/api/relationships", fd);
  e.target.reset(); toast("Relationship added"); await refresh(false); if (current) select(current);
};
$("#fRelInline").onsubmit = async (e) => {
  e.preventDefault(); const fd = Object.fromEntries(new FormData(e.target));
  const body = fd.dir === "out" ? { source: current, target: fd.other, type: fd.type } : { source: fd.other, target: current, type: fd.type };
  await api("POST", "/api/relationships", body); e.target.other.value = ""; toast("Relationship added"); await refresh(false); select(current);
};
$("#voiceFile").onchange = async (e) => {
  const file = e.target.files[0]; if (!file) return; const fd = new FormData(); fd.append("file", file);
  await api("POST", `/api/characters/${current}/voice`, fd, true); e.target.value = ""; toast("Voice clip attached"); await refresh(false); select(current);
};
$("#btnRemoveVoice").onclick = async () => { if (!confirm("Detach the reference clip? (file is kept on disk)")) return; await api("DELETE", `/api/characters/${current}/voice`); await refresh(false); select(current); };
$("#btnSaveVoice").onclick = async () => { await api("PATCH", "/api/characters/" + current, { voice_prompt: $("#vPrompt").value, sample_line: $("#vLine").value }); toast("Voice prompt saved"); };
$("#btnGen").onclick = async () => {
  const j = await api("POST", `/api/characters/${current}/voice/generate`, { prompt: $("#vPrompt").value, text: $("#vLine").value });
  toast(`Job #${j.id} queued (≈1–2 min on CPU incl. model load)`); loadJobs();
};
$("#importFile").onchange = async (e) => {
  const file = e.target.files[0]; if (!file) return; const data = JSON.parse(await file.text());
  const r = await api("POST", "/api/import?mode=merge", data); toast(`Imported ${r.characters} characters, ${r.relationships} relationships`); e.target.value = ""; refresh();
};
$("#btnSaveExport").onclick = async () => { const r = await api("GET", "/api/export?save=true"); toast("Saved " + r.saved_to); };
$("#btnReseed").onclick = async () => { const r = await api("POST", "/api/import/seed?mode=merge"); toast(`Seed merged: ${r.characters} characters`); refresh(); };
init();
