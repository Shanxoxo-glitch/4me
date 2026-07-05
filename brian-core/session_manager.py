"""
Session Manager for Brian AI
Manages multiple concurrent conversation sessions with independent contexts.
Allows switching between sessions via wake word while maintaining single voice output.
"""

import threading
import time
import uuid
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """States a session can be in."""
    IDLE = "idle"           # Waiting for wake word
    LISTENING = "listening"  # Recording user input
    PROCESSING = "processing"  # Thinking/executing tools
    SPEAKING = "speaking"    # Playing TTS response
    PAUSED = "paused"       # Temporarily paused (background session)


@dataclass
class Session:
    """Represents a single conversation session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    state: SessionState = SessionState.IDLE
    history: List[dict] = field(default_factory=list)
    brain: Optional[object] = None  # BrianBrain instance
    last_active: float = field(default_factory=time.time)
    is_active: bool = False  # Whether this is the currently active session
    
    def update_last_active(self):
        """Update the last active timestamp."""
        self.last_active = time.time()


class TTSQueue:
    """
    Global TTS queue to prevent voice overlap between sessions.
    Only one session can speak at a time.
    """
    def __init__(self):
        self._queue: List[tuple] = []  # (session_id, text, emotion)
        self._lock = threading.Lock()
        self._current_speaker: Optional[str] = None
        self._speaking = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        self._tts_callback = None  # Will be set to main.tts.speak
    
    def set_tts_callback(self, callback):
        """Set the TTS callback function."""
        self._tts_callback = callback
    
    def enqueue(self, session_id: str, text: str, emotion: str = "neutral"):
        """Add TTS request to queue."""
        with self._lock:
            self._queue.append((session_id, text, emotion))
            logger.info(f"[TTSQueue] Enqueued speech for session {session_id}")
    
    def _worker(self):
        """Worker thread that processes TTS queue sequentially."""
        while True:
            if self._queue:
                with self._lock:
                    if self._queue:
                        session_id, text, emotion = self._queue.pop(0)
                        self._current_speaker = session_id
                        self._speaking.set()
                
                # Speak (blocking)
                if self._tts_callback:
                    try:
                        self._tts_callback(text, emotion=emotion, blocking=True)
                    except Exception as e:
                        logger.error(f"[TTSQueue] TTS error: {e}")
                
                with self._lock:
                    self._current_speaker = None
                    self._speaking.clear()
            else:
                time.sleep(0.1)
    
    def is_speaking(self) -> bool:
        """Check if any session is currently speaking."""
        return self._speaking.is_set()
    
    def get_current_speaker(self) -> Optional[str]:
        """Get the session ID currently speaking."""
        return self._current_speaker
    
    def clear_session_queue(self, session_id: str):
        """Remove all pending TTS requests for a session."""
        with self._lock:
            self._queue = [item for item in self._queue if item[0] != session_id]
            logger.info(f"[TTSQueue] Cleared queue for session {session_id}")


class SessionManager:
    """
    Manages multiple concurrent sessions with independent contexts.
    Handles session switching and ensures single voice output.
    """
    def __init__(self, brain_factory, tts_callback):
        """
        Args:
            brain_factory: Function that creates a new BrianBrain instance
            tts_callback: Function to call for TTS (main.tts.speak)
        """
        self._sessions: Dict[str, Session] = {}
        self._active_session_id: Optional[str] = None
        self._brain_factory = brain_factory
        self._lock = threading.Lock()
        self._tts_queue = TTSQueue()
        self._tts_queue.set_tts_callback(tts_callback)
        
        logger.info("[SessionManager] Initialized")
    
    def create_session(self) -> Session:
        """Create a new session with its own brain instance."""
        with self._lock:
            session = Session()
            session.brain = self._brain_factory()
            self._sessions[session.id] = session
            logger.info(f"[SessionManager] Created session {session.id}")
            return session
    
    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session."""
        with self._lock:
            return self._sessions.get(self._active_session_id)
    
    def set_active_session(self, session_id: str):
        """Set the active session (switch context)."""
        with self._lock:
            if session_id in self._sessions:
                # Pause previous active session
                if self._active_session_id and self._active_session_id != session_id:
                    prev_session = self._sessions[self._active_session_id]
                    prev_session.is_active = False
                    prev_session.state = SessionState.PAUSED
                    logger.info(f"[SessionManager] Paused session {self._active_session_id}")
                
                # Activate new session
                self._active_session_id = session_id
                session = self._sessions[session_id]
                session.is_active = True
                session.update_last_active()
                session.state = SessionState.LISTENING
                logger.info(f"[SessionManager] Activated session {session_id}")
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        with self._lock:
            return self._sessions.get(session_id)
    
    def get_all_sessions(self) -> List[Session]:
        """Get all sessions."""
        with self._lock:
            return list(self._sessions.values())
    
    def remove_session(self, session_id: str):
        """Remove a session."""
        with self._lock:
            if session_id in self._sessions:
                self._tts_queue.clear_session_queue(session_id)
                del self._sessions[session_id]
                if self._active_session_id == session_id:
                    self._active_session_id = None
                logger.info(f"[SessionManager] Removed session {session_id}")
    
    def speak(self, session_id: str, text: str, emotion: str = "neutral", blocking: bool = True):
        """Queue speech for a session (prevents overlap)."""
        self._tts_queue.enqueue(session_id, text, emotion)
        if blocking:
            # Wait for this session's speech to complete
            while self._tts_queue.is_speaking() and self._tts_queue.get_current_speaker() == session_id:
                time.sleep(0.05)
    
    def is_anyone_speaking(self) -> bool:
        """Check if any session is currently speaking."""
        return self._tts_queue.is_speaking()
    
    def get_current_speaker(self) -> Optional[str]:
        """Get the session ID currently speaking."""
        return self._tts_queue.get_current_speaker()
