"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  BarChart3, 
  Terminal, 
  Users2, 
  Wrench, 
  Archive, 
  Settings, 
  ShieldCheck,
  Zap,
  Building2
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Executive Cockpit", icon: BarChart3, badge: "Overview" },
  { href: "/mission-control", label: "Mission Control", icon: Terminal, badge: "Live DAG" },
  { href: "/leads", label: "Lead Explorer", icon: Users2, badge: "1,199 Leads" },
  { href: "/tools", label: "Agentic Tools", icon: Wrench },
  { href: "/artifacts", label: "Artifacts Vault", icon: Archive, badge: "Excel / CSV" },
  { href: "/settings", label: "Provider Hub", icon: Settings },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <aside className="w-64 flex flex-col glass-panel border-r border-slate-800/80 bg-surface-100/70 h-screen sticky top-0 z-40 select-none">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-cyan-600 flex items-center justify-center shadow-glowCyan">
            <Zap className="w-5 h-5 text-slate-950 fill-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-base tracking-tight text-white">HEIDI</span>
              <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-primary/20 text-primary border border-primary/30">
                COCKPIT
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium tracking-wide">Metering LeadOps Suite</p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Command Center
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all group",
                isActive
                  ? "bg-primary/15 text-primary border border-primary/30 shadow-[0_0_15px_-3px_rgba(56,189,248,0.25)] font-semibold"
                  : "text-slate-400 hover:text-slate-100 hover:bg-white/[0.04] border border-transparent"
              )}
            >
              <div className="flex items-center gap-3">
                <Icon className={cn("w-4 h-4 transition-transform group-hover:scale-110", isActive ? "text-primary" : "text-slate-400")} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded-md font-mono",
                    isActive
                      ? "bg-primary/20 text-primary border border-primary/30"
                      : "bg-slate-800 text-slate-400 group-hover:text-slate-300"
                  )}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/40">
        <div className="flex items-center gap-2.5 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <div className="truncate">
            <p className="font-medium text-slate-300 text-[11px]">Anti-Hallucination Gate</p>
            <p className="text-[10px] text-emerald-400/90 font-mono">100% Grounded (0% Fabricated)</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

