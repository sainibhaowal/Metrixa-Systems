"use client";

import { useEffect, useState } from "react";
import { Download, RefreshCw, Database, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { fetchMetrics } from "@/lib/api";
import { useSidebar } from "./SidebarContext";

export function StickyTopbar() {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const { isCollapsed, toggleSidebar } = useSidebar();

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
    <header className="h-16 px-5 bg-[#111114] border border-zinc-800/90 rounded-2xl sticky top-3 z-30 flex items-center justify-between select-none shadow-matte m-3 mb-2">
      {/* Left: Single Sidebar Expand/Collapse Toggle & System Status Pulse */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Rounded-Square Toggle Button */}
        <button
          onClick={toggleSidebar}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          className="p-2 rounded-xl text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 border border-zinc-800 transition-colors flex items-center justify-center group"
        >
          {isCollapsed ? (
            <PanelLeftOpen className="w-4 h-4 text-emerald-400 transition-transform group-hover:scale-110" />
          ) : (
            <PanelLeftClose className="w-4 h-4 text-zinc-400 group-hover:text-zinc-200 transition-transform group-hover:scale-110" />
          )}
        </button>

        {/* Rounded-Square Status Pill */}
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 shadow-sm">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-sm bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-sm h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[11px] font-mono font-medium text-zinc-300">
            {metrics?.pipeline_state?.is_running
              ? `RUNNING: ${metrics?.pipeline_state?.current_stage}`
              : "SYSTEM ONLINE"}
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-zinc-400">
          <Database className="w-3.5 h-3.5 text-emerald-400" />
          <span>
            Database: <strong className="text-zinc-200">{metrics?.golden_total || "1,199"}</strong> Qualified Berlin Leads
          </span>
        </div>
      </div>

      {/* Right: Quick Action Buttons */}
      <div className="flex items-center gap-2.5">
        <button
          onClick={loadData}
          disabled={loading}
          className="p-2 rounded-xl text-zinc-400 hover:text-zinc-100 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 transition-colors"
          title="Refresh Telemetry"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-400" : ""}`} />
        </button>

        <a
          href="http://127.0.0.1:8000/api/artifacts/download/excel"
          download
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold text-xs shadow-glowEmerald hover:shadow-lg transition-all"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Master Excel (.xlsx)</span>
        </a>
      </div>
    </header>
  );
}
