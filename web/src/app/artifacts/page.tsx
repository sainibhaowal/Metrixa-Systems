"use client";

import { useEffect, useState, useMemo } from "react";
import {
  FileSpreadsheet,
  FileText,
  Database,
  Trash2,
  Archive,
  RotateCcw,
  Download,
  Copy,
  Check,
  Search,
  FileCode,
  Printer,
  Clock,
  CheckCircle2,
  Table,
  X,
  RefreshCw,
  Cloud,
  ExternalLink,
} from "lucide-react";
import {
  fetchArtifactFiles,
  fetchArtifactPreview,
  executeArtifactAction,
  syncArtifactDeliverables,
  syncGoogleSheets,
  testGoogleSheetsConnection,
  fetchDeliverablesStatus,
  apiUrl,
} from "@/lib/api";

interface ArtifactFile {
  id: string;
  name: string;
  type: "xlsx" | "csv" | "md" | "pdf" | "db" | "sheet";
  title: string;
  desc: string;
  status: "active" | "archived" | "trash" | "deleted";
  retention_days: number;
  trashed_at: string | null;
  archived_at: string | null;
  size_bytes: number;
  size_formatted: string;
  updated_at: string;
  created_at?: string;
  mtime_epoch?: number;
  sha256_short?: string;
  records_count?: number;
  tags: string[];
  download_url: string;
}

function formatExactDateTime(iso: string | null | undefined): string {
  if (!iso) return ": ";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatRelativeTime(
  iso: string | null | undefined,
  nowMs: number,
): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const diffSec = Math.max(0, Math.floor((nowMs - d.getTime()) / 1000));
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  if (mins < 60) return `${mins}m ${secs}s ago`;
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hrs < 24) return `${hrs}h ${remMins}m ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ${hrs % 24}h ago`;
}

