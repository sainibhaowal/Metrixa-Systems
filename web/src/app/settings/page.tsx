"use client";

import { useEffect, useState } from "react";
import { 
  Cpu, 
  Globe, 
  CheckCircle2, 
  AlertCircle, 
  Activity, 
  Zap, 
  Sliders, 
  Save, 
  Key, 
  Terminal, 
  ExternalLink,
  ShieldCheck,
  Eye,
  EyeOff,
  Server,
  Cloud,
  Laptop
} from "lucide-react";
import { fetchSettings, saveSettings, pingProvider } from "@/lib/api";

interface ProviderDefinition {
  id: string;
  name: string;
  category: "cloud" | "local" | "system";
  badge: string;
  defaultBaseUrl: string;
  defaultModel: string;
  requiresKey: boolean;
  desc: string;
}

const PROVIDERS: ProviderDefinition[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    defaultModel: "gemini-2.5-flash",
    requiresKey: true,
    desc: "Google Gemini 2.5 Flash with native JSON mode and huge context window for complex Impressum parsing.",
  },
  {
    id: "openai",
    name: "OpenAI GPT-4o",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o-mini",
    requiresKey: true,
    desc: "Industry standard GPT-4o and GPT-4o-mini structured JSON comprehension.",
  },
  {
    id: "deepseek",
    name: "DeepSeek API",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://api.deepseek.com/v1",
    defaultModel: "deepseek-chat",
    requiresKey: true,
    desc: "Cost-efficient reasoning (~$0.14/1M tokens) with exceptional German B2B website extraction accuracy.",
  },
  {
    id: "ollama",
    name: "Ollama (Local Server)",
    category: "local",
    badge: "Local Offline",
    defaultBaseUrl: "http://localhost:11434/v1",
    defaultModel: "llama3.2",
    requiresKey: false,
    desc: "Run open-weights models (llama3.2, mistral, qwen2.5) locally on your GPU/CPU with 0 data leaving your system.",
  },
  {
    id: "lm_studio",
    name: "LM Studio",
    category: "local",
    badge: "Local GUI",
    defaultBaseUrl: "http://localhost:1234/v1",
    defaultModel: "local-model",
    requiresKey: false,
    desc: "Connect to LM Studio's local OpenAI-compatible server running quantized GGUF weights.",
  },
  {
    id: "local_llamacpp",
    name: "llama.cpp Server",
    category: "local",
    badge: "Local CLI",
    defaultBaseUrl: "http://localhost:8080/v1",
    defaultModel: "qwen2.5-14b-instruct",
    requiresKey: false,
    desc: "High-performance standalone C++ server with hardware acceleration (CUDA/Metal/AVX512).",
  },
  {
    id: "nvidia_nim",
    name: "NVIDIA NIM",
    category: "cloud",
    badge: "Enterprise API",
    defaultBaseUrl: "https://integrate.api.nvidia.com/v1",
    defaultModel: "meta/llama-3.3-70b-instruct",
    requiresKey: true,
    desc: "Accelerated containerized enterprise inference for Llama 3.3 70B.",
  },
  {
    id: "auto_fallback",
    name: "Auto Fallback Cascade",
    category: "system",
    badge: "Resilient Cascade",
    defaultBaseUrl: "internal://cascade",
    defaultModel: "cascading-router",
    requiresKey: false,
    desc: "Cascades sequentially: DeepSeek → Gemini → NIM → Local Llama → Deterministic German Parser.",
  },
  {
    id: "deterministic",
    name: "Deterministic Legal Parser",
    category: "system",
    badge: "Zero-Cost Engine",
    defaultBaseUrl: "internal://regex",
    defaultModel: "regex_german_impressum_v2",
    requiresKey: false,
    desc: "German § 5 DDG legal notice parser, DOM tech scanner, and RFC MX validator. 100% deterministic, $0 cost.",
  },
];

