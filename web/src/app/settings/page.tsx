"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import Link from "next/link";
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
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
  ChevronDown,
  X,
  Check,
} from "lucide-react";
import {
  fetchSettings,
  saveSettings,
  pingProvider,
  pingSearchProvider,
  discoverProviderModels,
} from "@/lib/api";
import { ProviderIcon } from "@/components/icons/ProviderLogos";
import { RoundedSelect } from "@/components/ui/RoundedSelect";

// 1. Real AI / LLM Models Only (7)
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
    name: "Google Gemini API",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    defaultModel: "",
    requiresKey: true,
    desc: "Official Google Generative Language API (/v1beta) with live model discovery and native JSON schema extraction.",
  },
  {
    id: "openai",
    name: "OpenAI API",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://api.openai.com/v1",
    defaultModel: "",
    requiresKey: true,
    desc: "Official OpenAI Platform API (/v1) :  full live model catalog (GPT-4.1, GPT-4o, o3, o4-mini) with structured JSON outputs.",
  },
  {
    id: "deepseek",
    name: "DeepSeek API",
    category: "cloud",
    badge: "Cloud API",
    defaultBaseUrl: "https://api.deepseek.com/v1",
    defaultModel: "",
    requiresKey: true,
    desc: "Official DeepSeek Platform API (/v1) :  live DeepSeek Chat & Reasoner models for German B2B website extraction.",
  },
  {
    id: "ollama",
    name: "Ollama Local API",
    category: "local",
    badge: "Local Offline",
    defaultBaseUrl: "http://localhost:11434/v1",
    defaultModel: "",
    requiresKey: false,
    desc: "Local Ollama inference daemon (/api/tags & /v1) :  auto-discovers all locally installed GGUF models on your GPU/CPU.",
  },
  {
    id: "lm_studio",
    name: "LM Studio Local API",
    category: "local",
    badge: "Local GUI",
    defaultBaseUrl: "http://localhost:1234/v1",
    defaultModel: "",
    requiresKey: false,
    desc: "Local LM Studio OpenAI-compatible server (/v1/models) :  auto-discovers loaded local quantized GGUF models.",
  },
  {
    id: "local_llamacpp",
    name: "llama.cpp Server API",
    category: "local",
    badge: "Local CLI",
    defaultBaseUrl: "http://localhost:8080/v1",
    defaultModel: "",
    requiresKey: false,
    desc: "Standalone C++ llama.cpp HTTP server (/v1/models) with hardware acceleration (CUDA/Metal/AVX512).",
  },
  {
    id: "nvidia_nim",
    name: "NVIDIA NIM API",
    category: "cloud",
    badge: "Enterprise API",
    defaultBaseUrl: "https://integrate.api.nvidia.com/v1",
    defaultModel: "",
    requiresKey: true,
    desc: "Official NVIDIA NIM enterprise inference API (/v1/models) :  accelerated cloud foundation models.",
  },
];

// 2. Non-LLM System Parsers & Fallback Routers (2)
const SYSTEM_ENGINES: LLMProviderDef[] = [
  {
    id: "auto_fallback",
    name: "Auto Fallback Cascade",
    category: "system",
    badge: "Resilient Router",
    defaultBaseUrl: "internal://cascade",
    defaultModel: "cascading-router",
    requiresKey: false,
    desc: "Non-LLM traffic controller. Cascades sequentially: Cloud LLM → Local GPU → Deterministic German Legal Parser.",
  },
  {
    id: "deterministic",
    name: "Deterministic Legal Parser",
    category: "system",
    badge: "Non-LLM Rule Engine",
    defaultBaseUrl: "internal://regex",
    defaultModel: "regex_german_impressum_v2",
    requiresKey: false,
    desc: "Pure Python German § 5 DDG legal notice parser, DOM tech scanner, and RFC MX validator. Zero AI tokens, $0 cost.",
  },
];

const ALL_EXTRACTION_ENGINES: LLMProviderDef[] = [
  ...LLM_PROVIDERS,
  ...SYSTEM_ENGINES,
];

// 3. Web Search Providers (5)
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
    desc: "Self-hosted meta-search. Upstream engines, limits, and privacy depend on this instance's configuration.",
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
    name: "Native Public Web Search",
    category: "system",
    badge: "Directory Scrapers",
    defaultBaseUrl: "internal://scrapers",
    requiresKey: false,
    desc: "Queries public DuckDuckGo and Brave web pages directly from this laptop.",
  },
  {
    id: "brave",
    name: "Brave Search API",
    category: "cloud",
    badge: "Independent Index",
    defaultBaseUrl: "https://api.search.brave.com/res/v1",
    requiresKey: true,
    desc: "Search API. Availability, limits, and data handling depend on your provider plan and settings.",
  },
  {
    id: "google_cse",
    name: "Google Custom Search (CSE)",
    category: "cloud",
    badge: "Google Cloud",
    defaultBaseUrl: "https://www.googleapis.com/customsearch/v1",
    requiresKey: true,
    desc: "Google Custom Search API. Requires an API key and a configured Search Engine ID.",
  },
];

