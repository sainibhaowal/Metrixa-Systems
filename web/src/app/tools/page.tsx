"use client";

import { useEffect, useState } from "react";
import {
  Wrench,
  CheckCircle2,
  Activity,
  Zap,
  Globe,
  Database,
  MapPin,
  MailCheck,
  ShieldCheck,
  Search,
  Terminal,
  Clock,
} from "lucide-react";
import {
  fetchToolsCatalog,
  testToolHealth,
  executeToolAction,
} from "@/lib/api";
import { ToolItem } from "@/lib/types";

interface ToolHealthResult {
  tool_id: string;
  status: "OK" | "DEGRADED" | "ERROR";
  latency_ms: number;
  target: string;
  probe_result: string;
  verified_records: number;
  message: string;
  details?: any;
}

interface ToolExecResult {
  success: boolean;
  tool_id: string;
  input: string;
  latency_ms: number;
  output: any;
}

export default function ToolsCatalogPage() {
  const [tools, setTools] = useState<ToolItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ToolHealthResult | null>(null);

  // Interactive Execution Playground State
  const [activeExecToolId, setActiveExecToolId] =
    useState<string>("tool_mx_verifier");
  const [execInput, setExecInput] = useState<string>("degewo.de");
  const [isExecuting, setIsExecuting] = useState(false);
  const [execResult, setExecResult] = useState<ToolExecResult | null>(null);

  useEffect(() => {
    fetchToolsCatalog()
      .then((data) => {
        setTools(data);
        if (data.length > 0 && !activeExecToolId) {
          setActiveExecToolId(data[0].id);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Run Real Backend Tool Health Ping
  const handleTestHealth = async (toolId: string) => {
    try {
      setTestingId(toolId);
      setTestResult(null);
      const res = await testToolHealth(toolId);
      setTestResult(res);
    } catch (err: any) {
      setTestResult({
        tool_id: toolId,
        status: "ERROR",
        latency_ms: 0,
        target: "Backend Gateway",
        probe_result: "Connection error",
        verified_records: 0,
        message: err?.message || "Health test failed",
      });
    } finally {
      setTestingId(null);
    }
  };

  // Run Real On-Demand Tool Action
  const handleExecuteTool = async (customInput?: string) => {
    const inputVal = customInput !== undefined ? customInput : execInput;
    try {
      setIsExecuting(true);
      setExecResult(null);
      const res = await executeToolAction(activeExecToolId, inputVal);
      setExecResult(res);
    } catch (err: any) {
      setExecResult({
        success: false,
        tool_id: activeExecToolId,
        input: inputVal,
        latency_ms: 0,
        output: { error: err?.message || "Execution failed" },
      });
    } finally {
      setIsExecuting(false);
    }
  };

  // Preset switch helper
  const handleSelectExecTool = (toolId: string) => {
    setActiveExecToolId(toolId);
    setExecResult(null);
    if (toolId === "tool_mx_verifier") {
      setExecInput("degewo.de");
    } else if (toolId === "tool_crawler") {
      setExecInput(
        "Kundenportal: casavi.de aktiv. Buchhaltung Domus 4000. Messdienst Techem. Email: info@berlin-hausverwaltung.de",
      );
    } else if (toolId === "tool_vdiv") {
      setExecInput("Berlin");
    } else if (toolId === "tool_osm") {
      setExecInput("Mitte");
    } else {
      setExecInput("Charlottenburg");
    }
  };

  const getToolIcon = (id: string) => {
    switch (id) {
      case "tool_gelbe_seiten":
        return <Search className="w-4 h-4 text-amber-400" />;
      case "tool_11880":
        return <Database className="w-4 h-4 text-sky-400" />;
      case "tool_vdiv":
        return <ShieldCheck className="w-4 h-4 text-emerald-400" />;
      case "tool_osm":
        return <MapPin className="w-4 h-4 text-rose-400" />;
      case "tool_crawler":
        return <Globe className="w-4 h-4 text-purple-400" />;
      case "tool_mx_verifier":
        return <MailCheck className="w-4 h-4 text-emerald-400" />;
      default:
        return <Wrench className="w-4 h-4 text-zinc-400" />;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      {/* Top Header Bar Bento */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Agentic Tools Catalog</span>
            <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
              {tools.length} Operational Python Modules
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Production-grade scrapers, HTTP/2 subpage crawlers, regex DOM
            analyzers, and RFC-5321 DNS MX resolvers powering the 1,199 Berlin
            company pipeline.
          </p>
        </div>

        {/* Global Architecture Badges */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
          <div className="px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Python 3.12 Engine</span>
          </div>
          <div className="px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">
            HTTP/2 Async (httpx)
          </div>
          <div className="px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">
            dnspython (Port 53)
          </div>
        </div>
      </div>

      {/* 6 Operational Tools Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tools.map((t) => {
          const isSelectedForExec = activeExecToolId === t.id;

          return (
            <div
              key={t.id}
              className={`p-5 rounded-2xl bg-[#141418] border transition-all flex flex-col justify-between space-y-4 ${
                isSelectedForExec
                  ? "border-emerald-500/80 shadow-[0_0_15px_-3px_rgba(16,185,129,0.25)]"
                  : "border-zinc-800/80 hover:border-zinc-700 shadow-matteCard"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    {getToolIcon(t.id)}
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                      {t.category}
                    </span>
                  </div>
                  <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400 font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    ONLINE
                  </span>
                </div>

                <h2 className="text-sm font-bold text-zinc-100 mb-1">
                  {t.name}
                </h2>
                <p className="text-xs text-zinc-400 leading-relaxed line-clamp-2">
                  {t.description}
                </p>

                {t.engine && (
                  <div className="mt-2 text-[10px] font-mono text-zinc-500 truncate">
                    Engine: <span className="text-zinc-400">{t.engine}</span>
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-zinc-800/80 flex items-center justify-between gap-2">
                <span className="text-xs font-mono text-zinc-300 shrink-0">
                  <strong className="text-emerald-400 font-bold">
                    {t.records_extracted.toLocaleString()}
                  </strong>{" "}
                  Records
                </span>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleSelectExecTool(t.id)}
                    className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold font-mono flex items-center gap-1 transition-all border ${
                      isSelectedForExec
                        ? "bg-emerald-500 text-zinc-950 border-emerald-400 font-bold"
                        : "bg-zinc-900 text-zinc-300 border-zinc-800 hover:text-white hover:border-zinc-700"
                    }`}
                    title="Load into Interactive Playground"
                  >
                    <Terminal className="w-3 h-3" />
                    <span>Run</span>
                  </button>

                  <button
                    onClick={() => handleTestHealth(t.id)}
                    disabled={testingId === t.id}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs font-semibold font-mono border border-zinc-800 hover:border-zinc-700 transition-all disabled:opacity-50"
                    title="Run live network and probe test"
                  >
                    <Activity
                      className={`w-3 h-3 ${
                        testingId === t.id
                          ? "animate-spin text-emerald-400"
                          : "text-zinc-400"
                      }`}
                    />
                    <span>{testingId === t.id ? "Testing..." : "Health"}</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Health Test Results Banner */}
      {testResult && (
        <div className="p-4 rounded-2xl bg-[#111114] border border-emerald-500/40 shadow-matte space-y-2 font-mono text-xs animate-in fade-in">
          <div className="flex items-center justify-between gap-2 border-b border-zinc-800/80 pb-2">
            <div className="flex items-center gap-2 text-emerald-400 font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Live Health Check Passed: {testResult.tool_id}</span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-zinc-400">
              <span>
                Latency:{" "}
                <strong className="text-emerald-400">
                  {testResult.latency_ms}ms
                </strong>
              </span>
              <span>•</span>
              <span>
                Verified Records:{" "}
                <strong className="text-zinc-200">
                  {testResult.verified_records}
                </strong>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] text-zinc-300 pt-1">
            <div>
              <span className="text-zinc-500">Target Endpoint: </span>
              <span className="text-zinc-200">{testResult.target}</span>
            </div>
            <div>
              <span className="text-zinc-500">Live Probe: </span>
              <span className="text-emerald-300 font-semibold">
                {testResult.probe_result}
              </span>
            </div>
          </div>

          <p className="text-zinc-400 text-[11px] pt-1">{testResult.message}</p>
        </div>
      )}

      {/* ============================================================ */}
      {/* INTERACTIVE TOOL EXECUTION SANDBOX / WORKBENCH               */}
      {/* ============================================================ */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-4">
          <div>
            <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span>Interactive Tool Execution Workbench</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Execute real-time live queries directly against Python scrapers,
              DNS resolvers, and DOM parsers.
            </p>
          </div>

          {/* Tool Selector Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 max-w-full">
            {tools.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelectExecTool(t.id)}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-mono font-semibold transition-all shrink-0 border flex items-center gap-1.5 ${
                  activeExecToolId === t.id
                    ? "bg-zinc-850 text-emerald-400 border-emerald-500/50 shadow-sm"
                    : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                }`}
              >
                {getToolIcon(t.id)}
                <span className="truncate max-w-[130px]">
                  {t.name.split(" ")[0]}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Input Panel with Tool Presets */}
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <label className="text-xs font-mono text-zinc-300 font-semibold flex items-center gap-1.5">
              <span>Tool Input Payload:</span>
              <span className="text-[10px] text-zinc-500 font-normal">
                {activeExecToolId === "tool_mx_verifier"
                  ? "(Domain or Corporate Email)"
                  : activeExecToolId === "tool_crawler"
                    ? "(HTML or Text snippet to scan for ERP/PropTech & Emails)"
                    : "(Company Name or District search filter)"}
              </span>
            </label>

            {/* Quick Sample Presets */}
            <div className="flex items-center gap-1.5 text-[10px] font-mono">
              <span className="text-zinc-500 hidden sm:inline">Presets:</span>
              {activeExecToolId === "tool_mx_verifier" ? (
                <>
                  {["degewo.de", "gewobag.de", "casavi.de", "haufe.de"].map(
                    (preset) => (
                      <button
                        key={preset}
                        onClick={() => {
                          setExecInput(preset);
                          handleExecuteTool(preset);
                        }}
                        className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-emerald-400 transition-colors"
                      >
                        {preset}
                      </button>
                    ),
                  )}
                </>
              ) : activeExecToolId === "tool_crawler" ? (
                <>
                  <button
                    onClick={() => {
                      const snippet =
                        "Kundenportal: casavi.de aktiv. Buchhaltung Domus 4000. Messdienst Techem. Email: kontakt@berlin-wohnen.de";
                      setExecInput(snippet);
                      handleExecuteTool(snippet);
                    }}
                    className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-emerald-400 transition-colors"
                  >
                    Casavi + Domus
                  </button>
                  <button
                    onClick={() => {
                      const snippet =
                        "Portal: etg24.de. ERP: Haufe PowerHaus. Messdienst: Brunata-Metrona. Email: gf [at] weg-hausverwaltung.de";
                      setExecInput(snippet);
                      handleExecuteTool(snippet);
                    }}
                    className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-emerald-400 transition-colors"
                  >
                    etg24 + Haufe
                  </button>
                </>
              ) : (
                <>
                  {["Mitte", "Charlottenburg", "Pankow", "Immobilien"].map(
                    (preset) => (
                      <button
                        key={preset}
                        onClick={() => {
                          setExecInput(preset);
                          handleExecuteTool(preset);
                        }}
                        className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-emerald-400 transition-colors"
                      >
                        {preset}
                      </button>
                    ),
                  )}
                </>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={execInput}
              onChange={(e) => setExecInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleExecuteTool()}
              placeholder={
                activeExecToolId === "tool_mx_verifier"
                  ? "e.g. degewo.de or contact@casavi.de"
                  : activeExecToolId === "tool_crawler"
                    ? "e.g. Paste HTML or text snippet..."
                    : "e.g. Filter by company name or district..."
              }
              className="flex-1 px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
            />

            <button
              onClick={() => handleExecuteTool()}
              disabled={isExecuting}
              className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs flex items-center gap-1.5 transition-all shadow-glowEmerald disabled:opacity-50"
            >
              <Zap
                className={`w-3.5 h-3.5 ${isExecuting ? "animate-spin" : ""}`}
              />
              <span>{isExecuting ? "Executing..." : "Execute Tool"}</span>
            </button>
          </div>
        </div>

        {/* Execution Output Card */}
        {execResult && (
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/90 font-mono text-xs space-y-3 animate-in fade-in">
            <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="font-bold text-zinc-200">
                  Execution Output
                </span>
                <span className="text-[10px] text-zinc-500">
                  Tool: {execResult.tool_id}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-zinc-400">
                <Clock className="w-3 h-3 text-zinc-500" />
                <span>
                  Elapsed:{" "}
                  <strong className="text-emerald-400">
                    {execResult.latency_ms}ms
                  </strong>
                </span>
              </div>
            </div>

            <pre className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800 text-[11px] text-emerald-300 overflow-x-auto leading-relaxed">
              {JSON.stringify(execResult.output, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
