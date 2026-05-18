"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { ActiveReaction } from "@/lib/types";

interface Props {
  reactions: ActiveReaction[];
}

export default function ReactionOverlay({ reactions }: Props) {
  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
      <AnimatePresence>
        {reactions.map((r) => (
          <motion.div
            key={r.id}
            initial={{ y: 0, opacity: 0, scale: 0.6 }}
            animate={{ y: -280, opacity: [0, 1, 1, 0], scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 2, ease: "easeOut", times: [0, 0.15, 0.7, 1] }}
            className="absolute bottom-20 text-5xl select-none flex flex-col items-center"
            style={{ left: `${r.x}%`, transform: "translateX(-50%)" }}
          >
            <span>{r.emoji}</span>
            <span className="text-xs text-muted opacity-80 mt-1 font-mono">{r.name}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
