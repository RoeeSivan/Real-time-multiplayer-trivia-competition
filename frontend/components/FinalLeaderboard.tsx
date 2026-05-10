"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { PublicPlayer } from "@/lib/types";

interface Props {
  leaderboard: PublicPlayer[];
  winner: string | null;
  selfId: string | null;
}

const MEDALS = ["🥇", "🥈", "🥉"];

export default function FinalLeaderboard({ leaderboard, winner, selfId }: Props) {
  return (
    <div className="w-full max-w-xl mx-auto text-center">
      <motion.h1
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="text-5xl md:text-6xl font-extrabold bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent mb-2"
      >
        🏆 {winner || "Game Over"}
      </motion.h1>
      <p className="text-muted mb-8">wins!</p>

      <ul className="space-y-2 mb-8">
        {leaderboard.map((p, i) => (
          <motion.li
            key={p.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className={`flex items-center justify-between rounded-xl px-4 py-3 ${
              p.id === selfId ? "bg-accent/15 border border-accent/40" : "glass"
            }`}
          >
            <span className="flex items-center gap-3">
              <span className="text-2xl w-8">{MEDALS[i] || `${i + 1}.`}</span>
              <span>{p.is_bot ? "🤖" : "🧑"}</span>
              <span className="font-semibold">{p.name}</span>
            </span>
            <span className="font-mono text-accent text-lg">{p.score}</span>
          </motion.li>
        ))}
      </ul>

      <div className="flex gap-3 justify-center">
        <Link
          href="/"
          className="px-5 py-2.5 bg-gradient-to-r from-accent to-accent2 rounded-xl font-semibold"
        >
          Play again
        </Link>
      </div>
    </div>
  );
}
