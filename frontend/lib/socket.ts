"use client";

import { io, Socket } from "socket.io-client";

let socket: Socket | null = null;

function resolveBackendUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (envUrl) return envUrl;
  if (typeof window !== "undefined" && window.location?.hostname) {
    const proto = window.location.protocol === "https:" ? "https" : "http";
    return `${proto}://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export function getSocket(): Socket {
  if (socket && socket.connected) return socket;
  if (socket) return socket;
  const url = resolveBackendUrl();
  socket = io(url, {
    path: "/socket.io",
    transports: ["websocket", "polling"],
    autoConnect: true,
  });
  return socket;
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
