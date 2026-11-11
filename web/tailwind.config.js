/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#09090b",
        surface: {
          50: "#0d0d10",
          100: "#111114",
          200: "#16161b",
          300: "#1c1c22",
        },
        frost: {
          matte: "#111114",
          card: "#141418",
          border: "rgba(255, 255, 255, 0.08)",
          hover: "rgba(255, 255, 255, 0.04)",
        },
        primary: {
          DEFAULT: "#10b981",
          glow: "rgba(16, 185, 129, 0.15)",
          dark: "#059669",
        },
        accent: {
          DEFAULT: "#f4f4f5",
          muted: "#71717a",
        },
        tierA: {
          DEFAULT: "#10b981",
          glow: "rgba(16, 185, 129, 0.15)",
          border: "rgba(16, 185, 129, 0.3)",
        },
        tierB: {
          DEFAULT: "#f59e0b",
          glow: "rgba(245, 158, 11, 0.15)",
          border: "rgba(245, 158, 11, 0.3)",
        },
        tierC: {
          DEFAULT: "#a1a1aa",
          glow: "rgba(161, 161, 170, 0.1)",
          border: "rgba(161, 161, 170, 0.25)",
        },
      },
      boxShadow: {
        matte: "0 4px 24px -4px rgba(0, 0, 0, 0.8)",
        matteCard: "0 2px 12px -2px rgba(0, 0, 0, 0.6)",
        matteHover: "0 8px 28px -4px rgba(0, 0, 0, 0.9)",
        glowEmerald: "0 0 20px -3px rgba(16, 185, 129, 0.25)",
      },
      fontFamily: {
        sans: [
          "Calibri",
          "Segoe UI",
          "Segoe UI Variable",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "sans-serif",
        ],
        mono: [
          "Consolas",
          "Cascadia Mono",
          "Cascadia Code",
          "SFMono-Regular",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
