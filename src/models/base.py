"""Base interfaces for transcription and cleanup providers.

These abstract base classes define the contract for pluggable STT and cleanup models.
"""
from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class TranscriptionProvider(ABC):
    """Base interface for speech-to-text providers.

    CRITICAL: All implementations must maintain zero-file-I/O architecture.
    Audio must be processed directly from numpy arrays without writing to disk.
    """

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio array to text.

        IMPORTANT: Must accept numpy array directly. NO FILE I/O!

        Args:
            audio: Audio data as numpy float32 array
            sample_rate: Sample rate in Hz (default 16000)

        Returns:
            str: Transcribed text
        """
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming transcription.

        Returns:
            bool: True if streaming is supported
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Get the backend name for display.

        Returns:
            str: Human-readable backend name
        """
        pass


class CleanupProvider(ABC):
    """Base interface for text cleanup providers."""

    @abstractmethod
    def cleanup(self, text: str) -> str:
        """Clean up transcription text.

        Args:
            text: Raw transcription text

        Returns:
            str: Cleaned transcription text
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name for display.

        Returns:
            str: Human-readable provider name
        """
        pass
