"use client";

import { useEffect, useState } from "react";
import {
  X,
  ShieldCheck,
  ExternalLink,
  Copy,
  Check,
  Building2,
  User,
  Mail,
  Phone,
  MapPin,
  FileText,
  Layers,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { fetchLeadEvidence } from "@/lib/api";
import { getTierColorClasses, formatNumber } from "@/lib/utils";

interface EvidenceDrawerProps {
  companyId: number | null;
  onClose: () => void;
}

export function EvidenceDrawer({ companyId, onClose }: EvidenceDrawerProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"dossier" | "evidence" | "pages">(
    "dossier",
  );

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    fetchLeadEvidence(companyId)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [companyId]);

  if (!companyId) return null;

  const comp = data?.company;
  const kpi = data?.kpi;
  const scorecard = data?.scorecard;
  const dms = data?.decision_makers || [];
  const pages = data?.crawled_pages || [];

  const copyEmail = (email: string) => {
    navigator.clipboard.writeText(email);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/80 flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-[#111114] border-l border-zinc-800 h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Drawer Header */}
        <div className="p-6 border-b border-zinc-800/90 flex items-start justify-between bg-[#141418]">
          <div className="space-y-1.5 pr-6">
            <div className="flex items-center gap-2.5">
              <span
                className={`text-[11px] font-mono font-semibold px-2.5 py-1 rounded-xl border ${getTierColorClasses(comp?.lead_tier)}`}
              >
                {comp?.lead_tier || "Tier Loading"}
              </span>
              <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-zinc-850 text-zinc-300 border border-zinc-700/60">
                Score:{" "}
                <strong className="text-emerald-400">
                  {comp?.metrixa_lead_score ?? comp?.total_score ?? "-"}
                </strong>
                /100
              </span>
            </div>
            <h2 className="text-lg font-bold text-zinc-100 tracking-tight leading-snug">
              {comp?.display_name || "Loading..."}
            </h2>
            <div className="flex items-center gap-4 text-xs text-zinc-400">
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                {comp?.district || "Berlin"} ({comp?.postal_code || "-"})
              </span>
              {comp?.website_url && (
                <a
                  href={comp.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-emerald-400 hover:underline"
                >
                  <ExternalLink className="w-3 h-3" />
                  Website
                </a>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="px-6 border-b border-zinc-800 flex gap-6 text-xs font-semibold select-none bg-[#111114]">
          <button
            onClick={() => setActiveTab("dossier")}
            className={`py-3 border-b-2 transition-all ${
              activeTab === "dossier"
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Executive Dossier
          </button>
          <button
            onClick={() => setActiveTab("evidence")}
            className={`py-3 border-b-2 transition-all ${
              activeTab === "evidence"
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Verbatim Evidence & Quotes
          </button>
          <button
            onClick={() => setActiveTab("pages")}
            className={`py-3 border-b-2 transition-all ${
              activeTab === "pages"
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Crawled Pages ({pages.length})
          </button>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {loading ? (
            <div className="h-64 flex items-center justify-center text-xs text-zinc-400 font-mono">
              Loading verified dossier...
            </div>
          ) : (
            <>
              {activeTab === "dossier" && (
                <div className="space-y-6">
                  {/* Scorecard Pillar Breakdown */}
                  <div className="p-4 rounded-xl bg-[#141418] border border-zinc-800/80 shadow-matteCard space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                      5-Pillar Scorecard Breakdown
                    </h3>
                    <div className="grid grid-cols-5 gap-2 text-center font-mono">
                      <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">
                          Scale
                        </span>
                        <strong className="text-emerald-400 text-sm">
                          {scorecard?.scale_pts}/35
                        </strong>
                      </div>
                      <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">
                          Focus
                        </span>
                        <strong className="text-emerald-400 text-sm">
                          {scorecard?.focus_pts}/25
                        </strong>
                      </div>
                      <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">
                          Digital
                        </span>
                        <strong className="text-emerald-400 text-sm">
                          {scorecard?.digital_pts}/20
                        </strong>
                      </div>
                      <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">
                          Trust
                        </span>
                        <strong className="text-emerald-400 text-sm">
                          {scorecard?.trust_pts}/10
                        </strong>
                      </div>
                      <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">
                          Contact
                        </span>
                        <strong className="text-emerald-400 text-sm">
                          {scorecard?.contact_pts}/10
                        </strong>
                      </div>
                    </div>
                  </div>

                  {/* Decision-Maker Dossier */}
                  <div className="p-4 rounded-xl bg-[#141418] border border-zinc-800/80 shadow-matteCard space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center justify-between">
                      <span>Decision-Maker Contacts</span>
                      <span className="text-emerald-400 text-[11px] font-mono">
                        § 5 DDG Impressum
                      </span>
                    </h3>

                    {dms.length === 0 ? (
                      <p className="text-xs text-zinc-500 italic">
                        No named Geschäftsführer found on website.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {dms.map((dm: any, i: number) => (
                          <div
                            key={i}
                            className="p-3.5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2"
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-bold text-sm text-zinc-100 block">
                                  {dm.full_name}
                                </span>
                                <span className="text-xs text-emerald-400 font-medium">
                                  {dm.role || "Geschäftsführer"}
                                </span>
                              </div>
                              {dm.email_status && (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                                  {dm.email_status}
                                </span>
                              )}
                            </div>

                            {dm.personal_email && (
                              <div className="flex items-center justify-between pt-2 border-t border-zinc-800 text-xs font-mono">
                                <span className="text-zinc-300">
                                  {dm.personal_email}
                                </span>
                                <button
                                  onClick={() => copyEmail(dm.personal_email)}
                                  className="flex items-center gap-1 text-[11px] text-emerald-400 hover:underline"
                                >
                                  {copied ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                  <span>
                                    {copied ? "Copied" : "Copy Email"}
                                  </span>
                                </button>
                              </div>
                            )}

                            {dm.mx_host && (
                              <p className="text-[10px] text-zinc-500 font-mono">
                                DNS MX Server:{" "}
                                <strong className="text-zinc-400">
                                  {dm.mx_host}
                                </strong>
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Technical & Commercial Footprint */}
                  <div className="p-4 rounded-xl bg-[#141418] border border-zinc-800/80 shadow-matteCard space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                      Commercial & PropTech Profile
                    </h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-zinc-400 block text-[11px]">
                          Reported Units:
                        </span>
                        <strong className="text-zinc-100 font-mono">
                          {kpi?.exact_units_managed
                            ? `${formatNumber(kpi.exact_units_managed)} Units`
                            : kpi?.estimated_units_tier || "<250"}
                        </strong>
                      </div>
                      <div>
                        <span className="text-zinc-400 block text-[11px]">
                          ERP Stack:
                        </span>
                        <strong className="text-emerald-400 font-mono">
                          {kpi?.detected_erp_proptech || "None detected"}
                        </strong>
                      </div>
                      <div>
                        <span className="text-zinc-400 block text-[11px]">
                          Commercial Register:
                        </span>
                        <strong className="text-zinc-200 font-mono">
                          {comp?.commercial_register_id ||
                            "Amtsgericht Charlottenburg"}
                        </strong>
                      </div>
                      <div>
                        <span className="text-zinc-400 block text-[11px]">
                          VDIV Certified:
                        </span>
                        <strong
                          className={
                            comp?.is_vdiv_member
                              ? "text-emerald-400"
                              : "text-zinc-400"
                          }
                        >
                          {comp?.is_vdiv_member
                            ? "Yes (Association Member)"
                            : "No"}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "evidence" && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-[#141418] border border-emerald-500/30 space-y-2">
                    <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4" />
                      Verbatim Impressum / Team Evidence Quote
                    </span>
                    <blockquote className="text-xs font-mono text-zinc-200 p-3 rounded-lg bg-zinc-950 border border-zinc-850 leading-relaxed">
                      {dms[0]?.evidence_quote ||
                        "Extracted from German legal notice (§ 5 DDG)."}
                    </blockquote>
                  </div>

                  {kpi?.units_evidence_quote && (
                    <div className="p-4 rounded-xl bg-[#141418] border border-zinc-800/80 space-y-2">
                      <span className="text-xs font-semibold text-emerald-400">
                        Verbatim Unit Count Evidence Quote
                      </span>
                      <blockquote className="text-xs font-mono text-zinc-200 p-3 rounded-lg bg-zinc-950 border border-zinc-850 leading-relaxed">
                        &quot;{kpi.units_evidence_quote}&quot;
                      </blockquote>
                    </div>
                  )}

                  <div className="p-4 rounded-xl bg-[#141418] border border-zinc-800/80 space-y-2">
                    <span className="text-xs font-semibold text-zinc-300">
                      AI Qualification Summary Reasoning
                    </span>
                    <p className="text-xs text-zinc-400 leading-relaxed">
                      {kpi?.qualification_reasoning ||
                        "Active Berlin Hausverwaltung meeting residential submetering qualification criteria."}
                    </p>
                  </div>
                </div>
              )}

              {activeTab === "pages" && (
                <div className="space-y-3">
                  {pages.map((p: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-zinc-100 uppercase font-mono">
                          {p.page_type}
                        </span>
                        <span className="text-emerald-400 font-mono text-[10px]">
                          HTTP {p.http_status}
                        </span>
                      </div>
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-emerald-400 hover:underline truncate block"
                      >
                        {p.url}
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
