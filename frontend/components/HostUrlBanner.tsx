"use client";

import { useEffect, useState } from "react";

/**
 * Warns when the host opened the page via a URL that scanning phones can't
 * reach. Triggers when NEXT_PUBLIC_TUNNEL_URL is set (i.e. ./run.sh --tunnel
 * is running) AND the current window's host doesn't match the tunnel host.
 */
export default function HostUrlBanner() {
  const [tunnelHref, setTunnelHref] = useState<string | null>(null);

  useEffect(() => {
    const tunnel = process.env.NEXT_PUBLIC_TUNNEL_URL?.trim();
    if (!tunnel) return;
    try {
      const tunnelHost = new URL(tunnel).host;
      if (window.location.host !== tunnelHost) {
        setTunnelHref(`${tunnel.replace(/\/$/, "")}/host`);
      }
    } catch {
      // Bad NEXT_PUBLIC_TUNNEL_URL — silently ignore.
    }
  }, []);

  if (!tunnelHref) return null;

  return (
    <div className="w-full max-w-2xl mx-auto mb-4 rounded-xl border border-amber-400/40 bg-amber-500/10 p-4 text-sm">
      <div className="font-semibold text-amber-200">
        ⚠️ Friends won&apos;t be able to scan this QR.
      </div>
      <div className="mt-1 text-amber-100/80">
        You opened <code className="font-mono">{typeof window !== "undefined" ? window.location.host : ""}</code>{" "}
        — phones can&apos;t reach localhost. Open the public tunnel URL instead:
      </div>
      <a
        href={tunnelHref}
        className="mt-2 inline-block font-mono text-accent break-all underline"
      >
        {tunnelHref}
      </a>
    </div>
  );
}
