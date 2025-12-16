"""Transcription history management with JSON persistence."""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class TranscriptionHistory:
    """Manages transcription history with automatic persistence.

    History is stored in ~/.recordtranscribe/history.json
    """

    def __init__(self, history_dir: Optional[Path] = None, max_items: int = 50):
        """Initialize history manager.

        Args:
            history_dir: Optional custom history directory (defaults to ~/.recordtranscribe)
            max_items: Maximum number of history items to keep
        """
        if history_dir is None:
            self.history_dir = Path.home() / ".recordtranscribe"
        else:
            self.history_dir = Path(history_dir)

        self.history_file = self.history_dir / "history.json"
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        """Load history from file.

        Returns:
            list: Loaded history items
        """
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load history: {e}")
                return []
        return []

    def _save(self):
        """Save history to file."""
        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self.items, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save history: {e}")

    def add(self, text: str, cleanup_used: bool = False, metadata: Optional[Dict[str, Any]] = None):
        """Add a transcription to history.

        Args:
            text: Transcribed text
            cleanup_used: Whether cleanup was applied
            metadata: Optional additional metadata
        """
        item = {
            "timestamp": datetime.now().isoformat(),
            "text": text,
            "cleanup_used": cleanup_used,
            "metadata": metadata or {}
        }

        # Add to beginning (most recent first)
        self.items.insert(0, item)

        # Trim to max items
        if len(self.items) > self.max_items:
            self.items = self.items[:self.max_items]

        self._save()

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all history items.

        Returns:
            list: All history items (most recent first)
        """
        return self.items.copy()

    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent history items.

        Args:
            count: Number of items to return

        Returns:
            list: Recent history items
        """
        return self.items[:count]

    def clear(self):
        """Clear all history."""
        self.items = []
        self._save()

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search history by text content.

        Args:
            query: Search query

        Returns:
            list: Matching history items
        """
        query_lower = query.lower()
        return [
            item for item in self.items
            if query_lower in item["text"].lower()
        ]

    def delete(self, index: int):
        """Delete a history item by index.

        Args:
            index: Index of item to delete
        """
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._save()

    def get_count(self) -> int:
        """Get total number of history items.

        Returns:
            int: Number of items
        """
        return len(self.items)
