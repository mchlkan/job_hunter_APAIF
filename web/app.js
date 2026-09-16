const SOURCE_COLOR = {
  arbeitsagentur: "var(--source-arbeitsagentur)",
  arbeitnow: "var(--source-arbeitnow)",
  eures: "var(--source-eures)",
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
  if (!iso) return "date n/a";
  return iso.slice(0, 10);
}

function jobCard(job) {
  const li = document.createElement("li");
  li.className = "job-card";
  li.style.setProperty("--card-color", SOURCE_COLOR[job.source] || "var(--ink-dim)");

  const scoreHtml = job.score === null || job.score === undefined
    ? `<div class="job-score unscored">unscored</div>`
    : `<div class="job-score"><span class="num">${job.score.toFixed(0)}</span> / 100</div>`;

  li.innerHTML = `
    <div class="job-title">${escapeHtml(job.title || "untitled")}</div>
    ${scoreHtml}
    <div class="job-meta">
      <span>${escapeHtml(job.company || "unknown company")}</span>
      <span class="sep">&middot;</span>
      <span>${escapeHtml(job.location || "location n/a")}</span>
      <span class="sep">&middot;</span>
      <span>${job.source}</span>
      <span class="sep">&middot;</span>
      <span>${fmtDate(job.published)}</span>
      ${job.remote ? '<span class="sep">&middot;</span><span class="remote-badge">remote</span>' : ""}
    </div>
  `;
  li.addEventListener("click", () => openDetail(job.id));
  return li;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

async function openDetail(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) return showToast("couldn't load that posting");
  const job = await res.json();

  detailBody.innerHTML = `
    <h2>${escapeHtml(job.title || "untitled")}</h2>
    <div class="job-meta">
      <span>${escapeHtml(job.company || "unknown company")}</span>
      <span class="sep">&middot;</span>
      <span>${escapeHtml(job.location || "location n/a")}</span>
      <span class="sep">&middot;</span>
      <span>${job.source}</span>
      ${job.remote ? '<span class="sep">&middot;</span><span class="remote-badge">remote</span>' : ""}
    </div>
    ${job.url ? `<a class="apply-link" href="${job.url}" target="_blank" rel="noopener">view posting &rarr;</a>` : ""}
    <div class="description">${escapeHtml(job.description || "no description fetched yet.")}</div>
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
  if (!res.ok) return showToast("failed to load postings");
  const data = await res.json();

  jobList.innerHTML = "";
  emptyState.hidden = data.jobs.length > 0;
  for (const job of data.jobs) jobList.appendChild(jobCard(job));
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
    const span = document.createElement("span");
    span.innerHTML = `<span class="dot" style="background:${SOURCE_COLOR[source] || "var(--ink-dim)"}"></span>${source} ${count}`;
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
    strip.innerHTML = '<span class="candidate-empty">no CV on file</span>';
    return;
  }
  const c = await res.json();
  strip.innerHTML = `
    <span class="name">${escapeHtml(c.name || "unnamed candidate")}</span>
    <span>&middot; ${c.skills.length} skills matched</span>
  `;
}

async function uploadCv(file) {
  const form = new FormData();
  form.append("file", file);
  showToast("parsing CV…");
  const res = await fetch("/api/cv", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return showToast(`upload failed: ${err.detail || res.statusText}`);
  }
  const candidate = await res.json();
  showToast(`parsed ${candidate.name || "candidate"} — ${candidate.skills.length} skills`);
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
