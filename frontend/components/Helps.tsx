"use client";

import { motion } from "framer-motion";

interface Props {
  used: { fifty: boolean; friend: boolean; double: boolean };
  doubled: boolean;
  disabled: boolean;
  onUse: (type: "fifty" | "friend" | "double") => void;
}

const helps = [
  { key: "fifty" as const, label: "50/50", icon: "✂️", hint: "Remove 2 wrong answers" },
  { key: "friend" as const, label: "Call a Friend", icon: "📞", hint: "Get a witty hint" },
  { key: "double" as const, label: "Double Score", icon: "✨", hint: "2× points if correct" },
];

export default function Helps({ used, doubled, disabled, onUse }: Props) {
  return (
    <div className="flex gap-2 flex-wrap">
      {helps.map((h) => {
        const isUsed = used[h.key];
        const isActive = h.key === "double" && doubled;
        return (
          <motion.button
            key={h.key}
            whileTap={!isUsed && !disabled ? { scale: 0.92 } : undefined}
            onClick={() => !isUsed && !disabled && onUse(h.key)}
            disabled={isUsed || disabled}
            title={h.hint}
            className={`relative px-3 py-2 rounded-lg text-sm font-medium border ${
              isActive
                ? "border-accent2 bg-accent2/20"
                : isUsed
                ? "border-white/5 bg-panel/30 text-muted line-through"
                : "border-white/10 bg-panel/60 hover:border-accent"
            } disabled:cursor-not-allowed`}
          >
            <span className="mr-1">{h.icon}</span>
            {h.label}
          </motion.button>
        );
      })}
    </div>
  );
}
