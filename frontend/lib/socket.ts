"use client";

import { io, Socket } from "socket.io-client";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (socket && socket.connected) return socket;
  if (socket) return socket;
  const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
