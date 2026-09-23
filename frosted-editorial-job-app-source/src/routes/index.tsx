import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, Panel } from "@/components/AppShell";
import { CvUpload } from "@/components/CvUpload";
import { JobRow } from "@/components/JobRow";
import { JobDetailSheet } from "@/components/JobDetailSheet";
import { useCandidate, useJobs, useStats } from "@/lib/queries";
import { useSavedJobs } from "@/lib/use-saved-jobs";
import type { ApiJob } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — Kestrel Job Match Studio" },
      { name: "description", content: "Your postings on file, tracked sources and newest job matches at a glance." },
      { property: "og:title", content: "Dashboard — Kestrel Job Match Studio" },
      { property: "og:description", content: "Your postings on file, tracked sources and newest job matches at a glance." },
    ],
  }),
  component: Dashboard,
});

const SOURCE_LABEL: Record<string, string> = {
  arbeitsagentur: "Bundesagentur",
  arbeitnow: "Arbeitnow",
  eures: "EURES",
};

function Dashboard() {
  const { savedIds, toggle } = useSavedJobs();
  const { data: stats } = useStats();
  const { data: candidate } = useCandidate();
  const { data: jobsData, isLoading } = useJobs({ limit: 5 });
  const [openJob, setOpenJob] = useState<ApiJob | null>(null);

  const bySourceLine = stats
    ? Object.entries(stats.by_source)
        .map(([src, count]) => `${SOURCE_LABEL[src] ?? src} ${count}`)
        .join(", ")
    : "—";

  const metrics = [
    { label: "Postings tracked", value: stats ? String(stats.total_jobs) : "—", note: bySourceLine },
    { label: "Scored so far", value: stats ? String(stats.scored_jobs) : "—", note: "match engine not live yet" },
    { label: "Skills on file", value: candidate ? String(candidate.skills.length) : "—", note: candidate?.name ?? "no CV uploaded" },
    { label: "Saved jobs", value: String(savedIds.length), note: "bookmarked to revisit" },
  ];

  return (
    <AppShell
      eyebrow="Overview"
      title={candidate?.name ? `Good morning, ${candidate.name.split(" ")[0]}` : "Good morning"}
      action={
        <Link
          to="/matches"
          className="inline-flex items-center gap-2 rounded-[10px] bg-ink px-4 py-2.5 text-[13px] font-medium text-white ring-1 ring-ink ring-offset-2 ring-offset-mist"
        >
          Search jobs
        </Link>
      }
    >
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {metrics.map((m) => (
          <Panel key={m.label}>
            <p className="text-[12px] font-medium text-ink/50">{m.label}</p>
            <p className="mt-3 font-display text-[32px] leading-none font-semibold tracking-tight">
              {m.value}
            </p>
            <p className="mt-2 truncate text-[12px] text-ink/45">{m.note}</p>
          </Panel>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-4">
          <CvUpload />
        </div>

        <Panel>
          <div className="flex items-center justify-between">
            <p className="font-display text-[15px] font-semibold tracking-tight">Job matches</p>
            <span className="text-[12px] text-ink/45">
              {isLoading ? "Loading…" : "Newest first"}
            </span>
          </div>
          <div className="mt-3 divide-y divide-line">
            {jobsData?.jobs.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                saved={savedIds.includes(job.id)}
                onToggleSave={toggle}
                onOpen={setOpenJob}
              />
            ))}
            {jobsData && jobsData.jobs.length === 0 && (
              <p className="py-8 text-center text-[13px] text-ink/45">
                Nothing on file yet — run the collection pipeline.
              </p>
            )}
          </div>
        </Panel>
      </section>

      <JobDetailSheet job={openJob} onOpenChange={(open) => !open && setOpenJob(null)} />
    </AppShell>
  );
}
