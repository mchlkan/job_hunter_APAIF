import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import avatar from "@/assets/avatar.jpg";
import { useCandidate } from "@/lib/queries";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/matches", label: "Matches" },
  { to: "/applications", label: "Applications" },
  { to: "/saved", label: "Saved jobs" },
  { to: "/profile", label: "Profile" },
] as const;

export function AppShell({
  eyebrow,
  title,
  action,
  children,
}: {
  eyebrow: string;
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  const { data: candidate } = useCandidate();

  return (
    <div className="relative min-h-screen overflow-hidden bg-mist font-sans text-ink antialiased">
      <div className="pointer-events-none absolute -top-40 -left-32 h-[420px] w-[420px] rounded-full bg-white/70 blur-3xl" />
      <div className="pointer-events-none absolute top-1/3 -right-24 h-[360px] w-[360px] rounded-full bg-accent/10 blur-3xl" />

      <div className="relative mx-auto flex max-w-[1340px] flex-col gap-6 px-6 py-6 lg:flex-row">
        <aside className="w-full shrink-0 lg:w-[248px]">
          <div className="rounded-[16px] bg-white/55 p-4 ring-1 ring-black/5 backdrop-blur-xl">
            <div className="flex items-center gap-2.5 px-2 pb-5">
              <div className="grid size-8 place-items-center rounded-[10px] bg-ink font-display text-[15px] font-semibold text-white">
                K
              </div>
              <div>
                <p className="font-display text-[15px] leading-none font-semibold tracking-tight">Kestrel</p>
                <p className="mt-1 text-[11px] leading-none text-ink/45">Job match studio</p>
              </div>
            </div>
            <nav className="space-y-1">
              {nav.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  activeOptions={{ exact: item.to === "/" }}
                  className="flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] font-medium text-ink/60 transition-colors hover:text-ink"
                  activeProps={{ className: "bg-accent/10 text-accent hover:text-accent" }}
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={`size-1.5 shrink-0 rounded-full ${isActive ? "bg-accent" : "bg-ink/20"}`}
                      />
                      {item.label}
                    </>
                  )}
                </Link>
              ))}
            </nav>
            <div className="mt-5 border-t border-line px-2 pt-4">
              <div className="flex items-center gap-2.5">
                <img
                  src={avatar}
                  alt={candidate?.name ?? "No CV uploaded"}
                  className="size-9 rounded-full object-cover outline-1 -outline-offset-1 outline-black/5"
                />
                <div className="min-w-0">
                  <p className="truncate text-[13px] leading-none font-medium">
                    {candidate?.name ?? "No CV yet"}
                  </p>
                  <p className="mt-1 truncate text-[11px] leading-none text-ink/45">
                    {candidate ? `${candidate.skills.length} skills on file` : "Upload one from Profile"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1 space-y-6">
          <header className="flex items-end justify-between gap-4">
            <div>
              <p className="text-[12px] font-medium tracking-[0.14em] text-ink/40 uppercase">{eyebrow}</p>
              <h1 className="mt-2 font-display text-[34px] leading-none font-semibold tracking-tight text-balance">
                {title}
              </h1>
            </div>
            {action}
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-[16px] bg-white/55 p-5 ring-1 ring-black/5 backdrop-blur-xl ${className}`}>
      {children}
    </div>
  );
}
