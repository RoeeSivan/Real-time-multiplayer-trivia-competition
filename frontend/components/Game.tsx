"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import type { GameState } from "@/hooks/useGameSocket";
import Countdown from "./Countdown";
import QuestionView from "./QuestionView";
import PersonalResult from "./PersonalResult";
import Chat from "./Chat";
import Helps from "./Helps";
import FriendModal from "./FriendModal";
import FinalLeaderboard from "./FinalLeaderboard";
import ReactionOverlay from "./ReactionOverlay";

interface Props {
  game: GameState;
}

export default function Game({ game }: Props) {
  // Local audio cue when private result arrives.
  useEffect(() => {
    if (!game.myResult) return;
    try {
      const ctx = new (window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.connect(g);
      g.connect(ctx.destination);
      osc.frequency.value = game.myResult.correct ? 880 : 220;
      g.gain.setValueAtTime(0.18, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch {
      /* audio off */
    }
  }, [game.myResult]);

  if (game.phase === "ended" && game.finalLeaderboard) {
    return (
      <main className="min-h-screen p-6 flex items-center justify-center">
        <ReactionOverlay reactions={game.reactions} />
        <FinalLeaderboard
          leaderboard={game.finalLeaderboard}
          winner={game.winner}
          selfId={game.selfId}
          isHost={game.isHost}
          onRestart={game.restartGame}
        />
      </main>
    );
  }

  if (game.phase === "countdown") {
    return (
      <main className="min-h-screen p-6">
        <ReactionOverlay reactions={game.reactions} />
        <Countdown seconds={game.countdown ?? 3} />
      </main>
    );
  }

  return (
    <main className="min-h-screen p-4 md:p-6">
      <ReactionOverlay reactions={game.reactions} />
      <div className="max-w-6xl mx-auto grid lg:grid-cols-[1fr_320px] gap-6">
        <div className="flex flex-col items-center gap-4">
          {(game.phase === "question" || game.phase === "feedback") && game.question && (
            <>
              <div className="w-full max-w-3xl flex items-center justify-between">
                <Helps
                  used={game.helpsUsed}
                  doubled={game.doubled}
                  disabled={game.phase === "feedback"}
                  onUse={(t) => game.useHelp(t)}
                />
                <div className="text-sm text-muted flex items-center gap-2">
                  <span>
                    Your score: <span className="font-mono text-accent">{game.myScore}</span>
                  </span>
                  {game.myResult && game.myResult.streak >= 2 && (
                    <motion.span
                      key={`combo-${game.myResult.question_idx}`}
                      initial={{ scale: 0.6, opacity: 0 }}
                      animate={{ scale: [1, 1.3, 1], opacity: 1 }}
                      transition={{ duration: 0.5 }}
                      className="font-mono text-accent2 text-sm"
                      title={`${game.myResult.streak} in a row`}
                    >
                      🔥 ×{game.myResult.streak_multiplier.toFixed(2)} ({game.myResult.streak})
                    </motion.span>
                  )}
                </div>
              </div>
              <QuestionView
                question={game.question}
                answeredIdx={game.answeredIdx}
                fiftyRemoved={game.fiftyRemoved}
                myResult={game.myResult}
                doubled={game.doubled}
                onAnswer={(i) => game.submitAnswer(i)}
              />
            </>
          )}
        </div>

        <aside className="flex flex-col gap-4">
          <PersonalResult result={game.myResult} />
          <div className="glass rounded-2xl p-4">
            <h3 className="text-sm uppercase text-muted mb-2 tracking-wider">Players</h3>
            <ul className="space-y-1.5 text-sm">
              {game.players.map((p) => (
                <li
                  key={p.id}
                  className={`flex items-center gap-2 px-2 py-1 rounded ${
                    p.id === game.selfId ? "text-accent" : ""
                  }`}
                >
                  <span>{p.is_bot ? "🤖" : "🧑"}</span>
                  <span className="truncate">{p.name}</span>
                  {p.id === game.selfId && <span className="text-xs text-muted">(you)</span>}
                </li>
              ))}
            </ul>
          </div>
          <Chat
            messages={game.chat}
            selfId={game.selfId}
            onSend={game.sendChat}
            onReact={game.sendReaction}
          />
        </aside>
      </div>

      <FriendModal text={game.friendAdvice} onClose={game.clearFriendAdvice} />

      {game.errorMsg && (
        <div className="fixed bottom-4 right-4 bg-bad/90 text-white px-4 py-2 rounded-lg shadow-lg">
          {game.errorMsg}
        </div>
      )}
    </main>
  );
}
