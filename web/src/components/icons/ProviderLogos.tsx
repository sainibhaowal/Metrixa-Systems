import React from "react";

interface LogoProps {
  className?: string;
  size?: number;
}

// 1. Google Gemini Official 4-Point Sparkle Logo (Pure Vector, No Border Box)
export function GeminiLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="gemini-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4E88D4" />
          <stop offset="35%" stopColor="#9B72CF" />
          <stop offset="70%" stopColor="#DE51A8" />
          <stop offset="100%" stopColor="#FF7769" />
        </linearGradient>
      </defs>
      <path
        d="M12 1.5C12 7.299 7.299 12 1.5 12C7.299 12 12 16.701 12 22.5C12 16.701 16.701 12 22.5 12C16.701 12 12 7.299 12 1.5Z"
        fill="url(#gemini-grad)"
      />
    </svg>
  );
}

// 2. OpenAI Official Spiral Knot Logo (Pure Vector, No Border Box)
export function OpenAILogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={`text-zinc-100 ${className}`}
    >
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zm-1.22-9.61a4.486 4.486 0 0 1 2.36-1.974V12.2a.784.784 0 0 0 .392.68l5.823 3.37-2.02 1.168a.076.076 0 0 1-.067 0L4.02 14.66a4.505 4.505 0 0 1-1.64-5.966zm15.422 3.109l-5.843-3.37 2.02-1.168a.076.076 0 0 1 .067 0l4.848 2.762a4.505 4.505 0 0 1-.692 8.164v-5.707a.789.789 0 0 0-.4-.681zm2.616-2.585a4.48 4.48 0 0 1-.535 3.014l-.142-.085-4.783-2.759a.771.771 0 0 0-.78 0L8.335 12.75v-2.332a.08.08 0 0 1 .033-.062l4.84-2.776a4.505 4.505 0 0 1 6.14 1.646zm-9.83-4.32a4.476 4.476 0 0 1 2.876 1.04l-.141.081-4.779 2.758a.795.795 0 0 0-.392.681v6.737l-2.02-1.168a.071.071 0 0 1-.038-.052V6.998a4.504 4.504 0 0 1 4.494-4.494zm.83 8.354l2.84-1.639 2.84 1.639v3.278l-2.84 1.64-2.84-1.64v-3.278z" />
    </svg>
  );
}

// 3. DeepSeek Official Whale/Dolphin Logo (Pure Vector, No Border Box)
export function DeepSeekLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="deepseek-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#1D4ED8" />
        </linearGradient>
      </defs>
      <path
        d="M4 17C6 11.5 11.5 8 18 8C25 8 30 12.5 30.5 18C30.5 22.5 26.5 25.5 21.5 25.5C16 25.5 12.5 22.5 10.5 20L4 17Z"
        fill="url(#deepseek-grad)"
      />
      <circle cx="15" cy="13.5" r="1.75" fill="#FFFFFF" />
      <path
        d="M26 13.5C28.5 11 30.5 7.5 30 5.5C27 6.5 25.5 9.5 26 13.5Z"
        fill="#60A5FA"
      />
      <path
        d="M18 25.5C15.5 27.5 12 28.5 9 28C10 26 12 24.5 14 24L18 25.5Z"
        fill="#1E40AF"
      />
    </svg>
  );
}

// 4. Ollama Official Minimalist Llama Logo (Pure Vector, No Border Box)
export function OllamaLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M12 2C10.9 2 10 2.9 10 4V7.5H7C5.9 7.5 5 8.4 5 9.5V12.5C5 13.3 5.7 14 6.5 14H7V20C7 21.1 7.9 22 9 22H10.5C11.3 22 12 21.3 12 20.5V15.5H13.5V20.5C13.5 21.3 14.2 22 15 22H16.5C17.6 22 18.5 21.1 18.5 20V13.5C18.5 10.2 16 7.5 13 7.5V4C13 2.9 12.1 2 12 2ZM9.5 5.5C10 5.5 10.5 6 10.5 6.5C10.5 7 10 7.5 9.5 7.5C9 7.5 8.5 7 8.5 6.5C8.5 6 9 5.5 9.5 5.5ZM13.5 5.5C14 5.5 14.5 6 14.5 6.5C14.5 7 14 7.5 13.5 7.5C13 7.5 12.5 7 12.5 6.5C12.5 6 13 5.5 13.5 5.5Z"
        fill="#FFFFFF"
      />
      <circle cx="9.5" cy="10.5" r="1" fill="#18181B" />
    </svg>
  );
}

