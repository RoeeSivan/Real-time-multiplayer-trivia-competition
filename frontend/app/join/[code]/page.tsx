"use client";

import { useParams } from "next/navigation";
import { useGameSocket } from "@/hooks/useGameSocket";
import NameForm from "@/components/NameForm";
import Lobby from "@/components/Lobby";
import Game from "@/components/Game";

export default function JoinPage() {
  const params = useParams<{ code: string }>();
  const code = (params?.code || "").toUpperCase();
  const game = useGameSocket();

  if (game.phase === "idle") {
    return (
      <main className="min-h-screen flex items-center justify-center p-6">
        <NameForm
          title={`Join room ${code}`}
          cta="Join"
          onSubmit={(name) => game.joinRoom(code, name).then(() => undefined)}
        />
      </main>
    );
  }

  if (game.phase === "lobby" && game.roomCode) {
    return (
      <main className="min-h-screen p-6 flex items-center justify-center">
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
