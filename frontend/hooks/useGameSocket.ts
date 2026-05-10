"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Socket } from "socket.io-client";
import { getSocket } from "@/lib/socket";
import type {
  AckCreateRoom,
  AckJoinRoom,
  AnswerResultEvt,
  ChatMsgEvt,
  ErrorEvt,
  GameOverEvt,
  GameStartingEvt,
  HelpResult,
  LobbyUpdateEvt,
  Mode,
  Phase,
  PublicPlayer,
  QuestionEvt,
  RoundEndEvt,
} from "@/lib/types";

export interface GameState {
  socket: Socket | null;
  phase: Phase;
  roomCode: string | null;
  mode: Mode | null;
  selfId: string | null;
  isHost: boolean;
  players: PublicPlayer[];
  hostId: string | null;
  question: QuestionEvt | null;
  myResult: AnswerResultEvt | null;   // private feedback for current question
  myScore: number;                     // own running score (only known to self)
  finalLeaderboard: PublicPlayer[] | null;
  winner: string | null;
  countdown: number | null;
  chat: ChatMsgEvt[];
  answeredIdx: number | null;
  fiftyRemoved: number[];
  doubled: boolean;
  helpsUsed: { fifty: boolean; friend: boolean; double: boolean };
  friendAdvice: string | null;
  errorMsg: string | null;
  // actions
  createRoom: (mode: Mode, name: string) => Promise<AckCreateRoom>;
  joinRoom: (code: string, name: string) => Promise<AckJoinRoom>;
  startGame: () => Promise<void>;
  submitAnswer: (optionIdx: number) => Promise<void>;
  useHelp: (type: "fifty" | "friend" | "double") => Promise<HelpResult | null>;
  sendChat: (text: string) => void;
  clearFriendAdvice: () => void;
}

