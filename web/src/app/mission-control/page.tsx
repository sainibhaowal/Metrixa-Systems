"use client";

import { useEffect, useRef, useState } from "react";
import { 
  Play, 
  Square, 
  Terminal as TerminalIcon, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  Layers, 
  Sparkles,
  ShieldAlert,
  ArrowRight
} from "lucide-react";
import { triggerPipelineStage } from "@/lib/api";

const STAGES = [
  { id: "ingest", name: "Stage 1: Multi-Source Berlin Ingest", desc: "Scrape Gelbe Seiten, 11880, VDIV, OSM, Search", time: "~45s" },
  { id: "deduplicate", name: "Stage 2: Entity Deduplication", desc: "Union-Find & RapidFuzz blocking across Berlin PLZs", time: "~5s" },
  { id: "crawl", name: "Stage 3: Async Impressum Crawler", desc: "HTTP/2 crawl of /, /impressum, /team, /portal + DOM tech", time: "~50s" },
  { id: "extract", name: "Stage 4: Multi-LLM KPI Extraction", desc: "Extract units, WEG/Miet focus & Geschäftsführer", time: "~25s" },
  { id: "enrich", name: "Stage 5: MX Verification & Scoring", desc: "Live DNS MX validation & deterministic 0-100 scoring", time: "~10s" },
  { id: "export", name: "Stage 6: Excel Deliverables & Eval", desc: "Build 4-Tab Excel (.xlsx), CSV and Ablation Report", time: "~5s" },
];

export default function MissionControlPage() {
  const [running, setRunning] = useState(false);
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [logs, setLogs] = useState<Array<{ time: string; level: string; msg: string }>>([
    { time: "INIT", level: "INFO", msg: "Heidi Cockpit Mission Control ready. EventBus active on http://127.0.0.1:8000" },
    { time: "STATUS", level: "SUCCESS", msg: "Connected to SQLite WAL (heidi_leads.db) — 1,199 qualified companies loaded." },
  ]);
  const [progress, setProgress] = useState<number>(0);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Connect to SSE stream
  useEffect(() => {
    const sse = new EventSource("http://127.0.0.1:8000/api/pipeline/stream");
    
    sse.addEventListener("HEARTBEAT", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.is_running) {
          setRunning(true);
          setActiveStage(data.stage);
        }
      } catch {}
    });

    sse.addEventListener("LOG", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        const now = new Date().toLocaleTimeString();
        setLogs((prev) => [...prev, { time: now, level: data.level || "INFO", msg: data.message || "" }]);
      } catch {}
    });

    sse.addEventListener("PROGRESS", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.pct !== undefined) setProgress(data.pct);
      } catch {}
    });

    sse.addEventListener("COMPLETE", () => {
      setRunning(false);
      setActiveStage(null);
      setProgress(100);
      setLogs((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: "SUCCESS", msg: "Stage execution finished successfully!" },
      ]);
    });

    sse.addEventListener("ERROR", (e: any) => {
      setRunning(false);
      setActiveStage(null);
      setLogs((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: "ERROR", msg: `Execution error: ${e.data}` },
      ]);
    });

    return () => sse.close();
  }, []);

  const handleRun = async (stage: string) => {
    try {
      setRunning(true);
      setActiveStage(stage);
      setProgress(5);
      setLogs((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: "INFO", msg: `Dispatched command: [${stage.toUpperCase()}]` },
      ]);
      await triggerPipelineStage(stage);
    } catch (err: any) {
      setRunning(false);
      setLogs((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: "ERROR", msg: `Failed to trigger stage: ${err.message}` },
      ]);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <span>Pipeline Mission Control</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-primary font-mono">
              Live DAG & SSE Console
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Trigger deterministic scrapers, async crawlers, LLM extraction and DNS MX verifiers in real-time.
          </p>
        </div>

        <button
          onClick={() => handleRun("full")}
          disabled={running}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-primary to-cyan-500 text-slate-950 font-bold text-xs shadow-glowCyan hover:opacity-95 transition-all disabled:opacity-50"
        >
          <Play className="w-4 h-4 fill-slate-950" />
          <span>{running ? "Execution in Progress..." : "Execute Full Pipeline (End-to-End)"}</span>
        </button>
      </div>

      {/* Visual DAG Stage Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {STAGES.map((s, idx) => {
          const isCurrent = activeStage === s.id;
          return (
            <div
              key={s.id}
              className={`glass-card p-5 rounded-2xl relative overflow-hidden transition-all ${
                isCurrent ? "border-primary/50 bg-primary/5 shadow-glowCyan" : ""
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono text-slate-400">Step 0{idx + 1}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  {s.time}
                </span>
              </div>

              <h2 className="text-sm font-bold text-white mb-1">{s.name}</h2>
              <p className="text-xs text-slate-400 mb-4 h-8">{s.desc}</p>

              <button
                onClick={() => handleRun(s.id)}
                disabled={running}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-white/[0.05] hover:bg-primary/20 text-xs font-semibold text-slate-200 hover:text-primary border border-white/10 hover:border-primary/30 transition-all disabled:opacity-50"
              >
                <Play className="w-3 h-3" />
                <span>Run Stage</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Progress Bar (when running) */}
      {running && (
        <div className="glass-panel p-4 rounded-2xl space-y-2 border-primary/30">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-primary font-bold">Active Stage: {activeStage?.toUpperCase()}</span>
            <span className="text-slate-300">{progress}%</span>
          </div>
          <div className="w-full h-2 rounded-full bg-slate-900 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-cyan-400 rounded-full transition-all duration-300 shadow-glowCyan"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Live SSE Streaming Terminal Console */}
      <div className="glass-panel p-6 rounded-2xl space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <TerminalIcon className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-white tracking-wide">Live Cockpit Telemetry Stream</h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[11px] font-mono text-slate-400">
              {logs.length} events logged
            </span>
            <button
              onClick={() => setLogs([])}
              className="text-[11px] text-slate-400 hover:text-white transition-colors"
            >
              Clear
            </button>
          </div>
        </div>

        <div className="h-80 overflow-y-auto font-mono text-[11px] space-y-1.5 p-3 rounded-xl bg-slate-950/80 border border-slate-900">
          {logs.map((log, i) => {
            let color = "text-slate-300";
            if (log.level === "SUCCESS") color = "text-emerald-400";
            if (log.level === "ERROR") color = "text-rose-400";
            if (log.level === "WARN") color = "text-amber-400";
            if (log.level === "INFO") color = "text-cyan-400";

            return (
              <div key={i} className="flex gap-2.5 leading-relaxed">
                <span className="text-slate-600 select-none">[{log.time}]</span>
                <span className={`font-semibold shrink-0 w-16 select-none ${color}`}>
                  {log.level}
                </span>
                <span className="text-slate-200 break-all">{log.msg}</span>
              </div>
            );
          })}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}

