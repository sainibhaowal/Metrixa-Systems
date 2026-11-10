"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  Sparkles,
  UserCheck,
  MailCheck,
  Layers,
  Zap,
  ArrowUpRight,
} from "lucide-react";
import { fetchMetrics } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    fetchMetrics()
      .then(setMetrics)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const totalMarket = metrics?.golden_total ?? 0;
  const rawTotal = metrics?.raw_total ?? 0;
  const tiers = metrics?.tiers || {};
  const tierA = tiers["Tier A (High Priority)"] ?? 0;
  const tierB = tiers["Tier B (Qualified Mid-Market)"] ?? 0;
  const decisionMakers = metrics?.coverage?.with_decision_maker ?? 0;
  const publicPersonalEmails =
    metrics?.coverage?.with_public_personal_email ?? 0;
  const patternEmailCandidates =
    metrics?.coverage?.with_pattern_email_candidate ?? 0;
  const portals = metrics?.coverage?.with_customer_portal ?? 0;

  const erpData = Object.entries(metrics?.erp_breakdown || {}).map(
    ([name, value]) => ({ name, value }),
  );

  const districtData = (metrics?.district_breakdown || []).slice(0, 8);

  const maxErpCount = Math.max(
    1,
    ...erpData.map((item) => Number(item.value) || 0),
  );

  const COLORS = ["#10b981", "#34d399", "#f59e0b", "#a1a1aa", "#71717a"];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Title Top Bar Bento */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Executive Cockpit</span>
            <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
              Berlin Property Management Leads
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Current local dataset, scoring bands, observed technology signals,
            and source-listed contact coverage.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Link
            href="/mission-control"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-300 hover:text-white hover:border-zinc-700 transition-all shadow-sm"
          >
            <Zap className="w-3.5 h-3.5 text-emerald-400" />
            <span>Mission Control (DAG)</span>
          </Link>
          <Link
            href="/leads"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-500 text-zinc-950 font-semibold text-xs hover:bg-emerald-400 transition-all shadow-glowEmerald"
          >
            <span>
              {totalMarket > 0
                ? `Explore ${formatNumber(totalMarket)} Leads`
                : "Explore Leads"}
            </span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* 5 KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card 1: Total Market */}
        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard hover:border-zinc-700/80 transition-all">
          <div className="flex items-center justify-between text-zinc-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Canonical Companies
            </span>
            <Building2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-zinc-100 tracking-tight font-mono">
            {formatNumber(totalMarket)}
          </div>
          <p className="text-[11px] text-zinc-400 mt-2 flex items-center gap-1 font-mono">
            {totalMarket > 0 ? (
              <>
                <span className="text-emerald-400 font-medium">
                  {formatNumber(rawTotal)}
                </span>{" "}
                scraped :{" "}
                <span className="text-zinc-300">
                  {formatNumber(totalMarket)}
                </span>{" "}
                unique
              </>
            ) : (
              <span className="text-zinc-500">
                Database empty : Run #1 ready
              </span>
            )}
          </p>
        </div>

        {/* Card 2: Tier A Leads */}
        <div className="p-5 rounded-2xl bg-[#141418] border border-emerald-500/30 shadow-matteCard hover:border-emerald-500/50 transition-all">
          <div className="flex items-center justify-between text-zinc-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-emerald-400">
              Tier A (Priority)
            </span>
            <Sparkles className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-emerald-400 tracking-tight font-mono">
            {formatNumber(tierA)}
          </div>
          <p className="text-[11px] text-zinc-400 mt-2 font-mono">
            {tierA > 0 ? (
              <>Prioritized by the current lead scoring rules</>
            ) : (
              <span className="text-zinc-500">0 high-density portfolios</span>
            )}
          </p>
        </div>

        {/* Card 3: Decision Makers */}
        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard hover:border-zinc-700/80 transition-all">
          <div className="flex items-center justify-between text-zinc-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Decision Makers
            </span>
            <UserCheck className="w-4 h-4 text-zinc-200" />
          </div>
          <div className="text-3xl font-bold text-zinc-100 tracking-tight font-mono">
            {formatNumber(decisionMakers)}
          </div>
          <p className="text-[11px] text-zinc-400 mt-2 font-mono">
            {decisionMakers > 0 ? (
              <>
                <strong className="text-zinc-200">
                  {formatNumber(decisionMakers)}
                </strong>{" "}
                named Geschäftsführer
              </>
            ) : (
              <span className="text-zinc-500">0 leaders extracted</span>
            )}
          </p>
        </div>

        {/* Card 4: Email Evidence */}
        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard hover:border-zinc-700/80 transition-all">
          <div className="flex items-center justify-between text-zinc-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Decision-Maker Emails
            </span>
            <MailCheck className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-zinc-100 tracking-tight font-mono">
            {formatNumber(publicPersonalEmails)}
          </div>
          <p className="text-[11px] text-zinc-400 mt-2 font-mono">
            <>
              <strong className="text-emerald-400">
                {formatNumber(publicPersonalEmails)}
              </strong>{" "}
              publicly listed;{" "}
              <strong className="text-amber-400">
                {formatNumber(patternEmailCandidates)}
              </strong>{" "}
              pattern candidates. Mailboxes are not tested.
            </>
          </p>
        </div>

        {/* Card 5: PropTech ERP */}
        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard hover:border-zinc-700/80 transition-all">
          <div className="flex items-center justify-between text-zinc-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              PropTech / ERPs
            </span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-zinc-100 tracking-tight font-mono">
            {formatNumber(portals)}
          </div>
          <p className="text-[11px] text-zinc-400 mt-2 font-mono">
            {portals > 0 ? (
              <span>Observed portal and ERP signals</span>
            ) : (
              <span className="text-zinc-500">0 tenant portals detected</span>
            )}
          </p>
        </div>
      </div>

      {/* Visual Analytics Grid (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* District Penetration Bar Chart (7 Cols) */}
        <div className="lg:col-span-7 p-6 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-zinc-100 tracking-tight">
                Companies by Berlin District
              </h2>
              <p className="text-[11px] text-zinc-400">
                Dataset records with a mapped district
              </p>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">
              {districtData.length > 0
                ? `${districtData.length} Bezirke Active`
                : "Awaiting Pipeline Run"}
            </span>
          </div>

          {districtData.length > 0 ? (
            <div className="h-64 w-full">
              {mounted ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={districtData}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 50, bottom: 5 }}
                  >
                    <XAxis
                      type="number"
                      stroke="#52525b"
                      fontSize={11}
                      tickLine={false}
                    />
                    <YAxis
                      dataKey="district"
                      type="category"
                      stroke="#a1a1aa"
                      fontSize={11}
                      tickLine={false}
                      width={130}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        borderColor: "rgba(255,255,255,0.1)",
                        borderRadius: "12px",
                        color: "#f4f4f5",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="count" fill="#27272a" radius={[0, 6, 6, 0]}>
                      {districtData.map((_: any, index: number) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={index === 0 ? "#10b981" : "#3f3f46"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full w-full flex items-center justify-center text-xs font-mono text-zinc-600">
                  Loading district distribution...
                </div>
              )}
            </div>
          ) : (
            <div className="h-64 w-full flex flex-col items-center justify-center gap-2.5 text-center p-6 rounded-xl bg-zinc-950/60 border border-zinc-800/60">
              <Building2 className="w-8 h-8 text-zinc-600 stroke-[1.5]" />
              <div className="space-y-1">
                <p className="text-xs font-semibold text-zinc-300 font-mono">
                  No District Data Available
                </p>
                <p className="text-[11px] text-zinc-500 max-w-xs">
                  Execute the pipeline from Mission Control to discover and map
                  Berlin Hausverwaltungen across all 12 Bezirke.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ERP & Portal Share (5 Cols) */}
        <div className="lg:col-span-5 p-6 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-bold text-zinc-100 tracking-tight">
                  Observed PropTech / ERP Signals
                </h2>
                <p className="text-[11px] text-zinc-400">
                  Signal counts from the current dataset; categories may overlap
                </p>
              </div>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">
                {erpData.length > 0 ? "Signals Recorded" : "No Signals"}
              </span>
            </div>

            {erpData.length > 0 ? (
              <div className="space-y-3 mt-4">
                {erpData.map(
                  (item: { name: string; value: any }, idx: number) => {
                    const numVal = Number(item.value) || 0;
                    const barWidth = Math.round((numVal / maxErpCount) * 100);
                    return (
                      <div key={item.name} className="space-y-1">
                        <div className="flex justify-between text-xs font-medium">
                          <span className="text-zinc-300">{item.name}</span>
                          <span className="font-mono text-zinc-400">
                            {formatNumber(numVal)} records
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-md bg-zinc-800 overflow-hidden">
                          <div
                            className="h-full rounded-md transition-all duration-500"
                            style={{
                              width: `${barWidth}%`,
                              backgroundColor: COLORS[idx % COLORS.length],
                            }}
                          />
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            ) : (
              <div className="h-44 w-full flex flex-col items-center justify-center gap-2.5 text-center p-6 rounded-xl bg-zinc-950/60 border border-zinc-800/60 my-auto">
                <Layers className="w-8 h-8 text-zinc-600 stroke-[1.5]" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-zinc-300 font-mono">
                    No ERP Signals Detected
                  </p>
                  <p className="text-[11px] text-zinc-500 max-w-xs">
                    Run Stage 03 (Crawl) and Stage 04 (Extract) to scan tenant
                    portals, Domus, Casavi, and Haufe stacks.
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-zinc-800/80 mt-6 flex items-center justify-between text-xs text-zinc-400">
            <span>Customer Portals Detected:</span>
            <strong className="text-zinc-100 font-mono">
              {formatNumber(portals)} Companies
            </strong>
          </div>
        </div>
      </div>

      {/* Strategic Qualification Pillars Callout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard">
          <div className="flex items-center gap-2.5 text-emerald-400 mb-2 font-semibold text-xs">
            <span className="w-2 h-2 rounded-sm bg-emerald-400" />
            <span>Tier A Target Strategy</span>
          </div>
          <p className="text-xs text-zinc-300 leading-relaxed font-sans">
            {tierA > 0
              ? `${formatNumber(tierA)} companies are currently in Tier A under the configured heuristic. Review each company's source evidence before prioritizing outreach.`
              : "Companies enter Tier A when their current heuristic score meets the configured threshold. Scores are prioritization signals, not independent verification."}
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard">
          <div className="flex items-center gap-2.5 text-amber-400 mb-2 font-semibold text-xs">
            <span className="w-2 h-2 rounded-sm bg-amber-400" />
            <span>Tier B Outbound Sequencer</span>
          </div>
          <p className="text-xs text-zinc-300 leading-relaxed font-sans">
            {tierB > 0
              ? `${formatNumber(tierB)} companies are currently in Tier B under the configured heuristic. Check source and contact evidence before acting on a record.`
              : "Companies enter Tier B when their current heuristic score meets the configured threshold. This app does not verify every contact channel."}
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-[#141418] border border-zinc-800/80 shadow-matteCard">
          <div className="flex items-center gap-2.5 text-zinc-200 mb-2 font-semibold text-xs">
            <span className="w-2 h-2 rounded-sm bg-zinc-400" />
            <span>Audit & Evidence Proof</span>
          </div>
          <p className="text-xs text-zinc-300 leading-relaxed font-sans">
            Source URLs and quotes are stored where available. Extraction and
            scoring still require human review; the app does not claim zero
            errors or independently verified facts.
          </p>
        </div>
      </div>
    </div>
  );
}
