import React from "react";

interface LogoProps {
  className?: string;
  size?: number;
}

// 1. Google Gemini Official 4-Point Sparkle Logo
export function GeminiLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
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
          <stop offset="40%" stopColor="#9B72CF" />
          <stop offset="70%" stopColor="#DE51A8" />
          <stop offset="100%" stopColor="#FF7769" />
        </linearGradient>
      </defs>
      <path
        d="M12 2C12 7.523 7.523 12 2 12C7.523 12 12 16.477 12 22C12 16.477 16.477 12 22 12C16.477 12 12 7.523 12 2Z"
        fill="url(#gemini-grad)"
      />
    </svg>
  );
}

// 2. OpenAI Official Spiral Vortex Glyph
export function OpenAILogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={`text-zinc-100 ${className}`}
    >
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zm-1.22-9.61a4.486 4.486 0 0 1 2.36-1.974V12.2a.784.784 0 0 0 .392.68l5.823 3.37-2.02 1.168a.076.076 0 0 1-.067 0L4.02 14.66a4.505 4.505 0 0 1-1.64-5.966zm15.422 3.109l-5.843-3.37 2.02-1.168a.076.076 0 0 1 .067 0l4.848 2.762a4.505 4.505 0 0 1-.692 8.164v-5.707a.789.789 0 0 0-.4-.681zm2.616-2.585a4.48 4.48 0 0 1-.535 3.014l-.142-.085-4.783-2.759a.771.771 0 0 0-.78 0L8.335 12.75v-2.332a.08.08 0 0 1 .033-.062l4.84-2.776a4.5 4.5 0 0 1 6.14 1.646zm-9.83-4.32a4.476 4.476 0 0 1 2.876 1.04l-.141.081-4.779 2.758a.795.795 0 0 0-.392.681v6.737l-2.02-1.168a.071.071 0 0 1-.038-.052V6.998a4.504 4.504 0 0 1 4.494-4.494zm.83 8.354l2.84-1.639 2.84 1.639v3.278l-2.84 1.64-2.84-1.64v-3.278z" />
    </svg>
  );
}

// 3. DeepSeek Official Blue Whale Logo
export function DeepSeekLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
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
          <stop offset="0%" stopColor="#2A73FF" />
          <stop offset="100%" stopColor="#0051E8" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#0C152B" />
      <path
        d="M7 17.5C8.5 13.5 12.5 11 17 11C22 11 25.5 14 26 18C26 21 23 23 19.5 23C15.5 23 13 21 11.5 19.5L7 17.5Z"
        fill="url(#deepseek-grad)"
      />
      <circle cx="14" cy="14.5" r="1.5" fill="#FFFFFF" />
      <path
        d="M23 15C25.5 13 27 10 26.5 8C24.5 9 23.5 11 23 15Z"
        fill="#3B82F6"
      />
      <path
        d="M17 23C15.5 24.5 13 25.5 10.5 25C11 23.5 12.5 22.5 14 22L17 23Z"
        fill="#1D4ED8"
      />
    </svg>
  );
}

// 4. Ollama Official Minimalist Llama Logo
export function OllamaLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <rect width="32" height="32" rx="8" fill="#18181B" />
      {/* Llama silhouette */}
      <path
        d="M16 6C15.2 6 14.5 6.7 14.5 7.5V11H12C10.9 11 10 11.9 10 13V15.5C10 16.3 10.7 17 11.5 17H12V24C12 25.1 12.9 26 14 26H15.5C16.3 26 17 25.3 17 24.5V19H18.5V24.5C18.5 25.3 19.2 26 20 26H21.5C22.6 26 23.5 25.1 23.5 24V16.5C23.5 13.5 21 11 18 11V7.5C18 6.7 17.3 6 16.5 6H16ZM14 9.5C14 9.2 14.2 9 14.5 9C14.8 9 15 9.2 15 9.5C15 9.8 14.8 10 14.5 10C14.2 10 14 9.8 14 9.5ZM17 9.5C17 9.2 17.2 9 17.5 9C17.8 9 18 9.2 18 9.5C18 9.8 17.8 10 17.5 10C17.2 10 17 9.8 17 9.5Z"
        fill="#FFFFFF"
      />
      <circle cx="15" cy="13.5" r="1" fill="#18181B" />
    </svg>
  );
}

