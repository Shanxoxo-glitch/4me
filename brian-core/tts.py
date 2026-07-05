"""
Brian AI Assistant — TTS (Text-to-Speech)
Multi-key ElevenLabs fallback architecture with deep British old man voice.
Voice settings tuned for a hoarse, warm, caring, emotionally expressive gentleman.
Falls back to Windows SAPI if all ElevenLabs keys are exhausted.
"""

import os
import logging
import threading
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio
from typing import Optional
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

logger = logging.getLogger(__name__)

TTS_MODEL = "eleven_turbo_v2"   # Fastest model — lowest latency

# ─────────────────────────────────────────────────────────────────────────────
# ElevenLabs fallback chain — tries each key/voice pair in order.
# If a key's quota is exhausted or invalid, the next entry is tried automatically.
# Voice ID rpHxE9XX4Gaivr7xDBjD = deep, hoarse, British old man (warm & caring)
# ─────────────────────────────────────────────────────────────────────────────
ELEVENLABS_CREDENTIALS = [
    # (api_key,                                              voice_id)
    ("sk_e5e3c446b518920a2c9fad179606250c36a1057f8776e3ee", "rpHxE9XX4Gaivr7xDBjD"),  # 1st
    ("sk_cfde8abc8b00038b5f7eae3ac0d1883ed46f7c9dbe15e647", "c6Ra2LmSJNAPFlNiDaAE"),  # 2nd
    ("sk_26ac1055d44d93728e508eb357c8a95156d0c03515d14320", "2dvfDOBVqI4ZEgadEUBV"),  # 3rd
    ("sk_d534b15d9e22d54ea6eef1eb8043a9bd949b1a3379ce2e29", "ibSqUWoU5zIJC3ijklvo"),  # 4th
    ("sk_084a0e13e8db9e770fb9a4aebd16a3d5cf8ad44566b487bc", "UIDLSt7f2b1eo8Xvv74q"),  # 5th
    ("sk_d7999149f91d86b7d58e43c8a4d90b23497ba16f3c57ed4c", "giKIowbpfO8vH9J5oPKQ"),  # 6th
    ("sk_2ad61a9caebed542f7faa4087d582722b9597f2c7a305a2d", "WYiLccAfqXjyYDvMfHAX"),  # 7th
    ("sk_fea19b326f0e8bfd53c9eee3df1a69e12557dde8a60c32a0", "DRLuRqRyy1c4HsxtNWa1"),  # 8th
]


# ─────────────────────────────────────────────────────────────────────────────
# Voice personality — tuned for a deep, hoarse, warm British old gentleman.
# High stability  → steady aged voice (no warbling)
# High similarity → preserves the hoarse, characterful quality of the voice
# Moderate style  → emotionally present without being theatrical
# ─────────────────────────────────────────────────────────────────────────────
BASE_VOICE_SETTINGS = dict(stability=0.72, similarity_boost=0.90, style=0.30)

# Per-emotion overrides layered on top of the base personality
EMOTION_OVERRIDES = {
    # Calm, measured. The old man at rest, composed.
    "neutral":    dict(stability=0.75, similarity_boost=0.90, style=0.25),
    # Warm delight — a gentle, genuine smile in the voice.
    "excited":    dict(stability=0.55, similarity_boost=0.88, style=0.55),
    # Thoughtful, slightly slower. Like a grandfather pondering.
    "curious":    dict(stability=0.70, similarity_boost=0.90, style=0.38),
    # Measured gravity. Serious but caring.
    "cautious":   dict(stability=0.82, similarity_boost=0.88, style=0.15),
    # Soft and warm. Genuine concern, like a caring butler.
    "empathetic": dict(stability=0.68, similarity_boost=0.93, style=0.42),
    # A dry, warm wit — the cheeky side of the old gentleman.
    "humorous":   dict(stability=0.50, similarity_boost=0.88, style=0.58),
    # Sharp and attentive. Alert, ready to act.
    "focused":    dict(stability=0.78, similarity_boost=0.90, style=0.20),
    # Urgent concern but not panicked — experienced in a crisis.
    "alert":      dict(stability=0.60, similarity_boost=0.88, style=0.48),
}


