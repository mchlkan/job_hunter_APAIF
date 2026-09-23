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
  if (!iso) return "date unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

function srcTag(source, inline = false) {
  const src = SOURCE_CODE[source] || { code: source.slice(0, 2).toUpperCase(), cls: "" };
  const cls = inline ? "src-inline" : "src-tag";
  return `<span class="${cls} ${src.cls}" title="${escapeHtml(src.label || source)}">${src.code}</span>`;
}

function jobCard(job) {
  const li = document.createElement("li");
  li.className = "job-card";

  const scoreHtml = job.score === null || job.score === undefined
    ? `<span class="job-score empty">&mdash;</span>`
    : `<span class="job-score">${Math.round(job.score)}</span>`;

  li.innerHTML = `
    ${srcTag(job.source)}
    <div>
      <div class="job-title">${escapeHtml(job.title || "untitled posting")}</div>
      <div class="job-meta">
        ${escapeHtml(job.company || "company withheld")} &middot; ${escapeHtml(job.location || "location unknown")} &middot; ${fmtDate(job.published)}
        ${job.remote ? '<span class="remote-flag">Remote</span>' : ""}
      </div>
    </div>
    ${scoreHtml}
  `;
  li.addEventListener("click", () => openDetail(job.id));
  return li;
}

async function openDetail(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) return showToast("Couldn't load that posting.");
  const job = await res.json();

  detailBody.innerHTML = `
    ${srcTag(job.source)}
    <h2>${escapeHtml(job.title || "untitled posting")}</h2>
    <div class="detail-meta">
      <div>${escapeHtml(job.company || "company withheld")}, ${escapeHtml(job.location || "location unknown")}</div>
      ${job.remote ? '<span class="remote-flag">Remote</span>' : ""}
    </div>
    ${job.url ? `<a class="apply-link" href="${job.url}" target="_blank" rel="noopener">View original posting</a>` : ""}
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
  for (const job of data.jobs) jobList.appendChild(jobCard(job));
}

async function loadStats() {
  const res = await fetch("/api/stats");
  if (!res.ok) return;
  const stats = await res.json();
  $("#stat-total").textContent = stats.total_jobs;
  $("#stat-scored").textContent = stats.scored_jobs;

  const parts = Object.entries(stats.by_source).map(
    ([source, count]) => `${srcTag(source, true)} ${count}`
  );
  $("#stat-sources").innerHTML = parts.join(", ");
}

async function loadCandidate() {
  const strip = $("#candidate-strip");
  const res = await fetch("/api/candidate");
  if (!res.ok) {
    strip.innerHTML = '<span class="candidate-empty">No CV on file yet</span>';
    return;
  }
  const c = await res.json();
  strip.innerHTML = `<span class="name">${escapeHtml(c.name || "unnamed candidate")}</span> &middot; ${c.skills.length} skills on file`;
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
