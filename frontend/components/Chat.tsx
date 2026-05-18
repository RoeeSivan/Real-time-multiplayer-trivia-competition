"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ChatMsgEvt } from "@/lib/types";

const QUICK_EMOJIS = ["😂", "🔥", "💀", "🎉", "🤯", "👏", "🤔", "🥲"];
const QUICK_REACTIONS = ["🔥", "🎉", "💀", "🤯", "👏", "❤️", "😱", "🤣"];

interface Props {
  messages: ChatMsgEvt[];
  selfId: string | null;
  onSend: (text: string) => void;
  onReact: (emoji: string) => void;
}

export default function Chat({ messages, selfId, onSend, onReact }: Props) {
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  const submit = () => {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };

  return (
    <div className="glass rounded-2xl p-4 flex flex-col h-full min-h-[260px]">
      <h3 className="text-sm uppercase text-muted mb-2 tracking-wider">Chat</h3>
      <div ref={listRef} className="flex-1 overflow-y-auto space-y-1.5 mb-2">
        <AnimatePresence>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: m.player_id === selfId ? 8 : -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-sm"
            >
              <span className={`font-semibold ${m.player_id === selfId ? "text-accent" : "text-accent2"}`}>
                {m.name}:
              </span>{" "}
              <span>{m.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <div className="flex items-center gap-1 mb-1 flex-wrap">
        <span className="text-[10px] uppercase tracking-wider text-muted mr-1">React</span>
        {QUICK_REACTIONS.map((e) => (
          <button
            key={e}
            onClick={() => onReact(e)}
            title="Floats across all screens"
            className="text-lg hover:scale-125 transition active:scale-95"
          >
            {e}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1 mb-2 flex-wrap">
        <span className="text-[10px] uppercase tracking-wider text-muted mr-1">Send</span>
        {QUICK_EMOJIS.map((e) => (
          <button
            key={e}
            onClick={() => onSend(e)}
            title="Sent as a chat message"
            className="text-lg hover:scale-110 transition opacity-80"
          >
            {e}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Say something…"
          maxLength={200}
          className="flex-1 bg-panel/80 rounded-lg px-3 py-2 text-sm outline-none border border-white/10 focus:border-accent"
        />
        <button
          onClick={submit}
          className="px-3 py-2 bg-accent rounded-lg text-sm font-semibold"
        >
          Send
        </button>
      </div>
    </div>
  );
}