class BrianTTS:
    """
    Text-to-speech engine powered by ElevenLabs with automatic multi-key fallback.
    When a key's quota is exhausted, it silently moves to the next key in the chain.
    Falls back to Windows SAPI if all ElevenLabs keys fail.
    """

    def __init__(self):
        self._lock    = threading.Lock()
        self._speaking = False
        self._stop_requested = threading.Event()

        # Build the ordered list of (ElevenLabs client, voice_id) pairs
        self._credentials = []
        for api_key, voice_id in ELEVENLABS_CREDENTIALS:
            if api_key and api_key.strip():
                self._credentials.append((ElevenLabs(api_key=api_key.strip()), voice_id.strip()))

        # Also support legacy single-key from .env for easy override
        env_key      = os.getenv("ELEVENLABS_API_KEY", "").strip()
        env_voice_id = os.getenv("TTS_VOICE_ID", "").strip()
        if env_key and env_voice_id:
            # Prepend the env key as highest priority
            self._credentials.insert(0, (ElevenLabs(api_key=env_key), env_voice_id))

        # Active index — increments automatically on quota exhaustion
        self._active_index = 0

        if self._credentials:
            _, voice_id = ELEVENLABS_CREDENTIALS[0]
            logger.info(f"BrianTTS initialized with {len(self._credentials)} ElevenLabs credential(s). Primary voice_id={voice_id}")
        else:
            logger.warning("No ElevenLabs credentials — TTS will use Windows SAPI fallback only.")

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def _voice_settings_for_emotion(self, emotion: str) -> VoiceSettings:
        """
        Build voice settings for the deep, caring British old man persona.
        Emotional overlays are layered onto the base personality.
        """
        overrides = EMOTION_OVERRIDES.get(emotion, EMOTION_OVERRIDES["neutral"])
        return VoiceSettings(
            stability=overrides["stability"],
            similarity_boost=overrides["similarity_boost"],
            style=overrides["style"],
            use_speaker_boost=True,   # Enhances voice clarity and presence
        )

    def speak(self, text: str, emotion: str = "neutral", blocking: bool = True):
        """
        Convert text to speech and play it.
        emotion: neutral / excited / curious / cautious / empathetic / humorous / focused / alert
        """
        if not text.strip():
            return
        if blocking:
            self._speak_internal(text, emotion)
        else:
            threading.Thread(
                target=self._speak_internal,
                args=(text, emotion),
                daemon=True,
                name="BrianTTS"
            ).start()

    def _speak_internal(self, text: str, emotion: str):
        """Internal: generate + play TTS audio with multi-key fallback."""
        with self._lock:
            self._speaking = True
            try:
                spoken = self._speak_elevenlabs_with_fallback(text, emotion)
                if not spoken:
                    self._speak_fallback(text)
            except Exception as e:
                logger.error(f"TTS critical error: {e}")
                self._speak_fallback(text)
            finally:
                self._speaking = False

    def _speak_elevenlabs_with_fallback(self, text: str, emotion: str) -> bool:
        """
        Try each ElevenLabs credential in order starting from the active index.
        Returns True if speech succeeded, False if all keys are exhausted.
        """
        if not self._credentials:
            return False

        total = len(self._credentials)
        for attempt in range(total):
            idx = (self._active_index + attempt) % total
            client, voice_id = self._credentials[idx]
            try:
                logger.info(f"Speaking [{emotion}] via credential #{idx+1} voice={voice_id}: {text[:60]}...")
                voice_settings = self._voice_settings_for_emotion(emotion)

                audio_stream = client.text_to_speech.convert(
                    text=text,
                    voice_id=voice_id,
                    model_id=TTS_MODEL,
                    voice_settings=voice_settings,
                    output_format="pcm_16000",
                )
                audio_bytes = b"".join(audio_stream)
                self._play_pcm(audio_bytes)
                # If we had advanced the index, log the switch
                if idx != self._active_index:
                    logger.info(f"[TTS] Switched to credential #{idx+1} permanently.")
                    self._active_index = idx
                return True

            except Exception as e:
                err_str = str(e).lower()
                # Quota exhausted or invalid key → try the next credential
                if "quota" in err_str or "quota_exceeded" in err_str or "401" in err_str or "invalid" in err_str:
                    logger.warning(f"[TTS] Credential #{idx+1} exhausted/invalid — trying next. Error: {e}")
                    continue
                else:
                    # Other error (network, etc.) — still try next
                    logger.warning(f"[TTS] Credential #{idx+1} failed ({e}) — trying next.")
                    continue

        logger.error("[TTS] All ElevenLabs credentials exhausted. Falling back to Windows SAPI.")
        return False

    def _play_pcm(self, audio_bytes: bytes):
        """Play raw PCM 16-bit 16kHz mono audio via PyAudio with interrupt support."""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
        )
        chunk_size = 4096
        for i in range(0, len(audio_bytes), chunk_size):
            # Check if stop was requested
            if self._stop_requested.is_set():
                logger.info("[TTS] Playback interrupted by user")
                break
            stream.write(audio_bytes[i:i + chunk_size])
        stream.stop_stream()
        stream.close()
        p.terminate()

    def _speak_fallback(self, text: str):
        """Windows SAPI fallback — lowest latency offline voice."""
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = 0    # Slightly slow — dignified old man pace
            speaker.Volume = 100
            speaker.Speak(text)
        except Exception as e:
            logger.error(f"SAPI fallback TTS error: {e}")
            try:
                import subprocess
                safe_text = text.replace("'", "")
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.Rate = 0; $s.Speak('{safe_text}')"
                )
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            except Exception as e2:
                logger.error(f"PowerShell TTS ultimate fallback failed: {e2}")

    def stop(self):
        """Interrupt current speech (best-effort)."""
        self._speaking = False
        self._stop_requested.set()
        # Reset the event after a short delay so it can be used again
        threading.Timer(0.5, self._stop_requested.clear).start()
