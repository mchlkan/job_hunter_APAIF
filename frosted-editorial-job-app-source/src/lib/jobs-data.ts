// Placeholder only — the Python backend (store.py) has no application-stage
// tracking concept, so routes/applications.tsx has nothing real to fetch yet.
// Everything else in this app (jobs, candidate, profile) comes from
// src/lib/api.ts against the real FastAPI backend.
export const applications = [
  { id: "a1", title: "Senior Product Designer", company: "Framewell", stage: "Interview", updated: "2h ago" },
  { id: "a2", title: "Lead UX Designer", company: "Northbeam", stage: "In review", updated: "Yesterday" },
  { id: "a3", title: "Product Designer", company: "Lumen Labs", stage: "Submitted", updated: "3d ago" },
  { id: "a4", title: "Design Systems Lead", company: "Cobalt", stage: "Interview", updated: "5d ago" },
  { id: "a5", title: "Product Designer", company: "Vantage", stage: "Submitted", updated: "1w ago" },
];
