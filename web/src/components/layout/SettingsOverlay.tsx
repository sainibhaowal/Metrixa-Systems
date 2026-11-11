"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  KeyRound,
  Maximize2,
  Minimize2,
  Settings,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";
import SettingsHubPage from "@/app/settings/page";
import DataControlPage from "@/app/data-control/page";
import { ThemeToggle } from "./ThemeToggle";

type SettingsSection = "providers" | "data";

interface SettingsOverlayProps {
  onClose: () => void;
}

/**
 * A single focused settings workspace. The existing Provider Hub and Data
 * Control pages are reused here so their backend wiring and destructive reset
 * protections remain unchanged while the main navigation stays uncluttered.
 */
export function SettingsOverlay({ onClose }: SettingsOverlayProps) {
  const [section, setSection] = useState<SettingsSection>("providers");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const providerSelected = section === "providers";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-dialog-title"
    >
      <button
        type="button"
        aria-label="Close settings"
        onClick={onClose}
        className="absolute inset-0 bg-black/75 backdrop-blur-[2px]"
      />

      <div
        className={`relative flex min-w-0 gap-3 overflow-hidden rounded-[28px] border border-zinc-700/80 bg-[#09090b] p-3 shadow-[0_28px_90px_-24px_rgba(0,0,0,0.95)] transition-[width,height] duration-200 ${
          expanded
            ? "h-[calc(100vh-24px)] w-[calc(100vw-24px)]"
            : "h-[min(900px,92vh)] w-[min(1440px,calc(100vw-32px))]"
        }`}
      >
        <aside className="flex w-56 shrink-0 flex-col rounded-2xl border border-zinc-800/80 bg-[#111114]">
          <div className="flex items-center justify-between rounded-t-2xl px-4 py-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10">
                <Settings className="h-4 w-4 text-emerald-400" />
              </div>
              <div>
                <h2
                  id="settings-dialog-title"
                  className="text-sm font-bold text-zinc-100"
                >
                  Settings
                </h2>
                <p className="text-[10px] text-zinc-500">Local configuration</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close settings"
              className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <nav
            className="flex-1 space-y-1.5 p-3"
            aria-label="Settings sections"
          >
            <p className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">
              Configuration
            </p>
            <button
              type="button"
              onClick={() => setSection("providers")}
              className={`flex min-h-[58px] w-full items-center gap-3 rounded-2xl border px-3.5 py-3 text-left text-xs transition ${
                providerSelected
                  ? "border-emerald-500/30 bg-zinc-900 text-emerald-400"
                  : "border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900/70 hover:text-zinc-100"
              }`}
            >
              <KeyRound className="h-4 w-4 shrink-0" />
              <span>
                <span className="block font-semibold">Provider Hub</span>
                <span className="mt-0.5 block text-[10px] text-zinc-500">
                  LLM and web search
                </span>
              </span>
            </button>
            <button
              type="button"
              onClick={() => setSection("data")}
              className={`flex min-h-[58px] w-full items-center gap-3 rounded-2xl border px-3.5 py-3 text-left text-xs transition ${
                !providerSelected
                  ? "border-rose-500/30 bg-zinc-900 text-rose-300"
                  : "border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900/70 hover:text-zinc-100"
              }`}
            >
              <ShieldAlert className="h-4 w-4 shrink-0" />
              <span>
                <span className="block font-semibold">Data Control</span>
                <span className="mt-0.5 block text-[10px] text-zinc-500">
                  Database and reset
                </span>
              </span>
            </button>

            <p className="px-3 pb-2 pt-6 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">
              System status
            </p>
            <div className="space-y-2 rounded-2xl border border-zinc-800/80 bg-zinc-950/60 p-3.5 text-[10px] text-zinc-500">
              <div className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-emerald-400" />
                <span>Local workspace active</span>
              </div>
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="h-3.5 w-3.5 text-zinc-500" />
                <span>Changes save to the local API</span>
              </div>
            </div>
          </nav>

          <div className="rounded-b-2xl p-3">
            <div className="mb-2 flex min-h-[48px] items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-950/60 px-3">
              <span className="text-[10px] font-semibold text-zinc-500">
                Appearance
              </span>
              <ThemeToggle compact />
            </div>
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              aria-pressed={expanded}
              className="flex min-h-[48px] w-full items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/60 px-3 text-left text-[10px] font-semibold text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-100"
            >
              <span>
                {expanded ? "Collapse workspace" : "Expand workspace"}
              </span>
              {expanded ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </aside>

        <section className="min-w-0 flex-1 overflow-y-auto rounded-2xl border border-zinc-800/80 bg-[#09090b]">
          <div className="settings-overlay-content p-4 sm:p-6">
            {providerSelected ? <SettingsHubPage /> : <DataControlPage />}
          </div>
        </section>
      </div>
    </div>
  );
}
