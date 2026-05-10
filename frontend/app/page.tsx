"use client";

import Link from "next/link";
import { motion } from "framer-motion";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6">
      <motion.h1
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-5xl md:text-7xl font-bold tracking-tight bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent mb-3"
      >
        Trivia Royale
      </motion.h1>
      <p className="text-muted text-lg mb-12">Pick your battle.</p>

      <div className="grid md:grid-cols-2 gap-6 w-full max-w-3xl">
        <Link
          href="/cpu"
          className="glass p-8 rounded-2xl hover:border-accent transition group"
        >
          <div className="text-5xl mb-4">🤖</div>
          <h2 className="text-2xl font-semibold mb-1 group-hover:text-accent">vs Computer</h2>
          <p className="text-muted">Play solo against bots. Instant start.</p>
        </Link>

        <Link
          href="/host"
          className="glass p-8 rounded-2xl hover:border-accent2 transition group"
        >
          <div className="text-5xl mb-4">📱</div>
          <h2 className="text-2xl font-semibold mb-1 group-hover:text-accent2">vs Friends</h2>
          <p className="text-muted">Generate a QR code. Friends scan and join.</p>
        </Link>
      </div>

      <p className="text-muted text-sm mt-12">
        10 questions. Adaptive difficulty. 3 helps. Bring snacks.
      </p>
    </main>
  );
}
