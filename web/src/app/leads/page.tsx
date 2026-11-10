"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Search,
  Filter,
  ExternalLink,
  Building2,
  User,
  Mail,
  Sparkles,
  Eye,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  MapPin,
} from "lucide-react";
import { apiUrl, fetchLeads } from "@/lib/api";
import { getTierColorClasses, formatNumber } from "@/lib/utils";
import { EvidenceDrawer } from "@/components/leads/EvidenceDrawer";
import { RoundedSelect, SelectOption } from "@/components/ui/RoundedSelect";

const DISTRICT_OPTIONS: SelectOption[] = [
  { value: "All Districts", label: "All Districts" },
  {
    value: "Charlottenburg-Wilmersdorf",
    label: "Charlottenburg-Wilmersdorf",
  },
  {
    value: "Steglitz-Zehlendorf",
    label: "Steglitz-Zehlendorf",
  },
  {
    value: "Tempelhof-Schöneberg",
    label: "Tempelhof-Schöneberg",
  },
  {
    value: "Friedrichshain-Kreuzberg",
    label: "Friedrichshain-Kreuzberg",
  },
  { value: "Pankow", label: "Pankow" },
  { value: "Mitte", label: "Mitte" },
  { value: "Reinickendorf", label: "Reinickendorf" },
  { value: "Treptow-Köpenick", label: "Treptow-Köpenick" },
  { value: "Spandau", label: "Spandau" },
  { value: "Neukölln", label: "Neukölln" },
  { value: "Lichtenberg", label: "Lichtenberg" },
  {
    value: "Marzahn-Hellersdorf",
    label: "Marzahn-Hellersdorf",
  },
];

