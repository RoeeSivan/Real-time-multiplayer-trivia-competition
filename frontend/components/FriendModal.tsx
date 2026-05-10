"use client";

import { motion, AnimatePresence } from "framer-motion";

interface Props {
  text: string | null;
  onClose: () => void;
}

export default function FriendModal({ text, onClose }: Props) {
  return (
    <AnimatePresence>
      {text && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.85, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
            className="glass rounded-2xl p-6 max-w-md w-full"
          >
            <div className="text-3xl mb-2">📞</div>
            <h3 className="text-xl font-bold mb-3">Your friend says…</h3>
            <p className="text-lg leading-relaxed mb-4">{text}</p>
            <button
              onClick={onClose}
              className="w-full py-2 bg-accent rounded-lg font-semibold"
            >
              Got it
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
