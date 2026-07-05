"""
Brian AI Assistant — Main Orchestrator
Ties together: wake word → audio capture → STT → brain → TTS → HUD updates.
Runs as a background process on Windows startup.
"""

import os
import sys
import asyncio
import logging
import threading
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment ─────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).parent.parent / "deployment.env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()   # fallback to .env in current dir

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "brian.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("Brian")

# ── Imports (after env loaded) ─────────────────────────────────────────────
from wake_word       import WakeWordListener
from audio_pipeline  import AudioPipeline
from brain           import BrianBrain
from tts             import BrianTTS
from emotion_engine  import EmotionEngine
from hud_server      import HudServer
from voice_id        import VoiceIdentifier
from caring_protocol import CaringProtocol

# ─────────────────────────────────────────────────────────────────────────────
# BRAIN STATE
# ─────────────────────────────────────────────────────────────────────────────
class BrianState:
    IDLE       = "idle"       # Waiting for wake word
    LISTENING  = "listening"  # Recording user speech
    PROCESSING = "processing" # Running STT + LLM
    SPEAKING   = "speaking"   # Playing TTS response
    ERROR      = "error"

# ─────────────────────────────────────────────────────────────────────────────
# BRIAN CORE
# ─────────────────────────────────────────────────────────────────────────────
class Brian:
    def __init__(self):
        logger.info("Initializing BRIAN...")

        self.state            = BrianState.IDLE
        self.emotion          = EmotionEngine()
        self.tts              = BrianTTS()
        self.audio            = AudioPipeline(whisper_model_size=os.getenv("WHISPER_MODEL", "base"))
        self.hud              = HudServer(brian=self)
        self.wake_word        = WakeWordListener(on_detected=self._on_wake_word)
        self.voice_id         = VoiceIdentifier()
        self._busy            = False   # Prevent re-entrant wake word handling
        self._session_active  = False   # Tracks continuous session mode
        self._last_wake_time  = 0.0     # Debounce time tracker
        self._last_session_end_time = 0.0  # Cooldown tracker after session ends
        self._caring_mode     = False   # Tracks if caring protocol is active
        self._interrupt_tts   = False   # Flag to interrupt TTS when user speaks

        openrouter_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._caring   = CaringProtocol(openrouter_key)
        self.brain     = BrianBrain(self.emotion)

    # ── State management ─────────────────────────────────────────────────────
    def _set_state(self, state: str):
        self.state = state
        emotion    = self.emotion.as_dict()
        self.hud.broadcast({
            "type":    "state",
            "state":   state,
            "emotion": emotion,
        })
        logger.info(f"Brian state -> {state}")

    def _on_action(self, action_desc: str):
        """Called by brain when a tool executes — updates HUD action log."""
        self.hud.broadcast({
            "type":   "action",
            "action": action_desc,
        })
        logger.info(f"Action: {action_desc}")

    # ── Wake word callback ────────────────────────────────────────────────────
    def _on_wake_word(self):
        """Called from WakeWordListener thread when 'Hey Brian' is detected."""
        now = time.time()
        # Cooldown guard: ignore wake word if the last session ended less than 5 seconds ago
        # (This prevents rapid loops due to echo or background fan noise right after Brian stops speaking)
        if now - self._last_session_end_time < 5.0:
            logger.info("Wake word ignored due to session end cooldown.")
            return

        # Debounce: ignore multiple trigger notifications within 2.5 seconds
        if now - self._last_wake_time < 2.5:
            logger.debug("Wake word triggered but debounced.")
            return
        self._last_wake_time = now

        # If Brian is speaking, interrupt and start listening
        if self.state == BrianState.SPEAKING:
            logger.info("Wake word detected during speech - interrupting")
            self._interrupt_tts = True
            self._busy = True
            self._session_active = True
            self.wake_word.pause()
            # Start a new conversation session immediately
            threading.Thread(target=self._run_interaction_loop, daemon=True).start()
            return

        if self._busy or self._session_active:
            logger.info("Wake word received but Brian is busy/in active session — ignoring.")
            return

        self._busy = True
        # Run interaction loop in a background thread so we don't block the wake word thread
        threading.Thread(target=self._run_interaction_loop, daemon=True).start()

    # ── Continuous Interaction Loop ──────────────────────────────────────────
    def _run_interaction_loop(self):
        """Continuous conversation loop (24/7 session mode)."""
        logger.info("Entering conversation session mode.")
        self._session_active = True

        is_first_turn   = True
        silence_strikes = 0
        max_silence_strikes = 3   # Exit session after 3 consecutive silent captures

        # Pause wake word mic while conversation session is active
        self.wake_word.pause()

        try:
            # ── On first activation: if no voice profile, run enrollment ─────
            if not self.voice_id.has_profile():
                self._run_enrollment()
                # After enrollment, continue normally

            while self._session_active:
                # 1. Listen (silent after first turn for natural conversation flow)
                self._set_state(BrianState.LISTENING)
                self.hud.broadcast({"type": "transcript", "text": "", "role": "user"})

                user_text, audio_np = self.audio.listen_and_transcribe(
                    on_listening  = lambda: self._set_state(BrianState.LISTENING),
                    on_processing = lambda: self._set_state(BrianState.PROCESSING),
                    silent        = not is_first_turn
                )

                # 2. Handle silence / no speech
                if not user_text:
                    silence_strikes += 1
                    logger.info(f"Silence detected. Strike {silence_strikes}/{max_silence_strikes}")
                    if silence_strikes >= max_silence_strikes:
                        logger.info("Silence limit reached. Ending session silently.")
                        break
                    time.sleep(0.5)
                    continue

                silence_strikes = 0
                is_first_turn   = False

                # 3. Voice fingerprint check — reject non-owner voices silently
                if audio_np is not None and self.voice_id.has_profile():
                    # Raised threshold to 0.84 to strictly reject background fans/noises
                    if not self.voice_id.is_owner(audio_np, threshold=0.84):
                        logger.warning("Speaker verification failed — not the owner's voice. Ignoring command silently.")
                        continue   # Say nothing, keep listening

                # 4. Show transcript in HUD
                self.hud.broadcast({"type": "transcript", "text": user_text, "role": "user"})
                logger.info(f"User said: {user_text}")

                # 5. Handle special commands (goodbye, re-register, clear memory…)
                special_result = self._handle_special_commands(user_text, audio_np)
                if special_result == "exit":
                    break
                elif special_result == "continue":
                    continue

                # 6. Detect agent mode (complex multi-step tasks)
                # Agent mode triggers for tasks with multiple actions (contains "and", "then", multiple verbs)
                user_lower = user_text.lower()
                agent_keywords = [" and ", " then ", "after that", "next", "followed by", "also"]
                is_agent_task = any(kw in user_lower for kw in agent_keywords) and len(user_lower.split()) > 8

                if is_agent_task:
                    logger.info(f"Agent mode activated for task: {user_text}")
                    # Display agent mode status in HUD
                    self.hud.broadcast({
                        "type": "agent_mode",
                        "active": True,
                        "task": user_text
                    })

                # Check rogue mode status
                if self.brain.is_rogue_mode():
                    logger.info("Rogue mode is currently active")

                # 7. Think (LLM + tools)
                self._set_state(BrianState.PROCESSING)
                response = self.brain.think(user_text, on_action=self._on_action, agent_mode=is_agent_task)

                # 6a. Caring protocol activation signal
                if "CARING_PROTOCOL_ACTIVATE" in response:
                    self._run_caring_loop()
                    continue

                # 7. Show Brian's response in HUD
                emotion = self.emotion.get_state()
                self.hud.broadcast({
                    "type":    "transcript",
                    "text":    response,
                    "role":    "brian",
                    "emotion": emotion.name,
                })

                # 8. Speak response (non-blocking to allow interruption)
                self._set_state(BrianState.SPEAKING)
                self.tts.speak(response, emotion=emotion.name, blocking=False)
                
                # Monitor for voice interruption while speaking
                while self.tts.is_speaking:
                    time.sleep(0.1)
                    # If wake word is detected during speech, interrupt and start listening
                    if self._interrupt_tts:
                        logger.info("[Brian] User interrupted speech")
                        self.tts.stop()
                        self._interrupt_tts = False
                        # Immediately start listening for new command
                        break

                time.sleep(0.2)  # Brief yield

        except Exception as e:
            logger.error(f"Error in conversation session loop: {e}")
        finally:
            self._session_active = False
            self._busy = False
            self._last_session_end_time = time.time()  # Start cooldown timer
            self.wake_word.resume()
            self._set_state(BrianState.IDLE)
            logger.info("Conversation session ended. Returned to wake word mode.")

    def _run_enrollment(self):
        """Guided voice enrollment: play a spoken prompt and record owner's voice sample."""
        logger.info("Starting guided voice enrollment.")
        self.tts.speak(
            "Voice profile not registered, sir. Please say any sentence clearly to register your voice now.",
            emotion="neutral", blocking=True
        )
        # Record a clean enrollment sample (use chime so user knows when to speak)
        user_text, audio_np = self.audio.listen_and_transcribe(
            on_listening  = lambda: self._set_state(BrianState.LISTENING),
            on_processing = lambda: self._set_state(BrianState.PROCESSING),
            silent        = False  # Play chime so user knows to start speaking
        )
        if audio_np is not None and len(audio_np) > 0:
            success = self.voice_id.enroll(audio_np)
            if success:
                logger.info("Voice enrollment complete.")
                self.tts.speak(
                    "Voice registered successfully, sir. I will now only respond to your voice.",
                    emotion="neutral", blocking=True
                )
            else:
                logger.error("Voice enrollment failed.")
                self.tts.speak(
                    "Voice registration failed, sir. I will skip voice verification for now.",
                    emotion="neutral", blocking=True
                )
        else:
            logger.warning("No audio captured during enrollment — skipping voice registration.")
            self.tts.speak(
                "I didn't hear anything, sir. Voice registration skipped. You can say 're-register my voice' anytime.",
                emotion="neutral", blocking=True
            )


    def _run_caring_loop(self):
        """Enter the warm caring caretaker conversation loop."""
        logger.info("Entering caring protocol mode.")
        self._caring_mode = True

        # Opening message
        opening = self._caring.opening_message()
        self.tts.speak(opening, emotion="empathetic", blocking=True)

        while self._session_active and self._caring_mode:
            self._set_state(BrianState.LISTENING)
            user_text, audio_np = self.audio.listen_and_transcribe(
                on_listening  = lambda: self._set_state(BrianState.LISTENING),
                on_processing = lambda: self._set_state(BrianState.PROCESSING),
                silent        = True
            )

            if not user_text:
                continue

            # Voice ID check
            if audio_np is not None and self.voice_id.has_profile():
                if not self.voice_id.is_owner(audio_np, threshold=0.84):
                    continue

            self.hud.broadcast({"type": "transcript", "text": user_text, "role": "user"})

            # Exit caring mode
            if user_text.lower().strip() in ["exit", "exit caring mode", "stop", "that's enough", "okay thanks"]:
                farewell = "Of course, sir. I'm always here when you need me. Take good care of yourself."
                self.tts.speak(farewell, emotion="empathetic", blocking=True)
                self._caring_mode = False
                break

            self._set_state(BrianState.PROCESSING)
            response = self._caring.respond(user_text)

            if response is None:
                # Model signalled exit
                farewell = "Of course, sir. I'm always here when you need me."
                self.tts.speak(farewell, emotion="empathetic", blocking=True)
                self._caring_mode = False
                break

            self.hud.broadcast({"type": "transcript", "text": response, "role": "brian", "emotion": "empathetic"})
            self._set_state(BrianState.SPEAKING)
            self.tts.speak(response, emotion="empathetic", blocking=True)

        self._caring_mode = False
        logger.info("Caring protocol exited. Resuming normal mode.")

    def _handle_special_commands(self, text: str, audio_np=None) -> str:
        """Handle direct voice commands.
        Returns: 'exit' to end session, 'continue' to skip this turn, '' to proceed normally.
        """
        text_lower = text.lower().strip()

        # Voice re-registration
        if any(cmd in text_lower for cmd in ["re-register my voice", "register my voice", "reset voice", "reset voice profile", "re-enroll"]):
            self.voice_id.reset()
            self.tts.speak("Voice profile reset, sir. Starting enrollment now.", emotion="neutral", blocking=True)
            self._run_enrollment()
            return "continue"

        # Memory controls
        if any(cmd in text_lower for cmd in ["clear history", "forget everything", "reset memory"]):
            self.brain.clear_history()
            self.tts.speak("Memory cleared, sir. Starting fresh.", emotion="neutral", blocking=True)
            return "continue"

        # Caring protocol activation (voice-level shortcut, bypasses LLM tool call)
        # Only activate if explicitly requested with sufficient length (not wake word)
        caring_triggers = ["caring mode", "caring protocol", "check in on me", "empty protocol", "how am i doing protocol", "let's have a chat", "just talk to me"]
        if any(cmd in text_lower for cmd in caring_triggers) and len(text_lower.split()) > 3:
            self._run_caring_loop()
            return "continue"

        # IDE open (voice-level shortcut)
        ide_triggers = ["open brian ide", "execute coding protocol", "open the editor", "launch coding mode", "open coding protocol"]
        if any(cmd in text_lower for cmd in ide_triggers):
            import webbrowser
            import subprocess
            try:
                webbrowser.open("http://localhost:9003")
            except Exception:
                pass
            subprocess.Popen("cmd.exe /c start http://localhost:9003", shell=True)
            self.tts.speak("Brian IDE is now open in your browser, sir.", emotion="focused", blocking=True)
            return "continue"

        # Exit/farewell controls
        if any(cmd in text_lower for cmd in ["go to sleep", "stop listening", "goodbye brian", "goodbye", "that is all", "that's all", "go idle", "deactivate", "sleep", "idle"]):
            self.tts.speak("Going idle, sir. Let me know when you need me.", emotion="neutral", blocking=True)
            logger.info("User requested sleep/farewell/idle — ending conversation session.")
            return "exit"

        return ""  # proceed normally

    # ── Startup greeting ──────────────────────────────────────────────────────
    def _startup_greeting(self):
        import datetime
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning, sir."
        elif hour < 17:
            greeting = "Good afternoon, sir."
        else:
            greeting = "Good evening, sir."

        time.sleep(2.0)   # Let audio system stabilize
        self.tts.speak(
            f"{greeting} BRIAN is online. All systems operational. "
            "Say 'Hey Brian' whenever you need me.",
            emotion="neutral"
        )

    # ── Run ───────────────────────────────────────────────────────────────────
    def run(self):
        """Start Brian — launches all subsystems."""
        logger.info("Starting BRIAN subsystems...")

        # Start HUD server in background thread
        hud_thread = threading.Thread(target=self.hud.run, daemon=True, name="HUD")
        hud_thread.start()
        logger.info("HUD server starting on ws://localhost:9000")

        # Start Editor server in background thread
        try:
            import editor_server
            editor_thread = threading.Thread(
                target=lambda: asyncio.run(editor_server.main()),
                daemon=True,
                name="Editor-Backend"
            )
            editor_thread.start()
            logger.info("Editor server starting on ws://localhost:9002 and http://localhost:9003")
        except Exception as e:
            logger.error(f"Failed to start editor server: {e}")

        # Start wake word listener
        self.wake_word.start()
        self._set_state(BrianState.IDLE)

        # Startup greeting in background
        threading.Thread(target=self._startup_greeting, daemon=True).start()

        logger.info("BRIAN is online. Listening for wake word...")

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down BRIAN...")
            self.wake_word.stop()
            logger.info("BRIAN offline.")


# ─────────────────────────────────────────────────────────────────────────────
# TRAY ICON
# ─────────────────────────────────────────────────────────────────────────────
def run_tray_icon(brian: Brian):
    """System tray icon with right-click menu."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Create a simple orb icon
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, size-4, size-4], fill="#0288D1", outline="#4FC3F7", width=3)
        d.ellipse([20, 20, size-20, size-20], fill="#4FC3F7")

        def on_quit(icon, item):
            icon.stop()
            os._exit(0)

        def on_open_hud(icon, item):
            import webbrowser
            webbrowser.open("http://localhost:9001")

        menu = pystray.Menu(
            pystray.MenuItem("Open BRIAN HUD", on_open_hud),
            pystray.MenuItem("Quit BRIAN", on_quit),
        )
        icon = pystray.Icon("brian", img, "BRIAN AI Assistant", menu)
        icon.run()
    except Exception as e:
        logger.warning(f"Tray icon failed (non-critical): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    brian = Brian()

    # Start tray icon in background
    tray_thread = threading.Thread(target=run_tray_icon, args=(brian,), daemon=True, name="Tray")
    tray_thread.start()

    brian.run()
