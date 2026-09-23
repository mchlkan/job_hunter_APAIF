import { useRef, useState } from "react";
import { Panel } from "@/components/AppShell";
import { ApiError } from "@/lib/api";
import { useCandidate, useUploadCv } from "@/lib/queries";

export function CvUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const { data: candidate } = useCandidate();
  const upload = useUploadCv();

  const accept = (f: File | undefined) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      upload.reset();
      return;
    }
    upload.mutate(f);
  };

  const skills = upload.data?.skills ?? candidate?.skills ?? [];
  const name = upload.data?.name ?? candidate?.name;

  return (
    <Panel>
      <div className="flex items-center justify-between">
        <p className="font-display text-[15px] font-semibold tracking-tight">Your CV</p>
        <span className="rounded-full bg-accent/10 px-2.5 py-1 text-[11px] font-medium text-accent">
          {upload.isPending ? "Reading…" : name ? "Parsed" : "No CV yet"}
        </span>
      </div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files?.[0]);
        }}
        className={`mt-4 rounded-[10px] border border-dashed p-5 text-center transition-colors ${
          dragging ? "border-accent bg-accent/5" : "border-line bg-white/40"
        }`}
      >
        <p className="text-[13px] font-medium">{name ? `${name}'s CV on file` : "Drop a CV to scan"}</p>
        <p className="mt-1 text-[12px] text-ink/45">
          {upload.isError
            ? upload.error instanceof ApiError
              ? upload.error.message
              : "Something went wrong reading that file."
            : "PDF only, parsed on upload"}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => accept(e.target.files?.[0])}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={upload.isPending}
          className="mt-4 inline-flex items-center rounded-[10px] bg-blue-800 px-4 py-2 text-[13px] font-medium text-white ring-1 ring-blue-800 hover:bg-blue-900 disabled:opacity-60"
        >
          {name ? "Replace CV" : "Upload CV"}
        </button>
      </div>
      {skills.length > 0 && (
        <div className="mt-5">
          <p className="text-[12px] font-medium text-ink/50">Parsed skills</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {skills.map((skill) => (
              <span
                key={skill}
                className="rounded-full bg-ink/[0.04] px-3 py-1 text-[12px] font-medium text-ink/70"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}
