const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// In-memory request deduplication & micro-cache for ultra-low latency navigation
let metricsCache: { data: any; timestamp: number } | null = null;
let metricsPromise: Promise<any> | null = null;

export async function fetchMetrics(force = false) {
  const now = Date.now();
  if (!force && metricsCache && now - metricsCache.timestamp < 3500) {
    return metricsCache.data;
  }
  if (!force && metricsPromise) {
    return metricsPromise;
  }

  metricsPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/metrics`, { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to fetch metrics");
      const data = await res.json();
      metricsCache = { data, timestamp: Date.now() };
      return data;
    } finally {
      metricsPromise = null;
    }
  })();

  return metricsPromise;
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
  // Clear metrics cache on pipeline mutation
  metricsCache = null;
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

export async function testToolHealth(toolId: string) {
  const res = await fetch(`${API_BASE}/api/tools/test/${toolId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to test tool health");
  return res.json();
}

export async function executeToolAction(toolId: string, input?: string) {
  const res = await fetch(`${API_BASE}/api/tools/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool_id: toolId, input: input || "" }),
  });
  if (!res.ok) throw new Error("Failed to execute tool action");
  return res.json();
}

let settingsCache: { data: any; timestamp: number } | null = null;

export async function fetchSettings(force = false) {
  const now = Date.now();
  if (!force && settingsCache && now - settingsCache.timestamp < 5000) {
    return settingsCache.data;
  }
  const res = await fetch(`${API_BASE}/api/settings`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch settings");
  const data = await res.json();
  settingsCache = { data, timestamp: Date.now() };
  return data;
}

export async function saveSettings(data: Record<string, any>) {
  settingsCache = null;
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

export async function discoverProviderModels(data: {
  provider: string;
  base_url?: string;
  api_key?: string;
}) {
  const res = await fetch(`${API_BASE}/api/providers/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to discover provider models");
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

export async function fetchArtifactFiles() {
  const res = await fetch(`${API_BASE}/api/artifacts/files`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch artifacts library");
  return res.json();
}

export async function fetchArtifactPreview(artifactId: string) {
  const res = await fetch(`${API_BASE}/api/artifacts/preview/${artifactId}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch artifact preview");
  return res.json();
}

export async function executeArtifactAction(data: {
  action: string;
  file_ids?: string[];
  retention_days?: number;
}) {
  const res = await fetch(`${API_BASE}/api/artifacts/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to execute artifact action");
  return res.json();
}

export async function syncArtifactDeliverables() {
  const res = await fetch(`${API_BASE}/api/artifacts/sync`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to sync deliverables from database");
  return res.json();
}
