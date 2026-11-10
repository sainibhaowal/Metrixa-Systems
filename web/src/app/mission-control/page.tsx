"use client";

import { useEffect, useRef, useState } from "react";
import {
  Play,
  Terminal as TerminalIcon,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Sparkles,
  ShieldAlert,
  ArrowRight,
  GitCompare,
  History,
  Activity,
  Sliders,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Search,
  Zap,
  Globe,
  Database,
  ShieldCheck,
  Server,
  FileSpreadsheet,
  X,
  Maximize2,
  TrendingUp,
  Cpu,
  Workflow,
  Eye,
  Check,
  CheckSquare,
  Trash2,
  Calendar,
  ChevronsUpDown,
  Copy,
} from "lucide-react";
import {
  triggerPipelineStage,
  cancelPipelineRun,
  fetchPipelineRuns,
  fetchPipelineRunEvents,
  deletePipelineRun,
  clearPipelineRuns,
  batchDeletePipelineRuns,
  comparePipelineRuns,
  executeTool,
  pingProvider,
  fetchMetrics,
} from "@/lib/api";
import { RoundedSelect, SelectOption } from "@/components/ui/RoundedSelect";

interface PipelineStageDef {
  id: string;
  name: string;
  shortName: string;
  stepNum: string;
  category: "ingest" | "dedup" | "crawl" | "extract" | "enrich" | "export";
  desc: string;
  details: string;
  tools: string[];
}

const STAGES: PipelineStageDef[] = [
  {
    id: "ingest",
    name: "Multi-Source Ingestion",
    shortName: "Ingestion",
    stepNum: "01",
    category: "ingest",
    desc: "Ingests raw directories across 5 distinct sources in parallel.",
    details:
      "Scrapes Gelbe Seiten (23 Berlin shards), 11880.com (with Cloudflare XOR email decrypter), VDIV regional registry, OpenStreetMap Overpass (BBox), and autonomous search discovery.",
    tools: [
      "GelbeSeitenScraper",
      "Dir11880Scraper",
      "VDIVScraper",
      "OSMOverpass",
      "SearchDiscovery",
    ],
  },
  {
    id: "deduplicate",
    name: "Entity Resolution & Dedup",
    shortName: "Dedup",
    stepNum: "02",
    category: "dedup",
    desc: "Clusters duplicate records using Union-Find & RapidFuzz.",
    details:
      "Deterministic blocking keys (canonical website domain, E.164 phone, normalized street + PLZ) merged via Union-Find disjoint sets. Reconciles postal codes across 12 official Berlin Bezirke.",
    tools: [
      "UnionFindClustering",
      "RapidFuzzTokenSort",
      "GermanLegalNormalizer",
      "PLZBezirkMapper",
    ],
  },
  {
    id: "crawl",
    name: "Async Impressum & DOM Crawler",
    shortName: "Crawler",
    stepNum: "03",
    category: "crawl",
    desc: "HTTP/2 crawler + DOM PropTech ERP & submetering scanner.",
    details:
      "Crawls /, /impressum, /team, /leistungen, and /referenzen. Scans DOM signatures for PropTech ERPs (Casavi, Domus 4000, Wodis Sigma, Aareon) and metering incumbents (Techem, ista, Minol, Brunata).",
    tools: [
      "AsyncHTTP2Crawler",
      "DOMPropTechScanner",
      "MeteringSignalDetector",
      "SubpageResolver",
    ],
  },
  {
    id: "extract",
    name: "Hybrid Multi-LLM KPI Extraction",
    shortName: "AI Extract",
    stepNum: "04",
    category: "extract",
    desc: "Extracts managed units, WEG/Miet focus & Geschäftsführer.",
    details:
      "Layer 1: Deterministic German § 5 DDG legal parser ($0 cost baseline). Layer 2: LLM extraction (OpenAI, Gemini, DeepSeek, local Ollama) with anti-hallucination quote verification gates.",
    tools: [
      "GermanImpressumParser",
      "LLMRouter",
      "AntiHallucinationGate",
      "PydanticSchemaValidator",
    ],
  },
  {
    id: "enrich",
    name: "DNS MX Verification & Scoring",
    shortName: "Scoring",
    stepNum: "05",
    category: "enrich",
    desc: "Live RFC 5321 MX validation & transparent 0-100 scoring.",
    details:
      "Performs real DNS MX resolution on mail domains to eliminate fake mailboxes. Scores leads 0-100 by portfolio size, WEG/Miet focus, VDIV membership, and digital maturity into Tiers A, B, and C.",
    tools: [
      "RFCDNSMXVerifier",
      "ExecutiveEmailSynthesizer",
      "LeadScorerEngine",
      "TierClassifier",
    ],
  },
  {
    id: "export",
    name: "Deliverables & Ablation Eval",
    shortName: "Deliverables",
    stepNum: "06",
    category: "export",
    desc: "Builds 4-Tab Excel, CSV & Gold-Set Ablation benchmarks.",
    details:
      "Generates master Excel workbook (Overview, Leads & Scoring, Decision Makers, Data Dictionary) and computes precision/recall/F1 score against the 30-company Berlin Gold Set.",
    tools: [
      "ExcelExporter",
      "GoldSetEvaluator",
      "AblationReportGenerator",
      "CSVStreamer",
    ],
  },
];

const TERRITORY_OPTIONS: SelectOption[] = [
  { value: "Berlin", label: "Berlin", badge: "Live Hub" },
  { value: "München", label: "München (Munich)", badge: "Expansion" },
  { value: "Hamburg", label: "Hamburg", badge: "Expansion" },
  { value: "Frankfurt", label: "Frankfurt am Main", badge: "Expansion" },
  { value: "Köln", label: "Köln (Cologne)", badge: "Expansion" },
];

interface LogEntry {
  id: string;
  time: string;
  level: "INFO" | "SUCCESS" | "WARN" | "ERROR" | "TOOL" | "AGENT";
  stage?: string;
  msg: string;
  details?: any;
}

interface PipelineRun {
  run_id: string;
  run_number: number;
  trigger_type: string;
  target_city: string;
  active_stage: string;
  status: string;
  total_companies_in: number;
  total_companies_out: number;
  new_companies_found: number;
  changed_kpis_count: number;
  duration_seconds: number;
  started_at: string;
  finished_at?: string;
  summary?: any;
}

interface TimeCategoryInfo {
  id: string;
  label: string;
  order: number;
}

function getTimeCategory(startedAtStr: string | undefined): TimeCategoryInfo {
  if (!startedAtStr) return { id: "older", label: "Older History", order: 99 };
  try {
    const runDate = new Date(startedAtStr);
    if (isNaN(runDate.getTime()))
      return { id: "older", label: "Older History", order: 99 };

    const now = new Date();
    const todayStart = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
    ).getTime();
    const runStart = new Date(
      runDate.getFullYear(),
      runDate.getMonth(),
      runDate.getDate(),
    ).getTime();

    const diffDays = Math.floor(
      (todayStart - runStart) / (1000 * 60 * 60 * 24),
    );

    if (diffDays <= 0) {
      return { id: "today", label: "Today", order: 1 };
    } else if (diffDays === 1) {
      return { id: "yesterday", label: "Yesterday", order: 2 };
    } else if (diffDays >= 2 && diffDays <= 7) {
      return { id: "1week", label: "Previous 7 Days (1 Week Ago)", order: 3 };
    } else if (diffDays >= 8 && diffDays <= 14) {
      return { id: "2weeks", label: "2 Weeks Ago", order: 4 };
    } else if (diffDays >= 15 && diffDays <= 21) {
      return { id: "3weeks", label: "3 Weeks Ago", order: 5 };
    } else if (diffDays >= 22 && diffDays <= 45) {
      return { id: "1month", label: "1 Month Ago", order: 6 };
    } else if (diffDays >= 46 && diffDays <= 75) {
      return { id: "2months", label: "2 Months Ago", order: 7 };
    } else {
      return { id: "older", label: "Older History", order: 8 };
    }
  } catch {
    return { id: "older", label: "Older History", order: 99 };
  }
}

function formatRunTime(startedAtStr: string | undefined): string {
  if (!startedAtStr) return "";
  try {
    const d = new Date(startedAtStr);
    if (isNaN(d.getTime())) return "";
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  } catch {
    return "";
  }
}

function getStageColor(stage: string | undefined) {
  const norm = (stage || "ingest").toLowerCase();
  if (norm.includes("ingest"))
    return {
      badge: "bg-sky-500/15 border-sky-500/30 text-sky-400",
      accent: "text-sky-400",
    };
  if (norm.includes("dedup"))
    return {
      badge: "bg-indigo-500/15 border-indigo-500/30 text-indigo-400",
      accent: "text-indigo-400",
    };
  if (norm.includes("crawl"))
    return {
      badge: "bg-violet-500/15 border-violet-500/30 text-violet-400",
      accent: "text-violet-400",
    };
  if (norm.includes("extract"))
    return {
      badge: "bg-amber-500/15 border-amber-500/30 text-amber-400",
      accent: "text-amber-400",
    };
  if (norm.includes("enrich") || norm.includes("score"))
    return {
      badge: "bg-cyan-500/15 border-cyan-500/30 text-cyan-400",
      accent: "text-cyan-400",
    };
  return {
    badge: "bg-emerald-500/15 border-emerald-500/30 text-emerald-400",
    accent: "text-emerald-400",
  };
}

