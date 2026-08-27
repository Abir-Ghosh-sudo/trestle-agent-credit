/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        void:     "#050505",
        bg:       "#08080b",
        "bg-2":   "#0c0c11",
        surface:  "rgba(255,255,255,0.035)",
        elevated: "rgba(255,255,255,0.055)",
        "elevated-2": "rgba(255,255,255,0.08)",
        border:   "rgba(255,255,255,0.09)",
        "border-strong": "rgba(255,255,255,0.16)",
        "brand-start": "#8b5cf6",
        "brand-mid":   "#7c6df8",
        "brand-end":   "#22d3ee",
        accent:   "#8b5cf6", // Electric violet — primary brand accent
        "accent-hover": "#a78bfa",
        "accent-dim": "rgba(139,92,246,0.14)",
        success:  "#34d399", // Emerald
        "success-dim": "rgba(52,211,153,0.12)",
        danger:   "#fb7185", // Rose
        "danger-dim": "rgba(251,113,133,0.12)",
        warning:  "#fbbf24", // Amber
        "warning-dim": "rgba(251,191,36,0.12)",
        muted:    "rgba(255,255,255,0.09)",
        "text-muted": "#6b6b76",
        "text-primary": "#f5f5f7",
        "text-secondary": "#a1a1ab",
      },
      fontFamily: {
        display: ["Inter Tight", "Inter", "sans-serif"],
        sans:    ["Inter", "sans-serif"],
        mono:    ["JetBrains Mono", "Space Mono", "monospace"],
        pixel:   ["JetBrains Mono", "monospace"],
        hand:    ["Inter", "sans-serif"],
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #8b5cf6 0%, #7c6df8 45%, #22d3ee 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, rgba(139,92,246,0.14) 0%, rgba(34,211,238,0.10) 100%)",
        "radial-fade": "radial-gradient(circle at center, rgba(255,255,255,0.06), transparent 70%)",
      },
      boxShadow: {
        'soft-xs': '0 1px 2px rgba(0,0,0,0.4)',
        'soft-sm': '0 2px 12px rgba(0,0,0,0.5)',
        'soft-md': '0 12px 32px rgba(0,0,0,0.55), 0 2px 8px rgba(0,0,0,0.4)',
        'soft-lg': '0 28px 64px rgba(0,0,0,0.6), 0 6px 16px rgba(0,0,0,0.45)',
        'glow-accent': '0 0 0 1px rgba(139,92,246,0.25), 0 16px 48px rgba(139,92,246,0.28)',
      },
      animation: {
        shimmer:      "shimmer 1.6s infinite",
        "flash-green":"flash-green 1.5s ease-out",
        "flash-red":  "flash-red 1.5s ease-out",
        "spin-slow":  "spin 0.8s linear infinite",
        "pulse-dot":  "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite",
        "marquee":    "marquee 20s linear infinite",
        "drift":      "drift 7s ease-in-out infinite",
      },
      keyframes: {
        shimmer: {
          "0%":   { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-100%)" },
        },
        drift: {
          "0%, 100%": { transform: "translate(0,0) rotate(0deg)" },
          "50%": { transform: "translate(0,-18px) rotate(6deg)" },
        },
      },
      spacing: {
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px",
        "2xl": "48px",
        "3xl": "64px",
      },
      borderRadius: {
        "card": "16px",
        "input": "12px",
        "badge": "999px",
        "btn": "12px",
      },
    },
  },
  plugins: [],
};
