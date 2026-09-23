import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, Panel } from "@/components/AppShell";
import { JobRow } from "@/components/JobRow";
import { JobDetailSheet } from "@/components/JobDetailSheet";
import { useJobs } from "@/lib/queries";
import { useSavedJobs } from "@/lib/use-saved-jobs";
import type { ApiJob } from "@/lib/api";

export const Route = createFileRoute("/saved")({
  head: () => ({
    meta: [
      { title: "Saved jobs — Kestrel" },
      { name: "description", content: "The roles you bookmarked to revisit later." },
      { property: "og:title", content: "Saved jobs — Kestrel" },
      { property: "og:description", content: "The roles you bookmarked to revisit later." },
    ],
  }),
  component: Saved,
});

// Saves are bookmarked client-side (localStorage, see use-saved-jobs.ts) — the
// backend has no "saved" concept, so this pulls a wide slice of the store and
// filters to the bookmarked ids rather than adding a dedicated endpoint.
function Saved() {
  const { savedIds, toggle } = useSavedJobs();
  const [openJob, setOpenJob] = useState<ApiJob | null>(null);
  const { data, isLoading } = useJobs({ limit: 1000 });
  const savedJobs = (data?.jobs ?? []).filter((job) => savedIds.includes(job.id));

  return (
    <AppShell eyebrow="Saved jobs" title="Bookmarked roles">
      <Panel>
        <div className="divide-y divide-line">
          {savedJobs.map((job) => (
            <JobRow key={job.id} job={job} saved onToggleSave={toggle} onOpen={setOpenJob} />
          ))}
          {!isLoading && savedJobs.length === 0 && (
            <p className="py-8 text-center text-[13px] text-ink/45">
              Nothing saved yet — tap Save on a match to keep it here.
            </p>
          )}
        </div>
      </Panel>

      <JobDetailSheet job={openJob} onOpenChange={(open) => !open && setOpenJob(null)} />
    </AppShell>
  );
}
