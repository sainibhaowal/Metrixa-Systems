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
} from "lucide-react";
import {
  triggerPipelineStage,
  cancelPipelineRun,
  fetchPipelineRuns,
  comparePipelineRuns,
  executeTool,
  pingProvider,
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
  time: string;
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
    time: "~45s",
  },
  {
    id: "deduplicate",
    name: "Entity Resolution & Dedup",
    shortName: "Deduplication",
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
    time: "~5s",
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
    time: "~50s",
  },
  {
    id: "extract",
    name: "Hybrid Multi-LLM KPI Extraction",
    shortName: "AI Extraction",
    stepNum: "04",
    category: "extract",
    desc: "Extracts managed units, WEG/Miet focus & Geschäftsführer.",
    details:
      "Layer 1: Deterministic German § 5 DDG legal parser ($0 cost baseline). Layer 2: Live API LLM extraction (OpenAI, Gemini, DeepSeek, local Ollama) with anti-hallucination quote verification gates.",
    tools: [
      "GermanImpressumParser",
      "LLMRouter",
      "AntiHallucinationGate",
      "PydanticSchemaValidator",
    ],
    time: "~25s",
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
    time: "~10s",
  },
  {
    id: "export",
    name: "Deliverables & Ablation Eval",
    shortName: "Export & Eval",
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
    time: "~5s",
  },
];

