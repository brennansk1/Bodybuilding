import type { Config } from "tailwindcss";

/**
 * Viltrum theme — light mode rebrand of Coronado.
 *
 * The `viltrum` color group is the canonical token set used by new code.
 * The `jungle` color group is kept as a backward-compatibility alias —
 * every token has been re-pointed at its Viltrum equivalent so the ~100
 * legacy files still compile without a mass rename. See the rebind
 * mapping in `src/app/globals.css` for context.
 */
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // ── Canonical Viltrum palette ──────────────────────────────────
        viltrum: {
          // Backgrounds
          white:      "#FFFFFF",
          alabaster:  "#FAFAF8",
          marble:     "#F5F4F1",
          limestone:  "#F0EFEC",
          ash:        "#E2E0DC",
          pumice:     "#D0CFC8",
          // Text hierarchy
          obsidian:   "#1A1816",
          charcoal:   "#2C2825",
          iron:       "#5C5750",
          travertine: "#8A857D",
          pewter:     "#C4C0B9",
          basalt:     "#706B64",
          // Viltrumite reds (primary accent family)
          blush:          "#FAF0F0",
          "terracotta":   "#E8B4B4",
          legion:         "#C44040",
          "legion-hover": "#B33838",
          centurion:      "#8B2B2B",
          oxblood:        "#5C1A1A",
          // Semantic
          laurel:       "#2D7A45",
          "laurel-bg":  "#EDF7F0",
          aureus:       "#C48820",
          "aureus-bg":  "#FBF5E8",
          adriatic:     "#2E6B9C",
          "adriatic-bg":"#EBF3FA",
        },
        // ── Flat aliases for the most-used Viltrum tokens ──────────────
        obsidian:   "#1A1816",
        charcoal:   "#2C2825",
        iron:       "#5C5750",
        travertine: "#8A857D",
        pewter:     "#C4C0B9",
        basalt:     "#706B64",
        marble:     "#F5F4F1",
        alabaster:  "#FAFAF8",
        limestone:  "#F0EFEC",
        ash:        "#E2E0DC",
        pumice:     "#D0CFC8",
        blush:      "#FAF0F0",
        terracotta: "#E8B4B4",
        legion:     "#C44040",
        "legion-hover": "#B33838",
        centurion:  "#8B2B2B",
        oxblood:    "#5C1A1A",
        laurel:     "#2D7A45",
        aureus:     "#C48820",
        adriatic:   "#2E6B9C",
        // ── Legacy `jungle-*` aliases — DO NOT REMOVE ─────────────────
        // Every historic token now resolves to its Viltrum twin so existing
        // pages keep working during the rebrand. New code should use the
        // `viltrum-*` or flat aliases above.
        jungle: {
          dark:          "#F5F4F1",   // page bg → marble
          deeper:        "#FAFAF8",   // inset → alabaster
          card:          "#FFFFFF",   // card bg → white
          "card-hover":  "#F0EFEC",   // hover → limestone
          border:        "#E2E0DC",   // border → ash
          "border-hover":"#D0CFC8",   // hover border → pumice
          // Accent — was gold, now Viltrumite red
          accent:         "#C44040",  // legion
          "accent-hover": "#B33838",  // legion-hover
          "accent-muted": "#E8B4B4",  // terracotta
          // "Primary" was green — re-point to obsidian structural dark
          primary:         "#1A1816",
          "primary-hover": "#2C2825",
          "primary-muted": "#5C5750",
          canopy:          "#8B2B2B",
          moss:            "#C44040",
          fern:            "#E8B4B4",
          vine:            "#FAF0F0",
          // Semantic (now light-mode-appropriate)
          success: "#2D7A45",
          warning: "#C48820",
          danger:  "#C44040",
          // Text — INVERTED for light mode
          text:  "#1A1816",  // was cream, now obsidian
          muted: "#5C5750",  // iron
          dim:   "#8A857D",  // travertine
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Contrail One", "Impact", "system-ui", "sans-serif"],
        serif:   ["var(--font-serif)",   "Crimson Pro",  "Georgia",  "serif"],
        sans:    ["var(--font-sans)",    "Inter",        "system-ui","sans-serif"],
        body:    ["var(--font-sans)",    "Inter",        "system-ui","sans-serif"], // legacy alias
      },
      fontSize: {
        // Display tokens — Contrail One at showcase sizes
        "display-xl": ["48px", { letterSpacing: "8px",  lineHeight: "1" }],
        "display-lg": ["42px", { letterSpacing: "4px",  lineHeight: "1" }],
        "display-md": ["32px", { letterSpacing: "2px",  lineHeight: "1.05" }],
        "display-sm": ["24px", { letterSpacing: "2px",  lineHeight: "1.1" }],
        "h-card":     ["13px", { letterSpacing: "3px",  lineHeight: "1.2", fontWeight: "400" }],
        "h-section":  ["11px", { letterSpacing: "5px",  lineHeight: "1.2", fontWeight: "400" }],
        // Metric tokens
        "metric-xl": ["42px", { lineHeight: "1" }],
        "metric-lg": ["36px", { lineHeight: "1" }],
        "metric-md": ["28px", { lineHeight: "1" }],
      },
      borderRadius: {
        card:   "6px",
        button: "4px",
        pill:   "9999px",
      },
      borderWidth: {
        hairline: "0.5px",
        emphasis: "2.5px",
      },
      boxShadow: {
        card:  "0 1px 2px rgba(26,24,22,0.04)",
        focus: "0 0 0 3px rgba(26,24,22,0.08)",
      },
      backgroundImage: {
        "viltrum-fade": "linear-gradient(180deg, #F5F4F1 0%, #F0EFEC 100%)",
        "legion-gradient": "linear-gradient(90deg, #8B2B2B 0%, #C44040 100%)",
        // Legacy aliases
        "jungle-gradient": "linear-gradient(135deg, #F5F4F1 0%, #FAFAF8 50%, #F0EFEC 100%)",
        "gold-gradient":   "linear-gradient(135deg, #8B2B2B 0%, #C44040 50%, #E8B4B4 100%)",
        "canopy-gradient": "linear-gradient(180deg, #FFFFFF 0%, #F0EFEC 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
