"""
Brian AI Assistant — Wake Word Listener
Uses openWakeWord to detect "Hey Brian" (closest pre-trained model: 'hey jarvis' or 'alexa')
then fires a callback. Runs on its own thread, uses almost zero CPU.
"""

import numpy as np
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio
import logging
import threading
from typing import Callable, Optional
from openwakeword.model import Model

logger = logging.getLogger(__name__)

FORMAT     = pyaudio.paInt16
CHANNELS   = 1
RATE       = 16000
CHUNK_SIZE = 1280   # ~80ms of audio at 16kHz

# openWakeWord pre-trained models — we use 'hey_jarvis' as closest to 'hey brian'
# User can swap this for a custom trained model later
import os
WAKE_THRESHOLD  = float(os.getenv("WAKE_THRESHOLD", "0.4"))  # confidence score to trigger (0.0 – 1.0)

# Pre-trained model keywords shipped with openWakeWord
# Available: alexa, hey_mycroft, hey_jarvis, timer, weather, etc.
PREFERRED_MODELS = ["hey_brian"]    # Pre-trained hey_brian ONNX model (openwakeword)


class WakeWordListener:
    """
    Continuously monitors microphone audio.
    When the wake word is detected above the threshold, fires on_detected().
    """

    def __init__(
        self,
        on_detected: Callable[[], None],
        threshold: float = WAKE_THRESHOLD,
        cooldown_seconds: float = 2.0,
    ):
        self.on_detected     = on_detected
        self.threshold       = threshold
        self.cooldown        = cooldown_seconds
        self._running        = False
        self._paused         = False   # True while audio_pipeline is recording
        self._thread: Optional[threading.Thread] = None
        self._cooldown_active = False
        self._audio          = None
        self._stream         = None
        self._model: Optional[Model] = None

    def _load_model(self):
        """Load the openWakeWord model (ONNX on Windows)."""
        logger.info("Loading openWakeWord model...")
        try:
            self._model = Model(
                wakeword_models=PREFERRED_MODELS,
                inference_framework="onnx",
            )
            logger.info(f"Wake word model loaded. Listening for: {PREFERRED_MODELS}")
        except Exception as e:
            logger.warning(f"Could not load preferred models: {e}. Loading defaults.")
            self._model = Model(inference_framework="onnx")

    def _open_mic(self) -> bool:
        """Open PyAudio microphone stream. Returns True if successful, False if no device found."""
        try:
            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
            logger.info("Microphone stream opened for wake word detection.")
            return True
        except Exception as e:
            logger.error(f"Failed to open microphone: {e}. Checking again soon...")
            if self._audio:
                self._audio.terminate()
                self._audio = None
            return False

    def _listen_loop(self):
        """Main listen loop running on a background thread."""
        import time
        logger.info("Wake word listener started. Say 'Hey Brian' to activate.")

        while self._running:
            # Pause loop while audio_pipeline is using the mic
            if self._paused:
                time.sleep(0.1)
                continue

            if not self._stream:
                if not self._open_mic():
                    time.sleep(5)
                    continue

            try:
                raw = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_chunk = np.frombuffer(raw, dtype=np.int16)

                predictions = self._model.predict(audio_chunk)

                for model_name, score in predictions.items():
                    if score >= self.threshold and not self._cooldown_active:
                        logger.info(f"Wake word detected! Model={model_name}, score={score:.3f}")
                        self._trigger_cooldown()
                        threading.Thread(target=self.on_detected, daemon=True).start()
                        break

            except OSError as e:
                logger.warning(f"Audio read error (reconnecting): {e}")
                if self._stream:
                    try:
                        self._stream.close()
                    except Exception:
                        pass
                self._stream = None
                time.sleep(2)
            except Exception as e:
                logger.error(f"Wake word loop error: {e}")
                time.sleep(5)

    def _trigger_cooldown(self):
        """Prevent double-triggers for cooldown_seconds."""
        import time
        self._cooldown_active = True
        def reset():
            time.sleep(self.cooldown)
            self._cooldown_active = False
        threading.Thread(target=reset, daemon=True).start()

    def pause(self):
        """Pause wake word listening so audio_pipeline can use the mic."""
        self._paused = True
        if self._stream:
            try:
                self._stream.stop_stream()
            except Exception:
                pass
        logger.debug("WakeWordListener paused.")

    def resume(self):
        """Resume wake word listening after audio_pipeline is done."""
        if self._stream:
            try:
                self._stream.start_stream()
            except Exception:
                # Stream was closed, will reopen on next loop iteration
                self._stream = None
        self._paused = False
        logger.debug("WakeWordListener resumed.")

    def start(self):
        """Start the wake word listener thread."""
        if self._running:
            return
        self._load_model()
        self._open_mic()
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordListener")
        self._thread.start()
        logger.info("WakeWordListener thread started.")

    def stop(self):
        """Stop the listener cleanly."""
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._audio:
            self._audio.terminate()
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("WakeWordListener stopped.")
