"use client";

import { useEffect, useState } from "react";
import {
  ShieldAlert,
  AlertTriangle,
  RotateCcw,
  Database,
  Trash2,
  HardDrive,
  Users2,
  Globe2,
  Cpu,
  UserCheck,
  Terminal,
  Activity,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  Loader2,
  Sparkles,
} from "lucide-react";
import { fetchSystemStats, executeFactoryReset } from "@/lib/api";

interface SystemStats {
  status: string;
  counts: {
    companies_golden: number;
    raw_listings: number;
    crawled_pages: number;
    kpi_extractions: number;
    decision_makers: number;
    pipeline_runs: number;
    pipeline_run_events: number;
    next_run_number: number;
  };
  storage: {
    database_size_bytes: number;
    database_size_formatted: string;
    export_files_count: number;
    export_files: Array<{ name: string; size_bytes: number }>;
    export_total_bytes: number;
  };
}

export default function DataControlPage() {
  const [mounted, setMounted] = useState<boolean>(false);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [confirmedBox, setConfirmedBox] = useState<boolean>(false);
  const [confirmationWord, setConfirmationWord] = useState<string>("");
  const [resetting, setResetting] = useState<boolean>(false);
  const [resetSuccess, setResetSuccess] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadStats = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const res = await fetchSystemStats();
      setStats(res);
      setErrorMessage(null);
    } catch (err: any) {
      console.error("Failed to fetch system stats:", err);
      if (!silent)
        setErrorMessage(err.message || "Failed to load database stats");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    setMounted(true);
    loadStats(false);
    const interval = setInterval(() => {
      loadStats(true);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleOpenModal = () => {
    setConfirmedBox(false);
    setConfirmationWord("");
    setErrorMessage(null);
    setShowModal(true);
  };

  const handleCloseModal = () => {
    if (resetting) return;
    setShowModal(false);
    setConfirmedBox(false);
    setConfirmationWord("");
    setErrorMessage(null);
  };

  const isWordMatch =
    confirmationWord.trim().toUpperCase() === "DELETE" ||
    confirmationWord.trim().toUpperCase() === "DELEET";

  const isResetEnabled = confirmedBox && isWordMatch && !resetting;

  const handleConfirmReset = async () => {
    if (!isResetEnabled) return;
    try {
      setResetting(true);
      setErrorMessage(null);
      await executeFactoryReset(confirmationWord);
      setResetSuccess(true);
      // Wait 1.2 seconds, then automatically reload to mission control
      setTimeout(() => {
        window.location.href = "/mission-control";
      }, 1200);
    } catch (err: any) {
      console.error("Factory reset failed:", err);
      setErrorMessage(err.message || "Factory reset execution failed");
      setResetting(false);
    }
  };

  if (!mounted) {
    return (
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <div className="h-20 bg-zinc-900/50 rounded-2xl animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-28 bg-zinc-900/40 rounded-2xl animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  const counts = stats?.counts || {
    companies_golden: 0,
    raw_listings: 0,
    crawled_pages: 0,
    kpi_extractions: 0,
    decision_makers: 0,
    pipeline_runs: 0,
    pipeline_run_events: 0,
    next_run_number: 1,
  };

  const storage = stats?.storage || {
    database_size_bytes: 0,
    database_size_formatted: "0 KB",
    export_files_count: 0,
    export_files: [],
    export_total_bytes: 0,
  };

  const isCleanSlate =
    counts.companies_golden === 0 &&
    counts.raw_listings === 0 &&
    counts.pipeline_runs === 0;

  return (
    <div
      className="w-full max-w-7xl mx-auto space-y-8 select-none"
      suppressHydrationWarning
    >
      {/* Page Header */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <h1 className="text-2xl font-bold text-zinc-100 tracking-tight font-mono">
              DATA CONTROL & GOVERNANCE
            </h1>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/30">
              ADMIN
            </span>
          </div>
          <p className="text-xs text-zinc-400 max-w-2xl leading-relaxed">
            Direct operational control over the Metrixa lead database, pipeline
            execution ledger, telemetry stream events, and deliverable export
            workbooks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/80 border border-zinc-800 text-[11px] font-mono text-zinc-300">
            <span
              className={`w-2 h-2 rounded-full ${
                isCleanSlate ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
              }`}
            />
            <span>
              {isCleanSlate
                ? "Pristine Zero-State (Standby)"
                : "Active Production Dataset"}
            </span>
          </div>

          <button
            onClick={() => loadStats(false)}
            disabled={loading}
            title="Refresh database statistics"
            className="p-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800 transition-colors"
          >
            <RotateCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Real-Time Database Inventory Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs font-semibold text-zinc-400 uppercase tracking-wider font-mono">
          <span>Live SQLite WAL & File Inventory</span>
          <span className="text-[11px] text-zinc-500 lowercase">
            Next Sequence: Run #{counts.next_run_number}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Golden Leads</span>
              <Users2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.companies_golden.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              companies_golden table
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Raw Listings</span>
              <Database className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.raw_listings.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              raw_listings table
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Crawled Pages</span>
              <Globe2 className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.crawled_pages.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              crawled_pages table
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>KPI Extractions</span>
              <Cpu className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.kpi_extractions.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              kpi_extractions table
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Decision Makers</span>
              <UserCheck className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.decision_makers.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              decision_makers table
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Pipeline Runs</span>
              <Terminal className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.pipeline_runs.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              pipeline_runs ledger
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Telemetry Events</span>
              <Activity className="w-4 h-4 text-teal-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {counts.pipeline_run_events.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              stream events recorded
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141418] border border-zinc-800/80 space-y-2">
            <div className="flex items-center justify-between text-zinc-500 text-xs">
              <span>Database Size</span>
              <HardDrive className="w-4 h-4 text-zinc-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-zinc-100">
              {storage.database_size_formatted}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              {storage.export_files_count} export files
            </div>
          </div>
        </div>
      </div>

      {/* Dangerous Operations / Factory Reset Card */}
      <div className="data-control-danger-card p-6 md:p-8 rounded-2xl bg-gradient-to-br from-rose-950/20 via-[#161214] to-[#121215] border border-rose-500/30 space-y-6 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-rose-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-400 animate-ping" />
              <span className="text-xs font-bold text-rose-400 uppercase tracking-widest font-mono">
                Irreversible Dangerous Action
              </span>
            </div>
            <h2 className="text-lg font-bold text-zinc-100 font-mono">
              Full Application Factory Reset (Start Fresh Like New App)
            </h2>
            <p className="text-xs text-zinc-300 leading-relaxed">
              Completely clears and factory-resets the entire application.
              Purges all 6 normalized SQLite relational tables, wipes the
              execution run history so your next run is Run #1, clears generated
              Excel workbook deliverables, and resets all in-memory telemetry
              buffers.
            </p>
          </div>

          <button
            onClick={handleOpenModal}
            className="px-5 py-3 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs flex items-center gap-2.5 transition-all shadow-[0_0_20px_-3px_rgba(225,29,72,0.4)] hover:shadow-[0_0_25px_-2px_rgba(225,29,72,0.6)] active:scale-95 shrink-0"
          >
            <Trash2 className="w-4 h-4" />
            <span>Factory Reset Application</span>
          </button>
        </div>

        {/* Informational Guidance Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-4 border-t border-rose-500/20 text-xs">
          <div className="p-3.5 rounded-xl bg-black/40 border border-rose-500/20 space-y-1">
            <span className="font-semibold text-rose-300 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-rose-400" />
              <span>Full Data Wipe</span>
            </span>
            <p className="text-[11px] text-zinc-400 leading-normal">
              Drops all leads, raw listings, and crawled company pages from
              SQLite.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-black/40 border border-rose-500/20 space-y-1">
            <span className="font-semibold text-rose-300 flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-rose-400" />
              <span>Run Sequence Reset</span>
            </span>
            <p className="text-[11px] text-zinc-400 leading-normal">
              Clears pipeline history. The very next execution runs cleanly as
              Run #1.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-black/40 border border-rose-500/20 space-y-1">
            <span className="font-semibold text-rose-300 flex items-center gap-1.5">
              <FileSpreadsheet className="w-3.5 h-3.5 text-rose-400" />
              <span>Deliverables Clean</span>
            </span>
            <p className="text-[11px] text-zinc-400 leading-normal">
              Removes previous export workbooks so the Artifacts Vault starts
              fresh.
            </p>
          </div>
        </div>
      </div>

      {/* Safety Confirmation Modal Dialog */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="max-w-lg w-full bg-[#131317] border border-rose-500/40 rounded-3xl shadow-2xl overflow-hidden space-y-5 p-6 animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-3 pb-3 border-b border-zinc-800">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                    <AlertTriangle className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-[10px] font-bold tracking-wider text-rose-400 uppercase font-mono">
                    SAFETY CONFIRMATION GATE
                  </span>
                </div>
                <h3 className="text-base font-bold text-zinc-100 font-mono">
                  Confirm Complete Factory Reset
                </h3>
              </div>

              {!resetting && (
                <button
                  onClick={handleCloseModal}
                  className="p-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              )}
            </div>

            {/* Error Message */}
            {errorMessage && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Success State Indicator */}
            {resetSuccess ? (
              <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-center space-y-3">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto animate-bounce" />
                <h4 className="text-sm font-bold text-emerald-300 font-mono">
                  APPLICATION FACTORY RESET COMPLETE
                </h4>
                <p className="text-xs text-zinc-300">
                  All databases, runs, and artifacts have been purged. Reloading
                  workspace...
                </p>
                <div className="flex items-center justify-center gap-2 text-xs text-emerald-400 font-mono">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Reloading to Mission Control...</span>
                </div>
              </div>
            ) : (
              <>
                {/* Purge Checklist */}
                <div className="space-y-2 p-3.5 rounded-2xl bg-black/50 border border-zinc-800/80 text-xs">
                  <p className="font-semibold text-zinc-300">
                    The following assets will be permanently destroyed:
                  </p>
                  <ul className="space-y-1.5 text-zinc-400 text-[11px] font-mono pl-1">
                    <li className="flex items-center gap-2">
                      <span className="text-rose-400">✗</span>
                      <span>
                        All {counts.companies_golden} golden company lead
                        records & scoring tiers
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-rose-400">✗</span>
                      <span>
                        All {counts.raw_listings} raw scraper listings &
                        directory snapshots
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-rose-400">✗</span>
                      <span>
                        All {counts.crawled_pages} crawled domain HTML pages &
                        Impressum dossiers
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-rose-400">✗</span>
                      <span>
                        All {counts.decision_makers} executive contact profiles
                        & email records
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-rose-400">✗</span>
                      <span>
                        All {counts.pipeline_runs} historical pipeline execution
                        runs
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-rose-400">✗</span>
                      <span>
                        All generated Excel workbooks and master CSV exports
                      </span>
                    </li>
                    <li className="flex items-center gap-2 text-emerald-400 font-semibold pt-1 border-t border-zinc-800/60">
                      <span>✓</span>
                      <span>
                        Next pipeline execution will start clean from Run #1
                      </span>
                    </li>
                  </ul>
                </div>

                {/* Step 1: Mandatory Checkbox */}
                <label className="flex items-start gap-3 p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 cursor-pointer hover:border-zinc-700 transition-colors">
                  <input
                    type="checkbox"
                    id="confirm-checkbox"
                    checked={confirmedBox}
                    onChange={(e) => setConfirmedBox(e.target.checked)}
                    disabled={resetting}
                    className="mt-0.5 rounded border-zinc-700 text-rose-600 focus:ring-rose-500 focus:ring-offset-0 bg-zinc-950 cursor-pointer"
                  />
                  <span className="text-xs text-zinc-300 leading-snug">
                    I understand that this action will permanently purge all
                    application data and cannot be undone.
                  </span>
                </label>

                {/* Step 2: Confirmation Word Input */}
                <div className="space-y-1.5">
                  <label
                    htmlFor="delete-input"
                    className="block text-xs font-semibold text-zinc-300 font-mono"
                  >
                    To confirm, please type{" "}
                    <span className="text-rose-400 font-bold">DELETE</span>{" "}
                    below:
                  </label>
                  <input
                    id="delete-input"
                    type="text"
                    value={confirmationWord}
                    onChange={(e) => setConfirmationWord(e.target.value)}
                    disabled={resetting}
                    placeholder="Type DELETE to confirm"
                    spellCheck={false}
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="off"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-black border border-zinc-700 text-zinc-100 text-xs font-mono placeholder:text-zinc-600 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition-colors"
                  />
                  {confirmationWord.length > 0 && !isWordMatch && (
                    <p className="text-[10px] text-rose-400 font-mono">
                      Must match &quot;DELETE&quot; exactly (case-insensitive).
                    </p>
                  )}
                </div>

                {/* Modal Action Buttons */}
                <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
                  <button
                    onClick={handleCloseModal}
                    disabled={resetting}
                    className="px-4 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-300 text-xs font-semibold border border-zinc-800 transition-colors"
                  >
                    Cancel
                  </button>

                  <button
                    onClick={handleConfirmReset}
                    disabled={!isResetEnabled}
                    className={`px-5 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
                      isResetEnabled
                        ? "bg-rose-600 hover:bg-rose-500 text-white shadow-[0_0_15px_-2px_rgba(225,29,72,0.5)] active:scale-95 cursor-pointer"
                        : "bg-zinc-800 text-zinc-500 border border-zinc-700/50 cursor-not-allowed"
                    }`}
                  >
                    {resetting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Purging and Resetting...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Permanently Reset Application</span>
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
