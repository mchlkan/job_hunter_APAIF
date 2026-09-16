import type { ApiJob } from "@/lib/api";

const SOURCE_LABEL: Record<string, string> = {
  arbeitsagentur: "Bundesagentur",
  arbeitnow: "Arbeitnow",
  eures: "EURES",
};

function fmtDate(iso: string | null) {
  if (!iso) return "date unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function JobRow({
  job,
  saved,
  onToggleSave,
  onOpen,
}: {
  job: ApiJob;
  saved: boolean;
  onToggleSave: (id: string) => void;
  onOpen?: (job: ApiJob) => void;
}) {
  return (
    <div className="flex items-center gap-4 py-4">
      <button
        onClick={() => onOpen?.(job)}
        className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-accent/10 font-display text-[15px] font-semibold text-accent"
        title={job.score === null ? "Not scored yet" : `${Math.round(job.score)} / 100`}
      >
        {job.score === null ? "—" : Math.round(job.score)}
      </button>
      <button onClick={() => onOpen?.(job)} className="min-w-0 flex-1 text-left">
        <p className="truncate text-[14px] font-medium text-balance">{job.title}</p>
        <p className="mt-1 truncate text-[12px] text-ink/50">
          {job.company ?? "Company withheld"} · {job.location ?? "Location unknown"}
          {job.remote ? " · Remote" : ""}
        </p>
      </button>
      <div className="hidden w-28 shrink-0 sm:block">
        <p className="text-[13px] font-medium">{SOURCE_LABEL[job.source] ?? job.source}</p>
        <p className="text-[11px] text-ink/40">{fmtDate(job.published)}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          onClick={() => onToggleSave(job.id)}
          className={`rounded-[9px] px-3 py-1.5 text-[12px] font-medium ring-1 transition-colors ${
            saved ? "bg-accent/10 text-accent ring-accent/30" : "text-ink/60 ring-line hover:text-ink"
          }`}
        >
          {saved ? "Saved" : "Save"}
        </button>
        {job.url ? (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-[9px] bg-ink px-3 py-1.5 text-[12px] font-medium text-white"
          >
            Apply
          </a>
        ) : (
          <span className="rounded-[9px] bg-ink/20 px-3 py-1.5 text-[12px] font-medium text-white/60">
            No link
          </span>
        )}
      </div>
    </div>
  );
}
