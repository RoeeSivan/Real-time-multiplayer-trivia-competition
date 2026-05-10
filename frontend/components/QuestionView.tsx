"use client";

import { motion } from "framer-motion";
import type { AnswerResultEvt, QuestionEvt } from "@/lib/types";
import Timer from "./Timer";

interface Props {
  question: QuestionEvt;
  answeredIdx: number | null;
  fiftyRemoved: number[];
  myResult: AnswerResultEvt | null;
  doubled: boolean;
  onAnswer: (idx: number) => void;
}

const LETTERS = ["A", "B", "C", "D"];

export default function QuestionView({
  question,
  answeredIdx,
  fiftyRemoved,
  myResult,
  doubled,
  onAnswer,
}: Props) {
  const showResult = myResult !== null;

  return (
    <div className="w-full max-w-3xl">
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-muted">Q{question.idx + 1} / 10</span>
        <span className="text-muted">
          Difficulty: <span className="text-accent">{question.difficulty}</span>/10
        </span>
      </div>

      <Timer durationMs={question.time_limit * 1000} resetKey={question.idx} />

      <motion.div
        key={question.idx}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl p-6 my-5"
      >
        <h2 className="text-2xl md:text-3xl font-semibold leading-snug">{question.text}</h2>
      </motion.div>

      <div className="grid md:grid-cols-2 gap-3">
        {question.options.map((opt, i) => {
          const removed = fiftyRemoved.includes(i);
          const picked = answeredIdx === i;
          const isCorrectIdx = showResult && myResult && i === myResult.correct_idx;

          let cls = "border-white/10 bg-panel/60 hover:border-accent";
          if (showResult && isCorrectIdx) cls = "border-ok bg-ok/15";
          else if (showResult && picked && !isCorrectIdx) cls = "border-bad bg-bad/15";
          else if (picked) cls = "border-accent bg-accent/15";
          if (removed) cls += " opacity-30 line-through pointer-events-none";

          return (
            <motion.button
              key={i}
              whileTap={!showResult && answeredIdx === null ? { scale: 0.97 } : undefined}
              onClick={() => onAnswer(i)}
              disabled={showResult || answeredIdx !== null || removed}
              className={`text-left p-4 rounded-xl border-2 transition ${cls}`}
            >
              <div className="flex items-start gap-3">
                <span className="font-mono text-accent2 font-bold">{LETTERS[i]}</span>
                <span className="flex-1">{opt}</span>
                {showResult && isCorrectIdx && <span>✓</span>}
                {showResult && picked && !isCorrectIdx && <span>✗</span>}
              </div>
            </motion.button>
          );
        })}
      </div>

      {doubled && !showResult && (
        <div className="mt-4 text-center text-accent2 text-sm font-semibold">
          ✨ Double Score armed — answer correctly for 2× points!
        </div>
      )}

      {answeredIdx !== null && !showResult && (
        <div className="mt-4 text-center text-muted text-sm">
          Locked in. Waiting for the round to end…
        </div>
      )}
    </div>
  );
}
