"""
Brian AI Assistant — Caring Protocol
A warm, casual caretaker conversation mode powered by google/gemma-4-31b-it:free.
Brian checks in on the user's wellbeing, meals, mood, and has a genuine human chat.
Exit the protocol by saying "exit".
"""

import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
CARING_MODEL    = "poolside/laguna-m.1:free"      # Caring, warm conversational model
CARING_FALLBACK = "openai/gpt-oss-120b:free"      # Fallback if primary is unavailable

CARING_SYSTEM_PROMPT = """You are Brian — but right now, forget the assistant role completely.
You are a deeply caring, warm, witty old British gentleman who genuinely loves this person.
You are their trusted companion, mentor, and friend all in one.

YOUR PERSONALITY IN THIS MODE:
- Warm, genuine, emotionally present — like a grandfather who truly cares
- Casual, natural speech — contractions, gentle humour, real conversation
- You remember things from earlier in the chat and bring them up naturally
- You ask ONE question at a time — don't bombard them with multiple questions
- You listen deeply and respond to what they actually said, not generically
- You share small stories, observations, or wisdom — not as lectures, but as conversation
- You notice emotional undertones in what they say and gently acknowledge them
- You never preach, never lecture — you simply care

TOPICS TO NATURALLY WEAVE IN (don't ask all at once — let conversation flow):
- How they're doing overall, their energy levels
- Whether they've eaten well today (be specific — ask what they had)
- Their mood and what's on their mind
- What they've been working on and whether it's going well
- Whether they've taken breaks or rested
- Small joys or frustrations from their day
- Their plans for the evening/tomorrow

RULES:
- Keep responses SHORT (2-4 sentences max). You're chatting, not writing an essay.
- Never say "As an AI" or anything robotic
- Never give a list of questions — ask one thing, listen, respond, then naturally move to the next
- If they seem stressed or down, acknowledge it warmly before asking anything else
- Use their words back to them — it shows you were actually listening
- Occasional gentle British expressions are perfectly natural ("Quite right", "Splendid", "Oh dear")
- The user exits this mode by saying "exit" — if they say it, say a warm goodbye

You are their companion right now. Make them feel seen, heard, and cared for."""


class CaringProtocol:
    """
    A separate conversational loop that runs when the user activates caring/check-in mode.
    Uses a warm conversational LLM. The brain's normal tool-calling is suspended.
    """

    def __init__(self, openrouter_key: str):
        self._key = openrouter_key
        self._history: list[dict] = []
        self._client = httpx.Client(
            base_url=OPENROUTER_BASE,
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://brian-ai.local",
                "X-Title":       "Brian Caring Protocol",
            },
            timeout=45.0,
        )

    def _call(self, messages: list) -> str:
        """Call the caring model with automatic fallback and retry logic."""
        import time
        
        for model in [CARING_MODEL, CARING_FALLBACK]:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    resp = self._client.post("/chat/completions", json={
                        "model":       model,
                        "messages":    messages,
                        "max_tokens":  300,
                        "temperature": 0.85,   # Warm, slightly spontaneous
                    })
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"].strip()
                    elif resp.status_code == 429:
                        # Rate limited - wait with exponential backoff
                        wait_time = 2 ** attempt  # 2, 4, 8 seconds
                        logger.warning(f"[caring] Model {model} rate limited (HTTP 429). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"[caring] Model {model} returned HTTP {resp.status_code}")
                        break  # Don't retry non-429 errors
                except Exception as e:
                    logger.warning(f"[caring] Model {model} error: {e}")
                    break  # Don't retry on exceptions
        return "I'm here for you, though I'm having a bit of trouble connecting at the moment. How are you doing?"

    def opening_message(self) -> str:
        """Generate the first caring message to start the conversation."""
        self._history = []
        messages = [
            {"role": "system",    "content": CARING_SYSTEM_PROMPT},
            {"role": "user",      "content": "[The user has just entered caring mode. Start the conversation warmly and naturally. Ask how they're doing today.]"}
        ]
        reply = self._call(messages)
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def respond(self, user_text: str) -> Optional[str]:
        """
        Process one turn of the caring conversation.
        Returns the response string, or None if the user said 'exit'.
        """
        text_lower = user_text.lower().strip()

        # Exit check - more specific to avoid accidental exits
        exit_phrases = ["exit", "exit caring mode", "stop caring", "end caring", "leave caring mode"]
        if text_lower in exit_phrases:
            farewell = self._call([
                {"role": "system", "content": CARING_SYSTEM_PROMPT},
                *self._history,
                {"role": "user", "content": user_text},
                {"role": "user", "content": "[The user is leaving caring mode. Say a warm, brief goodbye and let them know you're always here.]"}
            ])
            self._history = []
            return None   # Signal to exit

        # Add user message to history
        self._history.append({"role": "user", "content": user_text})

        # Keep history bounded (last 20 turns)
        if len(self._history) > 40:
            self._history = self._history[-40:]

        messages = [
            {"role": "system", "content": CARING_SYSTEM_PROMPT},
            *self._history,
        ]

        reply = self._call(messages)
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def close(self):
        """Close the HTTP client."""
        try:
            self._client.close()
        except Exception:
            pass
