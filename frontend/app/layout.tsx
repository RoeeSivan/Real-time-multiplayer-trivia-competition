import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trivia Royale",
  description: "Real-time multiplayer trivia",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
