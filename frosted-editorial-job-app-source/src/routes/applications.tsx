import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel } from "@/components/AppShell";
import { applications } from "@/lib/jobs-data";

export const Route = createFileRoute("/applications")({
  head: () => ({
    meta: [
      { title: "Applications — Kestrel" },
      { name: "description", content: "Track where each application stands." },
      { property: "og:title", content: "Applications — Kestrel" },
      { property: "og:description", content: "Track where each application stands." },
    ],
  }),
  component: Applications,
});

function Applications() {
  return (
    <AppShell eyebrow="Applications" title="Where things stand">
      <div className="rounded-[10px] bg-accent/5 px-4 py-3 text-[12px] text-ink/60 ring-1 ring-accent/15">
        Sample data — application-stage tracking isn't built in the backend yet.
      </div>
      <Panel>
        <div className="divide-y divide-line">
          {applications.map((app) => (
            <div key={app.id} className="flex items-center gap-4 py-4">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14px] font-medium">{app.title}</p>
                <p className="mt-1 truncate text-[12px] text-ink/50">{app.company}</p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-[12px] font-medium ${
                  app.stage === "Interview"
                    ? "bg-accent/10 text-accent"
                    : "bg-ink/[0.04] text-ink/60"
                }`}
              >
                {app.stage}
              </span>
              <span className="w-20 shrink-0 text-right text-[12px] text-ink/40">{app.updated}</span>
            </div>
          ))}
        </div>
      </Panel>
    </AppShell>
  );
}