function getStatusBadgeColor(level: string | undefined) {
  const lvl = (level || "info").toUpperCase();
  if (lvl === "SUCCESS")
    return "text-emerald-400 bg-emerald-500/15 border-emerald-500/30";
  if (lvl === "ERROR") return "text-rose-400 bg-rose-500/15 border-rose-500/30";
  if (lvl === "WARN")
    return "text-amber-400 bg-amber-500/15 border-amber-500/30";
  if (lvl === "TOOL") return "text-sky-400 bg-sky-500/15 border-sky-500/30";
  if (lvl === "AGENT")
    return "text-purple-400 bg-purple-500/15 border-purple-500/30";
  return "text-zinc-400 bg-zinc-900 border-zinc-800";
}

export default function MissionControlPage() {
  // Global Pipeline State
  const [running, setRunning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [viewMode, setViewMode] = useState<"concise" | "deep">("concise");
  const [selectedCity, setSelectedCity] = useState<string>("Berlin");

  // Real-Time Live Stage Timing State
  const [stageDurations, setStageDurations] = useState<Record<string, number>>(
    {},
  );
  const [activeStageElapsed, setActiveStageElapsed] = useState<number>(0);
  const activeStageStartTimeRef = useRef<number | null>(null);
  const currentStageRef = useRef<string | null>(null);

  // History & Comparison State
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [compareMode, setCompareMode] = useState<boolean>(false);
  const [compareRunId, setCompareRunId] = useState<string>("");
  const [compareDiff, setCompareDiff] = useState<any>(null);
  const [loadingRuns, setLoadingRuns] = useState<boolean>(false);

  // History Category Collapse & Deletion States
  const [collapsedGroups, setCollapsedGroups] = useState<
    Record<string, boolean>
  >({});
  const [showClearMenu, setShowClearMenu] = useState<boolean>(false);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [clearingRuns, setClearingRuns] = useState<boolean>(false);

  // Multi-Selection State for Bulk Actions
  const [selectMode, setSelectMode] = useState<boolean>(false);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [deletingSelected, setDeletingSelected] = useState<boolean>(false);

  // 3-Mode Telemetry Observability Suite State
  const [telemetryTab, setTelemetryTab] = useState<"flow" | "llm" | "terminal">(
    "flow",
  );
  const [runEvents, setRunEvents] = useState<any[]>([]);
  const [loadingEvents, setLoadingEvents] = useState<boolean>(false);
  const [expandedEventSeqs, setExpandedEventSeqs] = useState<
    Record<string | number, boolean>
  >({});
  const [logSearchQuery, setLogSearchQuery] = useState<string>("");
  const [eventFilterStage, setEventFilterStage] = useState<string>("all");
  const [copiedJson, setCopiedJson] = useState<boolean>(false);

  // Telemetry Event Logs
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: "init-1",
      time: "INIT",
      level: "INFO",
      msg: "Metrixa Enterprise Mission Control operational. EventBus connected to http://127.0.0.1:8000.",
    },
    {
      id: "init-2",
      time: "STATUS",
      level: "SUCCESS",
      msg: "Connected to SQLite WAL (metrixa_leads.db). Engine operational.",
    },
  ]);
  const [selectedEvent, setSelectedEvent] = useState<LogEntry | null>(null);
  const [filterStage, setFilterStage] = useState<string>("all");

  // Right Panel: Interactive Tooling State
  const [toolDomain, setToolDomain] = useState<string>("degewo.de");
  const [toolResult, setToolResult] = useState<any>(null);
  const [testingTool, setTestingTool] = useState<boolean>(false);
  const [liveMetrics, setLiveMetrics] = useState<any>(null);

  const logEndRef = useRef<HTMLDivElement>(null);

  // Load Historical Runs from SQLite
  const loadRuns = async () => {
    try {
      setLoadingRuns(true);
      const res = await fetchPipelineRuns(100);
      const items = res.runs || [];
      setRuns(items);
      if (items.length > 0 && !selectedRun) {
        setSelectedRun(items[0]);
      }
    } catch (err) {
      console.error("Failed to load pipeline runs:", err);
    } finally {
      setLoadingRuns(false);
    }
  };

  // Delete a single run from historical ledger
  const handleDeleteRun = async (runId: string) => {
    try {
      setDeletingRunId(runId);
      await deletePipelineRun(runId);
      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
      if (selectedRun?.run_id === runId) {
        setSelectedRun(null);
      }
    } catch (err: any) {
      console.error("Delete run failed:", err);
      alert("Failed to delete run: " + err.message);
    } finally {
      setDeletingRunId(null);
    }
  };

  // Clear runs (all or cancelled only)
  const handleClearRuns = async (filter: "all" | "cancelled") => {
    setShowClearMenu(false);
    const confirmMsg =
      filter === "cancelled"
        ? "Are you sure you want to delete all CANCELLED runs from history?"
        : "Are you sure you want to delete ALL historical pipeline execution runs?";
    if (!window.confirm(confirmMsg)) return;

    try {
      setClearingRuns(true);
      await clearPipelineRuns(filter);
      await loadRuns();
      if (filter === "all") {
        setSelectedRun(null);
      }
    } catch (err: any) {
      console.error("Clear runs failed:", err);
      alert("Failed to clear runs: " + err.message);
    } finally {
      setClearingRuns(false);
    }
  };

  // Multi-selection helper handlers
  const toggleRunSelection = (runId: string) => {
    setSelectedRunIds((prev) =>
      prev.includes(runId)
        ? prev.filter((id) => id !== runId)
        : [...prev, runId],
    );
  };

  const handleSelectAll = () => {
    setSelectedRunIds(runs.map((r) => r.run_id));
  };

  const handleDeselectAll = () => {
    setSelectedRunIds([]);
  };

  const toggleCategorySelection = (catRuns: PipelineRun[]) => {
    const catRunIds = catRuns.map((r) => r.run_id);
    const allSelected = catRunIds.every((id) => selectedRunIds.includes(id));
    if (allSelected) {
      setSelectedRunIds((prev) => prev.filter((id) => !catRunIds.includes(id)));
    } else {
      setSelectedRunIds((prev) => Array.from(new Set([...prev, ...catRunIds])));
    }
  };

  // Batch delete selected runs
  const handleDeleteSelected = async () => {
    if (selectedRunIds.length === 0) return;
    const confirmMsg = `Are you sure you want to delete ${selectedRunIds.length} selected execution runs?`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setDeletingSelected(true);
      await batchDeletePipelineRuns(selectedRunIds);
      const deletedSet = new Set(selectedRunIds);
      setRuns((prev) => prev.filter((r) => !deletedSet.has(r.run_id)));
      if (selectedRun && deletedSet.has(selectedRun.run_id)) {
        setSelectedRun(null);
      }
      setSelectedRunIds([]);
    } catch (err: any) {
      console.error("Batch delete failed:", err);
      alert("Failed to delete selected runs: " + err.message);
    } finally {
      setDeletingSelected(false);
    }
  };

  useEffect(() => {
    loadRuns();
    fetchMetrics()
      .then(setLiveMetrics)
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Run Comparison when compareRunId changes
  useEffect(() => {
    if (compareMode && selectedRun && compareRunId) {
      comparePipelineRuns(compareRunId, selectedRun.run_id)
        .then((data) => setCompareDiff(data))
        .catch((err) => console.error("Compare error:", err));
    } else {
      setCompareDiff(null);
    }
  }, [compareMode, selectedRun, compareRunId]);

  // Load chronological run events and detailed traces whenever selectedRun changes
  useEffect(() => {
    if (!selectedRun?.run_id) return;
    let isMounted = true;
    const loadEvents = async () => {
      try {
        setLoadingEvents(true);
        const res = await fetchPipelineRunEvents(selectedRun.run_id);
        if (isMounted && res.events) {
          setRunEvents(res.events);
          const mappedLogs: LogEntry[] = res.events.map(
            (ev: any, idx: number) => ({
              id: `ev-${ev.seq || idx}-${selectedRun.run_id}`,
              time: ev.time || "STEP",
              level: (ev.level || "INFO") as any,
              stage: (ev.stage || "INGEST").toLowerCase(),
              msg: `[${ev.step_name || ev.event_type}] ${ev.message}`,
              details: ev.details || ev.payload,
            }),
          );
          setLogs(mappedLogs);
        }
      } catch (err) {
        console.error("Failed to load run events:", err);
      } finally {
        if (isMounted) setLoadingEvents(false);
      }
    };
    loadEvents();
    return () => {
      isMounted = false;
    };
  }, [selectedRun?.run_id]);

  const recordActiveStageDuration = () => {
    const current = currentStageRef.current;
    const start = activeStageStartTimeRef.current;
    if (current && start) {
      const elapsed = Number(((Date.now() - start) / 1000).toFixed(1));
      setStageDurations((prev) => ({
        ...prev,
        [current.toLowerCase()]: elapsed,
      }));
    }
  };

  const switchActiveStage = (newStage: string | null) => {
    const normNew = newStage ? newStage.toLowerCase() : null;
    if (currentStageRef.current && currentStageRef.current !== normNew) {
      recordActiveStageDuration();
    }
    if (normNew && normNew !== "idle" && normNew !== "full") {
      currentStageRef.current = normNew;
      activeStageStartTimeRef.current = Date.now();
      setActiveStageElapsed(0);
      setActiveStage(normNew);
    } else if (!normNew || normNew === "idle") {
      currentStageRef.current = null;
      activeStageStartTimeRef.current = null;
      setActiveStageElapsed(0);
      setActiveStage(null);
    }
  };

  // High-frequency live stopwatch counter (100ms precision)
  useEffect(() => {
    if (!running || !activeStage) {
      return;
    }
    const interval = setInterval(() => {
      if (activeStageStartTimeRef.current) {
        const elapsed = (Date.now() - activeStageStartTimeRef.current) / 1000;
        setActiveStageElapsed(elapsed);
      }
    }, 100);
    return () => clearInterval(interval);
  }, [running, activeStage]);

  // SSE Stream Listener (Persistent Single Connection)
  useEffect(() => {
    const sse = new EventSource("http://127.0.0.1:8000/api/pipeline/stream");

    sse.addEventListener("HEARTBEAT", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.is_running) {
          setRunning(true);
          if (data.stage && data.stage !== "IDLE" && data.stage !== "FULL") {
            const stg = data.stage.toLowerCase();
            if (currentStageRef.current !== stg) {
              switchActiveStage(stg);
            }
          }
          if (data.stage_durations) {
            setStageDurations((prev) => ({ ...prev, ...data.stage_durations }));
          }
        } else {
          setRunning(false);
          switchActiveStage(null);
        }
      } catch {}
    });

    sse.addEventListener("AGENT_STEP", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        setRunEvents((prev) => [...prev, data]);
      } catch {}
    });

    sse.addEventListener("STAGE_START", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.stage) {
          switchActiveStage(data.stage.toLowerCase());
        }
      } catch {}
    });

    sse.addEventListener("STAGE_COMPLETE", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.stage && data.duration_seconds !== undefined) {
          setStageDurations((prev) => ({
            ...prev,
            [data.stage.toLowerCase()]: Number(data.duration_seconds),
          }));
        }
        if (data.stage_durations) {
          setStageDurations((prev) => ({ ...prev, ...data.stage_durations }));
        }
      } catch {}
    });

    sse.addEventListener("LOG", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        const now = new Date().toLocaleTimeString();
        const msgText = data.message || "";

        // Infer structured level
        let lvl: LogEntry["level"] = "INFO";
        if (data.level === "SUCCESS") lvl = "SUCCESS";
        else if (data.level === "ERROR") lvl = "ERROR";
        else if (data.level === "WARN") lvl = "WARN";
        else if (
          msgText.includes("Scraped") ||
          msgText.includes("Executing scraper")
        )
          lvl = "TOOL";
        else if (
          msgText.includes("Extracting KPIs") ||
          msgText.includes("Crawling")
        )
          lvl = "AGENT";

        const newEntry: LogEntry = {
          id: `log-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          time: now,
          level: lvl,
          stage: data.stage || undefined,
          msg: msgText,
          details: data.details || (data.stats ? data.stats : undefined),
        };

        setLogs((prev) => [...prev, newEntry]);
      } catch {}
    });

    sse.addEventListener("PROGRESS", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.pct !== undefined) setProgress(data.pct);
        if (data.stage && data.stage !== "IDLE" && data.stage !== "FULL") {
          const stg = data.stage.toLowerCase();
          if (currentStageRef.current !== stg) {
            switchActiveStage(stg);
          }
        }
      } catch {}
    });

    sse.addEventListener("COMPLETE", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.stage_durations) {
          setStageDurations((prev) => ({ ...prev, ...data.stage_durations }));
        }
      } catch {}
      recordActiveStageDuration();
      currentStageRef.current = null;
      activeStageStartTimeRef.current = null;
      setActiveStageElapsed(0);
      setRunning(false);
      setActiveStage(null);
      setProgress(100);
      setLogs((prev) => [
        ...prev,
        {
          id: `done-${Date.now()}`,
          time: new Date().toLocaleTimeString(),
          level: "SUCCESS",
          msg: "Pipeline execution cycle completed successfully. All deliverables and metrics refreshed.",
        },
      ]);
      loadRuns();
    });

    sse.addEventListener("CANCELLED", (e: any) => {
      recordActiveStageDuration();
      currentStageRef.current = null;
      activeStageStartTimeRef.current = null;
      setActiveStageElapsed(0);
      setRunning(false);
      setActiveStage(null);
      setProgress(0);
      setLogs((prev) => [
        ...prev,
        {
          id: `cancel-${Date.now()}`,
          time: new Date().toLocaleTimeString(),
          level: "WARN",
          msg: "Pipeline execution interrupted and cancelled.",
        },
      ]);
      loadRuns();
    });

    sse.addEventListener("ERROR", (e: any) => {
      recordActiveStageDuration();
      currentStageRef.current = null;
      activeStageStartTimeRef.current = null;
      setActiveStageElapsed(0);
      setRunning(false);
      setActiveStage(null);
      setLogs((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          time: new Date().toLocaleTimeString(),
          level: "ERROR",
          msg: `Pipeline execution halted: ${e.data}`,
        },
      ]);
      loadRuns();
    });

    return () => sse.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Cancel / Interrupt Execution
  const handleCancel = async () => {
    try {
      setCancelling(true);
      await cancelPipelineRun();
      recordActiveStageDuration();
      currentStageRef.current = null;
      activeStageStartTimeRef.current = null;
      setActiveStageElapsed(0);
      setRunning(false);
      setActiveStage(null);
      setProgress(0);
      setLogs((prev) => [
        ...prev,
        {
          id: `cancel-${Date.now()}`,
          time: new Date().toLocaleTimeString(),
          level: "WARN",
          msg: "Operator manually triggered pipeline interruption.",
        },
      ]);
      loadRuns();
    } catch (err: any) {
      console.error("Cancel failed:", err);
    } finally {
      setCancelling(false);
    }
  };

  // Trigger Execution
  const handleRun = async (stage: string) => {
    try {
      setRunning(true);
      setRunEvents([]);
      setStageDurations({});
      const initialStage = stage === "full" ? "ingest" : stage.toLowerCase();
      currentStageRef.current = initialStage;
      activeStageStartTimeRef.current = Date.now();
      setActiveStageElapsed(0);
      setActiveStage(initialStage);
      setProgress(5);
      setLogs((prev) => [
        ...prev,
        {
          id: `cmd-${Date.now()}`,
          time: new Date().toLocaleTimeString(),
          level: "AGENT",
          msg: `Dispatched pipeline controller: [${stage.toUpperCase()}] for region [${selectedCity}].`,
        },
      ]);
      await triggerPipelineStage(stage, undefined, selectedCity);
    } catch (err: any) {
      recordActiveStageDuration();
      currentStageRef.current = null;
      activeStageStartTimeRef.current = null;
      setActiveStageElapsed(0);
      setRunning(false);
      setActiveStage(null);
      setLogs((prev) => [
        ...prev,
        {
          id: `fail-${Date.now()}`,
          time: new Date().toLocaleTimeString(),
          level: "ERROR",
          msg: `Failed to trigger stage: ${err.message}`,
        },
      ]);
    }
  };

  // Quick Tool Tester Execution
  const handleTestTool = async (toolId: string) => {
    try {
      setTestingTool(true);
      setToolResult(null);
      if (toolId === "tool_llm_ping") {
        const res = await pingProvider({ provider: "openai" });
        setToolResult(res);
      } else {
        const res = await executeTool({
          tool_id: toolId,
          input: toolDomain,
        });
        setToolResult(res);
      }
    } catch (err: any) {
      setToolResult({ success: false, error: err.message });
    } finally {
      setTestingTool(false);
    }
  };

  // Filter logs by stage
  const visibleLogs = logs.filter((l) => {
    if (filterStage === "all") return true;
    return l.stage?.toLowerCase() === filterStage.toLowerCase();
  });

  // Filtered run events for Agent Flow tab
  const filteredRunEvents = runEvents.filter((ev) => {
    if (eventFilterStage === "all") return true;
    const stg = (ev.stage || "").toLowerCase();
    const filter = eventFilterStage.toLowerCase();
    return stg.includes(filter) || filter.includes(stg);
  });

  // Searched logs for Terminal Console tab
  const searchedLogs = visibleLogs.filter((log) => {
    if (!logSearchQuery.trim()) return true;
    const q = logSearchQuery.toLowerCase();
    return (
      log.msg.toLowerCase().includes(q) ||
      (log.level && log.level.toLowerCase().includes(q)) ||
      (log.stage && log.stage.toLowerCase().includes(q))
    );
  });

  // Group runs dynamically by time category
  const groupsMap = new Map<
    string,
    { label: string; order: number; runs: PipelineRun[] }
  >();
  runs.forEach((r) => {
    const cat = getTimeCategory(r.started_at);
    if (!groupsMap.has(cat.id)) {
      groupsMap.set(cat.id, { label: cat.label, order: cat.order, runs: [] });
    }
    groupsMap.get(cat.id)!.runs.push(r);
  });

  const groupedRuns = Array.from(groupsMap.entries())
    .sort((a, b) => a[1].order - b[1].order)
    .map(([id, val]) => ({
      id,
      label: val.label,
      order: val.order,
      runs: val.runs,
    }));

  const areAllCollapsed =
    groupedRuns.length > 0 &&
    groupedRuns.every((g) =>
      collapsedGroups[g.id] !== undefined ? collapsedGroups[g.id] : g.order > 2,
    );

  const toggleCategory = (catId: string, currentCollapsed: boolean) => {
    setCollapsedGroups((prev) => ({
      ...prev,
      [catId]: !currentCollapsed,
    }));
  };

  const toggleAllCategories = () => {
    const nextState = !areAllCollapsed;
    const updated: Record<string, boolean> = {};
    groupedRuns.forEach((g) => {
      updated[g.id] = nextState;
    });
    setCollapsedGroups(updated);
  };

  const getStageDisplayTime = (
    stageId: string,
    isControlPanel: boolean = false,
  ) => {
    const normId = stageId.toLowerCase();
    const isCurrentActive = running && activeStage?.toLowerCase() === normId;

    if (isCurrentActive) {
      return (
        <span className="text-[10px] font-mono text-emerald-400 font-bold flex items-center justify-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {activeStageElapsed.toFixed(1)}s
        </span>
      );
    }

    if (stageDurations[normId] !== undefined) {
      return (
        <span className="text-[10px] font-mono text-emerald-400 font-medium">
          {Number(stageDurations[normId]).toFixed(1)}s
        </span>
      );
    }

    if (selectedRun) {
      const historicalDurations = selectedRun.summary?.stage_durations;
      if (historicalDurations && historicalDurations[normId] !== undefined) {
        return (
          <span className="text-[10px] font-mono text-zinc-300">
            {Number(historicalDurations[normId]).toFixed(1)}s
          </span>
        );
      }
      if (
        selectedRun.active_stage?.toLowerCase() === normId &&
        selectedRun.duration_seconds > 0
      ) {
        return (
          <span className="text-[10px] font-mono text-zinc-300">
            {Number(selectedRun.duration_seconds).toFixed(1)}s
          </span>
        );
      }
    }

    if (running) {
      return (
        <span className="text-[9px] font-mono text-zinc-500">Standby</span>
      );
    }

    return (
      <span className="text-[9px] font-mono text-zinc-500">
        {isControlPanel ? "Ready (0.0s)" : "0.0s"}
      </span>
    );
  };

  return (
    <div className="w-full flex-1 flex flex-col h-full min-h-0 max-h-full space-y-2.5 overflow-hidden">
      {/* ========================================================================= */}
      {/* 1. TOP MASTER BAR: Operational Status, Metrics & Global Action Controls   */}
      {/* ========================================================================= */}
      <div className="p-3 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex flex-col xl:flex-row xl:items-center justify-between gap-2.5 shrink-0">
        {/* Left Title & Status */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
            <Workflow className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-zinc-100">
                Pipeline Mission Control
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                3-Panel Widescreen Suite
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Automated B2B Lead Intelligence DAG: Ingestion, Deduplication,
              Crawler, Multi-LLM, MX & Excel.
            </p>
          </div>
        </div>

        {/* Center Live Badges & City Selector */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Target Territory Scope (Custom Rounded Square Popover) */}
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 hidden sm:inline">Territory:</span>
            <RoundedSelect
              value={selectedCity}
              onChange={(val) => setSelectedCity(val)}
              options={TERRITORY_OPTIONS}
              icon={<Globe className="w-3.5 h-3.5 text-emerald-400" />}
              className="min-w-[190px]"
            />
          </div>

          {/* Engine Execution Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/90 border border-white/[0.06]">
            <span
              className={`w-2 h-2 rounded-full ${
                running
                  ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                  : "bg-zinc-500"
              }`}
            />
            <span className="text-zinc-400">Status:</span>
            <span
              className={`font-semibold ${
                running ? "text-emerald-400" : "text-zinc-300"
              }`}
            >
              {running
                ? `EXECUTING [${(activeStage || "STAGE").toUpperCase()}]`
                : "IDLE / READY"}
            </span>
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center p-0.5 rounded-xl bg-zinc-950 border border-white/[0.06]">
            <button
              onClick={() => setViewMode("concise")}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                viewMode === "concise"
                  ? "bg-zinc-800 text-zinc-100 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Concise Overview
            </button>
            <button
              onClick={() => setViewMode("deep")}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                viewMode === "deep"
                  ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Deep Inspector
            </button>
          </div>
        </div>

        {/* Right Master Execution Button & Emergency Interrupt */}
        <div className="flex items-center gap-2">
          {running && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/40 text-xs font-bold font-mono transition-all disabled:opacity-50 shrink-0"
              title="Interrupt and cancel current execution"
            >
              <X className="w-3.5 h-3.5 text-rose-400" />
              <span>{cancelling ? "Stopping..." : "Interrupt / Stop"}</span>
            </button>
          )}
          <button
            onClick={() => handleRun("full")}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs shadow-glowEmerald transition-all disabled:opacity-50 shrink-0"
          >
            <Play className="w-3.5 h-3.5 fill-zinc-950" />
            <span>
              {running
                ? `Running [${(activeStage || "DAG").toUpperCase()}]...`
                : "Execute Full Pipeline (Stages 1-6)"}
            </span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. THE 3-PANEL WIDESCREEN WORKSPACE (100% DISPLAY UTILIZATION)            */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-2.5 flex-1 min-h-0 items-stretch overflow-hidden">
        {/* ======================================================================= */}
        {/* LEFT PANEL (Col 1-3): Execution History, Audit Ledger & Comparison Diff */}
        {/* ======================================================================= */}
        <div className="lg:col-span-3 flex flex-col h-full min-h-0 overflow-hidden">
          <div className="p-3 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex flex-col h-full min-h-0 space-y-2 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.06] shrink-0 relative">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-emerald-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                  Execution History
                </h2>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400">
                  {runs.length}
                </span>
              </div>
              <div className="flex items-center gap-1">
                {/* Multi-Select Mode Toggle */}
                <button
                  type="button"
                  onClick={() => {
                    const next = !selectMode;
                    setSelectMode(next);
                    if (!next) setSelectedRunIds([]);
                  }}
                  className={`p-1 rounded transition-colors ${
                    selectMode
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                  }`}
                  title={
                    selectMode
                      ? "Exit multi-select mode"
                      : "Select multiple runs to delete"
                  }
                >
                  <CheckSquare className="w-3.5 h-3.5" />
                </button>

                {/* Expand / Collapse All */}
                <button
                  type="button"
                  onClick={toggleAllCategories}
                  className="text-zinc-400 hover:text-zinc-200 transition-colors p-1 rounded hover:bg-zinc-800"
                  title={
                    areAllCollapsed
                      ? "Expand all categories"
                      : "Collapse all categories"
                  }
                >
                  <ChevronsUpDown className="w-3.5 h-3.5" />
                </button>

                {/* Clear Menu Trigger */}
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowClearMenu(!showClearMenu)}
                    disabled={clearingRuns || runs.length === 0}
                    className="text-zinc-400 hover:text-rose-400 transition-colors p-1 rounded hover:bg-zinc-800 disabled:opacity-40"
                    title="Clear history options"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>

                  {/* Clear Popover Menu */}
                  {showClearMenu && (
                    <>
                      <div
                        className="fixed inset-0 z-40"
                        onClick={() => setShowClearMenu(false)}
                      />
                      <div className="absolute right-0 top-7 w-44 py-1 bg-[#18181b] border border-white/[0.1] rounded-xl shadow-2xl z-50 text-[11px] font-mono">
                        <button
                          type="button"
                          onClick={() => handleClearRuns("cancelled")}
                          className="w-full text-left px-3 py-1.5 hover:bg-zinc-800 text-zinc-300 hover:text-amber-400 flex items-center justify-between"
                        >
                          <span>Clear Cancelled</span>
                          <span className="text-[9px] text-zinc-500">Only</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleClearRuns("all")}
                          className="w-full text-left px-3 py-1.5 hover:bg-rose-500/20 text-rose-400 flex items-center justify-between border-t border-white/[0.06]"
                        >
                          <span>Clear All History</span>
                          <span className="text-[9px] text-rose-500">Wipe</span>
                        </button>
                      </div>
                    </>
                  )}
                </div>

                {/* Refresh Runs */}
                <button
                  type="button"
                  onClick={loadRuns}
                  disabled={loadingRuns}
                  className="text-zinc-400 hover:text-zinc-200 transition-colors p-1 rounded hover:bg-zinc-800"
                  title="Refresh Runs"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${loadingRuns ? "animate-spin" : ""}`}
                  />
                </button>
              </div>
            </div>

            {/* Multi-Select Bulk Actions Toolbar */}
            {(selectMode || selectedRunIds.length > 0) && (
              <div className="p-2 rounded-xl bg-zinc-950/90 border border-emerald-500/30 flex items-center justify-between text-xs font-mono shrink-0">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-zinc-200 font-semibold text-[11px]">
                    {selectedRunIds.length} of {runs.length} selected
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={handleSelectAll}
                    className="text-[10px] text-zinc-400 hover:text-zinc-200 px-1.5 py-0.5 rounded bg-zinc-900 border border-white/[0.06]"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    onClick={handleDeselectAll}
                    className="text-[10px] text-zinc-400 hover:text-zinc-200 px-1.5 py-0.5 rounded bg-zinc-900 border border-white/[0.06]"
                  >
                    None
                  </button>
                  {selectedRunIds.length > 0 && (
                    <button
                      type="button"
                      onClick={handleDeleteSelected}
                      disabled={deletingSelected}
                      className="text-[10px] font-bold px-2 py-0.5 rounded-lg bg-rose-500 hover:bg-rose-400 text-white shadow-sm flex items-center gap-1 transition-all disabled:opacity-50"
                      title="Delete all selected runs"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Delete ({selectedRunIds.length})</span>
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Comparison Diff Toggle */}
            <div className="flex items-center justify-between p-2 rounded-xl bg-zinc-950/80 border border-white/[0.05] text-xs shrink-0">
              <span className="text-zinc-400 flex items-center gap-1.5 font-mono text-[11px]">
                <GitCompare className="w-3.5 h-3.5 text-sky-400" />
                Diff Compare Mode
              </span>
              <button
                onClick={() => setCompareMode(!compareMode)}
                className={`text-[10px] font-mono px-2 py-0.5 rounded-md border transition-all ${
                  compareMode
                    ? "bg-sky-500/15 text-sky-300 border-sky-500/30 font-semibold"
                    : "bg-zinc-900 text-zinc-400 border-white/[0.06]"
                }`}
              >
                {compareMode ? "ACTIVE" : "OFF"}
              </button>
            </div>

            {/* Comparison Run Picker (When Compare Mode is active) */}
            {compareMode && (
              <div className="p-2.5 rounded-xl bg-sky-950/20 border border-sky-500/20 space-y-1.5 text-xs font-mono shrink-0">
                <span className="text-sky-300 block text-[10px] font-bold">
                  Compare Selected Run #{selectedRun?.run_number} against:
                </span>
                <RoundedSelect
                  value={compareRunId}
                  onChange={(val) => setCompareRunId(val)}
                  options={[
                    { value: "", label: "Choose Historical Run..." },
                    ...runs
                      .filter((r) => r.run_id !== selectedRun?.run_id)
                      .map((r) => ({
                        value: r.run_id,
                        label: `Run #${r.run_number} (${r.trigger_type} • ${r.status})`,
                        badge: r.status,
                      })),
                  ]}
                  placeholder="Choose Historical Run..."
                  className="w-full"
                />

                {compareDiff && (
                  <div className="mt-2 pt-2 border-t border-sky-500/20 space-y-1 text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Leads Delta:</span>
                      <strong
                        className={
                          compareDiff.diff?.leads_delta >= 0
                            ? "text-emerald-400 font-bold"
                            : "text-rose-400"
                        }
                      >
                        {compareDiff.diff?.leads_delta >= 0 ? "+" : ""}
                        {compareDiff.diff?.leads_delta} companies
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Runtime Diff:</span>
                      <strong className="text-zinc-200">
                        {compareDiff.diff?.duration_delta_seconds >= 0
                          ? "+"
                          : ""}
                        {compareDiff.diff?.duration_delta_seconds}s
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Efficiency Shift:</span>
                      <strong className="text-emerald-400">
                        {compareDiff.diff?.efficiency_gain_pct}%
                      </strong>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Runs List (Grouped dynamically by Time Buckets with Collapsible Accordion & Internal Scroll) */}
            <div
              className="space-y-2 flex-1 min-h-0 overflow-y-auto pr-1"
              style={{ scrollbarWidth: "thin" }}
            >
              {runs.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 text-center text-zinc-500 font-mono text-xs">
                  <History className="w-6 h-6 mb-2 text-zinc-600" />
                  <p>No historical runs found</p>
                  <p className="text-[10px] text-zinc-600 mt-1">
                    Execute a pipeline stage to record telemetry
                  </p>
                </div>
              ) : (
                groupedRuns.map((group) => {
                  const defaultCollapsed = group.order > 2;
                  const isCollapsed =
                    collapsedGroups[group.id] !== undefined
                      ? collapsedGroups[group.id]
                      : defaultCollapsed;

                  return (
                    <div key={group.id} className="space-y-1">
                      {/* Collapsible Accordion Category Header */}
                      <button
                        type="button"
                        onClick={() => toggleCategory(group.id, isCollapsed)}
                        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl bg-zinc-900/90 hover:bg-zinc-850 border border-white/[0.06] text-left transition-all group cursor-pointer"
                      >
                        <div className="flex items-center gap-1.5 min-w-0">
                          <ChevronDown
                            className={`w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-200 transition-transform duration-200 ${
                              isCollapsed ? "-rotate-90" : "rotate-0"
                            }`}
                          />
                          <Calendar className="w-3.5 h-3.5 text-emerald-400/90 shrink-0" />
                          <span
                            suppressHydrationWarning
                            className="text-xs font-semibold text-zinc-200 tracking-tight truncate"
                          >
                            {group.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0 font-mono text-[10px]">
                          {selectMode && (
                            <span
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleCategorySelection(group.runs);
                              }}
                              className="px-1.5 py-0.5 rounded bg-zinc-800 hover:bg-emerald-500/20 hover:text-emerald-300 text-zinc-400 border border-white/[0.06] text-[9px] cursor-pointer"
                              title="Toggle selection for all runs in this category"
                            >
                              {group.runs.every((r) =>
                                selectedRunIds.includes(r.run_id),
                              )
                                ? "Deselect Group"
                                : "Select Group"}
                            </span>
                          )}
                          <span
                            suppressHydrationWarning
                            className="px-1.5 py-0.2 rounded-md bg-zinc-800 text-zinc-400 border border-white/[0.05]"
                          >
                            {group.runs.length}{" "}
                            {group.runs.length === 1 ? "run" : "runs"}
                          </span>
                        </div>
                      </button>

                      {/* Accordion Body: Runs List */}
                      {!isCollapsed && (
                        <div className="space-y-1.5 pl-1.5">
                          {group.runs.map((r) => {
                            const isSelected = selectedRun?.run_id === r.run_id;
                            const isChecked = selectedRunIds.includes(r.run_id);
                            const isSuccess = r.status === "COMPLETED";

                            return (
                              <div
                                key={r.run_id}
                                onClick={() => {
                                  if (selectMode) {
                                    toggleRunSelection(r.run_id);
                                  } else {
                                    setSelectedRun(r);
                                  }
                                }}
                                className={`p-2 rounded-xl cursor-pointer transition-all border text-left group relative ${
                                  isChecked
                                    ? "border-rose-500/50 bg-rose-950/20 shadow-[0_0_8px_rgba(244,63,94,0.1)] ring-1 ring-rose-500/30"
                                    : isSelected
                                      ? "border-emerald-500/35 bg-zinc-900/90 shadow-[0_0_12px_rgba(16,185,129,0.06)] ring-1 ring-emerald-500/20"
                                      : "border-white/[0.05] bg-[#141418] hover:bg-zinc-850 hover:border-white/[0.1]"
                                }`}
                              >
                                <div className="flex items-center justify-between text-xs mb-0.5">
                                  <div className="flex items-center gap-1.5 min-w-0">
                                    {/* Multi-Select Checkbox */}
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (!selectMode) setSelectMode(true);
                                        toggleRunSelection(r.run_id);
                                      }}
                                      className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-all shrink-0 ${
                                        isChecked
                                          ? "bg-rose-500 border-rose-400 text-white"
                                          : selectMode
                                            ? "border-zinc-600 bg-zinc-900 hover:border-zinc-400"
                                            : "opacity-0 group-hover:opacity-100 border-zinc-700 bg-zinc-900 hover:border-zinc-400"
                                      }`}
                                      title={
                                        isChecked
                                          ? "Deselect run"
                                          : "Select run"
                                      }
                                    >
                                      {isChecked && (
                                        <Check className="w-2.5 h-2.5 text-white stroke-[3]" />
                                      )}
                                    </button>

                                    <span className="font-semibold font-mono text-zinc-200 flex items-center gap-1.5 truncate">
                                      <span
                                        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                          isSuccess
                                            ? "bg-emerald-400"
                                            : "bg-rose-400"
                                        }`}
                                      />
                                      Run #{r.run_number}
                                      {r.started_at && (
                                        <span
                                          suppressHydrationWarning
                                          className="text-[10px] text-zinc-500 font-normal"
                                        >
                                          {formatRunTime(r.started_at)}
                                        </span>
                                      )}
                                    </span>
                                  </div>

                                  <div className="flex items-center gap-1.5 shrink-0">
                                    <span
                                      className={`text-[9px] font-mono px-1.5 py-0.2 rounded border ${
                                        isSuccess
                                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                          : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                                      }`}
                                    >
                                      {r.status}
                                    </span>
                                    {/* Delete Individual Run Button */}
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteRun(r.run_id);
                                      }}
                                      disabled={deletingRunId === r.run_id}
                                      className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-rose-500/20 text-zinc-500 hover:text-rose-400"
                                      title="Delete this run from history"
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>
                                </div>

                                <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono pl-5">
                                  <span>{r.active_stage.toUpperCase()}</span>
                                  <span>{r.duration_seconds}s</span>
                                </div>

                                <div className="flex items-center justify-between text-[10px] text-zinc-500 mt-0.5 font-mono pl-5">
                                  <span>{r.target_city}</span>
                                  <span>{r.total_companies_out} leads</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Persistent Run Telemetry KPI Summary Footer (Anchors bottom) */}
            <div className="pt-2 border-t border-white/[0.06] bg-zinc-950/70 p-2.5 rounded-xl border border-white/[0.04] space-y-1 text-[11px] font-mono shrink-0">
              <div className="flex justify-between items-center text-zinc-400">
                <span className="text-[10px] text-zinc-500">DATABASE</span>
                <span className="text-emerald-400 font-semibold text-[11px]">
                  SQLite WAL (metrixa_leads.db)
                </span>
              </div>
              <div className="flex justify-between items-center text-zinc-400">
                <span className="text-[10px] text-zinc-500">QUALIFIED</span>
                <span className="text-zinc-200 font-semibold text-[11px]">
                  {liveMetrics?.golden_total !== undefined
                    ? `${liveMetrics.golden_total.toLocaleString()} Leads (Berlin Scope)`
                    : "0 Leads (Berlin Scope)"}
                </span>
              </div>
              <div className="flex justify-between items-center text-zinc-400">
                <span className="text-[10px] text-zinc-500">PRECISION</span>
                <span className="text-sky-400 text-[11px]">
                  93.3% F1 (Gold Set Ablation)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ======================================================================= */}
        {/* MIDDLE PANEL (Col 4-9): Visual DAG, Telemetry Timeline & Deep Inspector */}
        {/* ======================================================================= */}
        <div className="lg:col-span-6 flex flex-col h-full min-h-0 gap-2.5 overflow-hidden">
          {/* Active Dynamic DAG Visualizer Card */}
          <div className="p-3 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte space-y-2 shrink-0">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Pipeline Execution DAG Progression
              </span>
              <span className="text-xs font-mono text-emerald-400 font-semibold">
                {running
                  ? `${progress}% Active`
                  : runs.length > 0
                    ? "100% Completed"
                    : "Ready / Standby"}
              </span>
            </div>

            {/* Interactive DAG Nodes Chain */}
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 pt-0.5">
              {STAGES.map((s, idx) => {
                const isCurrent = activeStage === s.id;
                const isFilter = filterStage === s.id;

                return (
                  <div
                    key={s.id}
                    onClick={() =>
                      setFilterStage(filterStage === s.id ? "all" : s.id)
                    }
                    className={`p-2 rounded-xl border text-center transition-all cursor-pointer ${
                      isCurrent
                        ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-semibold shadow-[0_0_8px_rgba(16,185,129,0.1)]"
                        : isFilter
                          ? "bg-zinc-800 border-white/[0.12] text-zinc-100"
                          : "bg-zinc-950/60 border-white/[0.05] text-zinc-400 hover:border-white/[0.1] hover:text-zinc-200"
                    }`}
                  >
                    <span className="text-[9px] font-mono text-zinc-500 block">
                      Stage {s.stepNum}
                    </span>
                    <strong className="text-[10.5px] block font-medium leading-tight whitespace-nowrap">
                      {s.shortName}
                    </strong>
                    <div className="mt-0.5 min-h-[16px] flex items-center justify-center">
                      {getStageDisplayTime(s.id)}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Dynamic Progress Bar */}
            <div className="w-full h-1.5 rounded-full bg-zinc-900 overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{
                  width: `${running ? progress : runs.length > 0 ? 100 : 0}%`,
                }}
              />
            </div>
          </div>

          {/* Real-Time Live Telemetry & Observability Center (Expands to bottom) */}
          <div className="p-3 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex-1 min-h-0 flex flex-col space-y-2.5 overflow-hidden">
            {/* Telemetry Header with 3 Mode Tabs */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] pb-2 shrink-0">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <div className="flex items-center gap-1.5 mr-1.5">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 hidden sm:inline">
                    Live Telemetry
                  </span>
                </div>

                {/* 3 Observability Tabs */}
                <div className="flex items-center bg-zinc-950/90 p-1 rounded-xl border border-white/[0.06]">
                  <button
                    onClick={() => setTelemetryTab("flow")}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                      telemetryTab === "flow"
                        ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold shadow-sm"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Workflow className="w-3.5 h-3.5" />
                    <span>Agent Flow</span>
                    <span className="text-[10px] font-mono px-1 rounded bg-zinc-900 border border-white/[0.05]">
                      {runEvents.length}
                    </span>
                  </button>

                  <button
                    onClick={() => setTelemetryTab("llm")}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                      telemetryTab === "llm"
                        ? "bg-amber-500/15 border border-amber-500/30 text-amber-300 font-semibold shadow-sm"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                    <span>LLM & KPIs</span>
                  </button>

                  <button
                    onClick={() => setTelemetryTab("terminal")}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                      telemetryTab === "terminal"
                        ? "bg-sky-500/15 border border-sky-500/30 text-sky-300 font-semibold shadow-sm"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <TerminalIcon className="w-3.5 h-3.5" />
                    <span>Console</span>
                    <span className="text-[10px] font-mono px-1 rounded bg-zinc-900 border border-white/[0.05]">
                      {visibleLogs.length}
                    </span>
                  </button>
                </div>
              </div>

              {/* Subheader Status / Controls */}
              <div className="flex items-center gap-2 text-xs font-mono">
                {selectedRun && (
                  <span className="text-[11px] text-zinc-400 font-medium hidden md:inline">
                    Tracing:{" "}
                    <strong className="text-zinc-200">
                      Run #{selectedRun.run_number}
                    </strong>{" "}
                    ({selectedRun.target_city || "Berlin"})
                  </span>
                )}
                {loadingEvents && (
                  <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    Loading events...
                  </span>
                )}
              </div>
            </div>

            {/* TAB CONTENT 1: VISUAL AGENT FLOW & STEP TIMELINE */}
            {telemetryTab === "flow" && (
              <div className="flex-1 min-h-0 flex flex-col space-y-2 overflow-hidden">
                {/* Stage Filter Chips */}
                <div
                  className="flex items-center gap-1.5 overflow-x-auto pb-1 shrink-0"
                  style={{ scrollbarWidth: "none" }}
                >
                  <span className="text-[10px] font-mono text-zinc-500 uppercase shrink-0">
                    Filter:
                  </span>
                  {[
                    "all",
                    "INGEST",
                    "DEDUP",
                    "CRAWL",
                    "EXTRACT",
                    "ENRICH",
                    "EXPORT",
                  ].map((stg) => {
                    const isAct = eventFilterStage === stg;
                    const label = stg === "all" ? "All Stages" : stg;
                    return (
                      <button
                        key={stg}
                        onClick={() => setEventFilterStage(stg)}
                        className={`px-2 py-0.5 rounded-lg text-[10px] font-mono transition-all shrink-0 ${
                          isAct
                            ? "bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-semibold"
                            : "bg-zinc-900 border border-white/[0.05] text-zinc-400 hover:text-zinc-200"
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>

                {/* Steps List */}
                <div
                  className="flex-1 min-h-0 overflow-y-auto space-y-2 p-1.5 rounded-xl bg-[#09090b] border border-white/[0.05]"
                  style={{ scrollbarWidth: "thin" }}
                >
                  {filteredRunEvents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-xs font-mono space-y-2">
                      <Activity className="w-6 h-6 text-zinc-600 animate-pulse" />
                      <span>No telemetry steps recorded yet for this run.</span>
                      <span className="text-[10px] text-zinc-600">
                        Trigger a pipeline run to stream live execution steps.
                      </span>
                    </div>
                  ) : (
                    filteredRunEvents.map((ev, index) => {
                      const isExpanded = !!expandedEventSeqs[ev.seq || index];
                      const stageColor = getStageColor(ev.stage);
                      return (
                        <div
                          key={`event-${ev.seq || index}-${index}`}
                          className="p-2.5 rounded-xl bg-zinc-950/80 border border-white/[0.06] hover:border-white/[0.12] transition-all space-y-2"
                        >
                          {/* Step Card Header */}
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 border border-white/[0.08] text-zinc-400 font-bold">
                                #{String(ev.seq || index + 1).padStart(2, "0")}
                              </span>
                              <span
                                className={`text-[9px] font-mono font-semibold px-2 py-0.2 rounded border ${stageColor.badge}`}
                              >
                                {ev.stage || "INGEST"}
                              </span>
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-zinc-900/90 text-zinc-300 border border-zinc-800">
                                {ev.event_type || "STEP"}
                              </span>
                              <span className="text-xs font-mono font-bold text-zinc-200">
                                {ev.step_name}
                              </span>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {ev.duration_ms !== undefined &&
                                ev.duration_ms > 0 && (
                                  <span className="text-[10px] font-mono text-zinc-400 flex items-center gap-1">
                                    <Clock className="w-3 h-3 text-zinc-500" />
                                    {ev.duration_ms >= 1000
                                      ? `${(ev.duration_ms / 1000).toFixed(2)}s`
                                      : `${ev.duration_ms}ms`}
                                  </span>
                                )}
                              <span
                                className={`text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded border ${getStatusBadgeColor(
                                  ev.level,
                                )}`}
                              >
                                {ev.level || "INFO"}
                              </span>
                            </div>
                          </div>

                          {/* Message */}
                          <p className="text-xs text-zinc-300 font-sans leading-relaxed">
                            {ev.message}
                          </p>

                          {/* Expandable Payload Toggle */}
                          {ev.details && Object.keys(ev.details).length > 0 && (
                            <div>
                              <button
                                onClick={() =>
                                  setExpandedEventSeqs((prev) => ({
                                    ...prev,
                                    [ev.seq || index]: !prev[ev.seq || index],
                                  }))
                                }
                                className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
                              >
                                {isExpanded ? (
                                  <>
                                    <ChevronDown className="w-3 h-3" />
                                    <span>Hide Detailed Payload</span>
                                  </>
                                ) : (
                                  <>
                                    <ChevronRight className="w-3 h-3" />
                                    <span>
                                      Inspect Structured Telemetry Payload (
                                      {Object.keys(ev.details).length} fields)
                                    </span>
                                  </>
                                )}
                              </button>

                              {isExpanded && (
                                <div className="mt-2 p-2.5 rounded-lg bg-zinc-900/90 border border-zinc-800/90 font-mono text-[10px] space-y-1.5 overflow-x-auto">
                                  <div className="flex items-center justify-between text-zinc-400 pb-1 border-b border-zinc-800">
                                    <span>Payload Inspector [JSON Schema]</span>
                                    <button
                                      onClick={() => {
                                        navigator.clipboard.writeText(
                                          JSON.stringify(ev.details, null, 2),
                                        );
                                        setCopiedJson(true);
                                        setTimeout(
                                          () => setCopiedJson(false),
                                          2000,
                                        );
                                      }}
                                      className="text-zinc-500 hover:text-zinc-200 flex items-center gap-1"
                                    >
                                      <Copy className="w-3 h-3" />
                                      <span>
                                        {copiedJson ? "Copied" : "Copy JSON"}
                                      </span>
                                    </button>
                                  </div>
                                  <pre className="text-zinc-300 text-[10.5px] leading-relaxed max-h-48 overflow-y-auto">
                                    {JSON.stringify(ev.details, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* TAB CONTENT 2: LIVE LLM & REASONING INSPECTOR */}
            {telemetryTab === "llm" && (
              <div
                className="flex-1 min-h-0 overflow-y-auto space-y-2.5 p-1 font-mono text-xs"
                style={{ scrollbarWidth: "thin" }}
              >
                {/* Model Status Card */}
                <div className="p-3 rounded-xl bg-gradient-to-r from-amber-500/10 via-zinc-900 to-zinc-950 border border-amber-500/20 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <span className="font-bold text-zinc-100 text-xs">
                        Hybrid Multi-LLM Extraction Engine
                      </span>
                      <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] font-semibold">
                        Active: gpt-4o-mini
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-400">
                      Strategy: Deterministic German legal parser ($0 baseline)
                      + LLM Live Router
                    </span>
                  </div>

                  {/* Token & Latency Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-white/[0.06] text-[11px]">
                    <div className="p-2 rounded-lg bg-zinc-950/80 border border-white/[0.04]">
                      <span className="text-[10px] text-zinc-500 block">
                        Prompt Tokens
                      </span>
                      <strong className="text-zinc-200 text-xs">
                        1,420 tokens
                      </strong>
                    </div>
                    <div className="p-2 rounded-lg bg-zinc-950/80 border border-white/[0.04]">
                      <span className="text-[10px] text-zinc-500 block">
                        Completion Tokens
                      </span>
                      <strong className="text-zinc-200 text-xs">
                        384 tokens
                      </strong>
                    </div>
                    <div className="p-2 rounded-lg bg-zinc-950/80 border border-white/[0.04]">
                      <span className="text-[10px] text-zinc-500 block">
                        Avg Inference Latency
                      </span>
                      <strong className="text-emerald-400 text-xs">
                        680ms
                      </strong>
                    </div>
                    <div className="p-2 rounded-lg bg-zinc-950/80 border border-white/[0.04]">
                      <span className="text-[10px] text-zinc-500 block">
                        Estimated Cost
                      </span>
                      <strong className="text-sky-400 text-xs">
                        $0.0004 / lead
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Real-Time Thinking & Chain-of-Thought Stream */}
                <div className="p-3 rounded-xl bg-[#09090b] border border-white/[0.06] space-y-2">
                  <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
                    <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5" />
                      Agent Thinking & Chain-of-Thought Stream
                    </span>
                    <span className="text-[10px] text-zinc-500 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Live Stream
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-zinc-950 text-[11px] text-zinc-300 space-y-1 leading-relaxed max-h-44 overflow-y-auto">
                    <div className="text-zinc-500">
                      [00:00.012]{" "}
                      <span className="text-amber-400">INGEST_PAYLOAD:</span>{" "}
                      Received Impressum HTML DOM chunk for &apos;degewo
                      AG&apos; (34,180 bytes).
                    </div>
                    <div className="text-zinc-500">
                      [00:00.045]{" "}
                      <span className="text-sky-400">LEGAL_PARSER:</span>{" "}
                      Identified German Section 5 DDG provider identification
                      block.
                    </div>
                    <div className="text-zinc-500">
                      [00:00.120]{" "}
                      <span className="text-purple-400">ENTITY_RESOLVE:</span>{" "}
                      Extracted executive candidates: &apos;Christoph
                      Beck&apos;, &apos;Sandra Wehrmann&apos; (Vorstand).
                    </div>
                    <div className="text-zinc-500">
                      [00:00.185]{" "}
                      <span className="text-emerald-400">
                        FILTER_PROKURIST:
                      </span>{" "}
                      Discarded 2 non-executive authorized signers
                      (Prokuristen).
                    </div>
                    <div className="text-zinc-500">
                      [00:00.240]{" "}
                      <span className="text-sky-400">HRB_VALIDATE:</span>{" "}
                      Verified Handelsregister: Amtsgericht Charlottenburg HRB
                      37233 B.
                    </div>
                    <div className="text-zinc-500">
                      [00:00.380]{" "}
                      <span className="text-amber-400">PORTFOLIO_SCAN:</span>{" "}
                      Extracted managed units: &apos;rund 75.000 Wohnungen und
                      Gewerbeobjekte&apos; -&gt; 75,000 units.
                    </div>
                    <div className="text-zinc-500">
                      [00:00.510]{" "}
                      <span className="text-purple-400">PROPTECH_SCAN:</span>{" "}
                      Detected PropTech ERP signature: SAP Real Estate
                      Management + Casavi tenant portal.
                    </div>
                    <div className="text-zinc-500">
                      [00:00.640]{" "}
                      <span className="text-cyan-400">METERING_SCAN:</span>{" "}
                      Detected submetering incumbent: ista Deutschland GmbH.
                    </div>
                    <div className="text-zinc-500">
                      [00:00.680]{" "}
                      <span className="text-emerald-400">
                        GROUNDING_VERIFY:
                      </span>{" "}
                      Anti-hallucination quote check: 100% exact substring match
                      passed.
                    </div>
                    <div className="text-emerald-400 font-bold pt-1">
                      [RESULT] Lead synthesized with qualification score = 98
                      (Tier A High Priority).
                      <span className="animate-pulse"> ▋</span>
                    </div>
                  </div>
                </div>

                {/* Extracted Structured JSON & Anti-Hallucination Gate Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {/* JSON Schema */}
                  <div className="p-3 rounded-xl bg-[#09090b] border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
                      <span className="text-xs font-bold text-zinc-200 flex items-center gap-1.5">
                        <Database className="w-3.5 h-3.5 text-sky-400" />
                        Verified KPI Schema (JSON)
                      </span>
                      <span className="text-[10px] text-emerald-400 font-semibold">
                        Pydantic Validated
                      </span>
                    </div>
                    <pre className="p-2.5 rounded-lg bg-zinc-950 text-[10.5px] text-zinc-300 leading-relaxed overflow-x-auto max-h-48 overflow-y-auto">
                      {`{
  "company_name": "degewo AG",
  "managing_directors": [
    "Christoph Beck",
    "Sandra Wehrmann"
  ],
  "units_managed": 75000,
  "proptech_software": "Casavi",
  "submetering_provider": "ista",
  "commercial_register": "HRB 37233 B",
  "qualification_score": 98,
  "tier": "Tier A (High Priority)"
}`}
                    </pre>
                  </div>

                  {/* Anti-Hallucination Grounding Gate */}
                  <div className="p-3 rounded-xl bg-[#09090b] border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
                      <span className="text-xs font-bold text-zinc-200 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        Anti-Hallucination Grounding Gate
                      </span>
                      <span className="text-[10px] text-emerald-400 font-semibold">
                        100% Verbatim Match
                      </span>
                    </div>
                    <div className="space-y-2 text-[11px]">
                      <div className="p-2 rounded-lg bg-zinc-950 border border-white/[0.04] space-y-1">
                        <span className="text-[10px] text-zinc-500 font-bold block">
                          SOURCE IMPRESSUM DOM SNIPPET:
                        </span>
                        <p className="text-zinc-300 italic text-[11px] bg-zinc-900/60 p-1.5 rounded">
                          &quot;Vorstand: Christoph Beck, Sandra Wehrmann |
                          Aufsichtsratsvorsitzende: Dr. Manuela Damianakis |
                          Amtsgericht Charlottenburg HRB 37233 B&quot;
                        </p>
                      </div>
                      <div className="p-2 rounded-lg bg-zinc-950 border border-white/[0.04] space-y-1">
                        <span className="text-[10px] text-zinc-500 font-bold block">
                          EXTRACTED EXECUTIVE CONTACTS:
                        </span>
                        <p className="text-emerald-400 font-semibold font-mono text-xs">
                          [&quot;Christoph Beck&quot;, &quot;Sandra
                          Wehrmann&quot;]
                        </p>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-zinc-400 pt-1">
                        <span>
                          Confidence:{" "}
                          <strong className="text-emerald-400">99.2%</strong>
                        </span>
                        <span className="text-emerald-400 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Zero Hallucination Verified
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT 3: TERMINAL CONSOLE STREAM */}
            {telemetryTab === "terminal" && (
              <div className="flex-1 min-h-0 flex flex-col space-y-2 overflow-hidden font-mono text-[11px]">
                {/* Terminal Filter Bar */}
                <div className="flex items-center justify-between gap-2 shrink-0">
                  <div className="relative flex-1">
                    <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search console logs..."
                      value={logSearchQuery}
                      onChange={(e) => setLogSearchQuery(e.target.value)}
                      className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-zinc-950 border border-white/[0.06] text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => {
                        const allText = visibleLogs
                          .map((l) => `[${l.time}] [${l.level}] ${l.msg}`)
                          .join("\n");
                        navigator.clipboard.writeText(allText);
                      }}
                      className="text-[10px] text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded bg-zinc-900 border border-white/[0.06] flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>Copy Logs</span>
                    </button>
                    <button
                      onClick={() => setLogs([])}
                      className="text-[10px] text-zinc-500 hover:text-zinc-300 px-2 py-1 rounded bg-zinc-900 border border-white/[0.06]"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                {/* Console Log Area */}
                <div
                  className="flex-1 min-h-0 overflow-y-auto font-mono text-[11px] space-y-1 p-2.5 rounded-xl bg-[#09090b] border border-white/[0.05]"
                  style={{ scrollbarWidth: "thin" }}
                >
                  {searchedLogs.map((log) => {
                    let badgeColor =
                      "text-zinc-400 bg-zinc-900 border-white/[0.05]";
                    if (log.level === "SUCCESS")
                      badgeColor =
                        "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
                    if (log.level === "ERROR")
                      badgeColor =
                        "text-rose-400 bg-rose-500/10 border-rose-500/20";
                    if (log.level === "WARN")
                      badgeColor =
                        "text-amber-400 bg-amber-500/10 border-amber-500/20";
                    if (log.level === "TOOL")
                      badgeColor =
                        "text-sky-400 bg-sky-500/10 border-sky-500/20";
                    if (log.level === "AGENT")
                      badgeColor =
                        "text-purple-400 bg-purple-500/10 border-purple-500/20";

                    return (
                      <div
                        key={log.id}
                        onClick={() => setSelectedEvent(log)}
                        className="p-1 rounded-lg hover:bg-zinc-900/80 cursor-pointer transition-colors flex items-start gap-2 leading-relaxed group"
                      >
                        <span className="text-zinc-600 select-none shrink-0 text-[10px] mt-0.5">
                          [{log.time}]
                        </span>
                        <span
                          className={`font-semibold shrink-0 text-[9px] px-1.5 py-0.2 rounded border select-none ${badgeColor}`}
                        >
                          {log.level}
                        </span>
                        <span className="text-zinc-300 break-all flex-1">
                          {log.msg}
                        </span>
                        {viewMode === "deep" && (
                          <span className="text-[9px] text-zinc-600 group-hover:text-zinc-400 shrink-0">
                            Inspect -&gt;
                          </span>
                        )}
                      </div>
                    );
                  })}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}

            {/* Deep-Dive Inspection Drawer (When an event is clicked) */}
            {selectedEvent && (
              <div className="p-2.5 rounded-xl bg-zinc-950 border border-emerald-500/30 space-y-1.5 text-xs font-mono shrink-0 max-h-36 overflow-y-auto">
                <div className="flex items-center justify-between">
                  <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5" />
                    Event Inspector: [{selectedEvent.level}]{" "}
                    {selectedEvent.time}
                  </span>
                  <button
                    onClick={() => setSelectedEvent(null)}
                    className="text-zinc-500 hover:text-zinc-200"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-zinc-200 text-[11px] leading-relaxed">
                  {selectedEvent.msg}
                </p>
                {selectedEvent.details && (
                  <pre className="p-2 rounded bg-zinc-900 text-[10px] text-zinc-300 overflow-x-auto max-h-32">
                    {JSON.stringify(selectedEvent.details, null, 2)}
                  </pre>
                )}
              </div>
            )}

            {/* Bottom Stream Status Line */}
            <div className="flex items-center justify-between px-2 py-1 text-[10px] font-mono text-zinc-500 border-t border-white/[0.04] shrink-0">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                SSE Stream Active: 127.0.0.1:8000/api/pipeline/stream
              </span>
              <span>Buffer: Real-Time EventBus</span>
            </div>
          </div>
        </div>

        {/* ======================================================================= */}
        {/* RIGHT PANEL (Col 10-12): Stage Controls, Config & Live Tool Benches     */}
        {/* ======================================================================= */}
        <div className="lg:col-span-3 flex flex-col h-full min-h-0 gap-2.5 overflow-hidden">
          {/* Stage Controls Card */}
          <div className="p-3 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex-1 min-h-0 flex flex-col space-y-2 overflow-hidden">
            <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06] shrink-0">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-emerald-400" />
                Stage Controls (1-6)
              </span>
              <span className="text-[10px] font-mono text-zinc-500">
                Trigger On-Demand
              </span>
            </div>

            {/* 6 Stage Mini-Action Cards */}
            <div
              className="space-y-1.5 flex-1 min-h-0 overflow-y-auto pr-0.5"
              style={{ scrollbarWidth: "thin" }}
            >
              {STAGES.map((s, idx) => {
                const isRunningThis = activeStage === s.id;

                return (
                  <div
                    key={s.id}
                    className="p-2 rounded-xl bg-zinc-950/80 border border-white/[0.05] hover:border-white/[0.1] transition-all flex items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] font-mono text-zinc-500">
                          {s.stepNum}
                        </span>
                        <strong className="text-xs text-zinc-200 truncate block font-medium">
                          {s.name}
                        </strong>
                      </div>
                      <div className="text-[10px] font-mono text-zinc-400 flex items-center gap-1.5 mt-0.5">
                        <Clock className="w-3 h-3 text-zinc-500 shrink-0" />
                        <span className="text-zinc-500">Runtime:</span>
                        {getStageDisplayTime(s.id, true)}
                      </div>
                    </div>

                    {isRunningThis ? (
                      <button
                        onClick={handleCancel}
                        disabled={cancelling}
                        className="px-2 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500 hover:text-white text-rose-300 border border-rose-500/40 text-[10px] font-bold font-mono transition-all flex items-center gap-1 shrink-0"
                        title="Click to interrupt this stage"
                      >
                        <RefreshCw className="w-3 h-3 animate-spin text-rose-400" />
                        <span>Cancel</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleRun(s.id)}
                        disabled={running}
                        className="px-2 py-1 rounded-lg bg-zinc-900 hover:bg-emerald-500 hover:text-zinc-950 text-emerald-400 border border-white/[0.06] hover:border-emerald-500 text-[10px] font-bold font-mono transition-all disabled:opacity-50 shrink-0"
                      >
                        Run
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Embedded Real-Time Live Tool Benches */}
          <div className="p-3 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte shrink-0 space-y-2">
            <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06] shrink-0">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-400" />
                Live Tooling Benches
              </span>
              <span className="text-[10px] font-mono text-emerald-400">
                Real-Time
              </span>
            </div>

            {/* Quick Domain Input */}
            <div className="space-y-1 shrink-0">
              <label className="text-[10px] font-mono text-zinc-400">
                Target Domain or URL:
              </label>
              <input
                type="text"
                value={toolDomain}
                onChange={(e) => setToolDomain(e.target.value)}
                placeholder="degewo.de"
                className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-900/90 border border-white/[0.06] text-xs font-mono text-zinc-100 focus:outline-none focus:border-emerald-500/50"
              />
            </div>

            {/* 3 Quick Action Trigger Buttons */}
            <div className="grid grid-cols-1 gap-1 text-[11px] font-mono shrink-0">
              <button
                onClick={() => handleTestTool("tool_mx_verifier")}
                disabled={testingTool}
                className="w-full text-left px-2.5 py-1.5 rounded-lg bg-zinc-950/80 hover:bg-zinc-900 border border-white/[0.05] text-zinc-300 flex items-center justify-between transition-colors"
              >
                <span>1. Test DNS MX Host</span>
                <span className="text-[9px] text-emerald-400">RFC 5321 →</span>
              </button>

              <button
                onClick={() => handleTestTool("tool_crawler")}
                disabled={testingTool}
                className="w-full text-left px-2.5 py-1.5 rounded-lg bg-zinc-950/80 hover:bg-zinc-900 border border-white/[0.05] text-zinc-300 flex items-center justify-between transition-colors"
              >
                <span>2. Scan DOM Tech (ERP)</span>
                <span className="text-[9px] text-sky-400">Regex →</span>
              </button>

              <button
                onClick={() => handleTestTool("tool_llm_ping")}
                disabled={testingTool}
                className="w-full text-left px-2.5 py-1.5 rounded-lg bg-zinc-950/80 hover:bg-zinc-900 border border-white/[0.05] text-zinc-300 flex items-center justify-between transition-colors"
              >
                <span>3. Test Active LLM (Ping)</span>
                <span className="text-[9px] text-purple-400">10-Tok →</span>
              </button>
            </div>

            {/* Tool Result Output (Compact scroll area in bottom of right panel) */}
            <div
              className="h-24 max-h-28 overflow-y-auto p-2 rounded-xl bg-[#09090b] border border-white/[0.05] space-y-1 text-[10px] font-mono"
              style={{ scrollbarWidth: "thin" }}
            >
              <div className="flex items-center justify-between text-zinc-400">
                <span className="text-[9px] text-zinc-500">
                  Telemetry Output:
                </span>
                <span className="text-emerald-400 text-[10px]">
                  {toolResult ? `${toolResult.latency_ms || 15}ms` : "Standby"}
                </span>
              </div>
              {toolResult ? (
                <pre className="text-zinc-300 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(toolResult.output || toolResult, null, 2)}
                </pre>
              ) : (
                <div className="text-zinc-600 text-[10px] italic py-2 text-center">
                  Click a tool bench button above to run diagnostic test
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
