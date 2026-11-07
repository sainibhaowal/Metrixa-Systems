import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(val: number | null | undefined): string {
  if (val === null || val === undefined) return "-";
  return new Intl.NumberFormat("de-DE").format(val);
}

export function getTierColorClasses(tier: string | null | undefined) {
  if (!tier) return "bg-zinc-800/40 border-zinc-700/50 text-zinc-400";
  if (tier.includes("Tier A")) {
    return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-[0_0_15px_-3px_rgba(16,185,129,0.25)]";
  }
  if (tier.includes("Tier B")) {
    return "bg-amber-500/10 border-amber-500/30 text-amber-400 shadow-[0_0_15px_-3px_rgba(245,158,11,0.2)]";
  }
  return "bg-zinc-800/60 border-zinc-700/60 text-zinc-400";
}
