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
        background: "#050811",
        surface: {
          50: "#0b101f",
          100: "#0f172a",
          200: "#131d36",
          300: "#1e293b",
        },
        frost: {
          light: "rgba(255, 255, 255, 0.04)",
          border: "rgba(255, 255, 255, 0.08)",
          card: "rgba(15, 23, 42, 0.65)",
          hover: "rgba(255, 255, 255, 0.07)",
        },
        primary: {
          DEFAULT: "#38bdf8",
          glow: "rgba(56, 189, 248, 0.15)",
        },
        tierA: {
          DEFAULT: "#10b981",
          glow: "rgba(16, 185, 129, 0.18)",
          border: "rgba(16, 185, 129, 0.35)",
        },
        tierB: {
          DEFAULT: "#f59e0b",
          glow: "rgba(245, 158, 11, 0.18)",
          border: "rgba(245, 158, 11, 0.35)",
        },
        tierC: {
          DEFAULT: "#94a3b8",
          glow: "rgba(148, 163, 184, 0.12)",
          border: "rgba(148, 163, 184, 0.25)",
        },
      },
      backdropBlur: {
        xs: "2px",
        frost: "20px",
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.6)",
        glowCyan: "0 0 25px -5px rgba(56, 189, 248, 0.3)",
        glowEmerald: "0 0 25px -5px rgba(16, 185, 129, 0.3)",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Menlo", "Courier New", "monospace"],
      },
    },
  },
  plugins: [],
};