export default function LeadsExplorerPage() {
  const [leads, setLeads] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState<string>("");
  const [district, setDistrict] = useState<string>("");
  const [hasDm, setHasDm] = useState(false);
  const [hasEmail, setHasEmail] = useState(false);
  const [hasErp, setHasErp] = useState(false);

  // Selected lead for evidence drawer
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(
    null,
  );
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const loadLeads = useCallback(() => {
    setLoading(true);
    fetchLeads({
      q: search || undefined,
      tier: tier || undefined,
      district: district && district !== "All Districts" ? district : undefined,
      has_dm: hasDm ? true : undefined,
      has_email: hasEmail ? true : undefined,
      has_erp: hasErp ? true : undefined,
      page,
      limit: 25,
    })
      .then((data) => {
        setLeads(data.items || []);
        setTotal(data.total || 0);
        setPages(data.pages || 1);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [search, tier, district, hasDm, hasEmail, hasErp, page]);

  useEffect(() => {
    const timer = setTimeout(loadLeads, 200);
    return () => clearTimeout(timer);
  }, [loadLeads]);

  const copyEmail = (companyId: number, email: string) => {
    navigator.clipboard.writeText(email);
    setCopiedId(companyId);
    setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Title & Stats Header Top Bar */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Lead Explorer & Data Grid</span>
            <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">
              {formatNumber(total)} Qualified Leads
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Browse current records and review the stored source evidence and
            contact status for each company.
          </p>
        </div>

        <a
          href={apiUrl("/api/artifacts/download/excel")}
          download
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-200 text-xs font-semibold border border-zinc-800 transition-all self-start sm:self-auto"
        >
          <Download className="w-3.5 h-3.5 text-emerald-400" />
          <span>Download Excel (.xlsx)</span>
        </a>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search Input */}
          <div className="flex-1 relative">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by Company Name, Geschäftsführer, Address, Domain..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-10 pr-4 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
            />
          </div>

          {/* District Dropdown (Custom Rounded Square Popover) */}
          <RoundedSelect
            value={district || "All Districts"}
            onChange={(val) => {
              setDistrict(val === "All Districts" ? "" : val);
              setPage(1);
            }}
            options={DISTRICT_OPTIONS}
            icon={<MapPin className="w-3.5 h-3.5 text-emerald-400" />}
            className="min-w-[220px]"
          />
        </div>

        {/* Tier & Feature Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-zinc-800/80 text-xs select-none">
          <span className="text-[11px] text-zinc-400 font-medium mr-1">
            Tiers:
          </span>
          <button
            onClick={() => setTier("")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              tier === ""
                ? "bg-emerald-500 text-zinc-950 font-bold"
                : "bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setTier("Tier A")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              tier === "Tier A"
                ? "bg-emerald-500 text-zinc-950 font-bold"
                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
            }`}
          >
            🟢 Tier A (Priority)
          </button>
          <button
            onClick={() => setTier("Tier B")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              tier === "Tier B"
                ? "bg-amber-500 text-zinc-950 font-bold"
                : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
            }`}
          >
            🟡 Tier B (Mid-Market)
          </button>
          <button
            onClick={() => setTier("Tier C")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              tier === "Tier C"
                ? "bg-zinc-700 text-white font-bold"
                : "bg-zinc-900 text-zinc-400 border border-zinc-800"
            }`}
          >
            ⚪ Tier C (Small)
          </button>

          <span className="text-zinc-700 mx-2">|</span>

          {/* Feature toggles */}
          <button
            onClick={() => setHasDm(!hasDm)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              hasDm
                ? "bg-zinc-200 text-zinc-950 font-bold"
                : "bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
            }`}
          >
            Named Decision Maker
          </button>
          <button
            onClick={() => setHasEmail(!hasEmail)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              hasEmail
                ? "bg-emerald-500 text-zinc-950 font-bold"
                : "bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
            }`}
          >
            Personal Email (MX Valid)
          </button>
          <button
            onClick={() => setHasErp(!hasErp)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              hasErp
                ? "bg-zinc-200 text-zinc-950 font-bold"
                : "bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
            }`}
          >
            PropTech ERP
          </button>
        </div>
      </div>

      {/* Main Data Table */}
      <div className="rounded-2xl overflow-hidden border border-zinc-800/80 bg-[#111114] shadow-matte">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#141418] text-[11px] font-mono uppercase text-zinc-400 border-b border-zinc-800 tracking-wider">
              <tr>
                <th className="py-3.5 px-4 w-20">Metrixa Score</th>
                <th className="py-3.5 px-4">Company Name</th>
                <th className="py-3.5 px-4">District (PLZ)</th>
                <th className="py-3.5 px-4">Scale / Units</th>
                <th className="py-3.5 px-4">Focus</th>
                <th className="py-3.5 px-4">ERP / Portal</th>
                <th className="py-3.5 px-4">Decision Maker</th>
                <th className="py-3.5 px-4">Personal Email</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-sans">
              {loading ? (
                <tr>
                  <td
                    colSpan={9}
                    className="py-12 text-center text-zinc-400 font-mono"
                  >
                    Loading verified Berlin property managers...
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td
                    colSpan={9}
                    className="py-12 text-center text-zinc-400 font-mono"
                  >
                    No leads match your filter criteria.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr
                    key={lead.company_id}
                    className="hover:bg-zinc-900/60 transition-colors group cursor-pointer"
                    onClick={() => setSelectedCompanyId(lead.company_id)}
                  >
                    {/* Score */}
                    <td className="py-3 px-4 font-mono">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-md font-bold text-xs border ${getTierColorClasses(lead.lead_tier)}`}
                      >
                        {lead.metrixa_lead_score}
                      </span>
                    </td>

                    {/* Company Name */}
                    <td className="py-3 px-4">
                      <div className="font-semibold text-zinc-100 group-hover:text-emerald-400 transition-colors flex items-center gap-1.5">
                        <span className="truncate max-w-[220px]">
                          {lead.display_name}
                        </span>
                        {lead.is_vdiv_member && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                            VDIV
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {lead.lead_id} • {lead.legal_form || "GmbH"}
                      </span>
                    </td>

                    {/* District */}
                    <td className="py-3 px-4 text-zinc-300">
                      <span>{lead.district || "Berlin"}</span>
                      <span className="text-[10px] text-zinc-500 block font-mono">
                        {lead.postal_code || "-"}
                      </span>
                    </td>

                    {/* Units */}
                    <td className="py-3 px-4 font-mono">
                      {lead.exact_units_managed ? (
                        <span className="text-emerald-400 font-bold">
                          {formatNumber(lead.exact_units_managed)} Units
                        </span>
                      ) : (
                        <span className="text-zinc-400">
                          {lead.estimated_units_tier || "Not estimated"}
                        </span>
                      )}
                    </td>

                    {/* Focus */}
                    <td className="py-3 px-4">
                      <div className="flex gap-1 text-[10px] font-mono">
                        {lead.manages_weg && (
                          <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/50">
                            WEG
                          </span>
                        )}
                        {lead.manages_miet && (
                          <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/50">
                            Miet
                          </span>
                        )}
                      </div>
                    </td>

                    {/* ERP */}
                    <td className="py-3 px-4 text-xs font-mono">
                      {lead.detected_erp_proptech ? (
                        <span className="text-zinc-200 font-semibold truncate block max-w-[120px]">
                          {lead.detected_erp_proptech}
                        </span>
                      ) : lead.has_customer_portal ? (
                        <span className="text-emerald-400">Portal</span>
                      ) : (
                        <span className="text-zinc-600">-</span>
                      )}
                    </td>

                    {/* Decision Maker */}
                    <td className="py-3 px-4">
                      {lead.decision_maker_name ? (
                        <div>
                          <span className="font-semibold text-zinc-100 block truncate max-w-[140px]">
                            {lead.decision_maker_name}
                          </span>
                          <span className="text-[10px] text-emerald-400">
                            {lead.decision_maker_role || "Geschäftsführer"}
                          </span>
                        </div>
                      ) : (
                        <span className="text-zinc-600 font-mono text-[11px]">
                          -
                        </span>
                      )}
                    </td>

                    {/* Personal Email */}
                    <td
                      className="py-3 px-4 font-mono text-[11px]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {lead.personal_email ? (
                        <div className="flex flex-col items-start gap-1">
                          <button
                            onClick={() =>
                              copyEmail(lead.company_id, lead.personal_email)
                            }
                            className="flex items-center gap-1.5 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:border-emerald-500 transition-all group/btn"
                          >
                            {copiedId === lead.company_id ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3 text-zinc-500 group-hover/btn:text-emerald-400" />
                            )}
                            <span className="truncate max-w-[130px]">
                              {lead.personal_email}
                            </span>
                          </button>
                          <span className="max-w-[190px] text-[9px] leading-tight text-amber-400">
                            {lead.email_status ||
                              "Email evidence status unknown"}
                          </span>
                        </div>
                      ) : (
                        <span className="text-zinc-600">-</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td
                      className="py-3 px-4 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => setSelectedCompanyId(lead.company_id)}
                        className="p-1.5 rounded-lg bg-zinc-800 hover:bg-emerald-500/20 text-zinc-400 hover:text-emerald-400 transition-colors"
                        title="Inspect Evidence & Impressum"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-400 font-mono bg-[#141418]">
          <span>
            Page {page} of {pages} ({formatNumber(total)} Leads)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 disabled:opacity-30 hover:text-white transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
              className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 disabled:opacity-30 hover:text-white transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Sliding Evidence Drawer */}
      <EvidenceDrawer
        companyId={selectedCompanyId}
        onClose={() => setSelectedCompanyId(null)}
      />
    </div>
  );
}
