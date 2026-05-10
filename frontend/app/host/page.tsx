"use client";

import { useGameSocket } from "@/hooks/useGameSocket";
import NameForm from "@/components/NameForm";
import Lobby from "@/components/Lobby";
import QRPanel from "@/components/QRPanel";
import Game from "@/components/Game";

export default function HostPage() {
  const game = useGameSocket();

  if (game.phase === "idle") {
    return (
      <main className="min-h-screen flex items-center justify-center p-6">
        <NameForm
          title="Host a Friends Game"
          cta="Create room"
          onSubmit={(name) => game.createRoom("friends", name).then(() => undefined)}
        />
      </main>
    );
  }

  if (game.phase === "lobby" && game.roomCode) {
    return (
      <main className="min-h-screen p-6 flex flex-col md:flex-row items-center md:items-start justify-center gap-6">
        <QRPanel roomCode={game.roomCode} />
        <Lobby
          roomCode={game.roomCode}
          players={game.players}
          hostId={game.hostId}
          selfId={game.selfId}
          isHost={game.isHost}
          onStart={game.startGame}
        />
      </main>
    );
  }

  return <Game game={game} />;
}
