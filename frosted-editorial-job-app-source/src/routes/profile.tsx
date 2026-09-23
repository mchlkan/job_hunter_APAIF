import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Panel } from "@/components/AppShell";
import { CvUpload } from "@/components/CvUpload";
import { useCandidate, useProfile } from "@/lib/queries";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Profile — Kestrel" },
      { name: "description", content: "Your CV, skills and search preferences." },
      { property: "og:title", content: "Profile — Kestrel" },
      { property: "og:description", content: "Your CV, skills and search preferences." },
    ],
  }),
  component: Profile,
});

function Profile() {
  const { data: candidate } = useCandidate();
  const { data: profile } = useProfile();

  const rows = [
    { label: "Must-have skills", value: profile?.must_have.length ? profile.must_have.join(", ") : "none set — edit config.yaml" },
    { label: "Locations", value: profile?.locations.length ? profile.locations.join(", ") : "anywhere" },
    { label: "Remote bonus", value: profile ? `+${profile.remote_bonus} pts` : "—" },
    { label: "Match alert threshold", value: profile ? `${profile.alert_threshold}%` : "—" },
  ];

  return (
    <AppShell eyebrow="Profile" title={candidate?.name ?? "No CV uploaded"}>
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <CvUpload />
        <Panel>
          <p className="font-display text-[15px] font-semibold tracking-tight">Search preferences</p>
          <p className="mt-1 text-[12px] text-ink/45">Configured in config.yaml — edit it by hand and re-run the collection.</p>
          <div className="mt-4 divide-y divide-line">
            {rows.map((row) => (
              <div key={row.label} className="flex items-center justify-between gap-4 py-3">
                <span className="text-[13px] text-ink/60">{row.label}</span>
                <span className="truncate text-[13px] font-medium">{row.value}</span>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </AppShell>
  );
}