// 5. LM Studio Official Robot / Cubic Logo
export function LMStudioLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
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
        <linearGradient id="lmstudio-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#A855F7" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#1A132F" />
      <path
        d="M16 6L24 10.5V19.5L16 24L8 19.5V10.5L16 6Z"
        stroke="url(#lmstudio-grad)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M16 11L20 13.5V17.5L16 20L12 17.5V13.5L16 11Z"
        fill="url(#lmstudio-grad)"
      />
    </svg>
  );
}

// 6. llama.cpp Official Mascot Logo
export function LlamaCppLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
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
        <linearGradient id="llamacpp-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#F59E0B" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#24180A" />
      <path
        d="M16 8C14.5 8 13.5 9 13.5 10.5V14H10C9 14 8 15 8 16V18C8 18.5 8.5 19 9 19H10V24H13V19H15V24H18V16C18 13.5 16.5 12 15 12V10.5C15 9.5 15.5 8 16 8Z"
        fill="url(#llamacpp-grad)"
      />
      <text
        x="19"
        y="25"
        fontFamily="monospace"
        fontSize="7"
        fontWeight="bold"
        fill="#F59E0B"
      >
        .cpp
      </text>
    </svg>
  );
}

// 7. NVIDIA Official Claw / Eye Logo
export function NvidiaLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <rect width="32" height="32" rx="8" fill="#0D1C0F" />
      <path
        d="M15.5 8C11.5 8 8 11.2 8 15.5C8 19.8 11.5 23 15.5 23C18.2 23 20.8 21.5 22.2 19.2C22.6 18.5 22.1 17.6 21.3 17.6H20.7C20.2 17.6 19.8 17.9 19.5 18.3C18.6 19.8 17.1 20.8 15.5 20.8C12.8 20.8 10.5 18.4 10.5 15.5C10.5 12.6 12.8 10.2 15.5 10.2C17.5 10.2 19.2 11.5 19.9 13.4C20.1 13.8 20.5 14.1 21 14.1H21.8C22.6 14.1 23.1 13.2 22.6 12.5C21.2 9.8 18.5 8 15.5 8Z"
        fill="#76B900"
      />
      <path
        d="M15.5 12.2C13.7 12.2 12.2 13.7 12.2 15.5C12.2 17.3 13.7 18.8 15.5 18.8C16.8 18.8 17.9 18 18.4 16.9C18.6 16.5 18.4 16 18 16H15.5V15H19.5C19.7 15 19.8 14.8 19.8 14.6C19.3 13.2 17.6 12.2 15.5 12.2Z"
        fill="#76B900"
      />
    </svg>
  );
}

// 8. Auto Fallback Routing DAG Logo
export function AutoFallbackLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
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
        <linearGradient id="fallback-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#10B981" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#061A12" />
      <circle cx="10" cy="10" r="3" fill="#10B981" />
      <circle cx="22" cy="10" r="3" fill="#3B82F6" />
      <circle cx="16" cy="22" r="3.5" fill="#F59E0B" />
      <path d="M12.5 11.5L14.5 19" stroke="#10B981" strokeWidth="1.5" strokeDasharray="2 2" />
      <path d="M19.5 11.5L17.5 19" stroke="#3B82F6" strokeWidth="1.5" strokeDasharray="2 2" />
    </svg>
  );
}

// 9. Deterministic Legal (§) Engine Logo
export function DeterministicLogo({ className = "w-5 h-5", size = 20 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <rect width="32" height="32" rx="8" fill="#18181B" />
      <path
        d="M16 6L24 9.5V16C24 21 20.5 25 16 26.5C11.5 25 8 21 8 16V9.5L16 6Z"
        fill="#27272A"
        stroke="#10B981"
        strokeWidth="1.2"
      />
      <text
        x="16"
        y="19"
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

// Map helper to return proper logo component
export function ProviderIcon({
  providerId,
  size = 22,
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
    default:
      return <GeminiLogo size={size} className={className} />;
  }
}
