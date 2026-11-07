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
  ChevronLeft,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useSidebar } from "./SidebarContext";

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
  const { isCollapsed, toggleSidebar } = useSidebar();

  return (
    <aside 
      className={cn(
        "flex flex-col bg-[#111114] border-r border-zinc-800/90 h-screen sticky top-0 z-40 select-none shadow-matte transition-all duration-300 ease-in-out",
        isCollapsed ? "w-[72px]" : "w-64"
      )}
    >
      {/* Brand Header & Collapse Toggle */}
      <div className={cn(
        "p-4 border-b border-zinc-800/80 flex items-center justify-between transition-all",
        isCollapsed ? "justify-center px-2" : "px-5"
      )}>
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-9 h-9 rounded-xl bg-zinc-900 border border-emerald-500/30 flex items-center justify-center shrink-0 shadow-[0_0_15px_-3px_rgba(16,185,129,0.3)]">
            <Zap className="w-5 h-5 text-emerald-400 fill-emerald-400" />
          </div>
          {!isCollapsed && (
            <div className="transition-opacity duration-200">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-base tracking-tight text-zinc-100">HEIDI</span>
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  COCKPIT
                </span>
              </div>
              <p className="text-[10px] text-zinc-400 font-medium tracking-wide">Metering LeadOps Suite</p>
            </div>
          )}
        </div>

        {/* Collapse / Expand Button */}
        {!isCollapsed && (
          <button
            onClick={toggleSidebar}
            title="Collapse Navigation"
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/80 border border-transparent hover:border-zinc-700/80 transition-all duration-200"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Floating expand button when collapsed */}
      {isCollapsed && (
        <div className="px-3 pt-3 flex justify-center">
          <button
            onClick={toggleSidebar}
            title="Expand Navigation"
            className="w-full py-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 bg-zinc-900/60 hover:bg-zinc-800 border border-zinc-800/80 flex items-center justify-center transition-all duration-200"
          >
            <PanelLeftOpen className="w-4 h-4 text-zinc-300" />
          </button>
        </div>
      )}

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {!isCollapsed && (
          <div className="px-3 py-2 text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">
            Command Center
          </div>
        )}

        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                "flex items-center rounded-xl text-xs font-medium transition-all duration-200 group relative",
                isCollapsed ? "justify-center p-3" : "justify-between px-3.5 py-2.5",
                isActive
                  ? "bg-zinc-900 text-emerald-400 border border-emerald-500/30 shadow-[0_0_12px_-2px_rgba(16,185,129,0.25)] font-semibold"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/80 border border-transparent hover:border-zinc-800"
              )}
            >
              <div className={cn("flex items-center gap-3", isCollapsed && "justify-center")}>
                <Icon className={cn(
                  "w-4 h-4 transition-transform group-hover:scale-110 shrink-0", 
                  isActive ? "text-emerald-400" : "text-zinc-400 group-hover:text-zinc-200"
                )} />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
              </div>

              {/* Badges for expanded view */}
              {!isCollapsed && item.badge && (
                <span
                  className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0 ml-2",
                    isActive
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : "bg-zinc-900 text-zinc-400 border border-zinc-800 group-hover:text-zinc-300"
                  )}
                >
                  {item.badge}
                </span>
              )}

              {/* Indicator dot for active item when collapsed */}
              {isCollapsed && isActive && (
                <span className="absolute right-1 top-1 w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer Info / Grounding Metric */}
      <div className={cn(
        "p-3.5 border-t border-zinc-800/80 bg-zinc-950/60 transition-all",
        isCollapsed && "flex justify-center p-2.5"
      )}>
        <div className={cn("flex items-center gap-2.5 text-xs text-zinc-400", isCollapsed && "justify-center")}>
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          {!isCollapsed && (
            <div className="truncate">
              <p className="font-medium text-zinc-300 text-[11px]">Anti-Hallucination Gate</p>
              <p className="text-[10px] text-emerald-400 font-mono">100% Grounded (0% Fabricated)</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
