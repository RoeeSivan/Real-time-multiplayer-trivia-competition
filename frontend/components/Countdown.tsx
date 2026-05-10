"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

interface Props {
  seconds: number;
}

export default function Countdown({ seconds }: Props) {
  const [n, setN] = useState(seconds);
  useEffect(() => {
    setN(seconds);
    const t = setInterval(() => setN((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(t);
  }, [seconds]);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <AnimatePresence mode="wait">
        <motion.div
          key={n}
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 1.5, opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="text-9xl font-extrabold bg-gradient-to-br from-accent to-accent2 bg-clip-text text-transparent"
        >
          {n > 0 ? n : "GO!"}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
