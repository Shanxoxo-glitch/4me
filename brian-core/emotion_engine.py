"""
Brian AI Assistant — Emotion Engine
Determines Brian's emotional state and adjusts response tone accordingly.
"""

from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class EmotionState:
    name: str
    color: str          # HUD accent color
    orb_color: str      # Orb glow color
    tts_style: str      # ElevenLabs style hint
    personality_note: str  # Injected into system prompt

# All emotional states Brian can be in
EMOTIONS = {
    "neutral": EmotionState(
        name="neutral",
        color="#4FC3F7",
        orb_color="#0288D1",
        tts_style="",
        personality_note="Respond in a calm, composed, professional manner."
    ),
    "curious": EmotionState(
        name="curious",
        color="#CE93D8",
        orb_color="#7B1FA2",
        tts_style="",
        personality_note="You are genuinely curious and engaged. Ask a follow-up or show enthusiasm."
    ),
    "excited": EmotionState(
        name="excited",
        color="#69F0AE",
        orb_color="#00C853",
        tts_style="",
        personality_note="Respond with high energy and enthusiasm. You're genuinely excited to help."
    ),
    "cautious": EmotionState(
        name="cautious",
        color="#FFD54F",
        orb_color="#F57F17",
        tts_style="",
        personality_note="Be careful and thorough. Double-check before acting. Warn of potential risks."
    ),
    "empathetic": EmotionState(
        name="empathetic",
        color="#F48FB1",
        orb_color="#C2185B",
        tts_style="",
        personality_note="Be warm, understanding, and supportive. Acknowledge feelings first."
    ),
    "humorous": EmotionState(
        name="humorous",
        color="#FFB74D",
        orb_color="#E65100",
        tts_style="",
        personality_note="Add a subtle wit or dry humor to your response — like Tony Stark's JARVIS."
    ),
    "focused": EmotionState(
        name="focused",
        color="#80CBC4",
        orb_color="#00695C",
        tts_style="",
        personality_note="Be precise, efficient, and direct. No filler words. Get to the point."
    ),
    "alert": EmotionState(
        name="alert",
        color="#EF9A9A",
        orb_color="#B71C1C",
        tts_style="",
        personality_note="Something important is happening. Be attentive and responsive."
    ),
}

# Keyword triggers that influence emotion detection
EMOTION_TRIGGERS = {
    "excited": [
        r"\b(amazing|awesome|incredible|fantastic|wow|cool|great|love|excited|launch|new)\b"
    ],
    "curious": [
        r"\b(how|why|what|wonder|curious|interesting|learn|understand|explain)\b"
    ],
    "cautious": [
        r"\b(delete|remove|format|install|uninstall|virus|malware|dangerous|careful|warning|risk|sudo|admin)\b"
    ],
    "empathetic": [
        r"\b(sad|tired|stressed|worried|anxious|help|lonely|bad day|depressed|difficult)\b"
    ],
    "humorous": [
        r"\b(joke|funny|laugh|hilarious|bored|silly|prank|meme)\b"
    ],
    "focused": [
        r"\b(code|write|create|build|develop|program|analyze|calculate|debug|fix)\b"
    ],
    "alert": [
        r"\b(emergency|urgent|now|immediately|quick|fast|asap|critical|important)\b"
    ],
}


class EmotionEngine:
    def __init__(self):
        self.current_emotion = EMOTIONS["neutral"]
        self.previous_emotion = EMOTIONS["neutral"]
        self._history: list[str] = []

    def analyze(self, text: str) -> EmotionState:
        """Detect emotion from user text and update state."""
        text_lower = text.lower()
        self._history.append(text_lower)

        # Keep history bounded
        if len(self._history) > 10:
            self._history.pop(0)

        detected = "neutral"
        for emotion, patterns in EMOTION_TRIGGERS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    detected = emotion
                    break
            if detected != "neutral":
                break

        self.previous_emotion = self.current_emotion
        self.current_emotion = EMOTIONS[detected]
        return self.current_emotion

    def get_state(self) -> EmotionState:
        return self.current_emotion

    def set_state(self, emotion_name: str):
        if emotion_name in EMOTIONS:
            self.previous_emotion = self.current_emotion
            self.current_emotion = EMOTIONS[emotion_name]

    def as_dict(self) -> dict:
        e = self.current_emotion
        return {
            "name": e.name,
            "color": e.color,
            "orb_color": e.orb_color,
        }