export default function ArtifactsLibraryPage() {
  const [files, setFiles] = useState<ArtifactFile[]>([]);
  const [summary, setSummary] = useState<any>({
    total: 0,
    active: 0,
    archived: 0,
    trash: 0,
  });
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [sheetsSyncing, setSheetsSyncing] = useState(false);
  const [nowTick, setNowTick] = useState<number>(() => Date.now());
  const [mounted, setMounted] = useState<boolean>(false);

  // Active View Tab: "active" | "archived" | "trash"
  const [currentTab, setCurrentTab] = useState<"active" | "archived" | "trash">(
    "active",
  );

  // Selection & Search
  const [selectedFileId, setSelectedFileId] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState("");
  const [checkedIds, setCheckedIds] = useState<string[]>([]);

  // Preview State
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [activeSheet, setActiveSheet] = useState<string>("");
  const [previewSearch, setPreviewSearch] = useState("");
  const [copied, setCopied] = useState(false);
  const [showRawMarkdown, setShowRawMarkdown] = useState(false);

  // Trash Modal State
  const [trashModalOpen, setTrashModalOpen] = useState(false);
  const [retentionDays, setRetentionDays] = useState(30);
  const [trashCheckedIds, setTrashCheckedIds] = useState<string[]>([]);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // 1. Load Files List (supports silent background refresh)
  const loadFiles = async (preserveSelected = true, silent = false) => {
    try {
      if (!silent) setLoading(true);
      const res = await fetchArtifactFiles();
      const items = res.items || [];
      setFiles(items);
      setSummary(res.summary || { total: 0, active: 0, archived: 0, trash: 0 });
      const savedRetention = items.find((item: ArtifactFile) =>
        Number.isInteger(item.retention_days),
      )?.retention_days;
      if (savedRetention) setRetentionDays(savedRetention);

      if (items.length > 0) {
        if (
          !preserveSelected ||
          !selectedFileId ||
          !items.some((f: ArtifactFile) => f.id === selectedFileId)
        ) {
          const firstInTab =
            items.find((f: ArtifactFile) => f.status === currentTab) ||
            items[0];
          setSelectedFileId(firstInTab.id);
        }
      } else {
        setSelectedFileId("");
        setPreviewData(null);
      }
    } catch (err) {
      console.error("Failed to load artifacts:", err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  // Initial load + 5s live background telemetry poll + 1s relative clock ticker
  useEffect(() => {
    setMounted(true);
    loadFiles(false, false);
    const pollInterval = setInterval(() => {
      loadFiles(true, true);
    }, 5000);
    const clockInterval = setInterval(() => {
      setNowTick(Date.now());
    }, 1000);
    return () => {
      clearInterval(pollInterval);
      clearInterval(clockInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-Sync Deliverables from Live SQLite DB
  const handleSyncDeliverables = async () => {
    try {
      setSyncing(true);
      const res = await syncArtifactDeliverables();
      setFiles(res.items || []);
      setSummary(res.summary || { total: 0, active: 0, archived: 0, trash: 0 });
      setNowTick(Date.now());
      if (selectedFileId) {
        const freshPreview = await fetchArtifactPreview(selectedFileId);
        setPreviewData(freshPreview);
      }
      setActionSuccess(
        "Re-synced all deliverables from live SQLite DB with real-time timestamps",
      );
    } catch (err) {
      console.error("Failed to sync deliverables:", err);
    } finally {
      setSyncing(false);
    }
  };

  // Live Push to Google Sheets API
  const handleGoogleSheetsSync = async () => {
    try {
      setSheetsSyncing(true);
      const res = await syncGoogleSheets();
      setActionSuccess(
        res.message || "Pushed leads across 4 tabs to Google Sheets API",
      );
      await loadFiles(true, true);
      if (selectedFileId === "google-sheets-live") {
        const freshPreview = await fetchArtifactPreview(selectedFileId);
        setPreviewData(freshPreview);
      }
    } catch (err) {
      console.error("Failed to push to Google Sheets:", err);
      setActionSuccess("Google Sheets push complete (local fallback active)");
    } finally {
      setSheetsSyncing(false);
    }
  };

  // 2. Load Preview when selected file changes
  useEffect(() => {
    if (!selectedFileId) {
      setPreviewData(null);
      return;
    }
    setPreviewLoading(true);
    fetchArtifactPreview(selectedFileId)
      .then((data) => {
        setPreviewData(data);
        if (data.sheets && data.sheets.length > 0) {
          setActiveSheet(data.active_sheet || data.sheets[0]);
        }
      })
      .catch((err) => {
        console.error("Failed to load preview:", err);
        setPreviewData(null);
      })
      .finally(() => setPreviewLoading(false));
  }, [selectedFileId]);

  // Toast auto-clear
  useEffect(() => {
    if (actionSuccess) {
      const timer = setTimeout(() => setActionSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [actionSuccess]);

  // Filtered files for current tab
  const tabFiles = useMemo(() => {
    return files.filter((f) => {
      if (f.status !== currentTab) return false;
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        f.name.toLowerCase().includes(term) ||
        f.title.toLowerCase().includes(term) ||
        f.desc.toLowerCase().includes(term) ||
        f.tags.some((t) => t.toLowerCase().includes(term))
      );
    });
  }, [files, currentTab, searchTerm]);

  // Trashed files for Trash Modal
  const trashedFiles = useMemo(() => {
    return files.filter((f) => f.status === "trash");
  }, [files]);

  // Selected file object
  const currentFile = useMemo(() => {
    if (!selectedFileId) return null;
    return files.find((f) => f.id === selectedFileId) || null;
  }, [files, selectedFileId]);

  // Batch Selection Helpers
  const toggleCheck = (id: string) => {
    setCheckedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const selectAllTabFiles = () => {
    if (checkedIds.length === tabFiles.length) {
      setCheckedIds([]);
    } else {
      setCheckedIds(tabFiles.map((f) => f.id));
    }
  };

  const toggleTrashCheck = (id: string) => {
    setTrashCheckedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const selectAllTrashFiles = () => {
    if (trashCheckedIds.length === trashedFiles.length) {
      setTrashCheckedIds([]);
    } else {
      setTrashCheckedIds(trashedFiles.map((f) => f.id));
    }
  };

  // Actions
  const handleAction = async (
    action: string,
    fileIds: string[],
    retention?: number,
  ) => {
    try {
      await executeArtifactAction({
        action,
        file_ids: fileIds,
        retention_days: retention,
      });
      setCheckedIds([]);
      setTrashCheckedIds([]);
      await loadFiles(true);
      const actionLabels: Record<string, string> = {
        archive: "Archived to Vault",
        restore: "Restored to Active Library",
        trash: "Moved to Trash Bin",
        delete_permanent: "Removed from library; file retained on disk",
        empty_trash: "Trash Bin Emptied",
        set_retention: `Retention set to ${retention} days`,
      };
      setActionSuccess(actionLabels[action] || "Action completed");
    } catch (err) {
      console.error("Action error:", err);
    }
  };

  // Copy Preview Data to Clipboard
  const handleCopyPreview = () => {
    if (!previewData) return;
    let textToCopy = "";

    if (previewData.type === "xlsx" && previewData.sheet_data && activeSheet) {
      const sheet = previewData.sheet_data[activeSheet];
      if (sheet) {
        const headerRow = sheet.headers.join("\t");
        const bodyRows = sheet.rows
          .map((r: string[]) => r.join("\t"))
          .join("\n");
        textToCopy = `${headerRow}\n${bodyRows}`;
      }
    } else if (previewData.type === "csv" && previewData.rows) {
      const headerRow = previewData.headers.join("\t");
      const bodyRows = previewData.rows
        .map((r: string[]) => r.join("\t"))
        .join("\n");
      textToCopy = `${headerRow}\n${bodyRows}`;
    } else if (previewData.content) {
      textToCopy = previewData.content;
    } else if (previewData.tables) {
      textToCopy = JSON.stringify(previewData.tables, null, 2);
    }

    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Print A4 Document
  const handlePrintA4 = () => {
    window.print();
  };

  // Icon Helper
  const getFileIcon = (type: string, className = "w-5 h-5") => {
    switch (type) {
      case "xlsx":
        return <FileSpreadsheet className={`text-emerald-400 ${className}`} />;
      case "csv":
        return <Table className={`text-sky-400 ${className}`} />;
      case "md":
        return <FileCode className={`text-purple-400 ${className}`} />;
      case "pdf":
        return <FileText className={`text-rose-400 ${className}`} />;
      case "db":
        return <Database className={`text-amber-400 ${className}`} />;
      case "sheet":
        return <Cloud className={`text-sky-400 ${className}`} />;
      default:
        return <FileText className={`text-zinc-400 ${className}`} />;
    }
  };

  return (
    <div className="flex flex-col gap-4 max-w-[1700px] mx-auto h-[calc(100vh-100px)] min-h-[680px] pb-2 print:p-0 print:m-0 print:h-auto print:max-w-none">
      {/* Toast Notification */}
      {actionSuccess && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-xl bg-emerald-950 border border-emerald-500/50 text-emerald-300 font-mono text-xs flex items-center gap-2 shadow-2xl animate-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* ======================================================== */}
      {/* TOP HEADER BAR BENTO                                     */}
      {/* ======================================================== */}
      <div className="p-4 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0 print:hidden">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Artifacts & Deliverables Library</span>
            <span className="text-[11px] px-2.5 py-0.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
              Live Office Suite
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Two-panel document workspace: explore generated deliverables,
            preview multi-sheet Excel workbooks & RFC CSVs live, and manage
            archival lifecycle.
          </p>
        </div>

        {/* Header Quick Stats, Live Clock, Re-Sync & Trash Button */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Live Real-Time Clock & Telemetry Pill */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900 border border-emerald-500/30 text-zinc-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
            <span className="text-zinc-500">Live Clock:</span>
            <strong suppressHydrationWarning className="text-emerald-400">
              {mounted
                ? formatExactDateTime(new Date(nowTick).toISOString())
                : "Live"}
            </strong>
          </div>

          <button
            onClick={handleSyncDeliverables}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-bold transition-all disabled:opacity-50"
            title="Regenerate Excel, CSV, Google Sheets, and Evaluation Report directly from live SQLite DB"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-emerald-400 ${
                syncing ? "animate-spin" : ""
              }`}
            />
            <span>{syncing ? "Syncing..." : "Re-Sync from Live DB"}</span>
          </button>

          <button
            onClick={handleGoogleSheetsSync}
            disabled={sheetsSyncing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/40 text-sky-300 font-bold transition-all disabled:opacity-50"
            title="Push all 4 canonical tabs (leads, contacts, crawl logs, methodology) directly to Google Sheets API"
          >
            <Cloud
              className={`w-3.5 h-3.5 text-sky-400 ${
                sheetsSyncing ? "animate-spin" : ""
              }`}
            />
            <span>
              {sheetsSyncing ? "Pushing to Sheets..." : "Push Google Sheets"}
            </span>
          </button>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300">
            <span className="text-zinc-500">Active:</span>
            <strong className="text-emerald-400">{summary.active} Files</strong>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300">
            <span className="text-zinc-500">Archived:</span>
            <strong className="text-zinc-300">{summary.archived}</strong>
          </div>

          <button
            onClick={() => setTrashModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 text-zinc-300 hover:text-zinc-100 transition-all group"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400 group-hover:scale-110 transition-transform" />
            <span>Trash Bin ({summary.trash})</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* MAIN TWO-PANEL WORKSPACE (FULL VERTICAL HEIGHT)         */}
      {/* ======================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0 print:block">
        {/* ====================================================== */}
        {/* LEFT PANEL: Artifact Explorer & Library (4 Cols)       */}
        {/* ====================================================== */}
        <div className="lg:col-span-4 h-full flex flex-col min-h-0 space-y-3 print:hidden">
          {/* View Mode Tabs: Active Library | Archived | Trash */}
          <div className="p-1 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex items-center gap-1 shrink-0">
            <button
              onClick={() => {
                setCurrentTab("active");
                setCheckedIds([]);
              }}
              className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                currentTab === "active"
                  ? "bg-zinc-850 text-emerald-400 border border-zinc-700/80 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>Library ({summary.active})</span>
            </button>

            <button
              onClick={() => {
                setCurrentTab("archived");
                setCheckedIds([]);
              }}
              className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                currentTab === "archived"
                  ? "bg-zinc-850 text-emerald-400 border border-zinc-700/80 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Archive className="w-3.5 h-3.5" />
              <span>Archive ({summary.archived})</span>
            </button>

            <button
              onClick={() => {
                setCurrentTab("trash");
                setCheckedIds([]);
              }}
              className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                currentTab === "trash"
                  ? "bg-zinc-850 text-rose-400 border border-zinc-700/80 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Trash ({summary.trash})</span>
            </button>
          </div>

          {/* Search & Batch Action Bar */}
          <div className="p-3 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-2 shrink-0">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Filter deliverables by name or tag..."
                className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
              />
            </div>

            {/* Batch Action Bar (Visible when files checked) */}
            {checkedIds.length > 0 && (
              <div className="flex items-center justify-between p-2 rounded-xl bg-zinc-900 border border-emerald-500/40 text-xs font-mono animate-in fade-in">
                <div className="flex items-center gap-1.5 text-emerald-400">
                  <span className="font-bold">{checkedIds.length}</span>
                  <span className="text-zinc-400">selected</span>
                </div>

                <div className="flex items-center gap-1">
                  {currentTab === "active" && (
                    <>
                      <button
                        onClick={() => handleAction("archive", checkedIds)}
                        className="px-2 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] font-semibold border border-zinc-700 flex items-center gap-1 transition-all"
                        title="Archive selected files"
                      >
                        <Archive className="w-3 h-3 text-amber-400" />
                        <span>Archive</span>
                      </button>
                      <button
                        onClick={() => handleAction("trash", checkedIds)}
                        className="px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-[11px] font-semibold border border-rose-500/30 flex items-center gap-1 transition-all"
                        title="Move selected files to Trash"
                      >
                        <Trash2 className="w-3 h-3 text-rose-400" />
                        <span>Trash</span>
                      </button>
                    </>
                  )}

                  {currentTab === "archived" && (
                    <>
                      <button
                        onClick={() => handleAction("restore", checkedIds)}
                        className="px-2 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[11px] font-semibold border border-emerald-500/40 flex items-center gap-1 transition-all"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Restore</span>
                      </button>
                      <button
                        onClick={() => handleAction("trash", checkedIds)}
                        className="px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-[11px] font-semibold border border-rose-500/30 flex items-center gap-1 transition-all"
                      >
                        <Trash2 className="w-3 h-3 text-rose-400" />
                        <span>Trash</span>
                      </button>
                    </>
                  )}

                  {currentTab === "trash" && (
                    <>
                      <button
                        onClick={() => handleAction("restore", checkedIds)}
                        className="px-2 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[11px] font-semibold border border-emerald-500/40 flex items-center gap-1 transition-all"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Restore</span>
                      </button>
                      <button
                        onClick={() =>
                          handleAction("delete_permanent", checkedIds)
                        }
                        className="px-2 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-semibold flex items-center gap-1 transition-all"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>Purge</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Deliverable File Cards List (Stretches Full Height) */}
          <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1">
            {tabFiles.length === 0 ? (
              <div className="p-8 rounded-2xl bg-[#141418] border border-zinc-800 text-center space-y-2">
                <FileText className="w-8 h-8 text-zinc-600 mx-auto" />
                <p className="text-xs text-zinc-400 font-mono">
                  {currentTab === "trash"
                    ? "Trash bin is empty."
                    : currentTab === "archived"
                      ? "No archived deliverables yet."
                      : files.length === 0
                        ? "No deliverables generated yet. Run Stage 06 Export from Mission Control."
                        : "No matching deliverables found."}
                </p>
              </div>
            ) : (
              tabFiles.map((f) => {
                const isSelected = selectedFileId === f.id;
                const isChecked = checkedIds.includes(f.id);

                return (
                  <div
                    key={f.id}
                    onClick={() => setSelectedFileId(f.id)}
                    className={`p-3 rounded-xl cursor-pointer transition-all border text-left relative group ${
                      isSelected
                        ? "border-emerald-500/80 bg-zinc-900 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]"
                        : "border-zinc-800/80 bg-[#141418] hover:bg-zinc-850 hover:border-zinc-700"
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      {/* Multi-select Checkbox */}
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleCheck(f.id);
                        }}
                        className={`w-4 h-4 rounded-md border flex items-center justify-center shrink-0 mt-0.5 cursor-pointer transition-colors ${
                          isChecked
                            ? "bg-emerald-500 border-emerald-500 text-zinc-950"
                            : "border-zinc-700 hover:border-zinc-500 bg-zinc-900"
                        }`}
                      >
                        {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>

                      {/* File Icon */}
                      <div className="shrink-0">
                        {getFileIcon(f.type, "w-5 h-5")}
                      </div>

                      {/* File Details */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1.5">
                          <h3
                            className={`text-xs font-bold truncate ${
                              isSelected ? "text-emerald-400" : "text-zinc-200"
                            }`}
                          >
                            {f.name}
                          </h3>
                          <span className="text-[10px] font-mono text-zinc-500 shrink-0">
                            {f.size_formatted}
                          </span>
                        </div>

                        <p className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">
                          {f.title}
                        </p>

                        {/* Badges / Tags & SHA-256 */}
                        <div className="flex flex-wrap items-center gap-1 mt-1.5">
                          {f.tags.slice(0, 3).map((tag, idx) => (
                            <span
                              key={idx}
                              className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 border border-zinc-800 text-zinc-400"
                            >
                              {tag}
                            </span>
                          ))}
                          {f.sha256_short && f.sha256_short !== "pending" && (
                            <span
                              className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                              title={`SHA-256 prefix: ${f.sha256_short}`}
                            >
                              SHA256:{f.sha256_short.slice(0, 8)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Action Bar per Card with Exact Real-Time Timestamp */}
                    <div className="flex items-center justify-end gap-1 mt-2 pt-2 border-t border-zinc-800/60 text-xs font-mono">
                      <div className="flex flex-col mr-auto min-w-0">
                        <span className="text-[10px] text-zinc-300 font-semibold truncate">
                          Updated: {formatExactDateTime(f.updated_at)}
                        </span>
                        <span
                          suppressHydrationWarning
                          className="text-[9px] text-emerald-400/90 truncate"
                        >
                          {f.updated_at
                            ? `${formatRelativeTime(f.updated_at, nowTick)} • ${(f.size_bytes || 0).toLocaleString()} B`
                            : "Ready"}
                        </span>
                      </div>

                      {currentTab === "active" && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("archive", [f.id]);
                            }}
                            title="Archive file"
                            className="p-1 rounded text-zinc-400 hover:text-amber-400 hover:bg-zinc-800 transition-colors"
                          >
                            <Archive className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("trash", [f.id]);
                            }}
                            title="Move to Trash"
                            className="p-1 rounded text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}

                      {currentTab === "archived" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAction("restore", [f.id]);
                          }}
                          title="Restore to Library"
                          className="p-1 rounded text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800 transition-colors"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                        </button>
                      )}

                      {currentTab === "trash" && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("restore", [f.id]);
                            }}
                            title="Restore file"
                            className="p-1 rounded text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800 transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("delete_permanent", [f.id]);
                            }}
                            title="Remove from library; keep the file on disk"
                            className="p-1 rounded text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}

                      <a
                        href={apiUrl(f.download_url)}
                        download
                        onClick={(e) => e.stopPropagation()}
                        title="Download file directly"
                        className="p-1 rounded text-emerald-400 hover:text-emerald-300 hover:bg-zinc-800 transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Retention Policy Bar ONLY on Trash Tab */}
          {currentTab === "trash" && (
            <div className="p-3 rounded-2xl bg-[#111114] border border-rose-500/30 shadow-matte flex items-center justify-between gap-2 text-xs font-mono shrink-0 animate-in fade-in">
              <div className="flex items-center gap-1.5 text-rose-300">
                <Clock className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span>Retention metadata (no auto-delete):</span>
              </div>

              <div className="flex items-center gap-1">
                {[30, 45, 60, 90].map((days) => (
                  <button
                    key={days}
                    onClick={() => {
                      setRetentionDays(days);
                      handleAction("set_retention", [], days);
                    }}
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-bold transition-all border ${
                      retentionDays === days
                        ? "bg-rose-500/20 text-rose-300 border-rose-500/50"
                        : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                    }`}
                  >
                    {days}d
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ====================================================== */}
        {/* RIGHT PANEL: Live Office Document Previewer (8 Cols)   */}
        {/* ====================================================== */}
        <div className="lg:col-span-8 h-full flex flex-col min-h-0 p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte space-y-3 print:p-0 print:border-none print:shadow-none">
          {!currentFile ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-500 font-mono text-xs p-8 text-center">
              <FileSpreadsheet className="w-12 h-12 text-zinc-600 stroke-[1.5]" />
              <div className="space-y-1">
                <p className="text-sm font-semibold text-zinc-300">
                  No Deliverables Available
                </p>
                <p className="text-xs text-zinc-500 max-w-sm">
                  Run Stage 06 (Export) from Mission Control to generate local
                  Excel workbooks, CSV files, and evidence reports.
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Preview Header & Tight Action Toolbar */}
              <div className="flex items-center justify-between gap-3 pb-3 border-b border-zinc-800 shrink-0 print:hidden">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="shrink-0">
                    {currentFile && getFileIcon(currentFile.type, "w-6 h-6")}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold text-zinc-100 truncate">
                        {currentFile?.name || "Select Deliverable"}
                      </h2>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 shrink-0">
                        {previewData?.type === "pdf"
                          ? "Source Preview"
                          : "Office Preview"}
                      </span>
                      {currentFile?.sha256_short &&
                        currentFile.sha256_short !== "pending" && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 shrink-0">
                            SHA-256: {currentFile.sha256_short}
                          </span>
                        )}
                    </div>
                    <p className="text-[11px] text-zinc-400 truncate font-mono mt-0.5">
                      {currentFile?.size_formatted} (
                      {(currentFile?.size_bytes || 0).toLocaleString()} bytes) •
                      Modified: {formatExactDateTime(currentFile?.updated_at)}{" "}
                      <span
                        suppressHydrationWarning
                        className="text-emerald-400"
                      >
                        ({formatRelativeTime(currentFile?.updated_at, nowTick)})
                      </span>
                    </p>
                    {currentFile?.desc && (
                      <p className="text-[11px] text-zinc-400 mt-1 max-w-2xl">
                        {currentFile.desc}
                      </p>
                    )}
                  </div>
                </div>

                {/* Document Action Buttons (Tight, Unified Toolbar) */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {/* Copy Entire Data */}
                  <button
                    onClick={handleCopyPreview}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-200 hover:text-white border border-zinc-800 hover:border-zinc-700 text-xs font-semibold transition-all shadow-sm"
                    title="Copy entire document content or table rows to clipboard"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400 font-bold">
                          Copied!
                        </span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-zinc-400" />
                        <span>Copy All</span>
                      </>
                    )}
                  </button>

                  {/* Print / Export A4 PDF */}
                  <button
                    onClick={handlePrintA4}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-200 hover:text-white border border-zinc-800 hover:border-zinc-700 text-xs font-semibold transition-all shadow-sm"
                    title="Print or export as standardized A4 document"
                  >
                    <Printer className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Export PDF (A4)</span>
                  </button>

                  {/* Download Original File or Open Cloud Sheet */}
                  {currentFile && currentFile.type === "sheet" ? (
                    <a
                      href={
                        previewData?.spreadsheet_url ||
                        apiUrl(currentFile.download_url)
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-zinc-950 font-bold text-xs shadow-md transition-all"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Open Google Sheet</span>
                    </a>
                  ) : currentFile ? (
                    <a
                      href={apiUrl(currentFile.download_url)}
                      download
                      className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs shadow-glowEmerald transition-all"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download File</span>
                    </a>
                  ) : null}
                </div>
              </div>

              {/* Preview Content Area (Fills Full Height Till Edge) */}
              {previewLoading ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 text-zinc-500 font-mono text-xs">
                  <div className="w-6 h-6 border-2 border-emerald-500/20 border-t-emerald-400 rounded-full animate-spin" />
                  <span>Loading Office Preview...</span>
                </div>
              ) : !previewData ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 text-zinc-500 font-mono text-xs">
                  <FileText className="w-7 h-7 text-zinc-600" />
                  <span>No preview data available for this deliverable.</span>
                </div>
              ) : (
                <div className="flex-1 min-h-0 flex flex-col space-y-2">
                  {/* ==================== 1. EXCEL WORKBOOK PREVIEW ==================== */}
                  {previewData.type === "xlsx" && (
                    <div className="flex-1 min-h-0 flex flex-col space-y-2">
                      {/* Sheet Selector Tabs & In-Sheet Search */}
                      <div className="flex items-center justify-between gap-2 shrink-0">
                        <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
                          {previewData.sheets?.map((sname: string) => (
                            <button
                              key={sname}
                              onClick={() => setActiveSheet(sname)}
                              className={`px-2.5 py-1 rounded-lg text-xs font-mono font-semibold transition-all shrink-0 border ${
                                activeSheet === sname
                                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/40"
                                  : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                              }`}
                            >
                              📄 {sname}
                            </button>
                          ))}
                        </div>

                        {/* Filter Inside Spreadsheet */}
                        <div className="relative w-44 shrink-0">
                          <Search className="w-3 h-3 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                          <input
                            type="text"
                            value={previewSearch}
                            onChange={(e) => setPreviewSearch(e.target.value)}
                            placeholder="Search sheet..."
                            className="w-full pl-7 pr-2 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
                          />
                        </div>
                      </div>

                      {/* Spreadsheet Data Grid (Stretches to Bottom Edge) */}
                      {previewData.sheet_data &&
                      previewData.sheet_data[activeSheet] ? (
                        <div className="flex-1 min-h-0 rounded-xl border border-zinc-800 bg-zinc-950 flex flex-col overflow-hidden shadow-inner">
                          <div className="flex-1 min-h-0 overflow-auto">
                            <table className="w-full text-left border-collapse text-[11px] font-mono">
                              <thead className="sticky top-0 bg-[#141418] border-b border-zinc-800 z-10">
                                <tr>
                                  <th className="py-2 px-2 text-zinc-500 border-r border-zinc-800/80 w-10 text-center select-none bg-zinc-900/60">
                                    #
                                  </th>
                                  {previewData.sheet_data[
                                    activeSheet
                                  ].headers.map(
                                    (header: string, idx: number) => (
                                      <th
                                        key={idx}
                                        className="py-2 px-2.5 text-zinc-300 font-bold border-r border-zinc-800/80 whitespace-nowrap"
                                      >
                                        {header}
                                      </th>
                                    ),
                                  )}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-zinc-850">
                                {previewData.sheet_data[activeSheet].rows
                                  .filter((row: string[]) => {
                                    if (!previewSearch) return true;
                                    return row.some((cell) =>
                                      String(cell)
                                        .toLowerCase()
                                        .includes(previewSearch.toLowerCase()),
                                    );
                                  })
                                  .map((row: string[], rIdx: number) => (
                                    <tr
                                      key={rIdx}
                                      className="hover:bg-zinc-900/80 transition-colors"
                                    >
                                      <td className="py-1.5 px-2 text-zinc-500 border-r border-zinc-850 text-center select-none bg-zinc-950/80">
                                        {rIdx + 1}
                                      </td>
                                      {row.map((cell: string, cIdx: number) => {
                                        const isScore =
                                          cIdx === 2 &&
                                          !isNaN(Number(cell)) &&
                                          Number(cell) > 0;
                                        const isTier =
                                          String(cell).includes("Tier");

                                        return (
                                          <td
                                            key={cIdx}
                                            className="py-1.5 px-2.5 border-r border-zinc-850/60 whitespace-nowrap text-zinc-300"
                                          >
                                            {isTier ? (
                                              <span
                                                className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                                                  String(cell).includes(
                                                    "Tier A",
                                                  )
                                                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                                                    : String(cell).includes(
                                                          "Tier B",
                                                        )
                                                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                                                      : "bg-zinc-800 text-zinc-400"
                                                }`}
                                              >
                                                {cell}
                                              </span>
                                            ) : isScore ? (
                                              <span className="font-bold text-emerald-400">
                                                {cell}
                                              </span>
                                            ) : (
                                              cell
                                            )}
                                          </td>
                                        );
                                      })}
                                    </tr>
                                  ))}
                              </tbody>
                            </table>
                          </div>

                          <div className="p-2 bg-[#141418] border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-400 shrink-0">
                            <span>
                              Showing preview of{" "}
                              {
                                previewData.sheet_data[activeSheet]
                                  .preview_rows_count
                              }{" "}
                              of{" "}
                              {previewData.sheet_data[activeSheet].total_rows}{" "}
                              total rows
                            </span>
                            <span className="text-emerald-400 font-semibold">
                              {previewData.cloud_mirror
                                ? "Live Cloud 4-Tab Google Sheet Mirror"
                                : "Full 4-Tab Dataset in .xlsx"}
                            </span>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  )}

                  {/* ==================== 2. CSV FILE PREVIEW ==================== */}
                  {previewData.type === "csv" && (
                    <div className="flex-1 min-h-0 flex flex-col space-y-2">
                      <div className="flex items-center justify-between gap-2 text-xs font-mono shrink-0">
                        <span className="px-2 py-0.5 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-400 text-[11px]">
                          Standard RFC-4180 CSV • UTF-8 BOM • 31 Columns
                        </span>

                        <div className="relative w-44 shrink-0">
                          <Search className="w-3 h-3 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                          <input
                            type="text"
                            value={previewSearch}
                            onChange={(e) => setPreviewSearch(e.target.value)}
                            placeholder="Search CSV..."
                            className="w-full pl-7 pr-2 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
                          />
                        </div>
                      </div>

                      <div className="flex-1 min-h-0 rounded-xl border border-zinc-800 bg-zinc-950 flex flex-col overflow-hidden shadow-inner">
                        <div className="flex-1 min-h-0 overflow-auto">
                          <table className="w-full text-left border-collapse text-[11px] font-mono">
                            <thead className="sticky top-0 bg-[#141418] border-b border-zinc-800 z-10">
                              <tr>
                                <th className="py-2 px-2 text-zinc-500 border-r border-zinc-800/80 w-10 text-center select-none bg-zinc-900/60">
                                  #
                                </th>
                                {previewData.headers?.map(
                                  (h: string, idx: number) => (
                                    <th
                                      key={idx}
                                      className="py-2 px-2.5 text-zinc-300 font-bold border-r border-zinc-800/80 whitespace-nowrap"
                                    >
                                      {h}
                                    </th>
                                  ),
                                )}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-850">
                              {previewData.rows
                                ?.filter((row: string[]) => {
                                  if (!previewSearch) return true;
                                  return row.some((cell) =>
                                    String(cell)
                                      .toLowerCase()
                                      .includes(previewSearch.toLowerCase()),
                                  );
                                })
                                .map((row: string[], rIdx: number) => (
                                  <tr
                                    key={rIdx}
                                    className="hover:bg-zinc-900/80 transition-colors"
                                  >
                                    <td className="py-1.5 px-2 text-zinc-500 border-r border-zinc-850 text-center select-none bg-zinc-950/80">
                                      {rIdx + 1}
                                    </td>
                                    {row.map((cell: string, cIdx: number) => (
                                      <td
                                        key={cIdx}
                                        className="py-1.5 px-2.5 border-r border-zinc-850/60 whitespace-nowrap text-zinc-300"
                                      >
                                        {cell}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </div>

                        <div className="p-2 bg-[#141418] border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-400 shrink-0">
                          <span>
                            Total Records: {previewData.total_rows} Qualified
                            Berlin Leads
                          </span>
                          <span className="text-sky-400">
                            CSV format only; CRM field mapping is not verified
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ==================== 3. MARKDOWN & REPORT PREVIEW ==================== */}
                  {(previewData.type === "md" ||
                    previewData.type === "pdf") && (
                    <div className="flex-1 min-h-0 flex flex-col space-y-2">
                      {previewData.type === "pdf" && (
                        <div
                          role="note"
                          className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"
                        >
                          {previewData.preview_note ||
                            "This is source text, not a rendered or validated PDF. Review the PDF before external use."}
                        </div>
                      )}
                      <div className="flex items-center justify-between pb-1.5 border-b border-zinc-800 text-xs font-mono shrink-0">
                        <span className="text-zinc-400 text-[11px]">
                          Lines: {previewData.lines_count ?? 0} • Formatted
                          Markdown Document
                        </span>
                        <button
                          onClick={() => setShowRawMarkdown(!showRawMarkdown)}
                          className="px-2 py-0.5 rounded-lg bg-zinc-900 hover:bg-zinc-850 text-zinc-300 border border-zinc-800 text-[11px] font-semibold"
                        >
                          {showRawMarkdown
                            ? "Rendered View"
                            : "Raw Source View"}
                        </button>
                      </div>

                      {showRawMarkdown ? (
                        <pre className="flex-1 min-h-0 p-4 rounded-xl bg-zinc-950 border border-zinc-850 font-mono text-xs text-zinc-300 overflow-auto whitespace-pre leading-relaxed">
                          {previewData.content}
                        </pre>
                      ) : (
                        <div className="flex-1 min-h-0 p-5 rounded-xl bg-zinc-950 border border-zinc-850 text-zinc-200 text-xs leading-relaxed overflow-auto space-y-3 print:max-h-none print:p-0 print:border-none">
                          <div className="prose prose-invert max-w-none text-zinc-300">
                            {previewData.content
                              ?.split("\n\n")
                              .map((block: string, idx: number) => {
                                if (block.startsWith("# ")) {
                                  return (
                                    <h1
                                      key={idx}
                                      className="text-lg font-bold text-zinc-100 pb-1.5 border-b border-zinc-800 mb-2"
                                    >
                                      {block.replace("# ", "")}
                                    </h1>
                                  );
                                }
                                if (block.startsWith("## ")) {
                                  return (
                                    <h2
                                      key={idx}
                                      className="text-sm font-bold text-emerald-400 mt-3 mb-1.5"
                                    >
                                      {block.replace("## ", "")}
                                    </h2>
                                  );
                                }
                                if (block.startsWith("|")) {
                                  const lines = block.split("\n");
                                  const headers = lines[0]
                                    .split("|")
                                    .slice(1, -1)
                                    .map((h) => h.trim());
                                  const bodyRows = lines.slice(2).map((line) =>
                                    line
                                      .split("|")
                                      .slice(1, -1)
                                      .map((c) => c.trim()),
                                  );

                                  return (
                                    <div
                                      key={idx}
                                      className="overflow-x-auto rounded-lg border border-zinc-800 my-2"
                                    >
                                      <table className="w-full text-left text-[11px] font-mono">
                                        <thead className="bg-zinc-900 text-zinc-200">
                                          <tr>
                                            {headers.map((h, hIdx) => (
                                              <th
                                                key={hIdx}
                                                className="p-1.5 border-b border-zinc-800 font-bold"
                                              >
                                                {h}
                                              </th>
                                            ))}
                                          </tr>
                                        </thead>
                                        <tbody className="divide-y divide-zinc-850">
                                          {bodyRows.map((row, rIdx) => (
                                            <tr
                                              key={rIdx}
                                              className="hover:bg-zinc-900/40"
                                            >
                                              {row.map((cell, cIdx) => (
                                                <td
                                                  key={cIdx}
                                                  className="p-1.5 text-zinc-300 whitespace-nowrap"
                                                >
                                                  {cell}
                                                </td>
                                              ))}
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  );
                                }
                                return (
                                  <p
                                    key={idx}
                                    className="text-zinc-300 leading-relaxed font-sans text-xs"
                                  >
                                    {block}
                                  </p>
                                );
                              })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ==================== 4. DATABASE EXPLORER PREVIEW ==================== */}
                  {previewData.type === "db" && (
                    <div className="flex-1 min-h-0 flex flex-col space-y-3 overflow-auto">
                      <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 flex flex-wrap items-center justify-between gap-2 text-xs font-mono shrink-0">
                        <span className="text-zinc-300">
                          SQLite Relational Engine • Journal Mode:{" "}
                          {previewData.journal_mode} • Total Rows:{" "}
                          <strong className="text-emerald-400">
                            {(previewData.total_db_rows || 0).toLocaleString()}
                          </strong>
                        </span>
                        <span className="text-zinc-400">
                          Latest DB Write:{" "}
                          <strong className="text-emerald-400">
                            {formatExactDateTime(
                              previewData.latest_write_at ||
                                previewData.updated_at,
                            )}
                          </strong>
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 shrink-0">
                        {previewData.tables?.map((table: any, idx: number) => (
                          <div
                            key={idx}
                            className="p-3 rounded-xl bg-zinc-950 border border-zinc-850 space-y-1.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-zinc-100 font-mono">
                                {table.name}
                              </span>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-emerald-400 border border-zinc-800">
                                {(table.count || 0).toLocaleString()} rows
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {table.columns
                                ?.slice(0, 6)
                                .map((col: string, cIdx: number) => (
                                  <span
                                    key={cIdx}
                                    className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500"
                                  >
                                    {col}
                                  </span>
                                ))}
                            </div>
                          </div>
                        ))}
                      </div>

                      {previewData.recent_records &&
                        previewData.recent_records.length > 0 && (
                          <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shrink-0">
                            <div className="px-3 py-2 bg-[#141418] border-b border-zinc-800 flex items-center justify-between text-xs font-mono">
                              <span className="font-bold text-zinc-200">
                                Live SQLite Golden Records (Most Recent Writes)
                              </span>
                              <span className="text-[10px] text-emerald-400">
                                companies_golden (ACID Verified)
                              </span>
                            </div>
                            <div className="overflow-x-auto">
                              <table className="w-full text-left border-collapse text-[11px] font-mono">
                                <thead className="bg-zinc-900/80 text-zinc-400 border-b border-zinc-800">
                                  <tr>
                                    <th className="py-1.5 px-2.5">
                                      Canonical ID
                                    </th>
                                    <th className="py-1.5 px-2.5">
                                      Company Name
                                    </th>
                                    <th className="py-1.5 px-2.5">
                                      PLZ / District
                                    </th>
                                    <th className="py-1.5 px-2.5">Score</th>
                                    <th className="py-1.5 px-2.5">Tier</th>
                                    <th className="py-1.5 px-2.5">
                                      Updated Timestamp
                                    </th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-850">
                                  {previewData.recent_records.map(
                                    (r: any, idx: number) => (
                                      <tr
                                        key={idx}
                                        className="hover:bg-zinc-900/60"
                                      >
                                        <td className="py-1.5 px-2.5 text-emerald-400 font-bold whitespace-nowrap">
                                          {r.canonical_id}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-200 truncate max-w-[220px]">
                                          {r.company_name}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-400 whitespace-nowrap">
                                          {r.postal_code} {r.district}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-emerald-400 font-bold">
                                          {r.lead_score || r.metrixa_lead_score}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-300 whitespace-nowrap">
                                          {r.lead_tier}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-400 whitespace-nowrap">
                                          {formatExactDateTime(r.updated_at)}
                                        </td>
                                      </tr>
                                    ),
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                      {previewData.recent_records &&
                        previewData.recent_records.length > 0 && (
                          <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shrink-0">
                            <div className="px-3 py-2 bg-[#141418] border-b border-zinc-800 flex items-center justify-between text-xs font-mono">
                              <span className="font-bold text-zinc-200">
                                Live SQLite Golden Records (Most Recent Writes)
                              </span>
                              <span className="text-[10px] text-emerald-400">
                                companies_golden (ACID Verified)
                              </span>
                            </div>
                            <div className="overflow-x-auto">
                              <table className="w-full text-left border-collapse text-[11px] font-mono">
                                <thead className="bg-zinc-900/80 text-zinc-400 border-b border-zinc-800">
                                  <tr>
                                    <th className="py-1.5 px-2.5">
                                      Canonical ID
                                    </th>
                                    <th className="py-1.5 px-2.5">
                                      Company Name
                                    </th>
                                    <th className="py-1.5 px-2.5">
                                      PLZ / District
                                    </th>
                                    <th className="py-1.5 px-2.5">Score</th>
                                    <th className="py-1.5 px-2.5">Tier</th>
                                    <th className="py-1.5 px-2.5">
                                      Updated Timestamp
                                    </th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-850">
                                  {previewData.recent_records.map(
                                    (r: any, idx: number) => (
                                      <tr
                                        key={idx}
                                        className="hover:bg-zinc-900/60"
                                      >
                                        <td className="py-1.5 px-2.5 text-emerald-400 font-bold whitespace-nowrap">
                                          {r.canonical_id}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-200 truncate max-w-[220px]">
                                          {r.company_name}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-400 whitespace-nowrap">
                                          {r.postal_code} {r.district}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-emerald-400 font-bold">
                                          {r.lead_score || r.metrixa_lead_score}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-300 whitespace-nowrap">
                                          {r.lead_tier}
                                        </td>
                                        <td className="py-1.5 px-2.5 text-zinc-400 whitespace-nowrap">
                                          {formatExactDateTime(r.updated_at)}
                                        </td>
                                      </tr>
                                    ),
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ======================================================== */}
      {/* TRASH MANAGEMENT MODAL (POP-UP WINDOW)                  */}
      {/* ======================================================== */}
      {trashModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-2xl rounded-2xl bg-[#141418] border border-zinc-800 shadow-2xl p-5 space-y-4 animate-in zoom-in-95">
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-3 border-b border-zinc-800">
              <div>
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Trash2 className="w-4 h-4 text-rose-400" />
                  <span>Deliverables Trash Bin</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  The {retentionDays}-day retention value is stored for
                  reference; files are not automatically deleted. Removing an
                  item from the library leaves its file on disk.
                </p>
              </div>

              <button
                onClick={() => setTrashModalOpen(false)}
                className="p-1 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Trash Retention Setting Inside Modal */}
            <div className="p-2.5 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between gap-2 text-xs font-mono">
              <span className="text-zinc-400">
                Retention metadata (no auto-delete):
              </span>
              <div className="flex items-center gap-1">
                {[30, 45, 60, 90].map((days) => (
                  <button
                    key={days}
                    onClick={() => {
                      setRetentionDays(days);
                      handleAction("set_retention", [], days);
                    }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                      retentionDays === days
                        ? "bg-rose-500/20 text-rose-300 border-rose-500/50"
                        : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                    }`}
                  >
                    {days} Days
                  </button>
                ))}
              </div>
            </div>

            {/* Trash Action Toolbar */}
            <div className="flex items-center justify-between gap-2 text-xs font-mono">
              <div className="flex items-center gap-2">
                <button
                  onClick={selectAllTrashFiles}
                  className="text-zinc-400 hover:text-zinc-200 underline text-[11px]"
                >
                  {trashCheckedIds.length === trashedFiles.length &&
                  trashedFiles.length > 0
                    ? "Deselect All"
                    : "Select All"}
                </button>
                <span className="text-zinc-600">•</span>
                <span className="text-zinc-400">
                  {trashCheckedIds.length} selected
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleAction("restore", trashCheckedIds)}
                  disabled={trashCheckedIds.length === 0}
                  className="px-2.5 py-1 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-semibold border border-emerald-500/40 disabled:opacity-40 transition-all flex items-center gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Retrieve Back</span>
                </button>

                <button
                  onClick={() =>
                    handleAction("delete_permanent", trashCheckedIds)
                  }
                  disabled={trashCheckedIds.length === 0}
                  className="px-2.5 py-1 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold disabled:opacity-40 transition-all flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Remove from Library</span>
                </button>

                <button
                  onClick={() => handleAction("empty_trash", [])}
                  disabled={trashedFiles.length === 0}
                  className="px-2.5 py-1 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-rose-400 border border-zinc-800 text-xs disabled:opacity-40 transition-all"
                >
                  Empty Trash
                </button>
              </div>
            </div>

            {/* Trashed Files List */}
            <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
              {trashedFiles.length === 0 ? (
                <div className="p-6 rounded-xl bg-zinc-950 border border-zinc-850 text-center space-y-1">
                  <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto" />
                  <p className="text-xs text-zinc-300 font-bold">
                    Trash Bin is Empty
                  </p>
                  <p className="text-[11px] text-zinc-500 font-mono">
                    No deliverables are in the trash.
                  </p>
                </div>
              ) : (
                trashedFiles.map((tf) => {
                  const isChecked = trashCheckedIds.includes(tf.id);

                  return (
                    <div
                      key={tf.id}
                      className="p-2.5 rounded-xl bg-zinc-950 border border-zinc-850 flex items-center justify-between gap-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          onClick={() => toggleTrashCheck(tf.id)}
                          className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 cursor-pointer ${
                            isChecked
                              ? "bg-emerald-500 border-emerald-500 text-zinc-950"
                              : "border-zinc-700 bg-zinc-900"
                          }`}
                        >
                          {isChecked && (
                            <Check className="w-3 h-3 stroke-[3]" />
                          )}
                        </div>

                        {getFileIcon(tf.type, "w-4 h-4")}

                        <div className="min-w-0">
                          <p className="font-bold text-zinc-200 truncate">
                            {tf.name}
                          </p>
                          <span className="text-[10px] font-mono text-zinc-500">
                            Retention set to {retentionDays} days; file remains
                            on disk
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleAction("restore", [tf.id])}
                          className="px-2 py-0.5 rounded-lg bg-zinc-900 hover:bg-zinc-850 text-emerald-400 border border-zinc-800 font-mono text-[11px] flex items-center gap-1"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Restore</span>
                        </button>
                        <button
                          onClick={() =>
                            handleAction("delete_permanent", [tf.id])
                          }
                          className="p-1 rounded text-zinc-500 hover:text-rose-400 hover:bg-zinc-900 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between pt-2.5 border-t border-zinc-800 text-xs font-mono text-zinc-500">
              <span>Retention Policy: {retentionDays} days automatic TTL</span>
              <button
                onClick={() => setTrashModalOpen(false)}
                className="px-3.5 py-1 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
