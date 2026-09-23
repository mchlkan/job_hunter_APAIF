import { useQuery } from "@tanstack/react-query";
import { getJob, type ApiJob } from "@/lib/api";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

const SOURCE_LABEL: Record<string, string> = {
  arbeitsagentur: "Bundesagentur",
  arbeitnow: "Arbeitnow",
  eures: "EURES",
};

export function JobDetailSheet({
  job,
  onOpenChange,
}: {
  job: ApiJob | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["job", job?.id],
    queryFn: () => getJob(job!.id),
    enabled: !!job,
  });

  return (
    <Sheet open={!!job} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {job && (
          <>
            <SheetHeader>
              <span className="w-fit rounded-full bg-accent/10 px-2.5 py-1 text-[11px] font-medium text-accent">
                {SOURCE_LABEL[job.source] ?? job.source}
              </span>
              <SheetTitle className="font-display text-[20px] leading-snug">{job.title}</SheetTitle>
              <p className="text-[13px] text-ink/50">
                {job.company ?? "Company withheld"}, {job.location ?? "location unknown"}
                {job.remote ? " · Remote" : ""}
              </p>
            </SheetHeader>

            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex w-fit items-center rounded-[10px] bg-accent px-4 py-2 text-[13px] font-medium text-white"
              >
                View original posting
              </a>
            )}

            <div className="mt-5 text-[13px] leading-relaxed whitespace-pre-wrap text-ink/80">
              {isLoading
                ? "Loading description…"
                : (data?.description ?? "No description was fetched for this posting.")}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
