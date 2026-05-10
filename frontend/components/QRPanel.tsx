"use client";

import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";

interface Props {
  roomCode: string;
}

export default function QRPanel({ roomCode }: Props) {
  const [joinUrl, setJoinUrl] = useState<string>("");

  useEffect(() => {
    const origin = window.location.origin;
    setJoinUrl(`${origin}/join/${roomCode}`);
  }, [roomCode]);

  if (!joinUrl) return null;

  return (
    <div className="glass rounded-2xl p-6 flex flex-col items-center gap-4">
      <h3 className="text-lg font-semibold">Scan to join</h3>
      <div className="bg-white p-3 rounded-lg">
        <QRCodeSVG value={joinUrl} size={200} level="M" />
      </div>
      <div className="text-center">
        <div className="text-xs text-muted">or open</div>
        <a href={joinUrl} className="font-mono text-sm text-accent break-all">
          {joinUrl}
        </a>
      </div>
    </div>
  );
}
