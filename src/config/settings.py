"""Application settings with JSON persistence."""
import json
from pathlib import Path
from typing import Optional, Dict, Any


class Settings:
    """Manages application settings with automatic persistence.

    Settings are stored in ~/.recordtranscribe/config.json
    """

    DEFAULT_CONFIG = {
        # Hotkey settings
        "hotkey": "alt",
        "stop_cooldown": 0.25,

        # Audio settings
        "sound_effects_enabled": True,

        # Model settings
        "stt_provider": "auto",  # auto, parakeet-mlx, nemo, openai, gemini
        "cleanup_enabled": False,
        "cleanup_provider": "auto",  # auto, qwen-mlx, qwen-pytorch, none, openai, gemini

        # UI settings
        "theme": "system",  # light, dark, system
        "window_always_on_top": False,
        "minimize_to_tray": True,

        # API keys (stored encrypted in production)
        "openai_api_key": None,
        "gemini_api_key": None,

        # History settings
        "history_enabled": True,
        "history_max_items": 50,
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize settings manager.

        Args:
            config_dir: Optional custom config directory (defaults to ~/.recordtranscribe)
        """
        if config_dir is None:
            self.config_dir = Path.home() / ".recordtranscribe"
        else:
            self.config_dir = Path(config_dir)

        self.config_file = self.config_dir / "config.json"
        self.config = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load settings from file or create with defaults.

        Returns:
            dict: Loaded settings merged with defaults
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new keys
                    return {**self.DEFAULT_CONFIG, **loaded}
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config: {e}")
                print("Using default settings.")
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()

    def save(self):
        """Save current settings to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value and save.

        Args:
            key: Setting key
            value: Setting value
        """
        self.config[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]):
        """Update multiple settings at once.

        Args:
            updates: Dictionary of setting updates
        """
        self.config.update(updates)
        self.save()

    def reset(self):
        """Reset all settings to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """Get all settings.

        Returns:
            dict: All current settings
        """
        return self.config.copy()

    # Convenience accessors for common settings

    @property
    def hotkey(self) -> str:
        """Get hotkey setting."""
        return self.get("hotkey", "alt")

    @hotkey.setter
    def hotkey(self, value: str):
        """Set hotkey setting."""
        self.set("hotkey", value)

    @property
    def cleanup_enabled(self) -> bool:
        """Get cleanup enabled setting."""
        return self.get("cleanup_enabled", False)

    @cleanup_enabled.setter
    def cleanup_enabled(self, value: bool):
        """Set cleanup enabled setting."""
        self.set("cleanup_enabled", value)

    @property
    def sound_effects_enabled(self) -> bool:
        """Get sound effects enabled setting."""
        return self.get("sound_effects_enabled", True)

    @sound_effects_enabled.setter
    def sound_effects_enabled(self, value: bool):
        """Set sound effects enabled setting."""
        self.set("sound_effects_enabled", value)
