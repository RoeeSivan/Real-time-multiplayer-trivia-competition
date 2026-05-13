"""Call-a-Friend help — PydanticAI agent calling OpenAI.

Falls back to a canned witty response if the API key is missing or the
call errors out, so a missing/over-quota key never crashes a game.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random

from pydantic_ai import Agent

from backend import config

log = logging.getLogger("trivia.llm")

_FALLBACK_LINES = (
    "Your friend Bob shrugs: 'No idea, mate, but trust your gut.'",
    "Aunt Linda says she'd guess option 2, but she always guesses 2.",
    "Cousin Dave whispers: 'I think it's the longest one... or maybe the shortest?'",
    "Your know-it-all friend hesitates: 'Hmm... toss-up between A and C.'",
)

SYSTEM_PROMPT = (
    "You are a witty phone-a-friend helper in a trivia game. The user will give "
    "you a question, 4 options, and the correct answer. Your job: write a SHORT "
    "(1-2 sentences, under 200 chars) playful hint that leads the player toward "
    "the correct option WITHOUT naming it or quoting it verbatim. Use indirect "
    "clues — historical context, category, a memorable fact, a process-of-"
    "elimination nudge, or a playful aside. Stay in character as a friend on "
    "the phone. Never reveal you are an AI. Never explicitly say 'the answer "
    "is X'."
)


def _build_agent() -> Agent | None:
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set — call-a-friend will use fallbacks")
        return None
    model = os.getenv("OPENAI_MODEL", config.LLM_DEFAULT_MODEL)
    try:
        return Agent(f"openai:{model}", system_prompt=SYSTEM_PROMPT)
    except Exception as e:  # pragma: no cover
        log.warning("Failed to init PydanticAI agent: %s", e)
        return None


_agent: Agent | None = None


def _get_agent() -> Agent | None:
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def call_a_friend(
    *,
    question: str,
    options: list[str],
    correct_option: str,
) -> str:
    """Return a short witty hint string. Never raises."""
    agent = _get_agent()
    if agent is None:
        return random.choice(_FALLBACK_LINES)

    prompt = (
        f"Question: {question}\n"
        f"Options:\n"
        + "\n".join(f"  {i + 1}. {opt}" for i, opt in enumerate(options))
        + f"\n\nCorrect answer: {correct_option}\n\n"
        "Give your hint now — lead them toward the correct option without "
        "naming it."
    )
    try:
        result = await asyncio.wait_for(agent.run(prompt), timeout=config.LLM_TIMEOUT_SECONDS)
        text = (result.output or "").strip()
        return text or random.choice(_FALLBACK_LINES)
    except Exception as e:
        log.warning("call_a_friend failed: %s", e)
        return random.choice(_FALLBACK_LINES)