// 5. LM Studio Official Isometric Cube Logo (Pure Vector, No Border Box)
export function LMStudioLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="lmstudio-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#C084FC" />
          <stop offset="100%" stopColor="#818CF8" />
        </linearGradient>
      </defs>
      <path
        d="M12 2L20.5 7V17L12 22L3.5 17V7L12 2Z"
        stroke="url(#lmstudio-grad)"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
      <path
        d="M12 7.5L16.5 10V15L12 17.5L7.5 15V10L12 7.5Z"
        fill="url(#lmstudio-grad)"
      />
    </svg>
  );
}

// 6. llama.cpp Official Mascot Logo (Pure Vector, No Border Box)
export function LlamaCppLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="llamacpp-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FBBF24" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
      </defs>
      <path
        d="M11 2C9.5 2 8.5 3 8.5 4.5V8H5C4 8 3 9 3 10V12C3 12.5 3.5 13 4 13H5V20H8V15H10V20H13V12C13 9.5 11.5 8 10 8V4.5C10 3.5 10.5 2 11 2Z"
        fill="url(#llamacpp-grad)"
      />
      <text
        x="13.5"
        y="21"
        fontFamily="ui-monospace, monospace"
        fontSize="7.5"
        fontWeight="bold"
        fill="#FBBF24"
      >
        .cpp
      </text>
    </svg>
  );
}

// 7. NVIDIA Official Claw/Eye Logo (Pure Vector, No Border Box)
export function NvidiaLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M12 3C7.5 3 3.5 6.6 3.5 11.5C3.5 16.4 7.5 20 12 20C15.1 20 18 18.3 19.5 15.7C19.9 14.9 19.4 13.9 18.5 13.9H17.8C17.3 13.9 16.8 14.2 16.5 14.7C15.5 16.3 13.8 17.5 12 17.5C8.9 17.5 6.3 14.8 6.3 11.5C6.3 8.2 8.9 5.5 12 5.5C14.3 5.5 16.2 7 17 9.1C17.2 9.6 17.7 9.9 18.2 9.9H19.1C20 9.9 20.5 8.9 20 8.1C18.4 5 15.4 3 12 3Z"
        fill="#76B900"
      />
      <path
        d="M12 7.8C9.9 7.8 8.3 9.5 8.3 11.5C8.3 13.6 9.9 15.2 12 15.2C13.5 15.2 14.7 14.3 15.3 13H12V11.5H16.7C16.9 11.5 17 11.3 17 11.1C16.4 9.2 14.4 7.8 12 7.8Z"
        fill="#76B900"
      />
    </svg>
  );
}

// 8. Auto Fallback Routing Cascade Logo (Pure Vector, No Border Box)
export function AutoFallbackLogo({
  className = "w-6 h-6",
  size = 24,
}: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <circle cx="6" cy="6" r="3" fill="#10B981" />
      <circle cx="18" cy="6" r="3" fill="#3B82F6" />
      <circle cx="12" cy="18" r="3.5" fill="#F59E0B" />
      <path
        d="M8.5 7.5L10.5 15"
        stroke="#10B981"
        strokeWidth="1.5"
        strokeDasharray="2 2"
      />
      <path
        d="M15.5 7.5L13.5 15"
        stroke="#3B82F6"
        strokeWidth="1.5"
        strokeDasharray="2 2"
      />
    </svg>
  );
}

