const SOURCE_CODE = {
  arbeitsagentur: { code: "BA", cls: "ba", label: "Bundesagentur" },
  arbeitnow: { code: "AN", cls: "an", label: "Arbeitnow" },
  eures: { code: "EU", cls: "eu", label: "EURES" },
};

const $ = (sel) => document.querySelector(sel);

const jobList = $("#job-list");
const emptyState = $("#empty-state");
const detailPanel = $("#detail-panel");
const detailBody = $("#detail-body");
const toast = $("#toast");

let toastTimer = null;
function showToast(msg) {
  toast.textContent = msg;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toast.hidden = true), 3200);
}

function fmtDate(iso) {
  if (!iso) return "—";
  return iso.slice(5, 10); // MM-DD, the year rarely matters day-to-day here
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

function srcBadge(source) {
  const src = SOURCE_CODE[source] || { code: source.slice(0, 2).toUpperCase(), cls: "" };
  return `<span class="src-code ${src.cls}" title="${escapeHtml(src.label || source)}">${src.code}</span>`;
}

function jobRow(job) {
  const row = document.createElement("div");
  row.className = "register-row job-row";
  row.setAttribute("role", "row");

  const scoreHtml = job.score === null || job.score === undefined
    ? `<span class="score-cell empty">—</span>`
    : `<span class="score-cell">${Math.round(job.score)}</span>`;

  row.innerHTML = `
    <span role="cell">${srcBadge(job.source)}</span>
    <span role="cell">
      <div class="posting-title">${escapeHtml(job.title || "untitled posting")}</div>
      <div class="posting-company">${escapeHtml(job.company || "company withheld")}${job.remote ? ' <span class="remote-flag">remote</span>' : ""}</div>
    </span>
    <span role="cell" class="col-location">${escapeHtml(job.location || "—")}</span>
    <span role="cell" class="col-posted">${fmtDate(job.published)}</span>
    <span role="cell">${scoreHtml}</span>
  `;
  row.addEventListener("click", () => openDetail(job.id));
  return row;
}

async function openDetail(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) return showToast("Couldn't load that posting.");
  const job = await res.json();

  detailBody.innerHTML = `
    ${srcBadge(job.source)}
    <h2>${escapeHtml(job.title || "untitled posting")}</h2>
    <div class="detail-meta">
      <div>${escapeHtml(job.company || "company withheld")}, ${escapeHtml(job.location || "location unknown")}</div>
      ${job.remote ? '<span class="remote-flag">remote</span>' : ""}
    </div>
    ${job.url ? `<a class="apply-link" href="${job.url}" target="_blank" rel="noopener">Original posting</a>` : ""}
    <div class="description">${escapeHtml(job.description || "No description was fetched for this posting.")}</div>
  `;
  detailPanel.hidden = false;
}

$("#detail-close").addEventListener("click", () => (detailPanel.hidden = true));
detailPanel.addEventListener("click", (e) => {
  if (e.target === detailPanel) detailPanel.hidden = true;
});

async function loadJobs() {
  const params = new URLSearchParams();
  const q = $("#f-q").value.trim();
  const source = $("#f-source").value;
  const remote = $("#f-remote").value;
  if (q) params.set("q", q);
  if (source) params.set("source", source);
  if (remote) params.set("remote", remote);

  const res = await fetch(`/api/jobs?${params}`);
  if (!res.ok) return showToast("Couldn't load postings.");
  const data = await res.json();

  jobList.innerHTML = "";
  emptyState.hidden = data.jobs.length > 0;
  for (const job of data.jobs) jobList.appendChild(jobRow(job));
}

async function loadStats() {
  const res = await fetch("/api/stats");
  if (!res.ok) return;
  const stats = await res.json();
  $("#stat-total").textContent = stats.total_jobs;
  $("#stat-scored").textContent = stats.scored_jobs;

  const tally = document.createElement("div");
  tally.className = "source-tally";
  for (const [source, count] of Object.entries(stats.by_source)) {
    const src = SOURCE_CODE[source] || { code: source };
    const span = document.createElement("span");
    span.innerHTML = `${src.code} <b>${count}</b>`;
    tally.appendChild(span);
  }
  const el = $("#stat-sources");
  el.querySelectorAll(".source-tally").forEach((n) => n.remove());
  el.appendChild(tally);
}

async function loadCandidate() {
  const strip = $("#candidate-strip");
  const res = await fetch("/api/candidate");
  if (!res.ok) {
    strip.innerHTML = '<span class="candidate-empty">No CV on file yet.</span>';
    return;
  }
  const c = await res.json();
  strip.innerHTML = `<span class="name">${escapeHtml(c.name || "unnamed candidate")}</span> (${c.skills.length} skills on file)`;
}

async function uploadCv(file) {
  const form = new FormData();
  form.append("file", file);
  showToast("Reading CV…");
  const res = await fetch("/api/cv", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return showToast(`Couldn't read that CV: ${err.detail || res.statusText}`);
  }
  const candidate = await res.json();
  showToast(`Filed ${candidate.name || "candidate"} (${candidate.skills.length} skills found).`);
  loadCandidate();
}

$("#f-q").addEventListener("input", debounce(loadJobs, 250));
$("#f-source").addEventListener("change", loadJobs);
$("#f-remote").addEventListener("change", loadJobs);
$("#f-cv").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) uploadCv(file);
  e.target.value = "";
});

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

loadJobs();
loadStats();
loadCandidate();
