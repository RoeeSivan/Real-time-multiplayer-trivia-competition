// Mirrors backend payloads. Keep in sync with backend/models.py and
// backend/socket_handlers.py / runner.py emit shapes.

export type Mode = "cpu" | "friends";
export type HelpType = "fifty" | "friend" | "double";

export type Phase = "idle" | "lobby" | "countdown" | "question" | "feedback" | "ended";

export interface PublicPlayer {
  id: string;
  name: string;
  is_bot: boolean;
  score: number;
  rank?: number;
}

export interface AckCreateRoom {
  ok: boolean;
  error: string | null;
  room_code: string;
  player_id: string;
  is_host: boolean;
  players: PublicPlayer[];
}

export interface AckJoinRoom extends AckCreateRoom {}

export interface QuestionEvt {
  idx: number;
  text: string;
  options: string[];
  time_limit: number;
  difficulty: number;
}

export interface AnswerResultEvt {
  question_idx: number;
  your_choice: number;
  correct: boolean;
  correct_idx: number;
  doubled: boolean;
  points: number;
  your_score: number;
  // Streak counter AFTER this round (0 if just missed); multiplier is what
  // was applied to this round's score (uses the pre-round streak).
  streak: number;
  streak_multiplier: number;
}

export interface RoundEndEvt {
  idx: number;
}

export interface GameOverEvt {
  leaderboard: PublicPlayer[];
  winner: string | null;
}

export interface LobbyUpdateEvt {
  players: PublicPlayer[];
  host_id: string | null;
}

export interface ChatMsgEvt {
  player_id: string;
  name: string;
  text: string;
}

export interface ReactionEvt {
  player_id: string;
  name: string;
  emoji: string;
}

// Reaction enriched with client-side display state.
export interface ActiveReaction extends ReactionEvt {
  id: string;
  x: number; // horizontal % within viewport (5-95)
}

export interface AnswerReceivedEvt {
  player_id: string;
}

export interface GameStartingEvt {
  countdown_seconds: number;
}

export interface ErrorEvt {
  message: string;
}

export interface HelpResultFifty {
  ok: boolean;
  error: string | null;
  type: "fifty";
  removed_indices: number[];
}
export interface HelpResultFriend {
  ok: boolean;
  error: string | null;
  type: "friend";
  advice: string;
}
export interface HelpResultDouble {
  ok: boolean;
  error: string | null;
  type: "double";
}
export type HelpResult = HelpResultFifty | HelpResultFriend | HelpResultDouble;
