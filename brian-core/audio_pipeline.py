"""
Brian AI Assistant — Audio Pipeline
Captures microphone audio after wake word trigger,
runs Whisper STT to transcribe speech, returns text.
"""

import numpy as np
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio
import whisper
import logging
import threading
import time
import io
import wave
import tempfile
import os
import httpx
from typing import Optional, Callable

logger = logging.getLogger(__name__)

FORMAT     = pyaudio.paInt16
CHANNELS   = 1
RATE       = 16000
CHUNK_SIZE = 1024

SILENCE_THRESHOLD   = 200    # RMS amplitude below this = silence
SILENCE_DURATION    = 2.2    # seconds of silence before stopping recording
MAX_RECORD_SECONDS  = 30     # max recording length
INITIAL_BUFFER_CHUNKS = 10  # chunks to always record before silence detection starts


class AudioPipeline:
    """
    Manages the full audio capture → STT pipeline.
    After wake word is detected:
      1. Plays a chime (auditory feedback)
      2. Records user speech until silence
      3. Transcribes with Whisper
      4. Returns transcribed text
    """

    def __init__(self, whisper_model_size: str = "base"):
        self._model_size = whisper_model_size
        self._whisper: Optional[whisper.Whisper] = None
        self._loading = False
        # Don't hold a persistent PyAudio — open/close per recording
        # to avoid conflict with the wake word listener's mic stream
        logger.info(f"AudioPipeline initialized (Whisper model: {whisper_model_size})")

    def _load_whisper(self):
        """Lazy-load Whisper model on first use."""
        if self._whisper is None and not self._loading:
            self._loading = True
            logger.info(f"Loading Whisper '{self._model_size}' model...")
            self._whisper = whisper.load_model(self._model_size)
            logger.info("Whisper model loaded.")
            self._loading = False

    def _rms(self, data: np.ndarray) -> float:
        """Compute RMS amplitude of audio chunk."""
        return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

    def play_chime(self, chime_type: str = "activate"):
        """Play a short audio chime as feedback (non-blocking)."""
        try:
            import math
            duration   = 0.18 if chime_type == "activate" else 0.12
            freq       = 880  if chime_type == "activate" else 660
            sample_rate = 44100
            samples    = np.linspace(0, duration, int(sample_rate * duration), False)
            wave_data  = (np.sin(2 * np.pi * freq * samples) * 32767 * 0.4).astype(np.int16)

            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)
            stream.write(wave_data.tobytes())
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            logger.warning(f"Could not play chime: {e}")

    def record_until_silence(self, on_start: Optional[Callable] = None) -> Optional[np.ndarray]:
        """
        Record audio from mic until silence is detected.
        Returns raw numpy int16 audio array at 16kHz, or None on error.
        Opens a fresh PyAudio instance each time to avoid conflicts.
        """
        audio = None
        stream = None
        try:
            time.sleep(0.3)   # brief pause so wake_word stream can release mic
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )

            if on_start:
                on_start()

            logger.info("Recording started — listening for speech...")
            frames = []
            silence_chunks = 0
            max_silence_chunks = int(SILENCE_DURATION * RATE / CHUNK_SIZE)
            max_chunks = int(MAX_RECORD_SECONDS * RATE / CHUNK_SIZE)
            recorded_something = False
            chunk_count = 0

            for _ in range(max_chunks):
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                chunk = np.frombuffer(raw, dtype=np.int16)
                frames.append(chunk)
                rms = self._rms(chunk)
                chunk_count += 1

                if rms > SILENCE_THRESHOLD:
                    silence_chunks = 0
                    recorded_something = True
                else:
                    # If they haven't spoken yet, check first-sound timeout (3.5 seconds)
                    if not recorded_something:
                        if chunk_count > int(3.5 * RATE / CHUNK_SIZE):
                            logger.info("No speech detected within 3.5s timeout. Stopping.")
                            break
                    else:
                        # If they spoke but are now silent
                        if chunk_count > INITIAL_BUFFER_CHUNKS:
                            silence_chunks += 1
                    
                    if silence_chunks >= max_silence_chunks:
                        logger.info("Silence detected — stopping recording.")
                        break

            stream.stop_stream()
            stream.close()
            audio.terminate()

            if not frames or not recorded_something:
                logger.info("No speech recorded (silence timeout).")
                return None

            audio_data = np.concatenate(frames)
            
            # Filter background noise/fans using peak RMS and mean RMS
            frame_rms_values = [self._rms(f) for f in frames]
            peak_rms = max(frame_rms_values) if frame_rms_values else 0
            mean_rms = self._rms(audio_data)
            
            logger.info(f"Recording complete: {len(audio_data)/RATE:.2f}s captured. Peak RMS: {peak_rms:.1f}, Mean RMS: {mean_rms:.1f}")
            
            if peak_rms < 550 or mean_rms < 220:
                logger.info("Rejected recording: audio energy matches background noise/fan pattern.")
                return None

            return audio_data

        except Exception as e:
            logger.error(f"record_until_silence error: {e}")
            if stream:
                try: stream.close()
                except Exception: pass
            if audio:
                try: audio.terminate()
                except Exception: pass
            return None

    def transcribe(self, audio: np.ndarray) -> str:
        """Run Whisper STT on captured audio. Returns transcription string."""
        tmp_path = None
        try:
            # Save to a temp WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp_path = tmp.name
                with wave.open(tmp_path, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # int16 = 2 bytes
                    wf.setframerate(RATE)
                    wf.writeframes(audio.tobytes())

            # Try Groq cloud transcription first (instant response, ~150ms)
            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            if groq_key:
                try:
                    logger.info("Transcribing using Groq Cloud Whisper API...")
                    t_start = time.time()
                    with open(tmp_path, "rb") as f:
                        resp = httpx.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers={"Authorization": f"Bearer {groq_key}"},
                            data={"model": "whisper-large-v3-turbo", "language": "en"},
                            files={"file": ("speech.wav", f, "audio/wav")},
                            timeout=10.0
                        )
                    if resp.status_code == 200:
                        text = resp.json().get("text", "").strip()
                        logger.info(f"Groq Cloud transcription complete in {time.time() - t_start:.2f}s: '{text}'")
                        return text
                    else:
                        logger.warning(f"Groq Cloud STT failed with code {resp.status_code}: {resp.text}. Falling back to local Whisper.")
                except Exception as ex:
                    logger.warning(f"Groq Cloud STT connection failed: {ex}. Falling back to local Whisper.")

            # Fallback to local Whisper
            logger.info("Running local Whisper model transcription...")
            self._load_whisper()
            result = self._whisper.transcribe(
                tmp_path,
                language="en",
                fp16=False,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                no_speech_threshold=0.5,
                condition_on_previous_text=True,
            )
            text = result.get("text", "").strip()

            # Filter Whisper hallucinations (repeated phrases from silence/noise)
            if text:
                words = text.split()
                if len(words) > 8:
                    # Check if more than 60% of the text is a repeated short phrase
                    unique_5grams = set(tuple(words[i:i+5]) for i in range(len(words)-4))
                    if len(unique_5grams) < 3:
                        logger.warning(f"Whisper hallucination detected, discarding: '{text[:80]}...'")
                        return ""

            logger.info(f"Local transcription: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


    def listen_and_transcribe(
        self,
        on_listening: Optional[Callable] = None,
        on_processing: Optional[Callable] = None,
        silent: bool = False,
    ) -> tuple[str, Optional[np.ndarray]]:
        """
        Full pipeline: play chime → record → transcribe → return (text, audio_np).
        Callbacks allow updating the HUD state.
        """
        if not silent:
            self.play_chime("activate")
        audio = self.record_until_silence(on_start=on_listening)

        if audio is None or len(audio) < RATE * 0.3:
            logger.info("No meaningful audio captured.")
            return "", None

        if not silent:
            self.play_chime("done")
        if on_processing:
            on_processing()

        text = self.transcribe(audio)
        return text, audio


