import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0b14",
        panel: "#161629",
        accent: "#7c5cff",
        accent2: "#ff6bd6",
        ok: "#22c55e",
        bad: "#ef4444",
        warn: "#f59e0b",
        muted: "#8b8ba7",
      },
      fontFamily: {
        display: ["ui-sans-serif", "system-ui", "Inter", "Segoe UI", "Helvetica"],
      },
      keyframes: {
        pop: {
          "0%": { transform: "scale(0.95)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
      },
      animation: {
        pop: "pop 200ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
