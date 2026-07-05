import os
import numpy as np
import librosa
import logging
from typing import Optional

logger = logging.getLogger("VoiceIdentifier")

class VoiceIdentifier:
    def __init__(self, profile_path="voice_profile.npy"):
        # Put it in the same directory as this script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.profile_path = os.path.join(base_dir, profile_path)
        self.reference_vector = None
        self._load_profile()

    def _load_profile(self):
        """Load the owner's voice fingerprint if it exists on disk."""
        if os.path.exists(self.profile_path):
            try:
                self.reference_vector = np.load(self.profile_path)
                logger.info(f"Loaded owner's voice profile from {self.profile_path}")
            except Exception as e:
                logger.error(f"Failed to load voice profile: {e}")

    def _extract_feature_vector(self, audio_np: np.ndarray, rate: int = 16000) -> Optional[np.ndarray]:
        """Extract a 40-dimensional speaker feature vector (mean & std of 20 MFCCs)."""
        try:
            # Ensure it's float32
            if audio_np.dtype != np.float32:
                # Normalize int16 to float32 (-1.0 to 1.0)
                audio_float = audio_np.astype(np.float32) / 32768.0
            else:
                audio_float = audio_np

            # Extract 20 MFCCs
            mfccs = librosa.feature.mfcc(y=audio_float, sr=rate, n_mfcc=20)
            
            # Compute mean and standard deviation along the time axis (axis=1)
            means = np.mean(mfccs, axis=1)
            stds = np.std(mfccs, axis=1)
            
            # Concatenate to make a 40-dimensional vector
            vector = np.concatenate([means, stds])
            
            # Normalize vector to unit length
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            return vector
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def enroll(self, audio_np: np.ndarray, rate: int = 16000) -> bool:
        """Enroll the owner's voice profile using a clean sample."""
        vector = self._extract_feature_vector(audio_np, rate)
        if vector is not None:
            self.reference_vector = vector
            try:
                np.save(self.profile_path, self.reference_vector)
                logger.info(f"Enrolled and saved owner's voice profile to {self.profile_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to save voice profile: {e}")
                return False
        return False

    def reset(self) -> bool:
        """Delete the stored voice profile so the owner can re-enroll."""
        self.reference_vector = None
        if os.path.exists(self.profile_path):
            try:
                os.remove(self.profile_path)
                logger.info(f"Voice profile deleted: {self.profile_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete voice profile: {e}")
                return False
        return True

    def has_profile(self) -> bool:
        """Return True if an owner voice profile exists."""
        return self.reference_vector is not None

    def is_owner(self, audio_np: np.ndarray, rate: int = 16000, threshold: float = 0.82) -> bool:
        """Compare the speaker of input audio against the enrolled owner.
        Returns False if no profile is enrolled — caller must explicitly enroll first."""
        if self.reference_vector is None:
            logger.warning("No voice profile enrolled yet. Call enroll() first.")
            return False

        vector = self._extract_feature_vector(audio_np, rate)
        if vector is None:
            return False

        # Cosine similarity (dot product since they are unit normalized)
        similarity = float(np.dot(self.reference_vector, vector))
        logger.info(f"Voice similarity score: {similarity:.4f} (threshold: {threshold})")

        return similarity >= threshold
