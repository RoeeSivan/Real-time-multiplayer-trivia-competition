"use client";

import { useGameSocket } from "@/hooks/useGameSocket";
import NameForm from "@/components/NameForm";
import Game from "@/components/Game";

export default function CpuPage() {
  const game = useGameSocket();

  if (game.phase === "idle") {
    return (
      <main className="min-h-screen flex items-center justify-center p-6">
        <NameForm
          title="vs Computer"
          cta="Start"
          onSubmit={(name) => game.createRoom("cpu", name).then(() => undefined)}
        />
      </main>
    );
  }

  return <Game game={game} />;
}