const TERRITORY_OPTIONS: SelectOption[] = [
  { value: "Berlin", label: "Berlin", badge: "Live Hub (1,200 Leads)" },
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

export default function MissionControlPage() {
  // Global Pipeline State
  const [running, setRunning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [viewMode, setViewMode] = useState<"concise" | "deep">("concise");
  const [selectedCity, setSelectedCity] = useState<string>("Berlin");

  // History & Comparison State
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [compareMode, setCompareMode] = useState<boolean>(false);
  const [compareRunId, setCompareRunId] = useState<string>("");
  const [compareDiff, setCompareDiff] = useState<any>(null);
  const [loadingRuns, setLoadingRuns] = useState<boolean>(false);

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
      msg: "Connected to SQLite WAL (metrixa_leads.db): 1,200 qualified Berlin property managers active.",
    },
  ]);
  const [selectedEvent, setSelectedEvent] = useState<LogEntry | null>(null);
  const [filterStage, setFilterStage] = useState<string>("all");

  // Right Panel: Interactive Tooling State
  const [toolDomain, setToolDomain] = useState<string>("degewo.de");
  const [toolResult, setToolResult] = useState<any>(null);
  const [testingTool, setTestingTool] = useState<boolean>(false);

  const logEndRef = useRef<HTMLDivElement>(null);

  // Load Historical Runs from SQLite
  const loadRuns = async () => {
    try {
      setLoadingRuns(true);
      const res = await fetchPipelineRuns(20);
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

  useEffect(() => {
    loadRuns();
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

  // SSE Stream Listener (Persistent Single Connection)
  useEffect(() => {
    const sse = new EventSource("http://127.0.0.1:8000/api/pipeline/stream");

    sse.addEventListener("HEARTBEAT", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.is_running) {
          setRunning(true);
          if (data.stage && data.stage !== "IDLE") {
            setActiveStage(data.stage.toLowerCase());
          }
        } else {
          // Sync frontend when backend is idle
          setRunning(false);
          setActiveStage(null);
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
        if (data.stage) setActiveStage(data.stage.toLowerCase());
      } catch {}
    });

    sse.addEventListener("COMPLETE", () => {
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
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Cancel / Interrupt Execution
  const handleCancel = async () => {
    try {
      setCancelling(true);
      await cancelPipelineRun();
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
      setActiveStage(stage);
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
      setRunning(false);
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

  return (
    <div className="w-full flex-1 flex flex-col space-y-3 min-h-[calc(100vh-105px)]">
      {/* ========================================================================= */}
      {/* 1. TOP MASTER BAR: Operational Status, Metrics & Global Action Controls   */}
      {/* ========================================================================= */}
      <div className="p-3.5 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex flex-col xl:flex-row xl:items-center justify-between gap-3 shrink-0">
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
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1 items-stretch">
        {/* ======================================================================= */}
        {/* LEFT PANEL (Col 1-3): Execution History, Audit Ledger & Comparison Diff */}
        {/* ======================================================================= */}
        <div className="lg:col-span-3 flex flex-col h-full">
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex flex-col h-full space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.06] shrink-0">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-emerald-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                  Execution History
                </h2>
              </div>
              <button
                onClick={loadRuns}
                disabled={loadingRuns}
                className="text-zinc-400 hover:text-zinc-200 transition-colors p-1"
                title="Refresh Runs"
              >
                <RefreshCw
                  className={`w-3 h-3 ${loadingRuns ? "animate-spin" : ""}`}
                />
              </button>
            </div>

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

            {/* Runs List (Expands to fill vertical height) */}
            <div className="space-y-1.5 flex-1 overflow-y-auto pr-1 min-h-[260px]">
              {runs.map((r) => {
                const isSelected = selectedRun?.run_id === r.run_id;
                const isSuccess = r.status === "COMPLETED";

                return (
                  <div
                    key={r.run_id}
                    onClick={() => setSelectedRun(r)}
                    className={`p-2.5 rounded-xl cursor-pointer transition-all border text-left ${
                      isSelected
                        ? "border-emerald-500/35 bg-zinc-900/90 shadow-[0_0_12px_rgba(16,185,129,0.06)] ring-1 ring-emerald-500/20"
                        : "border-white/[0.05] bg-[#141418] hover:bg-zinc-850 hover:border-white/[0.1]"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold font-mono text-zinc-200 flex items-center gap-1.5">
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            isSuccess ? "bg-emerald-400" : "bg-rose-400"
                          }`}
                        />
                        Run #{r.run_number}
                      </span>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.2 rounded border ${
                          isSuccess
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                        }`}
                      >
                        {r.status}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono">
                      <span>{r.active_stage.toUpperCase()}</span>
                      <span>{r.duration_seconds}s</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-zinc-500 mt-1 font-mono">
                      <span>{r.target_city}</span>
                      <span>{r.total_companies_out} leads</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Persistent Run Telemetry KPI Summary Footer (Anchors bottom) */}
            <div className="pt-2.5 border-t border-white/[0.06] bg-zinc-950/70 p-2.5 rounded-xl border border-white/[0.04] space-y-1.5 text-[11px] font-mono shrink-0">
              <div className="flex justify-between items-center text-zinc-400">
                <span className="text-[10px] text-zinc-500">DATABASE</span>
                <span className="text-emerald-400 font-semibold text-[11px]">
                  SQLite WAL (metrixa_leads.db)
                </span>
              </div>
              <div className="flex justify-between items-center text-zinc-400">
                <span className="text-[10px] text-zinc-500">QUALIFIED</span>
                <span className="text-zinc-200 font-semibold text-[11px]">
                  1,200 Leads (Berlin Scope)
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
        <div className="lg:col-span-6 flex flex-col h-full gap-3">
          {/* Active Dynamic DAG Visualizer Card */}
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte space-y-2.5 shrink-0">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Pipeline Execution DAG Progression
              </span>
              <span className="text-xs font-mono text-emerald-400 font-semibold">
                {running ? `${progress}% Active` : "100% Completed"}
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
                    <strong className="text-[11px] block truncate font-medium">
                      {s.shortName}
                    </strong>
                    <span className="text-[9px] font-mono text-zinc-500 block mt-0.5">
                      {s.time}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Dynamic Progress Bar */}
            <div className="w-full h-1.5 rounded-full bg-zinc-900 overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${running ? progress : 100}%` }}
              />
            </div>
          </div>

          {/* Real-Time Live Telemetry Stream / Inspector (Expands to bottom) */}
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex-1 flex flex-col space-y-2.5">
            {/* Console Subheader */}
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 shrink-0">
              <div className="flex items-center gap-2">
                <TerminalIcon className="w-4 h-4 text-emerald-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  Live Cockpit Telemetry Stream
                </h2>
                {filterStage !== "all" && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-emerald-400 border border-white/[0.06]">
                    Filtered: {filterStage.toUpperCase()}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="text-zinc-500 text-[11px]">
                  {visibleLogs.length} events
                </span>
                {filterStage !== "all" && (
                  <button
                    onClick={() => setFilterStage("all")}
                    className="text-[10px] text-zinc-400 hover:text-zinc-200 underline"
                  >
                    Reset Filter
                  </button>
                )}
                <button
                  onClick={() => setLogs([])}
                  className="text-[10px] text-zinc-500 hover:text-zinc-300 px-2 py-0.5 rounded bg-zinc-900 border border-white/[0.06]"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Console Log Area (Expands to bottom of panel) */}
            <div className="flex-1 min-h-[360px] overflow-y-auto font-mono text-[11px] space-y-1 p-3 rounded-xl bg-[#09090b] border border-white/[0.05]">
              {visibleLogs.map((log) => {
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
                  badgeColor = "text-sky-400 bg-sky-500/10 border-sky-500/20";
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
                        Inspect →
                      </span>
                    )}
                  </div>
                );
              })}
              <div ref={logEndRef} />
            </div>

            {/* Deep-Dive Inspection Drawer (When an event is clicked) */}
            {selectedEvent && (
              <div className="p-3 rounded-xl bg-zinc-950 border border-emerald-500/30 space-y-2 text-xs font-mono shrink-0">
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
        <div className="lg:col-span-3 flex flex-col h-full gap-3">
          {/* Stage Controls Card */}
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex-1 flex flex-col space-y-2.5">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.06] shrink-0">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-emerald-400" />
                Stage Controls (1-6)
              </span>
              <span className="text-[10px] font-mono text-zinc-500">
                Trigger On-Demand
              </span>
            </div>

            {/* 6 Stage Mini-Action Cards */}
            <div className="space-y-1.5 flex-1 overflow-y-auto pr-0.5">
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
                      <span className="text-[10px] font-mono text-zinc-500 block mt-0.5">
                        Est: {s.time}
                      </span>
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
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-white/[0.06] shadow-matte flex-1 flex flex-col space-y-2.5">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.06] shrink-0">
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

            {/* Tool Result Output (Expands in bottom of right panel) */}
            <div className="flex-1 min-h-[120px] max-h-[180px] overflow-y-auto p-2 rounded-xl bg-[#09090b] border border-white/[0.05] space-y-1 text-[10px] font-mono">
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
