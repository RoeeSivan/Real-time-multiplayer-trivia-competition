"use client";

import { motion } from "framer-motion";
import type { PublicPlayer } from "@/lib/types";

interface Props {
  roomCode: string;
  players: PublicPlayer[];
  hostId: string | null;
  selfId: string | null;
  isHost: boolean;
  onStart: () => void;
}

export default function Lobby({ roomCode, players, hostId, selfId, isHost, onStart }: Props) {
  return (
    <div className="glass rounded-2xl p-6 w-full max-w-xl">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-2xl font-bold">Lobby</h2>
        <div className="text-sm text-muted">
          Code: <span className="font-mono text-accent text-base">{roomCode}</span>
        </div>
      </div>

      <ul className="space-y-2 mb-6">
        {players.map((p) => (
          <motion.li
            key={p.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center justify-between bg-panel/60 rounded-lg px-4 py-2"
          >
            <span className="flex items-center gap-2">
              <span>{p.is_bot ? "🤖" : "🧑"}</span>
              <span className={p.id === selfId ? "font-semibold" : ""}>
                {p.name}
                {p.id === selfId && <span className="text-muted text-xs ml-2">(you)</span>}
              </span>
            </span>
            {p.id === hostId && (
              <span className="text-xs px-2 py-0.5 rounded bg-accent/20 text-accent">host</span>
            )}
          </motion.li>
        ))}
      </ul>

      {isHost ? (
        <button
          onClick={onStart}
          disabled={players.length < 1}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-accent to-accent2 font-bold text-lg disabled:opacity-40"
        >
          Start Game
        </button>
      ) : (
        <p className="text-center text-muted">Waiting for host to start…</p>
      )}
    </div>
  );
}
