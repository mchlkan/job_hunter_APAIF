import { useCallback, useEffect, useState } from "react";

const KEY = "kestrel-saved-jobs";
const listeners = new Set<(ids: string[]) => void>();
let current: string[] = [];

function publish(ids: string[]) {
  current = ids;
  if (typeof window !== "undefined") localStorage.setItem(KEY, JSON.stringify(ids));
  listeners.forEach((l) => l(ids));
}

export function useSavedJobs() {
  const [ids, setIds] = useState<string[]>(current);

  useEffect(() => {
    const stored = localStorage.getItem(KEY);
    if (stored) {
      try {
        current = JSON.parse(stored) as string[];
      } catch {
        current = [];
      }
    }
    setIds(current);
    listeners.add(setIds);
    return () => {
      listeners.delete(setIds);
    };
  }, []);

  const toggle = useCallback((id: string) => {
    publish(current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);
  }, []);

  return { savedIds: ids, toggle };
}
