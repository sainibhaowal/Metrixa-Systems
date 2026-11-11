"use client";

import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "./ThemeContext";

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  const isLight = theme === "light";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
      title={isLight ? "Switch to dark theme" : "Switch to light theme"}
      className={cn(
        "flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/80 text-zinc-300 transition-all hover:border-emerald-500/40 hover:text-emerald-400",
        compact ? "p-2" : "px-3 py-2 text-xs font-semibold",
      )}
    >
      {isLight ? (
        <Moon className="h-4 w-4" />
      ) : (
        <Sun className="h-4 w-4 text-amber-300" />
      )}
      {!compact && <span>{isLight ? "Dark" : "Light"}</span>}
    </button>
  );
}
