const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE}/api/metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchLeads(params: Record<string, any> = {}) {
  const url = new URL(`${API_BASE}/api/leads`);
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== "") {
      url.searchParams.set(key, String(val));
    }
  });
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch leads");
  return res.json();
}

export async function fetchLeadEvidence(companyId: number) {
  const res = await fetch(`${API_BASE}/api/leads/${companyId}/evidence`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch evidence dossier");
  return res.json();
}

export async function triggerPipelineStage(stage: string, provider?: string) {
  const res = await fetch(`${API_BASE}/api/pipeline/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage, provider: provider || "auto_fallback" }),
  });
  if (!res.ok) throw new Error("Failed to trigger pipeline");
  return res.json();
}

export async function fetchToolsCatalog() {
  const res = await fetch(`${API_BASE}/api/tools`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch tools");
  return res.json();
}

export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/api/settings`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function saveSettings(data: Record<string, any>) {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to save settings");
  return res.json();
}

export async function pingProvider(data: {
  provider: string;
  base_url?: string;
  api_key?: string;
  model?: string;
}) {
  const res = await fetch(`${API_BASE}/api/providers/ping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to ping provider");
  return res.json();
}

export async function pingSearchProvider(data: {
  provider: string;
  base_url?: string;
  api_key?: string;
  query?: string;
}) {
  const res = await fetch(`${API_BASE}/api/search/ping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to ping search provider");
  return res.json();
}
