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
  AlertTriangle,
  Layers,
  Eye,
  X,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  Table,
  Filter,
  Sparkles,
} from "lucide-react";
import {
  fetchArtifactFiles,
  fetchArtifactPreview,
  executeArtifactAction,
} from "@/lib/api";

interface ArtifactFile {
  id: string;
  name: string;
  type: "xlsx" | "csv" | "md" | "pdf" | "db";
  title: string;
  desc: string;
  status: "active" | "archived" | "trash" | "deleted";
  retention_days: number;
  trashed_at: string | null;
  archived_at: string | null;
  size_bytes: number;
  size_formatted: string;
  updated_at: string;
  tags: string[];
  download_url: string;
}

export default function ArtifactsLibraryPage() {
  const [files, setFiles] = useState<ArtifactFile[]>([]);
  const [summary, setSummary] = useState({
    total: 0,
    active: 0,
    archived: 0,
    trash: 0,
  });
  const [loading, setLoading] = useState(true);

  // Active View Tab: "active" | "archived" | "trash"
  const [currentTab, setCurrentTab] = useState<"active" | "archived" | "trash">(
    "active",
  );

  // Selection & Search
  const [selectedFileId, setSelectedFileId] = useState<string>("xlsx-master");
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

  // 1. Load Files List
  const loadFiles = async (preserveSelected = true) => {
    try {
      setLoading(true);
      const res = await fetchArtifactFiles();
      setFiles(res.items || []);
      setSummary(res.summary || { total: 0, active: 0, archived: 0, trash: 0 });

      if (res.items && res.items.length > 0) {
        if (!preserveSelected || !selectedFileId) {
          const firstActive =
            res.items.find((f: ArtifactFile) => f.status === "active") ||
            res.items[0];
          setSelectedFileId(firstActive.id);
        }
      }
    } catch (err) {
      console.error("Failed to load artifacts:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles(false);
  }, []);

  // 2. Load Preview when selected file changes
  useEffect(() => {
    if (!selectedFileId) return;
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
    return files.find((f) => f.id === selectedFileId) || files[0];
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
        delete_permanent: "Permanently Deleted",
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
      default:
        return <FileText className={`text-zinc-400 ${className}`} />;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 print:p-0 print:m-0 print:max-w-none">
      {/* Toast Notification */}
      {actionSuccess && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl bg-emerald-950 border border-emerald-500/50 text-emerald-300 font-mono text-xs flex items-center gap-2 shadow-2xl animate-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* ======================================================== */}
      {/* TOP HEADER BAR BENTO                                     */}
      {/* ======================================================== */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Artifacts & Deliverables Library</span>
            <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
              Live Office Suite
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Two-panel document workspace: explore generated deliverables,
            preview multi-sheet Excel workbooks & RFC CSVs live, and manage
            archival lifecycle.
          </p>
        </div>

        {/* Header Quick Stats & Trash Button */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono">
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
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 text-zinc-300 hover:text-zinc-100 transition-all group"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400 group-hover:scale-110 transition-transform" />
            <span>Trash Bin ({summary.trash})</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* MAIN TWO-PANEL WORKSPACE (12 COLS)                       */}
      {/* ======================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 print:block">
        {/* ====================================================== */}
        {/* LEFT PANEL: Artifact Explorer & Library (5 Cols)       */}
        {/* ====================================================== */}
        <div className="lg:col-span-5 space-y-4 print:hidden">
          {/* View Mode Tabs: Active Library | Archived | Trash */}
          <div className="p-1 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex items-center gap-1">
            <button
              onClick={() => {
                setCurrentTab("active");
                setCheckedIds([]);
              }}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
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
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
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
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
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
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-3">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Filter files by name, format, or tag..."
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
              />
            </div>

            {/* Batch Action Bar (Visible when files checked) */}
            {checkedIds.length > 0 && (
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-900 border border-emerald-500/40 text-xs font-mono animate-in fade-in">
                <div className="flex items-center gap-2 text-emerald-400">
                  <span className="font-bold">{checkedIds.length}</span>
                  <span className="text-zinc-400">selected</span>
                </div>

                <div className="flex items-center gap-1.5">
                  {currentTab === "active" && (
                    <>
                      <button
                        onClick={() => handleAction("archive", checkedIds)}
                        className="px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] font-semibold border border-zinc-700 flex items-center gap-1 transition-all"
                        title="Archive selected files"
                      >
                        <Archive className="w-3 h-3 text-amber-400" />
                        <span>Archive</span>
                      </button>
                      <button
                        onClick={() => handleAction("trash", checkedIds)}
                        className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-[11px] font-semibold border border-rose-500/30 flex items-center gap-1 transition-all"
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
                        className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[11px] font-semibold border border-emerald-500/40 flex items-center gap-1 transition-all"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Restore</span>
                      </button>
                      <button
                        onClick={() => handleAction("trash", checkedIds)}
                        className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-[11px] font-semibold border border-rose-500/30 flex items-center gap-1 transition-all"
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
                        className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[11px] font-semibold border border-emerald-500/40 flex items-center gap-1 transition-all"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Restore</span>
                      </button>
                      <button
                        onClick={() =>
                          handleAction("delete_permanent", checkedIds)
                        }
                        className="px-2.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-semibold flex items-center gap-1 transition-all"
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

          {/* Deliverable File Cards List */}
          <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
            {tabFiles.length === 0 ? (
              <div className="p-8 rounded-2xl bg-[#141418] border border-zinc-800 text-center space-y-2">
                <FileText className="w-8 h-8 text-zinc-600 mx-auto" />
                <p className="text-xs text-zinc-400 font-mono">
                  {currentTab === "trash"
                    ? "Trash bin is empty."
                    : currentTab === "archived"
                      ? "No archived deliverables yet."
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
                    className={`p-4 rounded-xl cursor-pointer transition-all border text-left relative group ${
                      isSelected
                        ? "border-emerald-500/80 bg-zinc-900 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]"
                        : "border-zinc-800/80 bg-[#141418] hover:bg-zinc-850 hover:border-zinc-700"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Multi-select Checkbox */}
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleCheck(f.id);
                        }}
                        className={`w-4 h-4 rounded-md border flex items-center justify-center shrink-0 mt-1 cursor-pointer transition-colors ${
                          isChecked
                            ? "bg-emerald-500 border-emerald-500 text-zinc-950"
                            : "border-zinc-700 hover:border-zinc-500 bg-zinc-900"
                        }`}
                      >
                        {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>

                      {/* File Icon */}
                      <div className="shrink-0 mt-0.5">
                        {getFileIcon(f.type, "w-6 h-6")}
                      </div>

                      {/* File Details */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
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

                        {/* Badges / Tags */}
                        <div className="flex flex-wrap items-center gap-1.5 mt-2">
                          {f.tags.slice(0, 3).map((tag, idx) => (
                            <span
                              key={idx}
                              className="text-[9px] font-mono px-2 py-0.5 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Hover Action Bar */}
                    <div className="flex items-center justify-end gap-1.5 mt-3 pt-2.5 border-t border-zinc-800/60 text-xs font-mono">
                      <span className="text-[10px] text-zinc-500 mr-auto">
                        Updated:{" "}
                        {f.updated_at
                          ? new Date(f.updated_at).toLocaleDateString()
                          : "Ready"}
                      </span>

                      {currentTab === "active" && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("archive", [f.id]);
                            }}
                            title="Archive file"
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-amber-400 hover:bg-zinc-800 transition-colors"
                          >
                            <Archive className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("trash", [f.id]);
                            }}
                            title="Move to Trash"
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 transition-colors"
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
                          className="p-1.5 rounded-lg text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800 transition-colors"
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
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800 transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAction("delete_permanent", [f.id]);
                            }}
                            title="Permanent delete"
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}

                      <a
                        href={`http://127.0.0.1:8000${f.download_url}`}
                        download
                        onClick={(e) => e.stopPropagation()}
                        title="Download file directly"
                        className="p-1.5 rounded-lg text-emerald-400 hover:text-emerald-300 hover:bg-zinc-800 transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Retention Policy Footer Bento */}
          <div className="p-3.5 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte flex items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-400">
              <Clock className="w-4 h-4 text-emerald-400" />
              <span>Retention Policy:</span>
            </div>

            <div className="flex items-center gap-1.5">
              {[30, 45, 60, 90].map((days) => (
                <button
                  key={days}
                  onClick={() => {
                    setRetentionDays(days);
                    handleAction("set_retention", [], days);
                  }}
                  className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all border ${
                    retentionDays === days
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/40"
                      : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                  }`}
                >
                  {days}d
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ====================================================== */}
        {/* RIGHT PANEL: Live Office Document Previewer (7 Cols)   */}
        {/* ====================================================== */}
        <div className="lg:col-span-7 p-6 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte space-y-5 print:p-0 print:border-none print:shadow-none">
          {/* Preview Header & Action Toolbar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-zinc-800 print:hidden">
            <div className="flex items-start gap-3 min-w-0">
              <div className="shrink-0 mt-0.5">
                {currentFile && getFileIcon(currentFile.type, "w-7 h-7")}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-base font-bold text-zinc-100 truncate">
                    {currentFile?.name || "Select Deliverable"}
                  </h2>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-zinc-900 border border-zinc-800 text-emerald-400">
                    Live Office Preview
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {currentFile?.title} • {currentFile?.size_formatted}
                </p>
              </div>
            </div>

            {/* Document Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Copy Entire Data */}
              <button
                onClick={handleCopyPreview}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-200 hover:text-white border border-zinc-800 hover:border-zinc-700 text-xs font-semibold transition-all shadow-sm"
                title="Copy entire document content or table rows to clipboard"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400 font-bold">Copied!</span>
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
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-200 hover:text-white border border-zinc-800 hover:border-zinc-700 text-xs font-semibold transition-all shadow-sm"
                title="Print or export as standardized A4 document"
              >
                <Printer className="w-3.5 h-3.5 text-zinc-400" />
                <span>Export PDF (A4)</span>
              </button>

              {/* Download Original File */}
              {currentFile && (
                <a
                  href={`http://127.0.0.1:8000${currentFile.download_url}`}
                  download
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs shadow-glowEmerald transition-all"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download File</span>
                </a>
              )}
            </div>
          </div>

          {/* Preview Content Area */}
          {previewLoading ? (
            <div className="h-96 flex flex-col items-center justify-center gap-3 text-zinc-500 font-mono text-xs">
              <div className="w-7 h-7 border-2 border-emerald-500/20 border-t-emerald-400 rounded-full animate-spin" />
              <span>Loading Office Preview...</span>
            </div>
          ) : !previewData ? (
            <div className="h-96 flex flex-col items-center justify-center gap-2 text-zinc-500 font-mono text-xs">
              <FileText className="w-8 h-8 text-zinc-600" />
              <span>No preview data available for this deliverable.</span>
            </div>
          ) : (
            <div className="space-y-4">
              {/* ==================== 1. EXCEL WORKBOOK PREVIEW ==================== */}
              {previewData.type === "xlsx" && (
                <div className="space-y-3">
                  {/* Sheet Selector Tabs */}
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                      {previewData.sheets?.map((sname: string) => (
                        <button
                          key={sname}
                          onClick={() => setActiveSheet(sname)}
                          className={`px-3 py-1.5 rounded-xl text-xs font-mono font-semibold transition-all shrink-0 border ${
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
                    <div className="relative w-full sm:w-48">
                      <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        value={previewSearch}
                        onChange={(e) => setPreviewSearch(e.target.value)}
                        placeholder="Search sheet..."
                        className="w-full pl-8 pr-2.5 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
                      />
                    </div>
                  </div>

                  {/* Spreadsheet Data Grid */}
                  {previewData.sheet_data &&
                  previewData.sheet_data[activeSheet] ? (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-inner">
                      <div className="max-h-[500px] overflow-auto">
                        <table className="w-full text-left border-collapse text-[11px] font-mono">
                          <thead className="sticky top-0 bg-[#141418] border-b border-zinc-800 z-10">
                            <tr>
                              <th className="py-2 px-2 text-zinc-500 border-r border-zinc-800/80 w-10 text-center select-none bg-zinc-900/60">
                                #
                              </th>
                              {previewData.sheet_data[activeSheet].headers.map(
                                (header: string, idx: number) => (
                                  <th
                                    key={idx}
                                    className="py-2.5 px-3 text-zinc-300 font-bold border-r border-zinc-800/80 whitespace-nowrap"
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
                                  <td className="py-2 px-2 text-zinc-500 border-r border-zinc-850 text-center select-none bg-zinc-950/80">
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
                                        className="py-2 px-3 border-r border-zinc-850/60 whitespace-nowrap text-zinc-300"
                                      >
                                        {isTier ? (
                                          <span
                                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                              String(cell).includes("Tier A")
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

                      <div className="p-2.5 bg-[#141418] border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                        <span>
                          Showing preview of{" "}
                          {
                            previewData.sheet_data[activeSheet]
                              .preview_rows_count
                          }{" "}
                          of {previewData.sheet_data[activeSheet].total_rows}{" "}
                          total rows
                        </span>
                        <span className="text-emerald-400 font-semibold">
                          Full 4-Tab Dataset in .xlsx
                        </span>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}

              {/* ==================== 2. CSV FILE PREVIEW ==================== */}
              {previewData.type === "csv" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3 text-xs font-mono">
                    <span className="px-2.5 py-1 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-400">
                      Standard RFC-4180 CSV • UTF-8 BOM • 31 Columns
                    </span>

                    <div className="relative w-full sm:w-48">
                      <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        value={previewSearch}
                        onChange={(e) => setPreviewSearch(e.target.value)}
                        placeholder="Search CSV..."
                        className="w-full pl-8 pr-2.5 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
                      />
                    </div>
                  </div>

                  <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-inner">
                    <div className="max-h-[500px] overflow-auto">
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
                                  className="py-2.5 px-3 text-zinc-300 font-bold border-r border-zinc-800/80 whitespace-nowrap"
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
                                <td className="py-2 px-2 text-zinc-500 border-r border-zinc-850 text-center select-none bg-zinc-950/80">
                                  {rIdx + 1}
                                </td>
                                {row.map((cell: string, cIdx: number) => (
                                  <td
                                    key={cIdx}
                                    className="py-2 px-3 border-r border-zinc-850/60 whitespace-nowrap text-zinc-300"
                                  >
                                    {cell}
                                  </td>
                                ))}
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="p-2.5 bg-[#141418] border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                      <span>
                        Total Records: {previewData.total_rows} Qualified Berlin
                        Leads
                      </span>
                      <span className="text-sky-400">
                        Salesforce & HubSpot Import Ready
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* ==================== 3. MARKDOWN & REPORT PREVIEW ==================== */}
              {(previewData.type === "md" || previewData.type === "pdf") && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-zinc-800 text-xs font-mono">
                    <span className="text-zinc-400">
                      Lines: {previewData.lines_count || 120} • Formatted
                      Markdown Document
                    </span>
                    <button
                      onClick={() => setShowRawMarkdown(!showRawMarkdown)}
                      className="px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-850 text-zinc-300 border border-zinc-800 text-[11px] font-semibold"
                    >
                      {showRawMarkdown ? "Rendered View" : "Raw Source View"}
                    </button>
                  </div>

                  {showRawMarkdown ? (
                    <pre className="p-4 rounded-xl bg-zinc-950 border border-zinc-850 font-mono text-xs text-zinc-300 overflow-x-auto whitespace-pre leading-relaxed max-h-[500px]">
                      {previewData.content}
                    </pre>
                  ) : (
                    <div className="p-6 rounded-xl bg-zinc-950 border border-zinc-850 text-zinc-200 text-xs leading-relaxed max-h-[520px] overflow-y-auto space-y-4 print:max-h-none print:p-0 print:border-none">
                      <div className="prose prose-invert max-w-none text-zinc-300">
                        {previewData.content
                          ?.split("\n\n")
                          .map((block: string, idx: number) => {
                            if (block.startsWith("# ")) {
                              return (
                                <h1
                                  key={idx}
                                  className="text-xl font-bold text-zinc-100 pb-2 border-b border-zinc-800 mb-3"
                                >
                                  {block.replace("# ", "")}
                                </h1>
                              );
                            }
                            if (block.startsWith("## ")) {
                              return (
                                <h2
                                  key={idx}
                                  className="text-base font-bold text-emerald-400 mt-4 mb-2"
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
                                  className="overflow-x-auto rounded-lg border border-zinc-800 my-3"
                                >
                                  <table className="w-full text-left text-[11px] font-mono">
                                    <thead className="bg-zinc-900 text-zinc-200">
                                      <tr>
                                        {headers.map((h, hIdx) => (
                                          <th
                                            key={hIdx}
                                            className="p-2 border-b border-zinc-800 font-bold"
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
                                              className="p-2 text-zinc-300 whitespace-nowrap"
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
                                className="text-zinc-300 leading-relaxed font-sans"
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
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between text-xs font-mono">
                    <span className="text-zinc-300">
                      SQLite Relational Engine • Journal Mode:{" "}
                      {previewData.journal_mode}
                    </span>
                    <span className="text-emerald-400 font-bold">
                      {previewData.tables?.length || 6} Relational Tables
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {previewData.tables?.map((table: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-850 space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-zinc-100 font-mono">
                            {table.name}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-emerald-400 border border-zinc-800">
                            {table.count} rows
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
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ======================================================== */}
      {/* TRASH MANAGEMENT MODAL (POP-UP WINDOW)                  */}
      {/* ======================================================== */}
      {trashModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-2xl rounded-2xl bg-[#141418] border border-zinc-800 shadow-2xl p-6 space-y-5 animate-in zoom-in-95">
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-3 border-b border-zinc-800">
              <div>
                <h3 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                  <Trash2 className="w-5 h-5 text-rose-400" />
                  <span>Deliverables Trash Bin & Lifecycle</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Trashed items are retained for {retentionDays} days before
                  automated purge. Restore files back to the active library or
                  delete permanently.
                </p>
              </div>

              <button
                onClick={() => setTrashModalOpen(false)}
                className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Trash Action Toolbar */}
            <div className="flex items-center justify-between gap-3 text-xs font-mono">
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

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleAction("restore", trashCheckedIds)}
                  disabled={trashCheckedIds.length === 0}
                  className="px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 font-semibold border border-emerald-500/40 disabled:opacity-40 transition-all flex items-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retrieve Back</span>
                </button>

                <button
                  onClick={() =>
                    handleAction("delete_permanent", trashCheckedIds)
                  }
                  disabled={trashCheckedIds.length === 0}
                  className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold disabled:opacity-40 transition-all flex items-center gap-1.5"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete Permanently</span>
                </button>

                <button
                  onClick={() => handleAction("empty_trash", [])}
                  disabled={trashedFiles.length === 0}
                  className="px-3 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-rose-400 border border-zinc-800 disabled:opacity-40 transition-all"
                >
                  Empty Trash
                </button>
              </div>
            </div>

            {/* Trashed Files List */}
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {trashedFiles.length === 0 ? (
                <div className="p-8 rounded-xl bg-zinc-950 border border-zinc-850 text-center space-y-1">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                  <p className="text-xs text-zinc-300 font-bold">
                    Trash Bin is Empty
                  </p>
                  <p className="text-[11px] text-zinc-500 font-mono">
                    All deliverables are active in the library.
                  </p>
                </div>
              ) : (
                trashedFiles.map((tf) => {
                  const isChecked = trashCheckedIds.includes(tf.id);

                  return (
                    <div
                      key={tf.id}
                      className="p-3 rounded-xl bg-zinc-950 border border-zinc-850 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-3 min-w-0">
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

                        {getFileIcon(tf.type, "w-5 h-5")}

                        <div className="min-w-0">
                          <p className="font-bold text-zinc-200 truncate">
                            {tf.name}
                          </p>
                          <span className="text-[10px] font-mono text-zinc-500">
                            Auto-purges in {retentionDays} days
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleAction("restore", [tf.id])}
                          className="px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-850 text-emerald-400 border border-zinc-800 font-mono text-[11px] flex items-center gap-1"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Restore</span>
                        </button>
                        <button
                          onClick={() =>
                            handleAction("delete_permanent", [tf.id])
                          }
                          className="p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-zinc-900 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between pt-3 border-t border-zinc-800 text-xs font-mono text-zinc-500">
              <span>Retention Policy: {retentionDays} days automatic TTL</span>
              <button
                onClick={() => setTrashModalOpen(false)}
                className="px-4 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold transition-colors"
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