// 9. Deterministic Legal (§) Engine Logo (Pure Vector, No Border Box)
export function DeterministicLogo({
  className = "w-6 h-6",
  size = 24,
}: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M12 2L19.5 5.5V12C19.5 16.8 16.2 20.8 12 22C7.8 20.8 4.5 16.8 4.5 12V5.5L12 2Z"
        stroke="#10B981"
        strokeWidth="1.8"
        fill="#10B981"
        fillOpacity="0.15"
      />
      <text
        x="12"
        y="15.5"
        textAnchor="middle"
        fontFamily="serif"
        fontSize="12"
        fontWeight="bold"
        fill="#10B981"
      >
        §
      </text>
    </svg>
  );
}

// 10. SearXNG Official Privacy Meta-Search Logo (Pure Vector, No Border Box)
export function SearXNGLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="searxng-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="50%" stopColor="#10B981" />
          <stop offset="100%" stopColor="#F59E0B" />
        </linearGradient>
      </defs>
      <circle
        cx="10.5"
        cy="10.5"
        r="7"
        stroke="url(#searxng-grad)"
        strokeWidth="2.5"
      />
      <path
        d="M15.5 15.5L21 21"
        stroke="#10B981"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M7.5 10.5H13.5M10.5 7.5V13.5"
        stroke="#38BDF8"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

// 11. Tavily AI Search Logo (Pure Vector, No Border Box)
export function TavilyLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="tavily-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#A855F7" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
      </defs>
      <path
        d="M12 2L14.8 8.8L22 12L14.8 15.2L12 22L9.2 15.2L2 12L9.2 8.8L12 2Z"
        fill="url(#tavily-grad)"
      />
    </svg>
  );
}

// 12. Native Meta-Search Direct German Directory Logo (Pure Vector, No Border Box)
export function NativeMetaSearchLogo({
  className = "w-6 h-6",
  size = 24,
}: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="#EAB308"
        strokeWidth="2"
        strokeDasharray="4 2"
      />
      <path
        d="M7 12H17"
        stroke="#3B82F6"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="3.5" fill="#10B981" />
    </svg>
  );
}

// 13. Brave Search Lion Emblem Logo (Pure Vector, No Border Box)
export function BraveLogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M12 3L18.5 5.5L20.5 12L17.5 17L12 21L6.5 17L3.5 12L5.5 5.5L12 3Z"
        fill="#FF5500"
      />
      <path
        d="M12 7L15 8.5L16 12L14 15L12 17L10 15L8 12L9 8.5L12 7Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}

// 14. Google Search CSE Logo (Pure Vector, No Border Box)
export function GoogleCSELogo({ className = "w-6 h-6", size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
        fill="#EA4335"
      />
    </svg>
  );
}

// Map helper to return proper logo component
export function ProviderIcon({
  providerId,
  size = 24,
  className = "",
}: {
  providerId: string;
  size?: number;
  className?: string;
}) {
  switch (providerId) {
    case "gemini":
      return <GeminiLogo size={size} className={className} />;
    case "openai":
      return <OpenAILogo size={size} className={className} />;
    case "deepseek":
      return <DeepSeekLogo size={size} className={className} />;
    case "ollama":
      return <OllamaLogo size={size} className={className} />;
    case "lm_studio":
      return <LMStudioLogo size={size} className={className} />;
    case "local_llamacpp":
      return <LlamaCppLogo size={size} className={className} />;
    case "nvidia_nim":
      return <NvidiaLogo size={size} className={className} />;
    case "auto_fallback":
      return <AutoFallbackLogo size={size} className={className} />;
    case "deterministic":
      return <DeterministicLogo size={size} className={className} />;
    // Search Providers
    case "searxng":
      return <SearXNGLogo size={size} className={className} />;
    case "tavily":
      return <TavilyLogo size={size} className={className} />;
    case "native_metasearch":
      return <NativeMetaSearchLogo size={size} className={className} />;
    case "brave":
      return <BraveLogo size={size} className={className} />;
    case "google_cse":
      return <GoogleCSELogo size={size} className={className} />;
    default:
      return <GeminiLogo size={size} className={className} />;
  }
}
