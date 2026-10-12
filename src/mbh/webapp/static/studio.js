// Episode Studio. Every action is a REST call; nothing here is UI-only.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const toast = (m) => { const t = $("#toast"); t.textContent = m; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2800); };
const fmt = (s) => { if (s == null || s === "") return "—"; const n = Number(s); const m = Math.floor(n / 60); const sec = Math.round(n % 60); return m ? `${m} min ${sec} s` : `${sec} s`; };

async function api(method, url, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(url, opt);
  const t = await r.text();
  let data; try { data = JSON.parse(t); } catch { data = t; }
  if (!r.ok) {
    const msg = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : r.statusText;
    toast(msg); throw new Error(msg);
  }
  return data;
}

let META = null, CAST = [], poll = null;
async function boot() {
  META = await api("GET", "/api/studio/meta");
  CAST = await api("GET", "/api/studio/cast");
  window.addEventListener("hashchange", draw);
  draw();
  setInterval(refreshPill, 2000);
  refreshPill();
}

function route() {
  const path = location.hash.replace(/^#\/?/, "").split("?")[0];
  const parts = path.split("/").filter(Boolean);
  if (!parts.length || parts[0] === "episodes") return { name: "episodes" };
  if (parts[0] === "new") return { name: "new" };
  if (parts[0] === "lexicon") return { name: "lexicon" };
  if (parts[0] === "voices") return { name: "voices", id: parts[1] || "" };
  if (parts[0] === "jobs") return { name: "jobs" };
  if (parts[0] === "e" && parts[1]) return { name: parts[2] === "play" ? "play" : "script", id: decodeURIComponent(parts[1]) };
  return { name: "episodes" };
}

function draw() {
  const r = route();
  $$("#subnav a").forEach((a) => a.classList.toggle("on", a.dataset.route === (r.name === "script" || r.name === "play" ? "episodes" : r.name)));
  const view = { episodes: viewEpisodes, "new": viewNew, script: viewScript, play: viewPlay, lexicon: viewLexicon, voices: viewVoices, jobs: viewJobs }[r.name];
  view(r);
}

async function refreshPill() {
  try {
    const jobs = await api("GET", "/api/jobs?limit=20");
    const active = jobs.filter((j) => j.status === "queued" || j.status === "running");
    const pill = $("#jobpill");
    pill.textContent = active.length ? `${active.length} job${active.length > 1 ? "s" : ""} · ${active[0].kind}` : "queue idle";
  } catch { /* pill is decorative */ }
}

function speakerOptions(selected) {
  const ids = new Set(CAST.map((c) => c.id));
  const extra = selected && !ids.has(selected) ? `<option value="${esc(selected)}">${esc(selected)}</option>` : "";
  return extra + CAST.map((c) => `<option value="${esc(c.id)}" ${c.id === selected ? "selected" : ""}>${esc(c.name)}</option>`).join("");
}
function emotionOptions(selected) {
  return META.emotions.map((e) => `<option ${e === selected ? "selected" : ""}>${esc(e)}</option>`).join("");
}
function paceOptions(selected) {
  return META.paces.map((e) => `<option ${e === selected ? "selected" : ""}>${esc(e)}</option>`).join("");
}
function cueOptions(selected) {
  const cues = META.music.cues.map((c) => c.id);
  const cur = selected || "";
  return `<option value="" ${cur === "" ? "selected" : ""}>automatic</option>` +
    cues.map((c) => `<option value="${esc(c)}" ${c === cur ? "selected" : ""}>${esc(c)}</option>`).join("");
}

async function viewEpisodes() {
  const rows = await api("GET", "/api/studio/episodes");
  $("#view").innerHTML = `<div class="page-head"><div><h1>Episodes</h1><p class="note">Create a span, review the script, then render. One heavy job at a time.</p></div><a class="primary" href="#/new" style="padding:8px 12px;border-radius:6px;text-decoration:none">New episode</a></div>` +
    (rows.length ? `<div class="cards">${rows.map(card).join("")}</div>` : `<p class="empty">No episodes in this folder yet.</p>`);
}
function card(ep) {
  if (ep.error) return `<div class="card"><h2>${esc(ep.id)}</h2><p>${esc(ep.error)}</p></div>`;
  return `<a class="card" href="#/e/${encodeURIComponent(ep.id)}"><h2>${esc(ep.title)}</h2><p>${esc(ep.id)} · target ${fmt(ep.target_duration_s)}${ep.duration_label ? " · est. " + esc(ep.duration_label) : ""}</p><p>${ep.line_count == null ? "not built" : ep.line_count + " lines"}${ep.non_kmg_lines ? " · " + ep.non_kmg_lines + " non-KMG" : ""} · music ${ep.music ? esc(ep.music_preset || "on") : "off"}</p><p>${ep.has_wav ? "assembled" : ep.has_script ? "script ready" : "draft"}</p></a>`;
}

async function viewNew() {
  const presets = META.music.presets.map((p) => `<option ${p === META.music.preset ? "selected" : ""}>${esc(p)}</option>`).join("");
  $("#view").innerHTML = `<div class="page-head"><h1>New episode</h1></div>
    <form class="studio-form" id="createForm">
      <div class="grid">
        <label>Id<input id="ep-id" required pattern="[a-z][a-z0-9_]*" placeholder="ep02"></label>
        <label>Title<input id="ep-title" required placeholder="Episode 2: …"></label>
        <label>Target minutes<input id="target-min" type="number" min="1" step="1" value="17"></label>
        <label>Music preset<select id="music-preset">${presets}</select></label>
      </div>
      <label class="inline"><input id="music-on" type="checkbox" checked> Mix music under the dialogue</label>
      <h3>Section</h3>
      <div class="grid">
        <label>Section<input id="seg-section" type="number" min="1" value="1"></label>
        <label>From paragraph<input id="seg-start" type="number" min="1" value="1"></label>
        <label>Through paragraph<input id="seg-end" type="number" min="1" value="2"></label>
        <label>Narrator<input id="seg-narrator" value="sauti"></label>
      </div>
      <p class="note" id="section-note"></p>
      <label>Label<input id="seg-label" placeholder="what this span is"></label>
      <h3>Non-KMG bridge <span class="badge warn">flagged</span></h3>
      <p class="bridge-flag">Text here is not in the KMG translation. Every line is stored with non_kmg and kept out of the quoted scripture.</p>
      <label>Bridge text (optional)<textarea id="bridge-text" rows="2" placeholder="Leave empty to skip"></textarea></label>
      <label>Why this ending<textarea id="end-reason" rows="2"></textarea></label>
      <div class="toolbar">
        <button type="button" data-action="estimate">Estimate duration</button>
        <button type="button" data-action="breaks">Suggest endings</button>
        <button class="primary" data-action="create">Create episode</button>
      </div>
      <div id="estimate"></div>
      <div id="breaks"></div>
    </form>`;
  $("#seg-section").onchange = loadSectionNote;
  loadSectionNote();
  $("[data-action=estimate]").onclick = runEstimate;
  $("[data-action=breaks]").onclick = runBreaks;
  $("#createForm").onsubmit = (e) => { e.preventDefault(); createEpisode(); };
}

function draftBody() {
  const segments = [{
    id: "main", kind: "section", section: Number($("#seg-section").value),
    paragraphs: [Number($("#seg-start").value), Number($("#seg-end").value)],
    narrator: $("#seg-narrator").value || "sauti", label: $("#seg-label").value,
  }];
  const bridge = $("#bridge-text").value.trim();
  if (bridge) segments.push({ id: "bridge", kind: "bridge", speaker: $("#seg-narrator").value || "sauti", text: bridge, non_kmg: true });
  return {
    id: $("#ep-id").value.trim() || "draft",
    title: $("#ep-title").value.trim() || "Draft",
    target_duration_s: Number($("#target-min").value) * 60,
    music: $("#music-on").checked,
    music_preset: $("#music-preset").value,
    narrator_default: $("#seg-narrator").value || "sauti",
    strip_glosses: true,
    speech_tags: "keep",
    end_reason: $("#end-reason").value,
    segments,
  };
}
async function loadSectionNote() {
  try {
    const data = await api("GET", "/api/studio/sections/" + $("#seg-section").value);
    $("#section-note").textContent = `§${data.section} ${data.sub_parva || ""} · ${data.paragraphs.length} paragraphs`;
  } catch { $("#section-note").textContent = ""; }
}
async function runEstimate() {
  const data = await api("POST", "/api/studio/estimate", draftBody());
  $("#estimate").innerHTML = `<p><b>${esc(data.duration_label)}</b> estimated · ${data.line_count} lines · target ${fmt(data.target_duration_s)} · ${data.non_kmg_lines} non-KMG</p>` +
    (data.warnings.length ? `<div class="warn-list">${data.warnings.slice(0, 6).map((w) => `<div>${esc(w)}</div>`).join("")}</div>` : "");
}
async function runBreaks() {
  const body = draftBody();
  body.limit = 6;
  const data = await api("POST", "/api/studio/breaks", body);
  const items = data.suggestions || [];
  $("#breaks").innerHTML = items.length ? items.map((s) => `<button type="button" class="break" data-para="${s.paragraph}">¶${s.paragraph} · ${fmt(s.at_s)} (${s.delta_s > 0 ? "+" : ""}${Math.round(s.delta_s)} s) · ${esc((s.reasons || []).join("; "))}<br><small>${esc((s.text || "").slice(0, 140))}</small></button>`).join("") : `<p class="note">No legal break in this span.</p>`;
  $$("#breaks button").forEach((b) => b.onclick = () => { $("#seg-end").value = b.dataset.para; $("#end-reason").value = $("#end-reason").value || `Ends at ¶${b.dataset.para}.`; runEstimate(); });
}
async function createEpisode() {
  const body = draftBody();
  if (!/^[a-z][a-z0-9_]*$/.test(body.id) || body.id === "draft") { toast("Give the episode a lowercase id"); return; }
  const made = await api("POST", "/api/studio/episodes", body);
  toast("Created " + made.id);
  location.hash = "#/e/" + made.id;
}

async function viewScript(r) {
  const data = await api("GET", `/api/studio/episodes/${r.id}/script`);
  const warnings = (data.warnings || []).slice(0, 8);
  $("#view").innerHTML = `<div class="page-head"><div><h1>${esc(data.title)}</h1><p class="note">${esc(data.episode_id)} · ${esc(data.duration_label)} estimated · target ${fmt(data.target_duration_s)} · ${data.non_kmg_lines} non-KMG line${data.non_kmg_lines === 1 ? "" : "s"}</p></div>
    <div class="toolbar"><a href="#/e/${r.id}/play">Play</a><button data-action="render" class="primary">Render</button><button data-action="assemble">Assemble</button><button data-action="qa">QA</button><button data-action="rebuild">Rebuild</button></div></div>
    <div id="jobline" class="note"></div>
    ${warnings.length ? `<div class="warn-list">${warnings.map((w) => `<div>${esc(w)}</div>`).join("")}</div>` : ""}
    <div class="scroll"><table class="lines" id="script-table"><thead><tr><th>Line</th><th>Speaker</th><th>Emotion</th><th>Pace</th><th>Original</th><th>TTS text</th><th>Music</th><th>Take</th><th></th></tr></thead><tbody>
    ${data.lines.map((line) => `<tr data-line="${esc(line.id)}" class="${line.non_kmg ? "nonkmg" : ""}">
      <td>${esc(line.id.split("-").pop())}<br><small>§${line.section ?? "—"} ¶${line.paragraph ?? "—"}</small><br>${line.non_kmg ? '<span class="badge warn">non-KMG</span>' : ""}${(line.flags || []).includes("override") ? '<span class="badge">override</span>' : ""}</td>
      <td><select class="speaker">${speakerOptions(line.speaker)}</select></td>
      <td><select class="emotion">${emotionOptions(line.emotion)}</select></td>
      <td><select class="pace">${paceOptions(line.pace)}</select></td>
      <td class="text">${esc(line.text)}</td>
      <td><textarea class="tts">${esc(line.tts_text)}</textarea></td>
      <td><select class="music">${cueOptions(line.music && typeof line.music === "object" ? line.music.cue : (line.music || ""))}</select><small>${esc(line.cue || "")} · ${esc(line.cue_source || "")}</small></td>
      <td><input class="take" type="number" min="0" value="${line.take || 0}"></td>
      <td><button data-action="save">Save</button>
        ${line.has_audio ? `<audio controls preload="none" src="/api/studio/episodes/${r.id}/lines/${line.id}/audio"></audio>` : ""}
        <button data-action="split">Split</button><button data-action="merge">Merge next</button></td>
    </tr>`).join("")}
    </tbody></table></div>`;
  $("[data-action=render]").onclick = () => enqueue(r.id, "render");
  $("[data-action=assemble]").onclick = () => enqueue(r.id, "assemble");
  $("[data-action=qa]").onclick = () => enqueue(r.id, "qa");
  $("[data-action=rebuild]").onclick = async () => { await api("POST", `/api/studio/episodes/${r.id}/build`); toast("Rebuilt"); draw(); };
  $$("tr[data-line]").forEach((tr) => {
    tr.querySelector("[data-action=save]").onclick = () => saveLine(r.id, tr);
    tr.querySelector("[data-action=split]").onclick = () => openSplit(r.id, tr.dataset.line, tr.querySelector(".text").textContent);
    tr.querySelector("[data-action=merge]").onclick = async () => { await api("POST", `/api/studio/episodes/${r.id}/lines/${tr.dataset.line}/merge`); toast("Merged"); draw(); };
  });
}

async function saveLine(id, tr) {
  const music = tr.querySelector(".music").value;
  const body = {
    speaker: tr.querySelector(".speaker").value,
    emotion: tr.querySelector(".emotion").value,
    pace: tr.querySelector(".pace").value,
    tts_text: tr.querySelector(".tts").value,
    take: Number(tr.querySelector(".take").value || 0),
  };
  if (music) body.music = music; else body.music = null;
  await api("POST", `/api/studio/episodes/${id}/lines/${tr.dataset.line}`, body);
  toast("Saved override");
  draw();
}

let splitEpisode = "", splitLine = "", splitOriginal = "";
function openSplit(id, lineId, text) {
  splitEpisode = id; splitLine = lineId; splitOriginal = text;
  $("#splitParts").innerHTML = "";
  addSplitPart(text);
  $("#splitDlg").showModal();
}
function addSplitPart(text) {
  const wrap = document.createElement("div");
  wrap.className = "seg";
  wrap.innerHTML = `<label>Text<textarea class="part-text" rows="2">${esc(text || "")}</textarea></label><label>Speaker (optional)<input class="part-speaker" placeholder="leave to keep"></label>`;
  $("#splitParts").appendChild(wrap);
}
$("#splitAdd").onclick = () => addSplitPart("");
$("#splitForm").onsubmit = async (e) => {
  if (e.submitter && e.submitter.value === "cancel") return;
  const parts = $$("#splitParts .seg").map((seg) => {
    const part = { text: seg.querySelector(".part-text").value };
    const speaker = seg.querySelector(".part-speaker").value.trim();
    if (speaker) part.speaker = speaker;
    return part;
  });
  await api("POST", `/api/studio/episodes/${splitEpisode}/lines/${splitLine}/split`, { parts });
  toast("Split saved");
  draw();
};

async function enqueue(id, kind) {
  const path = { render: "render", assemble: "assemble", qa: "qa" }[kind];
  const job = await api("POST", `/api/studio/episodes/${id}/${path}`, {});
  toast(`Job #${job.id} queued`);
  watchJob(job.id);
}
function watchJob(id) {
  clearInterval(poll);
  const tick = async () => {
    const job = await api("GET", "/api/jobs/" + id);
    const line = $("#jobline");
    if (line) line.textContent = `#${job.id} ${job.kind} ${job.status} ${Math.round((job.progress || 0) * 100)}% ${job.message || ""}`;
    if (job.status === "done" || job.status === "failed" || job.status === "cancelled") {
      clearInterval(poll);
      const name = route().name;
      if (name === "script" || name === "play" || name === "voices") draw();
    }
  };
  tick();
  poll = setInterval(tick, 1000);
}

async function viewPlay(r) {
  const script = await api("GET", `/api/studio/episodes/${r.id}/script`);
  let wave = null, qa = { lines: {} };
  try { wave = await api("GET", `/api/studio/episodes/${r.id}/waveform`); } catch { wave = null; }
  try { qa = await api("GET", `/api/studio/episodes/${r.id}/qa`); } catch { qa = { lines: {} }; }
  const qaLines = qa.lines || {};
  $("#view").innerHTML = `<div class="page-head"><div><h1>${esc(script.title)}</h1><p class="note"><a href="#/e/${r.id}">Back to script</a></p></div>
    <div class="toolbar"><a href="/api/studio/episodes/${r.id}/episode.wav">Download wav</a><a href="/api/studio/episodes/${r.id}/episode.mp3">Download mp3</a></div></div>
    <audio id="player" class="wide" controls src="/api/studio/episodes/${r.id}/episode.wav"></audio>
    <canvas id="wave" width="1000" height="140"></canvas>
    <div class="player-lines" id="player-lines">${(wave ? wave.timeline : script.lines.map((l) => ({ line_id: l.id, speaker: l.speaker, start_s: l.start_s, text: l.text, non_kmg: l.non_kmg }))).map((row) => {
      const flags = (qaLines[row.line_id] && qaLines[row.line_id].flags) || [];
      return `<button type="button" data-start="${row.start_s ?? 0}" data-line="${esc(row.line_id)}" class="${flags.length ? "flagged" : ""}"><b>${esc(row.speaker)}</b> ${fmt(row.start_s)} ${row.non_kmg ? '<span class="badge warn">non-KMG</span>' : ""} ${flags.length ? `<span class="flag">${esc(flags.join("; "))}</span>` : ""}<br>${esc(row.text || "")}</button>`;
    }).join("")}</div>`;
  const audio = $("#player");
  $$("#player-lines button").forEach((b) => b.onclick = () => { audio.currentTime = Number(b.dataset.start) || 0; audio.play(); });
  if (wave) paintWave(wave, 0);
  audio.ontimeupdate = () => {
    if (!wave) return;
    paintWave(wave, audio.currentTime);
    $$("#player-lines button").forEach((b) => b.classList.toggle("current", Math.abs(Number(b.dataset.start) - audio.currentTime) < 0.8 || (Number(b.dataset.start) <= audio.currentTime && nextStart(b) > audio.currentTime)));
  };
  $("#wave").onclick = (ev) => {
    if (!wave) return;
    const rect = $("#wave").getBoundingClientRect();
    audio.currentTime = ((ev.clientX - rect.left) / rect.width) * wave.seconds;
    audio.play();
  };
}
function nextStart(button) {
  const all = $$("#player-lines button");
  const i = all.indexOf(button);
  return i + 1 < all.length ? Number(all[i + 1].dataset.start) : 1e9;
}
function paintWave(wave, time) {
  const canvas = $("#wave");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#2b2118"; ctx.fillRect(0, 0, w, h);
  const peaks = wave.peaks || [];
  ctx.fillStyle = "#e6c07b";
  peaks.forEach((p, i) => {
    const bh = Math.max(1, p * (h - 16));
    ctx.fillRect(i * (w / peaks.length), (h - bh) / 2, Math.max(1, w / peaks.length - 1), bh);
  });
  if (wave.seconds) {
    const x = (time / wave.seconds) * w;
    ctx.fillStyle = "#fff"; ctx.fillRect(x, 0, 2, h);
  }
}

async function viewLexicon() {
  const q = new URLSearchParams(location.hash.split("?")[1] || "").get("q") || "";
  const rows = await api("GET", "/api/studio/lexicon?q=" + encodeURIComponent(q));
  $("#view").innerHTML = `<div class="page-head"><h1>Lexicon</h1></div>
    <div class="toolbar"><input id="lex-q" placeholder="Search a name" value="${esc(q)}"><button id="lex-go">Search</button></div>
    <p class="note">The caps respelling is a human guide. Only <b>spoken</b> is sent to TTS, and only after you mark it verified (or it falls back to the KMG spelling).</p>
    <div class="scroll"><table class="lines" id="lex-table"><thead><tr><th>Term</th><th>Respelling</th><th>Spoken</th><th>Verified</th><th>Notes</th><th></th></tr></thead><tbody>
    ${rows.slice(0, 200).map((row) => `<tr data-term="${esc(row.term)}">
      <td>${esc(row.term)}<br><small>${esc(row.source)}</small></td>
      <td><input class="respelling" value="${esc(row.respelling)}"></td>
      <td><input class="spoken" value="${esc(row.spoken)}"></td>
      <td><input class="verified" type="checkbox" ${row.verified ? "checked" : ""}></td>
      <td><input class="notes" value="${esc(row.notes)}"></td>
      <td><button data-action="save">Save</button> <button data-action="test">Test</button></td>
    </tr>`).join("")}
    </tbody></table></div><div id="pron"></div>`;
  $("#lex-go").onclick = () => { location.hash = "#/lexicon?q=" + encodeURIComponent($("#lex-q").value); };
  $$("#lex-table tr[data-term]").forEach((tr) => {
    tr.querySelector("[data-action=save]").onclick = () => saveLex(tr);
    tr.querySelector("[data-action=test]").onclick = () => testLex(tr.dataset.term);
  });
}
async function saveLex(tr) {
  const body = {
    term: tr.dataset.term,
    respelling: tr.querySelector(".respelling").value,
    spoken: tr.querySelector(".spoken").value,
    verified: tr.querySelector(".verified").checked ? 1 : 0,
    notes: tr.querySelector(".notes").value,
    source: "studio",
  };
  await api("PUT", "/api/studio/lexicon", body);
  toast("Lexicon saved");
}
async function testLex(term) {
  const job = await api("POST", "/api/studio/lexicon/test", { term, voices: ["sauti"], formats: ["orig"] });
  toast("Pronunciation job #" + job.id);
  const box = $("#pron");
  const tick = async () => {
    const current = await api("GET", "/api/jobs/" + job.id);
    if (current.status === "queued" || current.status === "running") { setTimeout(tick, 800); return; }
    let output = {}; try { output = JSON.parse(current.output || "{}"); } catch { output = {}; }
    const clips = output.clips || [];
    box.innerHTML = `<h3>${esc(term)}</h3>` + (clips.length ? clips.map((c) => `<div class="cand"><span>${esc(c.voice)} · ${esc(c.fmt)} · ${esc(c.form)}</span>${c.relative ? `<audio controls src="/api/studio/media?path=${encodeURIComponent(c.relative)}"></audio>` : ""}</div>`).join("") : `<pre class="log">${esc(current.log || current.message || current.status)}</pre>`) +
      `<p class="note">Listening decides. Mark the row verified when the spoken form is the one you want.</p>`;
  };
  tick();
}

async function viewVoices(r) {
  const chars = await api("GET", "/api/studio/voices" + (r.id ? "?q=" + encodeURIComponent(r.id) : ""));
  const shown = r.id ? chars.filter((c) => c.id === r.id) : chars.slice(0, 40);
  $("#view").innerHTML = `<div class="page-head"><div><h1>Voices</h1><p class="note">Design candidates from the character brief, audition them, then pick a reference. The map's Voice tab is the same clips.</p></div>
    <input id="voice-q" placeholder="Character id or name" value="${esc(r.id || "")}"></div>
    ${shown.map((c) => `<article class="card" style="margin-bottom:10px" data-voice="${esc(c.id)}">
      <h2>${esc(c.name)} <a href="/?tab=voice#${esc(c.id)}">on the map</a></h2>
      <p>${esc((c.voice_brief || c.voice_prompt || "No brief yet.").slice(0, 400))}</p>
      ${c.voice_clip ? `<audio controls preload="none" src="/${esc(c.voice_clip)}"></audio>` : `<p class="note">No reference clip.</p>`}
      ${c.voice_group ? `<p class="note">Uses group voice ${esc(c.voice_group)}</p>` : ""}
      <div class="toolbar"><label>Candidates <input class="n" type="number" min="1" max="8" value="2" style="width:70px"></label><button data-action="design" class="primary">Design from brief</button></div>
      <div class="cands">${(c.candidates || []).map((name) => `<div class="cand"><span>${esc(name)}</span><audio controls preload="none" src="/voices/${esc(c.id)}/candidates/${esc(name)}"></audio><button data-file="voices/${esc(c.id)}/candidates/${esc(name)}">Use as reference</button></div>`).join("") || `<p class="note">No candidates yet.</p>`}</div>
    </article>`).join("") || `<p class="empty">No characters. Seed the database with <code>python -m mbh.webapp.seed</code>.</p>`}`;
  const q = $("#voice-q");
  if (q) q.onchange = () => { location.hash = "#/voices/" + encodeURIComponent(q.value.trim()); };
  $$("[data-action=design]").forEach((b) => b.onclick = async () => {
    const article = b.closest("[data-voice]");
    const n = Number(article.querySelector(".n").value || 1);
    const job = await api("POST", `/api/studio/voices/${article.dataset.voice}/design`, { n });
    toast("Design job #" + job.id);
    watchJob(job.id);
  });
  $$("[data-file]").forEach((b) => b.onclick = async () => {
    const id = b.closest("[data-voice]").dataset.voice;
    await api("POST", `/api/characters/${id}/voice/select`, { file: b.dataset.file });
    toast("Reference updated");
    draw();
  });
}

async function viewJobs() {
  const jobs = await api("GET", "/api/jobs?limit=50");
  $("#view").innerHTML = `<div class="page-head"><h1>Jobs</h1></div><p class="note">Render, assemble, QA, pronunciation, and voice design share one worker, so a second heavy job waits. Cancel takes effect between lines; finished lines stay in the cache.</p>
    ${jobs.map((j) => `<article class="card job ${esc(j.status)}" style="margin-bottom:8px">
      <h2>#${j.id} ${esc(j.kind)} · ${esc(j.status)}</h2>
      <div class="bar"><span style="width:${Math.round((j.progress || 0) * 100)}%"></span></div>
      <p>${esc(j.message || "")} ${j.episode_id ? "· " + esc(j.episode_id) : ""} ${j.character_id ? "· " + esc(j.character_id) : ""}</p>
      ${j.status === "queued" || j.status === "running" ? `<button data-cancel="${j.id}">Cancel</button>` : ""}
      <details><summary>log</summary><pre class="log">${esc(j.log || "")}</pre></details>
    </article>`).join("") || `<p class="empty">No jobs yet.</p>`}`;
  $$("[data-cancel]").forEach((b) => b.onclick = async () => { await api("POST", "/api/jobs/" + b.dataset.cancel + "/cancel"); toast("Cancel requested"); draw(); });
  if (jobs.some((j) => j.status === "queued" || j.status === "running")) setTimeout(() => { if (route().name === "jobs") draw(); }, 1500);
}

boot();
