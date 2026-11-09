"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
  badge?: string;
  count?: number | string;
}

interface RoundedSelectProps {
  value: string;
  onChange: (val: string) => void;
  options: (string | SelectOption)[];
  placeholder?: string;
  icon?: React.ReactNode;
  className?: string;
  dropdownClassName?: string;
  align?: "left" | "right";
  disabled?: boolean;
}

export function RoundedSelect({
  value,
  onChange,
  options,
  placeholder = "Select option...",
  icon,
  className = "",
  dropdownClassName = "",
  align = "left",
  disabled = false,
}: RoundedSelectProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Normalize options into { value, label, badge, count } objects
  const normalizedOptions: SelectOption[] = options.map((opt) => {
    if (typeof opt === "string") {
      return { value: opt, label: opt };
    }
    return opt;
  });

  const selectedOption = normalizedOptions.find((opt) => opt.value === value);

  // Close on outside click
  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleOutsideClick);
    }
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  return (
    <div
      ref={containerRef}
      className={`relative inline-block text-left ${className}`}
    >
      {/* Trigger Button (Rounded Square Style) */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between gap-2 px-3.5 py-2 rounded-xl bg-zinc-900/90 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-100 transition-all select-none shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500/50 ${
          open ? "border-emerald-500/60 ring-1 ring-emerald-500/40" : ""
        } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          {icon && <span className="shrink-0 text-zinc-400">{icon}</span>}
          <span className="truncate font-medium text-zinc-200">
            {selectedOption ? selectedOption.label : placeholder}
          </span>
          {selectedOption?.badge && (
            <span className="hidden sm:inline-block px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 shrink-0">
              {selectedOption.badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={`w-3.5 h-3.5 text-zinc-400 shrink-0 transition-transform duration-200 ${
            open ? "rotate-180 text-emerald-400" : ""
          }`}
        />
      </button>

      {/* Floating Popup Menu (Modern Rounded Square Squircle) */}
      {open && (
        <div
          className={`absolute ${
            align === "right" ? "right-0" : "left-0"
          } mt-1.5 w-64 max-h-64 overflow-y-auto rounded-2xl bg-[#141418] border border-zinc-800/95 shadow-2xl p-1.5 backdrop-blur-xl z-50 animate-in fade-in-0 zoom-in-95 ${dropdownClassName}`}
          style={{ scrollbarWidth: "thin" }}
        >
          <div className="space-y-0.5">
            {normalizedOptions.map((opt) => {
              const isSelected = opt.value === value;
              return (
                <div
                  key={opt.value}
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-xs transition-all cursor-pointer select-none ${
                    isSelected
                      ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold"
                      : "text-zinc-300 hover:bg-zinc-800/80 hover:text-white"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="truncate">{opt.label}</span>
                    {opt.badge && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-zinc-800 text-zinc-400 border border-zinc-700 shrink-0">
                        {opt.badge}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {opt.count !== undefined && (
                      <span className="text-[10px] font-mono text-zinc-500">
                        {opt.count}
                      </span>
                    )}
                    {isSelected && (
                      <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