export default function SettingsHubPage() {
  const [cfg, setCfg] = useState<any>(null);
  const [activeProvider, setActiveProvider] = useState<string>("auto_fallback");
  const [selectedId, setSelectedId] = useState<string>("gemini");

  // Per-provider form states
  const [baseUrl, setBaseUrl] = useState<string>("");
  const [model, setModel] = useState<string>("");
  const [apiKey, setApiKey] = useState<string>("");
  const [showKey, setShowKey] = useState<boolean>(false);

  // Ping test state
  const [pinging, setPinging] = useState<boolean>(false);
  const [pingResult, setPingResult] = useState<any>(null);

  // Applying / Saving state
  const [applying, setApplying] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  // General settings
  const [concurrency, setConcurrency] = useState<number>(20);
  const [tavilyKey, setTavilyKey] = useState<string>("");

  useEffect(() => {
    fetchSettings()
      .then((data) => {
        setCfg(data);
        if (data.default_llm_provider) {
          setActiveProvider(data.default_llm_provider);
          setSelectedId(data.default_llm_provider);
        }
        if (data.max_concurrent_crawls) setConcurrency(data.max_concurrent_crawls);
      })
      .catch(console.error);
  }, []);

  const selectedDef = PROVIDERS.find((p) => p.id === selectedId) || PROVIDERS[0];

  // When selected provider changes, load its configured values or defaults
  useEffect(() => {
    setPingResult(null);
    setShowKey(false);
    if (!cfg) {
      setBaseUrl(selectedDef.defaultBaseUrl);
      setModel(selectedDef.defaultModel);
      setApiKey("");
      return;
    }

    if (selectedId === "deepseek") {
      setBaseUrl(cfg.deepseek_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.deepseek_model || selectedDef.defaultModel);
      setApiKey("");
    } else if (selectedId === "gemini") {
      setBaseUrl(cfg.gemini_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.gemini_model || selectedDef.defaultModel);
      setApiKey("");
    } else if (selectedId === "openai") {
      setBaseUrl(cfg.openai_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.openai_model || selectedDef.defaultModel);
      setApiKey("");
    } else if (selectedId === "ollama") {
      setBaseUrl(cfg.ollama_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.ollama_model || selectedDef.defaultModel);
      setApiKey("");
    } else if (selectedId === "lm_studio") {
      setBaseUrl(cfg.lmstudio_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.lmstudio_model || selectedDef.defaultModel);
      setApiKey("");
    } else if (selectedId === "local_llamacpp") {
      setBaseUrl(cfg.llamacpp_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.llamacpp_model || selectedDef.defaultModel);
      setApiKey("");
    } else if (selectedId === "nvidia_nim") {
      setBaseUrl(cfg.nvidia_nim_base_url || selectedDef.defaultBaseUrl);
      setModel(cfg.nvidia_nim_model || selectedDef.defaultModel);
      setApiKey("");
    } else {
      setBaseUrl(selectedDef.defaultBaseUrl);
      setModel(selectedDef.defaultModel);
      setApiKey("");
    }
  }, [selectedId, cfg]);

  // Execute 10-Token Test Ping
  const handleTestPing = async () => {
    try {
      setPinging(true);
      setPingResult(null);
      const res = await pingProvider({
        provider: selectedId,
        base_url: baseUrl || undefined,
        api_key: apiKey || undefined,
        model: model || undefined,
      });
      setPingResult(res);
    } catch (err: any) {
      setPingResult({
        status: "error",
        latency_ms: 0,
        error: err.message || "Failed to reach backend endpoint",
      });
    } finally {
      setPinging(false);
    }
  };

  // Connect & Set as Active Provider
  const handleApplyAndConnect = async () => {
    try {
      setApplying(true);
      const payload: Record<string, any> = {
        default_llm_provider: selectedId,
      };

      if (selectedId === "deepseek") {
        if (apiKey) payload.deepseek_api_key = apiKey;
        if (baseUrl) payload.deepseek_base_url = baseUrl;
        if (model) payload.deepseek_model = model;
      } else if (selectedId === "gemini") {
        if (apiKey) payload.gemini_api_key = apiKey;
        if (baseUrl) payload.gemini_base_url = baseUrl;
        if (model) payload.gemini_model = model;
      } else if (selectedId === "openai") {
        if (apiKey) payload.openai_api_key = apiKey;
        if (baseUrl) payload.openai_base_url = baseUrl;
        if (model) payload.openai_model = model;
      } else if (selectedId === "ollama") {
        if (baseUrl) payload.ollama_base_url = baseUrl;
        if (model) payload.ollama_model = model;
      } else if (selectedId === "lm_studio") {
        if (baseUrl) payload.lmstudio_base_url = baseUrl;
        if (model) payload.lmstudio_model = model;
      } else if (selectedId === "local_llamacpp") {
        if (baseUrl) payload.llamacpp_base_url = baseUrl;
        if (model) payload.llamacpp_model = model;
      } else if (selectedId === "nvidia_nim") {
        if (apiKey) payload.nvidia_nim_api_key = apiKey;
        if (baseUrl) payload.nvidia_nim_base_url = baseUrl;
        if (model) payload.nvidia_nim_model = model;
      }

      await saveSettings(payload);
      setActiveProvider(selectedId);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);

      // Refresh settings from server
      const refreshed = await fetchSettings();
      setCfg(refreshed);
    } catch (err: any) {
      alert("Failed to save settings: " + err.message);
    } finally {
      setApplying(false);
    }
  };

  const isConfigured = (id: string): boolean => {
    if (!cfg) return false;
    if (id === "deepseek") return cfg.deepseek_configured;
    if (id === "gemini") return cfg.gemini_configured;
    if (id === "openai") return cfg.openai_configured;
    if (id === "nvidia_nim") return cfg.nvidia_nim_configured;
    return true; // local and deterministic are ready
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Provider & Model Hub</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
              Pluggable Harness
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Connect Cloud APIs or offline local models (Ollama, LM Studio, llama.cpp), run live 10-token ping tests, and apply.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono">
          <span className="text-zinc-500">Active Engine:</span>
          <span className="text-emerald-400 font-bold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            {PROVIDERS.find((p) => p.id === activeProvider)?.name || activeProvider}
          </span>
        </div>
      </div>

      {/* Two-Panel Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ======================================================== */}
        {/* LEFT PANEL: Provider Inventory & Catalog (5 Columns)     */}
        {/* ======================================================== */}
        <div className="lg:col-span-5 p-5 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Provider Inventory ({PROVIDERS.length})
            </span>
            <span className="text-[10px] font-mono text-zinc-500">Select to Configure</span>
          </div>

          <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1">
            {PROVIDERS.map((p) => {
              const isSelected = selectedId === p.id;
              const isActive = activeProvider === p.id;
              const configured = isConfigured(p.id);

              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  className={`p-3.5 rounded-xl cursor-pointer transition-all border text-left flex items-start justify-between gap-3 ${
                    isSelected
                      ? "border-emerald-500/80 bg-zinc-900 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]"
                      : "border-zinc-800/80 bg-[#141418] hover:bg-zinc-850 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 shrink-0 mt-0.5">
                      {p.category === "cloud" ? (
                        <Cloud className="w-4 h-4 text-emerald-400" />
                      ) : p.category === "local" ? (
                        <Laptop className="w-4 h-4 text-amber-400" />
                      ) : (
                        <Cpu className="w-4 h-4 text-zinc-400" />
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-bold truncate ${isSelected ? "text-emerald-400" : "text-zinc-200"}`}>
                          {p.name}
                        </span>
                        {isActive && (
                          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shrink-0">
                            ACTIVE
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">{p.desc}</p>
                    </div>
                  </div>

                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 shrink-0">
                    {p.badge}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* ======================================================== */}
        {/* RIGHT PANEL: Provider Setup, Ping Test & Apply (7 Cols)  */}
        {/* ======================================================== */}
        <div className="lg:col-span-7 p-6 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-6">
          {/* Header of Selected Provider */}
          <div className="flex items-start justify-between pb-4 border-b border-zinc-800">
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-lg font-bold text-zinc-100">{selectedDef.name}</h2>
                <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-zinc-850 text-zinc-300 border border-zinc-700">
                  {selectedDef.badge}
                </span>
                {activeProvider === selectedDef.id && (
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Currently Active
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-1 leading-relaxed">{selectedDef.desc}</p>
            </div>
          </div>

          {/* Configuration Form Inputs */}
          <div className="space-y-4">
            {/* Base URL */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                <span>Base Endpoint URL</span>
                <span className="text-[10px] font-mono text-zinc-500">OpenAI-Compatible /v1</span>
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={selectedDef.defaultBaseUrl}
                disabled={selectedDef.category === "system"}
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-all"
              />
            </div>

            {/* Model Name / ID */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                <span>Model ID / Tag</span>
                <span className="text-[10px] font-mono text-zinc-500">e.g. llama3.2, gpt-4o-mini, gemini-2.5-flash</span>
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={selectedDef.defaultModel}
                disabled={selectedDef.category === "system"}
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-all"
              />
            </div>

            {/* API Key (if required) */}
            {selectedDef.requiresKey && (
              <div>
                <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                  <span>API Key</span>
                  <span className="text-[10px] font-mono text-zinc-500">
                    {isConfigured(selectedDef.id) ? "Configured in .env" : "Required"}
                  </span>
                </label>
                <div className="relative">
                  <input
                    type={showKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={
                      isConfigured(selectedDef.id)
                        ? "•••••••••••••••••••• (Key Configured, enter new to overwrite)"
                        : "sk-... or AIzaSy..."
                    }
                    className="w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons: Ping Test + Apply */}
          <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
            {/* Button 1: Test Connection (10-Token Ping) */}
            <button
              onClick={handleTestPing}
              disabled={pinging}
              className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-semibold text-xs border border-zinc-800 hover:border-zinc-700 transition-all disabled:opacity-50"
            >
              <Zap className={`w-4 h-4 ${pinging ? "animate-spin text-emerald-400" : "text-emerald-400"}`} />
              <span>{pinging ? "Pinging Endpoint (10 Tokens)..." : "Test Connection (10-Token Ping)"}</span>
            </button>

            {/* Button 2: Apply & Connect */}
            <button
              onClick={handleApplyAndConnect}
              disabled={applying}
              className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs shadow-glowEmerald transition-all disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>{savedSuccess ? "✓ Connected & Active!" : "Connect & Apply as Active"}</span>
            </button>
          </div>

          {/* Live Ping Test Result Box */}
          {pingResult && (
            <div
              className={`p-4 rounded-xl font-mono text-xs space-y-2 border animate-in fade-in transition-all ${
                pingResult.status === "ok"
                  ? "bg-zinc-950 border-emerald-500/40 text-emerald-400"
                  : "bg-zinc-950 border-rose-500/40 text-rose-400"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold">
                  {pingResult.status === "ok" ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Live 10-Token Ping: SUCCESS (200 OK)</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                      <span>Ping Failed (Connection Error)</span>
                    </>
                  )}
                </div>

                <span className="text-[11px] text-zinc-400">
                  Latency: <strong className="text-zinc-200">{pingResult.latency_ms}ms</strong>
                </span>
              </div>

              {pingResult.status === "ok" ? (
                <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 space-y-1">
                  <div className="flex justify-between text-[11px] text-zinc-400">
                    <span>Verified Model: <strong className="text-zinc-200">{pingResult.model}</strong></span>
                    <span>Tokens Returned: <strong className="text-emerald-400">{pingResult.tokens || 10}</strong></span>
                  </div>
                  <p className="text-[11px] font-mono text-zinc-100">
                    Response: <span className="text-emerald-400">"{pingResult.reply}"</span>
                  </p>
                </div>
              ) : (
                <p className="text-[11px] text-rose-300/90 leading-relaxed break-words bg-rose-950/20 p-2.5 rounded-lg border border-rose-900/40">
                  {pingResult.error}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Global Crawler Settings Section */}
      <div className="p-6 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-4">
        <h2 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-emerald-400" />
          <span>Async Crawler Performance & Concurrency</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          <div>
            <div className="flex items-center justify-between text-xs font-mono mb-2">
              <span className="text-zinc-400">HTTP/2 Async Crawler Workers:</span>
              <strong className="text-emerald-400">{concurrency} concurrent requests</strong>
            </div>
            <input
              type="range"
              min={5}
              max={35}
              value={concurrency}
              onChange={(e) => setConcurrency(Number(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500 mt-1">
              Higher workers increase scraping speed across Berlin domains. Recommended: 20 workers.
            </p>
          </div>

          <div className="flex justify-end">
            <button
              onClick={async () => {
                await saveSettings({ max_concurrent_crawls: concurrency });
                alert("Crawler concurrency updated to " + concurrency);
              }}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-200 text-xs font-semibold border border-zinc-800 transition-all"
            >
              <Save className="w-3.5 h-3.5 text-emerald-400" />
              <span>Save Concurrency Limit</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
