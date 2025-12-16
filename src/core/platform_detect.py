"""Platform detection and ASR backend loading."""
import sys
import platform


def detect_platform():
    """Detect the platform and available ASR backend.

    Returns:
        tuple: (backend_name, backend_modules)
            - backend_name: str, either "parakeet-mlx" or "nemo"
            - backend_modules: module or tuple of modules needed for initialization
    """
    system = platform.system()
    machine = platform.machine()

    # Check for Apple Silicon (M1/M2/M3/M4) - use Parakeet-MLX
    if system == "Darwin" and machine == "arm64":
        try:
            from parakeet_mlx import from_pretrained
            print("Detected: Apple Silicon with Parakeet-MLX support")
            return "parakeet-mlx", from_pretrained
        except ImportError:
            print("Apple Silicon detected but Parakeet-MLX not installed.")
            print("Install with: uv pip install parakeet-mlx")
            sys.exit(1)

    # Check for Linux - prefer NeMo
    if system == "Linux":
        try:
            from nemo.collections.asr.models import ASRModel
            import torch
            print("Detected: Linux with NeMo ASR support")
            return "nemo", (ASRModel, torch)
        except ImportError:
            print("Linux detected but NeMo not installed.")
            print("Install with: uv sync")
            sys.exit(1)

    # Windows or other platforms - fallback
    print(f"Platform {system} not fully supported yet. NeMo only works on Linux/macOS.")
    print("For Windows, consider using WSL2 with Linux setup.")
    sys.exit(1)
