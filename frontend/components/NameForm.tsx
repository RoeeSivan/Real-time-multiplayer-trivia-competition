"use client";

import { useState } from "react";

interface Props {
  title: string;
  cta: string;
  onSubmit: (name: string) => void | Promise<void>;
}

export default function NameForm({ title, cta, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const trimmed = name.trim().slice(0, 20);
    if (!trimmed) return;
    setBusy(true);
    try {
      await onSubmit(trimmed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass rounded-2xl p-8 w-full max-w-md">
      <h2 className="text-2xl font-bold mb-1">{title}</h2>
      <p className="text-muted text-sm mb-6">Pick a name to play.</p>
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="Your name"
        maxLength={20}
        className="w-full bg-panel/80 rounded-lg px-4 py-3 outline-none border border-white/10 focus:border-accent text-lg mb-4"
      />
      <button
        onClick={submit}
        disabled={busy || !name.trim()}
        className="w-full py-3 rounded-xl bg-gradient-to-r from-accent to-accent2 font-bold text-lg disabled:opacity-40"
      >
        {busy ? "Connecting…" : cta}
      </button>
    </div>
  );
}