export function useGameSocket(): GameState {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [roomCode, setRoomCode] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode | null>(null);
  const [selfId, setSelfId] = useState<string | null>(null);
  const [isHost, setIsHost] = useState(false);
  const [players, setPlayers] = useState<PublicPlayer[]>([]);
  const [hostId, setHostId] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuestionEvt | null>(null);
  const [myResult, setMyResult] = useState<AnswerResultEvt | null>(null);
  const [myScore, setMyScore] = useState(0);
  const [finalLeaderboard, setFinalLeaderboard] = useState<PublicPlayer[] | null>(null);
  const [winner, setWinner] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [chat, setChat] = useState<ChatMsgEvt[]>([]);
  const [answeredIdx, setAnsweredIdx] = useState<number | null>(null);
  const [fiftyRemoved, setFiftyRemoved] = useState<number[]>([]);
  const [doubled, setDoubled] = useState(false);
  const [helpsUsed, setHelpsUsed] = useState({ fifty: false, friend: false, double: false });
  const [friendAdvice, setFriendAdvice] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const sockRef = useRef<Socket | null>(null);

  useEffect(() => {
    const s = getSocket();
    sockRef.current = s;
    setSocket(s);

    const onLobby = (d: LobbyUpdateEvt) => {
      setPlayers(d.players);
      setHostId(d.host_id);
    };
    const onStarting = (d: GameStartingEvt) => {
      setPhase("countdown");
      setCountdown(d.countdown_seconds);
    };
    const onQuestion = (d: QuestionEvt) => {
      setPhase("question");
      setQuestion(d);
      setMyResult(null);
      setAnsweredIdx(null);
      setFiftyRemoved([]);
      setDoubled(false);
    };
    const onAnswerResult = (d: AnswerResultEvt) => {
      setMyResult(d);
      setMyScore(d.your_score);
    };
    const onRoundEnd = (_d: RoundEndEvt) => {
      setPhase("feedback");
    };
    const onGameOver = (d: GameOverEvt) => {
      setPhase("ended");
      setFinalLeaderboard(d.leaderboard);
      setWinner(d.winner);
    };
    const onChat = (d: ChatMsgEvt) => {
      setChat((c) => [...c, d].slice(-100));
    };
    const onErr = (d: ErrorEvt) => setErrorMsg(d.message);

    s.on("lobby_update", onLobby);
    s.on("game_starting", onStarting);
    s.on("question", onQuestion);
    s.on("answer_result", onAnswerResult);
    s.on("round_end", onRoundEnd);
    s.on("game_over", onGameOver);
    s.on("chat_msg", onChat);
    s.on("error", onErr);

    return () => {
      s.off("lobby_update", onLobby);
      s.off("game_starting", onStarting);
      s.off("question", onQuestion);
      s.off("answer_result", onAnswerResult);
      s.off("round_end", onRoundEnd);
      s.off("game_over", onGameOver);
      s.off("chat_msg", onChat);
      s.off("error", onErr);
    };
  }, []);

  const createRoom = useCallback(async (m: Mode, name: string): Promise<AckCreateRoom> => {
    const s = sockRef.current!;
    const ack: AckCreateRoom = await s.emitWithAck("create_room", { mode: m, name });
    if (ack.ok) {
      setRoomCode(ack.room_code);
      setMode(m);
      setSelfId(ack.player_id);
      setIsHost(ack.is_host);
      setPlayers(ack.players);
      setPhase(m === "cpu" ? "countdown" : "lobby");
    } else {
      setErrorMsg(ack.error);
    }
    return ack;
  }, []);

  const joinRoom = useCallback(async (code: string, name: string): Promise<AckJoinRoom> => {
    const s = sockRef.current!;
    const ack: AckJoinRoom = await s.emitWithAck("join_room", { room_code: code, name });
    if (ack.ok) {
      setRoomCode(ack.room_code);
      setMode("friends");
      setSelfId(ack.player_id);
      setIsHost(ack.is_host);
      setPlayers(ack.players);
      setPhase("lobby");
    } else {
      setErrorMsg(ack.error);
    }
    return ack;
  }, []);

  const startGame = useCallback(async () => {
    const s = sockRef.current!;
    const ack = await s.emitWithAck("start_game", {});
    if (!ack?.ok) setErrorMsg(ack?.error || "Failed to start");
  }, []);

  const submitAnswer = useCallback(
    async (optionIdx: number) => {
      if (!question || answeredIdx !== null) return;
      setAnsweredIdx(optionIdx);
      const s = sockRef.current!;
      const ack = await s.emitWithAck("submit_answer", {
        question_idx: question.idx,
        option_idx: optionIdx,
      });
      if (!ack?.ok) {
        setErrorMsg(ack?.error || "Answer rejected");
        setAnsweredIdx(null);
      }
    },
    [question, answeredIdx],
  );

  const useHelp = useCallback(
    async (type: "fifty" | "friend" | "double"): Promise<HelpResult | null> => {
      const s = sockRef.current!;
      const ack: HelpResult = await s.emitWithAck("use_help", { type });
      if (!ack?.ok) {
        setErrorMsg(ack?.error || "Help failed");
        return null;
      }
      if (ack.type === "fifty") {
        setFiftyRemoved(ack.removed_indices);
        setHelpsUsed((h) => ({ ...h, fifty: true }));
      } else if (ack.type === "double") {
        setDoubled(true);
        setHelpsUsed((h) => ({ ...h, double: true }));
      } else if (ack.type === "friend") {
        setFriendAdvice(ack.advice);
        setHelpsUsed((h) => ({ ...h, friend: true }));
      }
      return ack;
    },
    [],
  );

  const sendChat = useCallback((text: string) => {
    if (!text.trim()) return;
    sockRef.current!.emit("chat", { text: text.slice(0, 200) });
  }, []);

  const clearFriendAdvice = useCallback(() => setFriendAdvice(null), []);

  return {
    socket,
    phase,
    roomCode,
    mode,
    selfId,
    isHost,
    players,
    hostId,
    question,
    myResult,
    myScore,
    finalLeaderboard,
    winner,
    countdown,
    chat,
    answeredIdx,
    fiftyRemoved,
    doubled,
    helpsUsed,
    friendAdvice,
    errorMsg,
    createRoom,
    joinRoom,
    startGame,
    submitAnswer,
    useHelp,
    sendChat,
    clearFriendAdvice,
  };
}
