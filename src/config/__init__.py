"""Configuration and history management.

This module provides persistent settings and transcription history storage.
"""
from .settings import Settings
from .history import TranscriptionHistory

__all__ = [
    'Settings',
    'TranscriptionHistory',
]
