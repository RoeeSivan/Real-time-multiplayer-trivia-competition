-- Persisted game history. The `questions` table already exists in trivia.db
-- and is treated as read-only by the server.

CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code   TEXT    NOT NULL,
    mode        TEXT    NOT NULL,        -- 'friends' | 'cpu'
    started_at  TEXT    NOT NULL,        -- ISO8601 UTC
    ended_at    TEXT    NOT NULL,
    winner_name TEXT
);

CREATE TABLE IF NOT EXISTS game_players (
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    is_bot      INTEGER NOT NULL DEFAULT 0,
    final_score INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_game_players_game_id ON game_players(game_id);