export default function SettingsHubPage() {
  const [cfg, setCfg] = useState<any>(null);

  // 3-Tab Switcher: "llm" | "system" | "search"
  const [activeTab, setActiveTab] = useState<"llm" | "system" | "search">(
    "llm",
  );

  // Active configurations from backend
  const [activeLLM, setActiveLLM] = useState<string>("auto_fallback");
  const [activeSearch, setActiveSearch] = useState<string>("searxng");

  // Selection states per tab
  const [selectedLLMId, setSelectedLLMId] = useState<string>("gemini");
  const [selectedSystemId, setSelectedSystemId] =
    useState<string>("auto_fallback");
  const [selectedSearchId, setSelectedSearchId] = useState<string>("searxng");

  // Form states for LLM / System
  const [llmBaseUrl, setLlmBaseUrl] = useState<string>("");
  const [llmModel, setLlmModel] = useState<string>("");
  const [llmApiKey, setLlmApiKey] = useState<string>("");
  const [showLlmKey, setShowLlmKey] = useState<boolean>(false);

  // Live Model Discovery states
  const [discoveredModels, setDiscoveredModels] = useState<any[]>([]);
  const [discoverySource, setDiscoverySource] =
    useState<string>("catalog_presets");
  const [discoveryMessage, setDiscoveryMessage] = useState<string>("");
  const [discoveryLatency, setDiscoveryLatency] = useState<number>(0);
  const [discoveringModels, setDiscoveringModels] = useState<boolean>(false);

  // Model Live Search & Combobox states
  const [modelSearchInput, setModelSearchInput] = useState<string>("");
  const [modelDropdownOpen, setModelDropdownOpen] = useState<boolean>(false);
  const modelComboboxRef = useRef<HTMLDivElement>(null);

  // Filter and rank models so search query matches appear at the top
  const filteredModels = useMemo(() => {
    if (!discoveredModels || discoveredModels.length === 0) return [];
    const q = modelSearchInput.trim().toLowerCase();
    if (!q) return discoveredModels;

    return [...discoveredModels]
      .filter((m) => {
        const idLower = (m.id || "").toLowerCase();
        const nameLower = (m.name || "").toLowerCase();
        const capLower = (m.capabilities || "").toLowerCase();
        return (
          idLower.includes(q) || nameLower.includes(q) || capLower.includes(q)
        );
      })
      .sort((a, b) => {
        const aId = (a.id || "").toLowerCase();
        const bId = (b.id || "").toLowerCase();
        if (aId === q) return -1;
        if (bId === q) return 1;
        const aStarts = aId.startsWith(q);
        const bStarts = bId.startsWith(q);
        if (aStarts && !bStarts) return -1;
        if (!aStarts && bStarts) return 1;
        return aId.localeCompare(bId);
      });
  }, [discoveredModels, modelSearchInput]);

  // Close model suggestions dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        modelComboboxRef.current &&
        !modelComboboxRef.current.contains(e.target as Node)
      ) {
        setModelDropdownOpen(false);
      }
    };
    if (modelDropdownOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [modelDropdownOpen]);

  // Form states for Search
  const [searchBaseUrl, setSearchBaseUrl] = useState<string>("");
  const [searchApiKey, setSearchApiKey] = useState<string>("");
  const [searchEngineId, setSearchEngineId] = useState<string>("");
  const [showSearchKey, setShowSearchKey] = useState<boolean>(false);
  const [testQuery, setTestQuery] = useState<string>("");

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
          const isSys = SYSTEM_ENGINES.some(
            (s) => s.id === data.default_llm_provider,
          );
          if (isSys) {
            setSelectedSystemId(data.default_llm_provider);
          } else {
            setSelectedLLMId(data.default_llm_provider);
          }
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

  const currentEngineId =
    activeTab === "system" ? selectedSystemId : selectedLLMId;

  const selectedLLMDef =
    ALL_EXTRACTION_ENGINES.find((p) => p.id === currentEngineId) ||
    LLM_PROVIDERS[0];

  const selectedSearchDef =
    SEARCH_PROVIDERS.find((p) => p.id === selectedSearchId) ||
    SEARCH_PROVIDERS[0];

  // Update LLM form values when selection changes
  useEffect(() => {
    setPingResult(null);
    setShowLlmKey(false);
    setDiscoveredModels([]);
    if (!cfg) {
      setLlmBaseUrl(selectedLLMDef.defaultBaseUrl);
      setLlmModel(
        selectedLLMDef.category === "system" ? selectedLLMDef.defaultModel : "",
      );
      setLlmApiKey("");
      return;
    }

    if (currentEngineId === "deepseek") {
      setLlmBaseUrl(cfg.deepseek_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.deepseek_configured ? cfg.deepseek_model || "" : "");
      setLlmApiKey("");
    } else if (currentEngineId === "gemini") {
      setLlmBaseUrl(cfg.gemini_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.gemini_configured ? cfg.gemini_model || "" : "");
      setLlmApiKey("");
    } else if (currentEngineId === "openai") {
      setLlmBaseUrl(cfg.openai_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.openai_configured ? cfg.openai_model || "" : "");
      setLlmApiKey("");
    } else if (currentEngineId === "ollama") {
      setLlmBaseUrl(cfg.ollama_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel("");
      setLlmApiKey("");
    } else if (currentEngineId === "lm_studio") {
      setLlmBaseUrl(cfg.lmstudio_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel("");
      setLlmApiKey("");
    } else if (currentEngineId === "local_llamacpp") {
      setLlmBaseUrl(cfg.llamacpp_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel("");
      setLlmApiKey("");
    } else if (currentEngineId === "nvidia_nim") {
      setLlmBaseUrl(cfg.nvidia_nim_base_url || selectedLLMDef.defaultBaseUrl);
      setLlmModel(cfg.nvidia_nim_configured ? cfg.nvidia_nim_model || "" : "");
      setLlmApiKey("");
    } else {
      setLlmBaseUrl(selectedLLMDef.defaultBaseUrl);
      setLlmModel(selectedLLMDef.defaultModel);
      setLlmApiKey("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEngineId, cfg]);

  // Update Search form values when selection changes
  useEffect(() => {
    setPingResult(null);
    setShowSearchKey(false);
    if (!cfg) {
      setSearchBaseUrl(selectedSearchDef.defaultBaseUrl);
      setSearchApiKey("");
      setSearchEngineId("");
      return;
    }

    if (selectedSearchId === "searxng") {
      setSearchBaseUrl(
        cfg.searxng_base_url || selectedSearchDef.defaultBaseUrl,
      );
      setSearchApiKey("");
      setSearchEngineId("");
    } else if (selectedSearchId === "google_cse") {
      setSearchBaseUrl(selectedSearchDef.defaultBaseUrl);
      setSearchApiKey("");
      setSearchEngineId(cfg.google_cse_id || "");
    } else {
      setSearchBaseUrl(selectedSearchDef.defaultBaseUrl);
      setSearchApiKey("");
      setSearchEngineId("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSearchId, cfg]);

  // Automatically discover models when provider, base URL, or API key changes
  const handleDiscoverModels = async (
    provId = currentEngineId,
    baseUrl = llmBaseUrl,
    apiKey = llmApiKey,
  ) => {
    if (
      provId === "auto_fallback" ||
      provId === "deterministic" ||
      activeTab === "system"
    ) {
      setDiscoveredModels([]);
      setDiscoverySource("system");
      return;
    }
    try {
      setDiscoveringModels(true);
      const res = await discoverProviderModels({
        provider: provId,
        base_url: baseUrl || undefined,
        api_key: apiKey || undefined,
      });
      const liveModels: any[] = res.models || [];
      setDiscoveredModels(liveModels);
      setDiscoverySource(res.source || "awaiting_key");
      setDiscoveryMessage(res.message || "");
      setDiscoveryLatency(res.latency_ms || 0);

      if (res.source === "live_api" && liveModels.length > 0) {
        const rec = liveModels.find((m: any) => m.recommended) || liveModels[0];
        setLlmModel((prev) =>
          prev && liveModels.some((m: any) => m.id === prev)
            ? prev
            : rec?.id || "",
        );
      } else {
        setLlmModel("");
      }
    } catch (err) {
      console.error("Model discovery error:", err);
      setDiscoveredModels([]);
      setLlmModel("");
    } finally {
      setDiscoveringModels(false);
    }
  };

  useEffect(() => {
    if (activeTab !== "llm") return;
    const timer = setTimeout(() => {
      handleDiscoverModels(currentEngineId, llmBaseUrl, llmApiKey);
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEngineId, llmBaseUrl, llmApiKey, activeTab]);

  // Execute Ping Test
  const handleTestPing = async () => {
    try {
      setPinging(true);
      setPingResult(null);

      if (activeTab === "llm" || activeTab === "system") {
        const res = await pingProvider({
          provider: currentEngineId,
          base_url: llmBaseUrl || undefined,
          api_key: llmApiKey || undefined,
          model: llmModel || undefined,
        });
        setPingResult(res);
      } else {
        if (!testQuery.trim()) {
          setPingResult({
            status: "error",
            latency_ms: 0,
            error: "Enter a real search query before testing this provider.",
          });
          return;
        }
        const res = await pingSearchProvider({
          provider: selectedSearchId,
          base_url: searchBaseUrl || undefined,
          api_key: searchApiKey || undefined,
          google_cse_id: searchEngineId || undefined,
          query: testQuery.trim(),
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

      if (activeTab === "llm" || activeTab === "system") {
        payload.default_llm_provider = currentEngineId;
        if (currentEngineId === "deepseek") {
          if (llmApiKey) payload.deepseek_api_key = llmApiKey;
          if (llmBaseUrl) payload.deepseek_base_url = llmBaseUrl;
          if (llmModel) payload.deepseek_model = llmModel;
        } else if (currentEngineId === "gemini") {
          if (llmApiKey) payload.gemini_api_key = llmApiKey;
          if (llmBaseUrl) payload.gemini_base_url = llmBaseUrl;
          if (llmModel) payload.gemini_model = llmModel;
        } else if (currentEngineId === "openai") {
          if (llmApiKey) payload.openai_api_key = llmApiKey;
          if (llmBaseUrl) payload.openai_base_url = llmBaseUrl;
          if (llmModel) payload.openai_model = llmModel;
        } else if (currentEngineId === "ollama") {
          if (llmBaseUrl) payload.ollama_base_url = llmBaseUrl;
          if (llmModel) payload.ollama_model = llmModel;
        } else if (currentEngineId === "lm_studio") {
          if (llmBaseUrl) payload.lmstudio_base_url = llmBaseUrl;
          if (llmModel) payload.lmstudio_model = llmModel;
        } else if (currentEngineId === "local_llamacpp") {
          if (llmBaseUrl) payload.llamacpp_base_url = llmBaseUrl;
          if (llmModel) payload.llamacpp_model = llmModel;
        } else if (currentEngineId === "nvidia_nim") {
          if (llmApiKey) payload.nvidia_nim_api_key = llmApiKey;
          if (llmBaseUrl) payload.nvidia_nim_base_url = llmBaseUrl;
          if (llmModel) payload.nvidia_nim_model = llmModel;
        }
        await saveSettings(payload);
        setActiveLLM(currentEngineId);
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
          if (searchEngineId.trim())
            payload.google_cse_id = searchEngineId.trim();
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
    if (id === "google_cse")
      return cfg.google_cse_configured && Boolean(cfg.google_cse_id);
    if (id === "brave") return cfg.brave_configured;
    return true;
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
            Configure AI/LLM extraction models, non-LLM deterministic legal
            parsers, and web search engines.
          </p>
        </div>

        {/* Live Active Pills */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-zinc-500">Active Engine:</span>
            <span className="text-emerald-400 font-bold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-sm bg-emerald-400 animate-pulse"></span>
              {ALL_EXTRACTION_ENGINES.find((p) => p.id === activeLLM)?.name ||
                activeLLM}
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

      {/* Quick Navigation to Data Control & Factory Reset */}
      <div className="settings-quick-nav p-4 rounded-2xl bg-gradient-to-r from-rose-950/20 via-zinc-950 to-zinc-900 border border-rose-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-matte">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-zinc-200 font-mono flex items-center gap-2">
              <span>Database Lifecycle & Factory Reset</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                Governance
              </span>
            </h2>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Need to clear all runs, purge leads, or reset the app to a clean
              slate?
            </p>
          </div>
        </div>
        <Link
          href="/data-control"
          className="px-3.5 py-1.5 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 text-xs font-semibold flex items-center gap-1.5 transition-all self-start sm:self-auto shrink-0"
        >
          <span>Open Data Control</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* ======================================================== */}
      {/* 3-TAB SWITCHER: LLM Models (7) | Rule Parsers (2) | Search (5) */}
      {/* ======================================================== */}
      <div className="flex justify-start overflow-x-auto">
        <div className="p-1 rounded-2xl bg-zinc-900/90 border border-zinc-800 flex items-center gap-1 shadow-matte">
          <button
            onClick={() => {
              setActiveTab("llm");
              setPingResult(null);
            }}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 ${
              activeTab === "llm"
                ? "bg-zinc-800 text-emerald-400 border border-zinc-700/80 shadow-md"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>LLM Extraction Models ({LLM_PROVIDERS.length})</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("system");
              setPingResult(null);
            }}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 ${
              activeTab === "system"
                ? "bg-zinc-800 text-emerald-400 border border-zinc-700/80 shadow-md"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>System Parsers & Fallback ({SYSTEM_ENGINES.length})</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("search");
              setPingResult(null);
            }}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 ${
              activeTab === "search"
                ? "bg-zinc-800 text-emerald-400 border border-zinc-700/80 shadow-md"
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
        {/* LEFT PANEL: Inventory List (5 Columns)                   */}
        {/* ======================================================== */}
        <div className="lg:col-span-5 p-5 rounded-2xl bg-[#111114] border border-zinc-800/80 shadow-matte space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              {activeTab === "llm"
                ? "AI / LLM Model Inventory (7)"
                : activeTab === "system"
                  ? "Non-LLM Rule Parsers & Routers (2)"
                  : "Search Provider Inventory (5)"}
            </span>
            <span className="text-[10px] font-mono text-zinc-500">
              Click to Select
            </span>
          </div>

          <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1">
            {activeTab === "llm"
              ? // 1. Pure LLM Providers List (7)
                LLM_PROVIDERS.map((p) => {
                  const isSelected = selectedLLMId === p.id;
                  const isActive = activeLLM === p.id;

                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedLLMId(p.id)}
                      className={`p-3.5 rounded-xl cursor-pointer transition-all border text-left flex items-start justify-between gap-3 ${
                        isSelected
                          ? "border-emerald-500/35 bg-zinc-900/90 shadow-[0_0_12px_rgba(16,185,129,0.06)] ring-1 ring-emerald-500/20"
                          : "border-white/[0.06] bg-[#141418] hover:bg-zinc-850 hover:border-white/[0.1]"
                      }`}
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-8 h-8 flex items-center justify-center shrink-0 mt-0.5">
                          <ProviderIcon providerId={p.id} size={24} />
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-bold truncate ${
                                isSelected
                                  ? "text-emerald-400"
                                  : "text-zinc-200"
                              }`}
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
              : activeTab === "system"
                ? // 2. Non-LLM System Parsers & Fallback Routers (2)
                  SYSTEM_ENGINES.map((p) => {
                    const isSelected = selectedSystemId === p.id;
                    const isActive = activeLLM === p.id;

                    return (
                      <div
                        key={p.id}
                        onClick={() => setSelectedSystemId(p.id)}
                        className={`p-3.5 rounded-xl cursor-pointer transition-all border text-left flex items-start justify-between gap-3 ${
                          isSelected
                            ? "border-emerald-500/35 bg-zinc-900/90 shadow-[0_0_12px_rgba(16,185,129,0.06)] ring-1 ring-emerald-500/20"
                            : "border-white/[0.06] bg-[#141418] hover:bg-zinc-850 hover:border-white/[0.1]"
                        }`}
                      >
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="w-8 h-8 flex items-center justify-center shrink-0 mt-0.5">
                            <ProviderIcon providerId={p.id} size={24} />
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span
                                className={`text-xs font-bold truncate ${
                                  isSelected
                                    ? "text-emerald-400"
                                    : "text-zinc-200"
                                }`}
                              >
                                {p.name}
                              </span>
                              {isActive && (
                                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shrink-0">
                                  ACTIVE
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-zinc-400 line-clamp-2 mt-0.5">
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
                : // 3. Search Providers List (5)
                  SEARCH_PROVIDERS.map((p) => {
                    const isSelected = selectedSearchId === p.id;
                    const isActive = activeSearch === p.id;

                    return (
                      <div
                        key={p.id}
                        onClick={() => setSelectedSearchId(p.id)}
                        className={`p-3.5 rounded-xl cursor-pointer transition-all border text-left flex items-start justify-between gap-3 ${
                          isSelected
                            ? "border-emerald-500/35 bg-zinc-900/90 shadow-[0_0_12px_rgba(16,185,129,0.06)] ring-1 ring-emerald-500/20"
                            : "border-white/[0.06] bg-[#141418] hover:bg-zinc-850 hover:border-white/[0.1]"
                        }`}
                      >
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="w-8 h-8 flex items-center justify-center shrink-0 mt-0.5">
                            <ProviderIcon providerId={p.id} size={24} />
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span
                                className={`text-xs font-bold truncate ${
                                  isSelected
                                    ? "text-emerald-400"
                                    : "text-zinc-200"
                                }`}
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
          {activeTab === "llm" || activeTab === "system" ? (
            // ==================== LLM OR SYSTEM ENGINE CONFIGURATION ====================
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
                    <span>
                      {selectedLLMDef.category === "system"
                        ? "Internal Execution Engine URI"
                        : "Base Endpoint URL"}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      {selectedLLMDef.category === "system"
                        ? "Built-In Python Module"
                        : "OpenAI-Compatible /v1"}
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
                        : selectedLLMDef.category === "system"
                          ? "In-Process Python Execution (0ms Network Overhead)"
                          : "Local Loopback (HTTP)"}
                    </span>
                  </div>
                </div>

                {selectedLLMDef.requiresKey && (
                  <div>
                    <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                      <span>API Key</span>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {isLLMConfigured(selectedLLMDef.id)
                          ? "Configured in .env"
                          : "Required for Authentication"}
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
                            : "sk-... or AIzaSy... (Paste key to fetch models)"
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

                {/* Model ID / Tag + Model Inventory */}
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <label className="text-xs font-semibold text-zinc-300 flex items-center gap-2">
                      <span>
                        {selectedLLMDef.category === "system"
                          ? "Parser / Router Strategy"
                          : "Model ID / Tag"}
                      </span>
                      {selectedLLMDef.category !== "system" && (
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${
                            discoverySource === "live_api" &&
                            discoveredModels.length > 0
                              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40"
                              : discoverySource === "awaiting_key"
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                                : "bg-zinc-900 text-zinc-400 border-zinc-800"
                          }`}
                        >
                          {discoveringModels
                            ? "Connecting to endpoint..."
                            : discoverySource === "live_api" &&
                                discoveredModels.length > 0
                              ? `✓ ${discoveredModels.length} Models Available (${discoveryLatency}ms)`
                              : discoverySource === "awaiting_key"
                                ? "Awaiting API Key :  0 Models Loaded"
                                : "Endpoint Offline :  0 Models Loaded"}
                        </span>
                      )}
                    </label>

                    {selectedLLMDef.category !== "system" && (
                      <button
                        type="button"
                        onClick={() =>
                          handleDiscoverModels(
                            currentEngineId,
                            llmBaseUrl,
                            llmApiKey,
                          )
                        }
                        disabled={discoveringModels}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-emerald-500/40 text-[10px] font-mono text-emerald-400 transition-all disabled:opacity-50"
                        title="Query provider /v1/models or /api/tags endpoint now"
                      >
                        <RefreshCw
                          className={`w-3 h-3 ${
                            discoveringModels ? "animate-spin" : ""
                          }`}
                        />
                        <span>Discover Models</span>
                      </button>
                    )}
                  </div>

                  {/* Searchable Autocomplete Model Selector */}
                  <div ref={modelComboboxRef} className="relative">
                    <div className="relative flex items-center">
                      <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 pointer-events-none" />
                      <input
                        type="text"
                        value={modelSearchInput}
                        onChange={(e) => {
                          const val = e.target.value;
                          setModelSearchInput(val);
                          setModelDropdownOpen(true);
                          if (!discoveredModels.some((m) => m.id === val)) {
                            setLlmModel(val);
                          }
                        }}
                        onFocus={() => {
                          if (
                            selectedLLMDef.category !== "system" &&
                            discoveredModels.length > 0
                          ) {
                            setModelDropdownOpen(true);
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            if (filteredModels.length > 0) {
                              const chosen = filteredModels[0].id;
                              setLlmModel(chosen);
                              setModelSearchInput(chosen);
                              setModelDropdownOpen(false);
                            } else if (modelSearchInput.trim()) {
                              setLlmModel(modelSearchInput.trim());
                              setModelDropdownOpen(false);
                            }
                          } else if (e.key === "Escape") {
                            setModelDropdownOpen(false);
                          }
                        }}
                        placeholder={
                          selectedLLMDef.category === "system"
                            ? selectedLLMDef.defaultModel
                            : discoveredModels.length > 0
                              ? `Search ${discoveredModels.length} models or enter model ID (e.g. nemotron, llama)...`
                              : selectedLLMDef.requiresKey
                                ? "No models loaded : enter API Key above to auto-discover live models"
                                : "No models loaded : start local server to auto-discover models"
                        }
                        disabled={selectedLLMDef.category === "system"}
                        spellCheck={false}
                        autoComplete="off"
                        autoCorrect="off"
                        autoCapitalize="off"
                        className="w-full pl-10 pr-24 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/70 focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50 transition-all shadow-sm"
                      />

                      <div className="absolute right-2.5 flex items-center gap-1.5">
                        {modelSearchInput && (
                          <button
                            type="button"
                            onClick={() => {
                              setModelSearchInput("");
                              setLlmModel("");
                              setModelDropdownOpen(true);
                            }}
                            className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                            title="Clear search"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {selectedLLMDef.category !== "system" &&
                          discoveredModels.length > 0 && (
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-zinc-800 text-zinc-400 border border-zinc-700/80">
                              {filteredModels.length}
                            </span>
                          )}

                        {selectedLLMDef.category !== "system" &&
                          discoveredModels.length > 0 && (
                            <button
                              type="button"
                              onClick={() =>
                                setModelDropdownOpen((prev) => !prev)
                              }
                              className="p-1 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                              title="Toggle suggestions list"
                            >
                              <ChevronDown
                                className={`w-3.5 h-3.5 transition-transform duration-200 ${
                                  modelDropdownOpen
                                    ? "rotate-180 text-emerald-400"
                                    : ""
                                }`}
                              />
                            </button>
                          )}
                      </div>
                    </div>

                    {/* Floating Autocomplete Suggestions Dropdown (Ranked at Top) */}
                    {modelDropdownOpen &&
                      selectedLLMDef.category !== "system" &&
                      discoveredModels.length > 0 && (
                        <div
                          className="absolute left-0 right-0 mt-1.5 rounded-2xl bg-[#141418] border border-zinc-800/95 shadow-2xl p-2 backdrop-blur-xl z-50 animate-in fade-in-0 zoom-in-95 max-h-72 overflow-y-auto space-y-1"
                          style={{ scrollbarWidth: "thin" }}
                        >
                          {/* Dropdown Header */}
                          <div className="px-2.5 py-1.5 text-[10px] font-mono text-zinc-400 border-b border-zinc-800 flex items-center justify-between">
                            <span>
                              {modelSearchInput.trim()
                                ? `Matching Models (${filteredModels.length} of ${discoveredModels.length}) :`
                                : `All Discovered Models (${discoveredModels.length}) :`}
                            </span>
                            <span className="text-zinc-500">
                              Click or Press Enter
                            </span>
                          </div>

                          {/* Suggestions List - Ranked with query matches at top */}
                          {filteredModels.length > 0 ? (
                            <div className="space-y-0.5 pt-1">
                              {filteredModels.map((m) => {
                                const isPicked = llmModel === m.id;
                                return (
                                  <div
                                    key={m.id}
                                    onClick={() => {
                                      setLlmModel(m.id);
                                      setModelSearchInput(m.id);
                                      setModelDropdownOpen(false);
                                    }}
                                    className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-xs transition-all cursor-pointer select-none ${
                                      isPicked
                                        ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold"
                                        : "text-zinc-300 hover:bg-zinc-800/80 hover:text-white"
                                    }`}
                                  >
                                    <div className="flex items-center gap-2 min-w-0">
                                      <span className="font-mono text-xs truncate">
                                        {m.id}
                                      </span>
                                      {m.recommended && (
                                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shrink-0">
                                          REC
                                        </span>
                                      )}
                                    </div>

                                    <div className="flex items-center gap-2 shrink-0">
                                      {isPicked && (
                                        <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <div className="p-3 text-center space-y-2">
                              <p className="text-xs font-mono text-zinc-400">
                                No discovered models match &quot;
                                {modelSearchInput}&quot;.
                              </p>
                              <button
                                type="button"
                                onClick={() => {
                                  setLlmModel(modelSearchInput.trim());
                                  setModelDropdownOpen(false);
                                }}
                                className="px-3 py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/25 text-xs font-mono font-semibold transition-all"
                              >
                                Use &quot;{modelSearchInput.trim()}&quot; as
                                custom Model ID
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                  </div>

                  {/* Empty State Notice when No API Key / Offline */}
                  {selectedLLMDef.category !== "system" &&
                    discoveredModels.length === 0 && (
                      <div className="px-3.5 py-2.5 rounded-xl bg-zinc-950/80 border border-zinc-800/80 flex items-center justify-between gap-2 text-[11px] font-mono text-zinc-400">
                        <span>
                          {discoveryMessage ||
                            (selectedLLMDef.requiresKey
                              ? "No API key configured : enter your API key above to discover models from the provider."
                              : "Local server unreachable : start your local server to load installed models.")}
                        </span>
                      </div>
                    )}

                  {/* Discovered Models Interactive Pills & Active Model Specs */}
                  {selectedLLMDef.category !== "system" &&
                    discoveredModels.length > 0 && (
                      <div className="p-3 rounded-xl bg-zinc-950/90 border border-zinc-800/80 space-y-2.5">
                        <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400">
                          <div className="flex items-center gap-2">
                            <span>
                              {modelSearchInput.trim()
                                ? `Filtered Models (${filteredModels.length} of ${discoveredModels.length}) :`
                                : "Available Model IDs & Tags (Click to Select):"}
                            </span>
                            {modelSearchInput.trim() && (
                              <button
                                type="button"
                                onClick={() => {
                                  setModelSearchInput("");
                                  setLlmModel("");
                                }}
                                className="text-emerald-400 hover:text-emerald-300 underline font-medium"
                              >
                                Show All
                              </button>
                            )}
                          </div>
                          <span className="text-zinc-500">
                            {discoveryMessage}
                          </span>
                        </div>

                        <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                          {filteredModels.map((m) => {
                            const isPicked = llmModel === m.id;
                            return (
                              <button
                                key={m.id}
                                type="button"
                                onClick={() => {
                                  setLlmModel(m.id);
                                  setModelSearchInput(m.id);
                                }}
                                className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-all border flex items-center gap-1.5 ${
                                  isPicked
                                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/60 font-bold shadow-sm"
                                    : "bg-zinc-900 text-zinc-300 border-zinc-800 hover:border-zinc-700 hover:text-zinc-100"
                                }`}
                              >
                                <span>{m.id}</span>
                                {m.recommended && (
                                  <span className="text-[9px] px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-400">
                                    REC
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>

                        {/* Active Model Spec Details (Only shown after user chooses a model) */}
                        {(() => {
                          const activeSpec = discoveredModels.find(
                            (m) => m.id === llmModel,
                          );
                          if (!activeSpec) {
                            return (
                              <div className="pt-2 border-t border-zinc-800/80 text-[10px] font-mono text-amber-400/90">
                                → Step 2: Choose a discovered model above, then
                                click &quot;Test Connection&quot; and &quot;Save
                                &amp; Set Active Provider&quot;.
                              </div>
                            );
                          }
                          return (
                            <div className="pt-2 border-t border-zinc-800/80 grid grid-cols-1 sm:grid-cols-3 gap-2 text-[10px] font-mono">
                              <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800/80">
                                <span className="text-zinc-500 block">
                                  Chosen Model ID
                                </span>
                                <strong className="text-emerald-400 truncate block">
                                  {activeSpec.id}
                                </strong>
                              </div>
                              <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800/80">
                                <span className="text-zinc-500 block">
                                  Context / Type
                                </span>
                                <strong className="text-zinc-200 truncate block">
                                  {activeSpec.context_window &&
                                  !activeSpec.context_window
                                    .toLowerCase()
                                    .includes("live")
                                    ? activeSpec.context_window
                                    : "Standard"}
                                </strong>
                              </div>
                              <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800/80">
                                <span className="text-zinc-500 block">
                                  Provider Metadata
                                </span>
                                <strong className="text-zinc-300 truncate block">
                                  {activeSpec.capabilities || "Ready"}
                                </strong>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                <button
                  onClick={handleTestPing}
                  disabled={pinging}
                  className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-semibold text-xs border border-zinc-800 hover:border-zinc-700 transition-all disabled:opacity-50"
                >
                  <Zap
                    className={`w-4 h-4 ${
                      pinging
                        ? "animate-spin text-emerald-400"
                        : "text-emerald-400"
                    }`}
                  />
                  <span>
                    {pinging
                      ? "Testing Engine..."
                      : selectedLLMDef.category === "system"
                        ? "Test Engine Health"
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
                        ? "Requests go to the configured SearXNG instance; upstream behavior depends on its configuration."
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
                    placeholder="Enter a real search query"
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

                {selectedSearchId === "google_cse" && (
                  <div>
                    <label className="text-xs font-semibold text-zinc-300 block mb-1.5 flex items-center justify-between">
                      <span>Google Search Engine ID</span>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {searchEngineId ? "Configured" : "Required"}
                      </span>
                    </label>
                    <input
                      type="text"
                      value={searchEngineId}
                      onChange={(event) =>
                        setSearchEngineId(event.target.value)
                      }
                      placeholder="Enter your Google Programmable Search Engine ID"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-all"
                    />
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
                    className={`w-4 h-4 ${
                      pinging
                        ? "animate-spin text-emerald-400"
                        : "text-emerald-400"
                    }`}
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

          {/* Live Ping Test Result Box (Shared across tabs) */}
          {pingResult && (
            <div
              className={`p-4 rounded-xl font-mono text-xs space-y-2 border animate-in fade-in transition-all ${
                pingResult.status === "ok"
                  ? "bg-zinc-950 border-emerald-500/40 text-emerald-400"
                  : pingResult.status === "degraded"
                    ? "bg-zinc-950 border-amber-500/40 text-amber-400"
                    : "bg-zinc-950 border-rose-500/40 text-rose-400"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold">
                  {pingResult.status === "ok" ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>
                        {activeTab === "search"
                          ? "Search test succeeded"
                          : "Provider test succeeded"}
                      </span>
                    </>
                  ) : pingResult.status === "degraded" ? (
                    <>
                      <AlertCircle className="w-4 h-4 text-amber-400" />
                      <span>Provider is available with limited results</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                      <span>Provider test failed</span>
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

              {pingResult.status === "ok" ||
              pingResult.status === "degraded" ? (
                <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 space-y-1">
                  <div className="flex justify-between text-[11px] text-zinc-400">
                    <span>
                      {activeTab === "search"
                        ? `Engines reported: ${pingResult.engines_active ?? "Not reported"}`
                        : `Engine: ${pingResult.model}`}
                    </span>
                    <span>
                      {activeTab === "search"
                        ? `Routing: ${pingResult.privacy || "Not reported"}`
                        : `Tokens: ${pingResult.tokens ?? "Not reported by provider"}`}
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
