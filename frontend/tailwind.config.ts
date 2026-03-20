import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        jungle: {
          // Core backgrounds
          dark: "#0b1410",
          deeper: "#071210",
          card: "#0f1f18",
          "card-hover": "#142a20",
          border: "#1a3328",
          "border-hover": "#245a3a",
          // Accent — gold/amber tones
          accent: "#c8a84e",
          "accent-hover": "#dbbf6a",
          "accent-muted": "#8a7434",
          // Greens
          primary: "#2d8a4e",
          "primary-hover": "#38a85e",
          "primary-muted": "#1e5e35",
          canopy: "#1a4d2e",
          moss: "#3a7d44",
          fern: "#5da569",
          vine: "#7bc47a",
          // Semantic
          success: "#4ade80",
          warning: "#f59e0b",
          danger: "#ef4444",
          // Text
          text: "#e8efe9",
          muted: "#8faa96",
          dim: "#5a7a62",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "jungle-gradient": "linear-gradient(135deg, #0b1410 0%, #0f1f18 50%, #142a20 100%)",
        "gold-gradient": "linear-gradient(135deg, #c8a84e 0%, #dbbf6a 50%, #8a7434 100%)",
        "canopy-gradient": "linear-gradient(180deg, #071210 0%, #0f1f18 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
