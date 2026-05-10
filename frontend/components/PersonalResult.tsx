"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { AnswerResultEvt } from "@/lib/types";

interface Props {
  result: AnswerResultEvt | null;
}

export default function PersonalResult({ result }: Props) {
  return (
    <AnimatePresence>
      {result && (
        <motion.div
          key={result.question_idx}
          initial={{ opacity: 0, y: 10, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.25 }}
          className={`glass rounded-2xl p-4 text-center ${
            result.correct ? "border-ok/40 bg-ok/10" : "border-bad/40 bg-bad/10"
          }`}
        >
          <div className="text-3xl mb-1">{result.correct ? "✓" : "✗"}</div>
          <div className="font-semibold">
            {result.correct ? "Correct!" : "Wrong"}
            {result.doubled && result.correct && (
              <span className="ml-2 text-accent2">2×</span>
            )}
          </div>
          <div className="text-sm text-muted">
            +{result.points} pts · You: <span className="text-accent">{result.your_score}</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
