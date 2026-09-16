import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell, Panel } from "@/components/AppShell";
import { JobRow } from "@/components/JobRow";
import { JobDetailSheet } from "@/components/JobDetailSheet";
import { useJobs } from "@/lib/queries";
import { useSavedJobs } from "@/lib/use-saved-jobs";
import type { ApiJob } from "@/lib/api";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export const Route = createFileRoute("/matches")({
  head: () => ({
    meta: [
      { title: "Job matches — Kestrel" },
      { name: "description", content: "Every role on file, newest first." },
      { property: "og:title", content: "Job matches — Kestrel" },
      { property: "og:description", content: "Every role on file, newest first." },
    ],
  }),
  component: Matches,
});

function Matches() {
  const { savedIds, toggle } = useSavedJobs();
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [openJob, setOpenJob] = useState<ApiJob | null>(null);
  const debouncedQuery = useDebounced(query, 250);
  const { data, isLoading } = useJobs({ q: debouncedQuery || undefined, source: source || undefined, limit: 100 });
  const jobs = data?.jobs ?? [];

  return (
    <AppShell eyebrow="Matches" title="Ranked against your CV">
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search roles, companies, locations"
            className="w-full max-w-sm rounded-[10px] bg-white/60 px-3 py-2 text-[13px] ring-1 ring-line outline-none placeholder:text-ink/35 focus:ring-accent/50"
          />
          <div className="flex items-center gap-3">
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="rounded-[10px] bg-white/60 px-3 py-2 text-[13px] ring-1 ring-line outline-none"
            >
              <option value="">All sources</option>
              <option value="arbeitsagentur">Bundesagentur</option>
              <option value="arbeitnow">Arbeitnow</option>
              <option value="eures">EURES</option>
            </select>
            <span className="text-[12px] text-ink/45">
              {isLoading ? "Loading…" : `${jobs.length} roles`}
            </span>
          </div>
        </div>
        <div className="mt-3 divide-y divide-line">
          {jobs.map((job) => (
            <JobRow
              key={job.id}
              job={job}
              saved={savedIds.includes(job.id)}
              onToggleSave={toggle}
              onOpen={setOpenJob}
            />
          ))}
          {!isLoading && jobs.length === 0 && (
            <p className="py-8 text-center text-[13px] text-ink/45">No roles match that search.</p>
          )}
        </div>
      </Panel>

      <JobDetailSheet job={openJob} onOpenChange={(open) => !open && setOpenJob(null)} />
    </AppShell>
  );
}
