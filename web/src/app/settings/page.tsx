"use client";

import { useEffect, useState } from "react";
import {
  Cpu,
  Globe,
  CheckCircle2,
  AlertCircle,
  Zap,
  Sliders,
  Save,
  Eye,
  EyeOff,
  Lock,
  Wifi,
  Search,
  Server,
  Layers,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import {
  fetchSettings,
  saveSettings,
  pingProvider,
  pingSearchProvider,
} from "@/lib/api";
import { ProviderIcon } from "@/components/icons/ProviderLogos";

// 1. LLM Models
interface LLMProviderDef {
  id: string;
  name: string;
  category: "cloud" | "local" | "system";
  badge: string;
  defaultBaseUrl: string;
  defaultModel: string;
  requiresKey: boolean;
  desc: string;
}

const LLM_PROVIDERS: LLMProviderDef[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    defaultModel: "gemini-2.5-flash",
    requiresKey: true,
    desc: "Google Gemini 2.5 Flash with native JSON schema mode and large context window for complex German Impressum parsing.",
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

// 2. Web Search Providers
interface SearchProviderDef {
  id: string;
  name: string;
  category: "local" | "cloud" | "system";
  badge: string;
  defaultBaseUrl: string;
  requiresKey: boolean;
  desc: string;
}

const SEARCH_PROVIDERS: SearchProviderDef[] = [
  {
    id: "searxng",
    name: "SearXNG (Local Meta-Search)",
    category: "local",
    badge: "Local Default Active",
    defaultBaseUrl: "http://127.0.0.1:8888",
    requiresKey: false,
    desc: "Private self-hosted meta-search engine aggregating Google, Bing, Qwant, and DuckDuckGo with zero query limits.",
  },
  {
    id: "tavily",
    name: "Tavily AI Search",
    category: "cloud",
    badge: "Cloud AI Search",
    defaultBaseUrl: "https://api.tavily.com",
    requiresKey: true,
    desc: "AI-optimized search API specifically built for LLM agent research and LinkedIn profile enrichment.",
  },
  {
    id: "native_metasearch",
    name: "Native Directory Pipeline",
    category: "system",
    badge: "Air-Gapped Scrapers",
    defaultBaseUrl: "internal://scrapers",
    requiresKey: false,
    desc: "Direct German directory scrapers: Gelbe Seiten, 11880, and VDIV Berlin-Brandenburg with XOR decoders.",
  },
  {
    id: "brave",
    name: "Brave Search API",
    category: "cloud",
    badge: "Independent Index",
    defaultBaseUrl: "https://api.search.brave.com/res/v1",
    requiresKey: true,
    desc: "Privacy-focused independent web index with 2,000 free queries per month.",
  },
  {
    id: "google_cse",
    name: "Google Custom Search (CSE)",
    category: "cloud",
    badge: "Google Cloud",
    defaultBaseUrl: "https://www.googleapis.com/customsearch/v1",
    requiresKey: true,
    desc: "Official Google Search JSON API for high-precision Berlin company domain discovery.",
  },
];

export default function SettingsHubPage() {
  const [cfg, setCfg] = useState<any>(null);

  // Tab Switcher with Slide Motion: "llm" vs "search"
  const [activeTab, setActiveTab] = useState<"llm" | "search">("llm");

  // Active configurations from backend
  const [activeLLM, setActiveLLM] = useState<string>("auto_fallback");
  const [activeSearch, setActiveSearch] = useState<string>("searxng");

  // Selection states
  const [selectedLLMId, setSelectedLLMId] = useState<string>("gemini");
  const [selectedSearchId, setSelectedSearchId] = useState<string>("searxng");

  // Form states for LLM
  const [llmBaseUrl, setLlmBaseUrl] = useState<string>("");
  const [llmModel, setLlmModel] = useState<string>("");
  const [llmApiKey, setLlmApiKey] = useState<string>("");
  const [showLlmKey, setShowLlmKey] = useState<boolean>(false);

  // Form states for Search
  const [searchBaseUrl, setSearchBaseUrl] = useState<string>("");
  const [searchApiKey, setSearchApiKey] = useState<string>("");
  const [showSearchKey, setShowSearchKey] = useState<boolean>(false);
  const [testQuery, setTestQuery] = useState<string>("Hausverwaltung Berlin");

  // Ping and apply states
  const [pinging, setPinging] = useState<boolean>(false);
  const [pingResult, setPingResult] = useState<any>(null);
  const [applying, setApplying] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  // Concurrency slider
  const [concurrency, setConcurrency] = useState<number>(20);

  useEffect(() => {
    fetchSettings()
      .then((data) => {
        setCfg(data);
        if (data.default_llm_provider) {
          setActiveLLM(data.default_llm_provider);
          setSelectedLLMId(data.default_llm_provider);
        }
        if (data.default_search_provider) {
          setActiveSearch(data.default_search_provider);
          setSelectedSearchId(data.default_search_provider);
        }
        if (data.max_concurrent_crawls)
          setConcurrency(data.max_concurrent_crawls);
      })
      .catch(console.error);
  }, []);

  const selectedLLMDef =
    LLM_PROVIDERS.find((p) => p.id === selectedLLMId) || LLM_PROVIDERS[0];
  const selectedSearchDef =
    SEARCH_PROVIDERS.find((p) => p.id === selectedSearchId) ||
    SEARCH_PROVIDERS[0];

  // Update LLM form values when selection changes
  useEffect(() => {
    setPingResult(null);
    setShowLlmKey(false);
    if (!cfg) {
      setLlmBaseUrl(selectedLLMDef.defaultBaseUrl);
      setLlmModel(selectedLLMDef.defaultModel);
      setLlmApiKey("");
      return;
    }

    if (selectedLLMId === "deepseek") {
      setLlmBaseUrl(cfg.deepseek_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.deepseek_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else if (selectedLLMId === "gemini") {
      setLlmBaseUrl(cfg.gemini_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.gemini_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else if (selectedLLMId === "openai") {
      setLlmBaseUrl(cfg.openai_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.openai_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else if (selectedLLMId === "ollama") {
      setLlmBaseUrl(cfg.ollama_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.ollama_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else if (selectedLLMId === "lm_studio") {
      setLlmBaseUrl(cfg.lmstudio_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.lmstudio_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else if (selectedLLMId === "local_llamacpp") {
      setLlmBaseUrl(cfg.llamacpp_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.llamacpp_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else if (selectedLLMId === "nvidia_nim") {
      setLlmBaseUrl(cfg.nvidia_nim_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.nvidia_nim_model || selectedLLMDef.defaultModel);
      setLlmApiKey("");
    } else {
      setLlmBaseUrl(selectedLLMDef.defaultBaseUrl);
      setLlmModel(selectedLLMDef.defaultModel);
      setLlmApiKey("");
    }
  }, [selectedLLMId, cfg]);

  // Update Search form values when selection changes
  useEffect(() => {
    setPingResult(null);
    setShowSearchKey(false);
    if (!cfg) {
      setSearchBaseUrl(selectedSearchDef.defaultBaseUrl);
      setSearchApiKey("");
      return;
    }

    if (selectedSearchId === "searxng") {
      setSearchBaseUrl(
        cfg.searxng_base_url || selectedSearchDef.defaultBaseUrl,
      );
      setSearchApiKey("");
    } else if (selectedSearchId === "tavily") {
      setSearchBaseUrl(selectedSearchDef.defaultBaseUrl);
      setSearchApiKey("");
    } else {
      setSearchBaseUrl(selectedSearchDef.defaultBaseUrl);
      setSearchApiKey("");
    }
  }, [selectedSearchId, cfg]);

  // Execute Ping Test
  const handleTestPing = async () => {
    try {
      setPinging(true);
      setPingResult(null);

      if (activeTab === "llm") {
        const res = await pingProvider({
          provider: selectedLLMId,
          base_url: llmBaseUrl || undefined,
          api_key: llmApiKey || undefined,
          model: llmModel || undefined,
        });
        setPingResult(res);
      } else {
        const res = await pingSearchProvider({
          provider: selectedSearchId,
          base_url: searchBaseUrl || undefined,
          api_key: searchApiKey || undefined,
          query: testQuery || "Hausverwaltung Berlin",
        });
        setPingResult(res);
      }
    } catch (err: any) {
      setPingResult({
        status: "error",
        latency_ms: 0,
        error: err.message || "Failed to reach endpoint",
      });
    } finally {
      setPinging(false);
    }
  };

  // Connect & Set as Active
  const handleApplyAndConnect = async () => {
    try {
      setApplying(true);
      const payload: Record<string, any> = {};

      if (activeTab === "llm") {
        payload.default_llm_provider = selectedLLMId;
        if (selectedLLMId === "deepseek") {
          if (llmApiKey) payload.deepseek_api_key = llmApiKey;
          if (llmBaseUrl) payload.deepseek_base_url = llmBaseUrl;
          if (llmModel) payload.deepseek_model = llmModel;
        } else if (selectedLLMId === "gemini") {
          if (llmApiKey) payload.gemini_api_key = llmApiKey;
          if (llmBaseUrl) payload.gemini_base_url = llmBaseUrl;
          if (llmModel) payload.gemini_model = llmModel;
        } else if (selectedLLMId === "openai") {
          if (llmApiKey) payload.openai_api_key = llmApiKey;
          if (llmBaseUrl) payload.openai_base_url = llmBaseUrl;
          if (llmModel) payload.openai_model = llmModel;
        } else if (selectedLLMId === "ollama") {
          if (llmBaseUrl) payload.ollama_base_url = llmBaseUrl;
          if (llmModel) payload.ollama_model = llmModel;
        } else if (selectedLLMId === "lm_studio") {
          if (llmBaseUrl) payload.lmstudio_base_url = llmBaseUrl;
          if (llmModel) payload.lmstudio_model = llmModel;
        } else if (selectedLLMId === "local_llamacpp") {
          if (llmBaseUrl) payload.llamacpp_base_url = llmBaseUrl;
          if (llmModel) payload.llamacpp_model = llmModel;
        } else if (selectedLLMId === "nvidia_nim") {
          if (llmApiKey) payload.nvidia_nim_api_key = llmApiKey;
          if (llmBaseUrl) payload.nvidia_nim_base_url = llmBaseUrl;
          if (llmModel) payload.nvidia_nim_model = llmModel;
        }
        await saveSettings(payload);
        setActiveLLM(selectedLLMId);
      } else {
        payload.default_search_provider = selectedSearchId;
        if (selectedSearchId === "searxng") {
          if (searchBaseUrl) payload.searxng_base_url = searchBaseUrl;
        } else if (selectedSearchId === "tavily") {
          if (searchApiKey) payload.tavily_api_key = searchApiKey;
        } else if (selectedSearchId === "brave") {
          if (searchApiKey) payload.brave_search_api_key = searchApiKey;
        } else if (selectedSearchId === "google_cse") {
          if (searchApiKey) payload.google_cse_api_key = searchApiKey;
        }
        await saveSettings(payload);
        setActiveSearch(selectedSearchId);
      }

      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);

      const refreshed = await fetchSettings();
      setCfg(refreshed);
    } catch (err: any) {
      alert("Failed to save settings: " + err.message);
    } finally {
      setApplying(false);
    }
  };

  const isLLMConfigured = (id: string): boolean => {
    if (!cfg) return false;
    if (id === "deepseek") return cfg.deepseek_configured;
    if (id === "gemini") return cfg.gemini_configured;
    if (id === "openai") return cfg.openai_configured;
    if (id === "nvidia_nim") return cfg.nvidia_nim_configured;
    return true;
  };

  const isSearchConfigured = (id: string): boolean => {
    if (!cfg) return false;
    if (id === "tavily") return cfg.tavily_configured;
    if (id === "google_cse") return cfg.google_cse_configured;
    if (id === "brave") return cfg.brave_configured;
    return true; // SearXNG and Native are always active
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Header Bar Bento */}
      <div className="p-5 rounded-2xl bg-[#111114] border border-zinc-800/90 shadow-matte flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-2.5">
            <span>Provider & Harness Hub</span>
            <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
              Pluggable
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Toggle between LLM extraction models and Web Search engines, test
            live pings, and connect to Metrixa Engine.
          </p>
        </div>

        {/* Live Active Pills */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-zinc-500">Active LLM:</span>
            <span className="text-emerald-400 font-bold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-sm bg-emerald-400 animate-pulse"></span>
              {LLM_PROVIDERS.find((p) => p.id === activeLLM)?.name || activeLLM}
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-zinc-500">Active Search:</span>
            <span className="text-emerald-400 font-bold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-sm bg-emerald-400"></span>
              {SEARCH_PROVIDERS.find((p) => p.id === activeSearch)?.name ||
                activeSearch}
            </span>
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* SLIDE MOTION TOGGLE BUTTON: LLM Models vs Web Search    */}
      {/* ======================================================== */}
      <div className="flex justify-start">
        <div className="relative p-1 rounded-2xl bg-zinc-900/90 border border-zinc-800 flex items-center shadow-matte">
          {/* Sliding Motion Pill Background */}
          <div
            className="absolute top-1 bottom-1 rounded-xl bg-zinc-800 border border-zinc-700/80 shadow-md transition-all duration-300 ease-in-out"
            style={{
              left: activeTab === "llm" ? "4px" : "50%",
              width: "calc(50% - 4px)",
            }}
          />

          <button
            onClick={() => {
              setActiveTab("llm");
              setPingResult(null);
            }}
            className={`relative z-10 flex items-center gap-2.5 px-6 py-2.5 rounded-xl text-xs font-bold transition-colors duration-200 ${
              activeTab === "llm"
                ? "text-emerald-400"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>LLM Extraction Models ({LLM_PROVIDERS.length})</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("search");
              setPingResult(null);
            }}
            className={`relative z-10 flex items-center gap-2.5 px-6 py-2.5 rounded-xl text-xs font-bold transition-colors duration-200 ${
              activeTab === "search"
                ? "text-emerald-400"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Search className="w-4 h-4" />
            <span>Web Search Providers ({SEARCH_PROVIDERS.length})</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* TWO-PANEL WORKSPACE                                      */}
      {/* ======================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ======================================================== */}
        {/* LEFT PANEL: Inventory List (LLM or Search) (5 Columns)   */}
        {/* ======================================================== */}
        <div className="lg:col-span-5 p-5 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              {activeTab === "llm"
                ? "LLM Engine Inventory"
                : "Search Provider Inventory"}
            </span>
            <span className="text-[10px] font-mono text-zinc-500">
              Click to Select
            </span>
          </div>

          <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1">
            {activeTab === "llm"
              ? // LLM Providers List
                LLM_PROVIDERS.map((p) => {
                  const isSelected = selectedLLMId === p.id;
                  const isActive = activeLLM === p.id;

                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedLLMId(p.id)}
                      className={`p-3.5 rounded-xl cursor-pointer transition-all border text-left flex items-start justify-between gap-3 ${
                        isSelected
                          ? "border-emerald-500/80 bg-zinc-900 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]"
                          : "border-zinc-800/80 bg-[#141418] hover:bg-zinc-850 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-8 h-8 flex items-center justify-center shrink-0 mt-0.5">
                          <ProviderIcon providerId={p.id} size={24} />
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-bold truncate ${isSelected ? "text-emerald-400" : "text-zinc-200"}`}
                            >
                              {p.name}
                            </span>
                            {isActive && (
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shrink-0">
                                ACTIVE
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">
                            {p.desc}
                          </p>
                        </div>
                      </div>

                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 shrink-0">
                        {p.badge}
                      </span>
                    </div>
                  );
                })
              : // Search Providers List
                SEARCH_PROVIDERS.map((p) => {
                  const isSelected = selectedSearchId === p.id;
                  const isActive = activeSearch === p.id;

                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedSearchId(p.id)}
                      className={`p-3.5 rounded-xl cursor-pointer transition-all border text-left flex items-start justify-between gap-3 ${
                        isSelected
                          ? "border-emerald-500/80 bg-zinc-900 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]"
                          : "border-zinc-800/80 bg-[#141418] hover:bg-zinc-850 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-8 h-8 flex items-center justify-center shrink-0 mt-0.5">
                          <ProviderIcon providerId={p.id} size={24} />
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-bold truncate ${isSelected ? "text-emerald-400" : "text-zinc-200"}`}
                            >
                              {p.name}
                            </span>
                            {isActive && (
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shrink-0">
                                DEFAULT ACTIVE
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">
                            {p.desc}
                          </p>
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
        {/* RIGHT PANEL: Provider Setup, Real Ping & Connector (7 Cols) */}
        {/* ======================================================== */}
        <div className="lg:col-span-7 p-6 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-6">
          {activeTab === "llm" ? (
            // ==================== LLM CONFIGURATION ====================
            <>
              {/* Header */}
              <div className="flex items-start justify-between pb-4 border-b border-zinc-800">
                <div className="flex items-start gap-3.5">
                  <div className="w-9 h-9 flex items-center justify-center shrink-0">
                    <ProviderIcon providerId={selectedLLMDef.id} size={32} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-lg font-bold text-zinc-100">
                        {selectedLLMDef.name}
                      </h2>
                      <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-zinc-850 text-zinc-300 border border-zinc-700">
                        {selectedLLMDef.badge}
                      </span>
                      {activeLLM === selectedLLMDef.id && (
                        <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Currently Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                      {selectedLLMDef.desc}
                    </p>
                  </div>
                </div>
              </div>

              {/* Form Inputs */}
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                    <span>Base Endpoint URL</span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      OpenAI-Compatible /v1
                    </span>
                  </label>
                  <input
                    type="text"
                    value={llmBaseUrl}
                    onChange={(e) => setLlmBaseUrl(e.target.value)}
                    placeholder={selectedLLMDef.defaultBaseUrl}
                    disabled={selectedLLMDef.category === "system"}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-all"
                  />
                  <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-zinc-400">
                    <span className="flex items-center gap-1">
                      {llmBaseUrl.startsWith("https") ? (
                        <Lock className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Wifi className="w-3 h-3 text-amber-400" />
                      )}
                      {llmBaseUrl.startsWith("https")
                        ? "TLS Encrypted (HTTPS)"
                        : "Local Loopback (HTTP)"}
                    </span>
                    <span>•</span>
                    <span>Protocol: OpenAI ChatCompletions v1</span>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                    <span>Model ID / Tag</span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      e.g. llama3.2, gpt-4o-mini, gemini-2.5-flash
                    </span>
                  </label>
                  <input
                    type="text"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder={selectedLLMDef.defaultModel}
                    disabled={selectedLLMDef.category === "system"}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-all"
                  />
                </div>

                {selectedLLMDef.requiresKey && (
                  <div>
                    <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                      <span>API Key</span>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {isLLMConfigured(selectedLLMDef.id)
                          ? "Configured in .env"
                          : "Required"}
                      </span>
                    </label>
                    <div className="relative">
                      <input
                        type={showLlmKey ? "text" : "password"}
                        value={llmApiKey}
                        onChange={(e) => setLlmApiKey(e.target.value)}
                        placeholder={
                          isLLMConfigured(selectedLLMDef.id)
                            ? "•••••••••••••••••••• (Configured in .env, enter new to overwrite)"
                            : "sk-... or AIzaSy..."
                        }
                        className="w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-all"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLlmKey(!showLlmKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                      >
                        {showLlmKey ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                <button
                  onClick={handleTestPing}
                  disabled={pinging}
                  className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-semibold text-xs border border-zinc-800 hover:border-zinc-700 transition-all disabled:opacity-50"
                >
                  <Zap
                    className={`w-4 h-4 ${pinging ? "animate-spin text-emerald-400" : "text-emerald-400"}`}
                  />
                  <span>
                    {pinging
                      ? "Pinging Endpoint (10 Tokens)..."
                      : "Test Connection (10-Token Ping)"}
                  </span>
                </button>

                <button
                  onClick={handleApplyAndConnect}
                  disabled={applying}
                  className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs shadow-glowEmerald transition-all disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>
                    {savedSuccess
                      ? "✓ Connected & Active!"
                      : "Connect & Apply as Active"}
                  </span>
                </button>
              </div>
            </>
          ) : (
            // ==================== SEARCH CONFIGURATION ====================
            <>
              {/* Header */}
              <div className="flex items-start justify-between pb-4 border-b border-zinc-800">
                <div className="flex items-start gap-3.5">
                  <div className="w-9 h-9 flex items-center justify-center shrink-0">
                    <ProviderIcon providerId={selectedSearchDef.id} size={32} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-lg font-bold text-zinc-100">
                        {selectedSearchDef.name}
                      </h2>
                      <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-zinc-850 text-zinc-300 border border-zinc-700">
                        {selectedSearchDef.badge}
                      </span>
                      {activeSearch === selectedSearchDef.id && (
                        <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Default Active Search
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                      {selectedSearchDef.desc}
                    </p>
                  </div>
                </div>
              </div>

              {/* Form Inputs */}
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                    <span>Search Engine Endpoint URL</span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      {selectedSearchDef.id === "searxng"
                        ? "Local Self-Hosted Instance"
                        : "Cloud API"}
                    </span>
                  </label>
                  <input
                    type="text"
                    value={searchBaseUrl}
                    onChange={(e) => setSearchBaseUrl(e.target.value)}
                    placeholder={selectedSearchDef.defaultBaseUrl}
                    disabled={selectedSearchDef.category === "system"}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-all"
                  />
                  <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-zinc-400">
                    <span className="flex items-center gap-1">
                      {selectedSearchDef.id === "searxng" ? (
                        <ShieldCheck className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Globe className="w-3 h-3 text-zinc-400" />
                      )}
                      {selectedSearchDef.id === "searxng"
                        ? "100% Local Guard: Queries stay strictly on your machine"
                        : "Cloud Search Provider"}
                    </span>
                    <span>•</span>
                    <span>Format: JSON Search Response</span>
                  </div>
                </div>

                {/* Test Query Input */}
                <div>
                  <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                    <span>Verification Test Query</span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      Live Query Ping
                    </span>
                  </label>
                  <input
                    type="text"
                    value={testQuery}
                    onChange={(e) => setTestQuery(e.target.value)}
                    placeholder="Hausverwaltung Berlin"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-all"
                  />
                </div>

                {/* API Key (if required) */}
                {selectedSearchDef.requiresKey && (
                  <div>
                    <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                      <span>Search API Key</span>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {isSearchConfigured(selectedSearchDef.id)
                          ? "Configured in .env"
                          : "Required"}
                      </span>
                    </label>
                    <div className="relative">
                      <input
                        type={showSearchKey ? "text" : "password"}
                        value={searchApiKey}
                        onChange={(e) => setSearchApiKey(e.target.value)}
                        placeholder={
                          isSearchConfigured(selectedSearchDef.id)
                            ? "•••••••••••••••••••• (Configured in .env)"
                            : "tvly-... or BSA..."
                        }
                        className="w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-all"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSearchKey(!showSearchKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                      >
                        {showSearchKey ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                <button
                  onClick={handleTestPing}
                  disabled={pinging}
                  className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-semibold text-xs border border-zinc-800 hover:border-zinc-700 transition-all disabled:opacity-50"
                >
                  <Zap
                    className={`w-4 h-4 ${pinging ? "animate-spin text-emerald-400" : "text-emerald-400"}`}
                  />
                  <span>
                    {pinging
                      ? "Testing Search Connection..."
                      : "Test Search Engine (Live Ping)"}
                  </span>
                </button>

                <button
                  onClick={handleApplyAndConnect}
                  disabled={applying}
                  className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs shadow-glowEmerald transition-all disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>
                    {savedSuccess
                      ? "✓ Connected & Active!"
                      : "Connect & Apply as Active Search"}
                  </span>
                </button>
              </div>
            </>
          )}

          {/* Live Ping Test Result Box (Shared for both tabs) */}
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
                      <span>
                        {activeTab === "llm"
                          ? "10-Token Ping: SUCCESS (200 OK)"
                          : "Search Connection: VERIFIED (200 OK)"}
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                      <span>Connection Error</span>
                    </>
                  )}
                </div>

                <span className="text-[11px] text-zinc-400">
                  Latency:{" "}
                  <strong className="text-zinc-200">
                    {pingResult.latency_ms}ms
                  </strong>
                </span>
              </div>

              {pingResult.status === "ok" ? (
                <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 space-y-1">
                  <div className="flex justify-between text-[11px] text-zinc-400">
                    <span>
                      {activeTab === "llm"
                        ? `Model: ${pingResult.model}`
                        : `Engines Active: ${pingResult.engines_active || 4}`}
                    </span>
                    <span>
                      {activeTab === "llm"
                        ? `Tokens: ${pingResult.tokens || 10}`
                        : `Privacy: ${pingResult.privacy || "100% Private"}`}
                    </span>
                  </div>
                  <p className="text-[11px] font-mono text-zinc-100">
                    Output:{" "}
                    <span className="text-emerald-400">
                      &quot;{pingResult.reply}&quot;
                    </span>
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
          <span>Async Crawler Concurrency & Network Performance</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          <div>
            <div className="flex items-center justify-between text-xs font-mono mb-2">
              <span className="text-zinc-400">
                HTTP/2 Async Crawler Workers:
              </span>
              <strong className="text-emerald-400">
                {concurrency} concurrent requests
              </strong>
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
              Higher workers accelerate discovery across Berlin property
              management subpages.
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
