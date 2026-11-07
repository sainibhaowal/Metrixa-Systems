"use client";

import { useEffect, useState } from "react";
import { Settings, Save, CheckCircle2, Cpu, Globe, Sliders, ShieldCheck } from "lucide-react";
import { fetchSettings, saveSettings } from "@/lib/api";

const PROVIDERS = [
  { id: "auto_fallback", name: "Auto Fallback (Recommended)", desc: "Cascades: DeepSeek → Gemini → NIM → Local Llama → Deterministic" },
  { id: "deepseek", name: "DeepSeek API (deepseek-chat)", desc: "State of the art German JSON comprehension (~$0.14/1M tokens)" },
  { id: "gemini", name: "Google Gemini 2.5 Flash", desc: "Fast JSON schema mode & huge context window" },
  { id: "nvidia_nim", name: "NVIDIA NIM (Llama-3.3-70B)", desc: "High-speed enterprise inference" },
  { id: "local_llamacpp", name: "Local llama.cpp Server", desc: "Offline inference on http://127.0.0.1:8080/v1" },
  { id: "lm_studio", name: "Local LM Studio Server", desc: "Offline inference on http://127.0.0.1:1234/v1" },
  { id: "deterministic", name: "Deterministic German Legal Parser", desc: "$0 cost, zero-hallucination Impressum regex & DOM tech scanner" },
];

export default function SettingsHubPage() {
  const [cfg, setCfg] = useState<any>(null);
  const [provider, setProvider] = useState("auto_fallback");
  const [deepseekKey, setDeepseekKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [tavilyKey, setTavilyKey] = useState("");
  const [concurrency, setConcurrency] = useState(20);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then((data) => {
        setCfg(data);
        if (data.default_llm_provider) setProvider(data.default_llm_provider);
        if (data.max_concurrent_crawls) setConcurrency(data.max_concurrent_crawls);
      })
      .catch(console.error);
  }, []);

  const handleSave = async () => {
    try {
      await saveSettings({
        default_llm_provider: provider,
        deepseek_api_key: deepseekKey || undefined,
        gemini_api_key: geminiKey || undefined,
        tavily_api_key: tavilyKey || undefined,
        max_concurrent_crawls: concurrency,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      alert("Failed to save settings");
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <span>Provider & Model Hub</span>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-primary font-mono">
            Pluggable Harness
          </span>
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Switch between cloud APIs and local llama.cpp / LM Studio servers without restarting the engine.
        </p>
      </div>

      {/* Provider Selector Cards */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Cpu className="w-4 h-4 text-primary" />
          <span>Active LLM Extraction Provider</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {PROVIDERS.map((p) => {
            const isSelected = provider === p.id;
            return (
              <div
                key={p.id}
                onClick={() => setProvider(p.id)}
                className={`p-4 rounded-xl cursor-pointer transition-all border ${
                  isSelected
                    ? "border-primary bg-primary/10 shadow-[0_0_15px_-3px_rgba(56,189,248,0.25)]"
                    : "border-slate-800 bg-slate-900/60 hover:bg-slate-900"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold ${isSelected ? "text-primary" : "text-slate-200"}`}>
                    {p.name}
                  </span>
                  {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-primary" />}
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">{p.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* API Credentials Input */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Globe className="w-4 h-4 text-emerald-400" />
          <span>API Keys & Endpoints (Stored Locally in .env)</span>
        </h2>

        <div className="space-y-3 text-xs">
          <div>
            <label className="text-slate-400 block mb-1">DeepSeek API Key (Optional)</label>
            <input
              type="password"
              placeholder={cfg?.deepseek_configured ? "•••••••••••••••••••• (Configured)" : "sk-..."}
              value={deepseekKey}
              onChange={(e) => setDeepseekKey(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono placeholder-slate-600 focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Google Gemini API Key (Optional)</label>
            <input
              type="password"
              placeholder={cfg?.gemini_configured ? "•••••••••••••••••••• (Configured)" : "AIzaSy..."}
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono placeholder-slate-600 focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Tavily Search API Key (Fallback)</label>
            <input
              type="password"
              placeholder={cfg?.tavily_configured ? "•••••••••••••••••••• (Configured)" : "tvly-..."}
              value={tavilyKey}
              onChange={(e) => setTavilyKey(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono placeholder-slate-600 focus:outline-none focus:border-primary"
            />
          </div>
        </div>
      </div>

      {/* Concurrency Settings */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Sliders className="w-4 h-4 text-amber-400" />
          <span>Async Crawler Concurrency Limit</span>
        </h2>
        <div className="flex items-center gap-4 text-xs font-mono">
          <input
            type="range"
            min={5}
            max={35}
            value={concurrency}
            onChange={(e) => setConcurrency(Number(e.target.value))}
            className="flex-1 accent-primary"
          />
          <span className="w-24 text-right font-bold text-primary">{concurrency} workers</span>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary to-cyan-500 text-slate-950 font-bold text-xs shadow-glowCyan hover:opacity-95 transition-all"
        >
          <Save className="w-4 h-4" />
          <span>{saved ? "Settings Saved!" : "Save Configuration"}</span>
        </button>
      </div>
    </div>
  );
}

