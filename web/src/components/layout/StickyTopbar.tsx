"use client";

import { useEffect, useState } from "react";
import { Download, RefreshCw, Activity, Database, CheckCircle2 } from "lucide-react";
import { fetchMetrics } from "@/lib/api";

export function StickyTopbar() {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await fetchMetrics();
      setMetrics(data);
    } catch {
      // Backend may be starting up
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 12000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-16 px-6 glass-panel border-b border-slate-800/80 bg-surface-100/60 sticky top-0 z-30 flex items-center justify-between select-none">
      {/* Left: System Status & Pulse */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-slate-800">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[11px] font-mono font-medium text-slate-300">
            {metrics?.pipeline_state?.is_running
              ? `RUNNING: ${metrics?.pipeline_state?.current_stage}`
              : "SYSTEM ONLINE"}
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-slate-400">
          <Database className="w-3.5 h-3.5 text-primary" />
          <span>
            Database: <strong className="text-slate-200">{metrics?.golden_total || "1,199"}</strong> Qualified Berlin Leads
          </span>
        </div>
      </div>

      {/* Right: Quick Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={loadData}
          disabled={loading}
          className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/[0.05] border border-slate-800 transition-colors"
          title="Refresh Telemetry"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-primary" : ""}`} />
        </button>

        <a
          href="http://127.0.0.1:8000/api/artifacts/download/excel"
          download
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-primary to-cyan-500 text-slate-950 font-semibold text-xs shadow-glowCyan hover:opacity-95 transition-all"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Master Excel (.xlsx)</span>
        </a>
      </div>
    </header>
  );
}

