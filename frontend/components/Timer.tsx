"use client";

import { useEffect, useState } from "react";

interface Props {
  durationMs: number;
  resetKey: string | number;
}

export default function Timer({ durationMs, resetKey }: Props) {
  const [start, setStart] = useState(() => Date.now());
  const [now, setNow] = useState(start);

  useEffect(() => {
    const s = Date.now();
    setStart(s);
    setNow(s);
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [resetKey]);

  const elapsed = now - start;
  const pct = Math.max(0, 1 - elapsed / durationMs);
  const remaining = Math.max(0, Math.ceil((durationMs - elapsed) / 1000));
  const color = pct > 0.5 ? "bg-ok" : pct > 0.25 ? "bg-warn" : "bg-bad";

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-muted mb-1">
        <span>Time</span>
        <span className="font-mono">{remaining}s</span>
      </div>
      <div className="h-2 bg-panel rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-[width] duration-100`}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
    </div>
  );
}
