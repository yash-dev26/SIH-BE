import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        deep: "var(--deep)",
        teal: "var(--teal)",
        midnight: "var(--midnight)",
        ice: "var(--ice)",
        paper: "var(--paper)",
        gold: "var(--gold)",
        muted: "var(--muted)",
        line: "var(--line)",
        "risk-high": "var(--risk-high)",
        "risk-med": "var(--risk-med)",
        "risk-low": "var(--risk-low)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      boxShadow: {
        hair: "0 1px 0 rgba(15, 27, 36, 0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
