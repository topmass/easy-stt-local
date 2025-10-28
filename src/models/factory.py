"""Factory for creating platform-appropriate providers."""
import platform
import sys
from typing import Tuple
from .base import TranscriptionProvider, CleanupProvider


def create_stt_provider() -> TranscriptionProvider:
    """Create appropriate STT provider based on platform.

    Returns:
        TranscriptionProvider: Platform-optimized STT provider

    Raises:
        SystemExit: If platform is unsupported or dependencies missing
    """
    system = platform.system()
    machine = platform.machine()

    # macOS Apple Silicon → Parakeet-MLX
    if system == "Darwin" and machine == "arm64":
        try:
            from .local_stt import ParakeetMLXProvider
            print("Detected: Apple Silicon with Parakeet-MLX support")
            return ParakeetMLXProvider()
        except ImportError as e:
            print("Apple Silicon detected but Parakeet-MLX not installed.")
            print("Install with: uv pip install parakeet-mlx")
            print(f"Error: {e}")
            sys.exit(1)

    # Linux → NeMo
    elif system == "Linux":
        try:
            from .local_stt import NeMoProvider
            print("Detected: Linux with NeMo ASR support")
            return NeMoProvider()
        except ImportError as e:
            print("Linux detected but NeMo not installed.")
            print("Install with: uv sync")
            print(f"Error: {e}")
            sys.exit(1)

    # Unsupported platform
    else:
        print(f"Platform {system} not fully supported yet.")
        print("Supported platforms:")
        print("  - macOS Apple Silicon (M1/M2/M3/M4)")
        print("  - Linux with NVIDIA GPU")
        print("For Windows, consider using WSL2 with Linux setup.")
        sys.exit(1)


def create_cleanup_provider(enable: bool = False, prompt_file: str = "cleanup_prompt.txt") -> CleanupProvider:
    """Create appropriate cleanup provider based on platform and settings.

    Args:
        enable: Whether to enable cleanup
        prompt_file: Path to cleanup prompt file

    Returns:
        CleanupProvider: Platform-optimized cleanup provider or NoCleanupProvider
    """
    if not enable:
        from .local_cleanup import NoCleanupProvider
        return NoCleanupProvider()

    system = platform.system()
    machine = platform.machine()

    # macOS Apple Silicon → MLX-based Qwen
    if system == "Darwin" and machine == "arm64":
        try:
            from .local_cleanup import QwenMLXCleanupProvider
            return QwenMLXCleanupProvider(prompt_file=prompt_file)
        except ImportError as e:
            print(f"Warning: MLX cleanup not available: {e}")
            print("Install with: uv sync --extra cleanup")
            print("Falling back to no cleanup.")
            from .local_cleanup import NoCleanupProvider
            return NoCleanupProvider()

    # Linux → PyTorch-based Qwen
    elif system == "Linux":
        try:
            from .local_cleanup import QwenPyTorchCleanupProvider
            return QwenPyTorchCleanupProvider(prompt_file=prompt_file)
        except ImportError as e:
            print(f"Warning: PyTorch cleanup not available: {e}")
            print("Install transformers and bitsandbytes for cleanup support.")
            print("Falling back to no cleanup.")
            from .local_cleanup import NoCleanupProvider
            return NoCleanupProvider()

    # Unsupported platform
    else:
        print(f"Cleanup not available for platform {system}.")
        print("Falling back to no cleanup.")
        from .local_cleanup import NoCleanupProvider
        return NoCleanupProvider()
