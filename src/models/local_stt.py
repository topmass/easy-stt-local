"""Local speech-to-text providers (Parakeet-MLX, NeMo).

These providers maintain the critical zero-file-I/O architecture for maximum performance.
"""
import numpy as np
from .base import TranscriptionProvider


class ParakeetMLXProvider(TranscriptionProvider):
    """macOS Apple Silicon optimized STT using Parakeet-MLX.

    Features:
    - Streaming transcription during recording
    - MLX framework optimized for unified memory
    - Zero file I/O (direct numpy → MLX array processing)
    - ~50ms latency
    """

    def __init__(self):
        """Initialize Parakeet-MLX model."""
        from parakeet_mlx import from_pretrained
        self.model_name = "mlx-community/parakeet-tdt-0.6b-v3"
        print(f"Loading Parakeet-MLX model ({self.model_name})...")
        self.model = from_pretrained(self.model_name)
        self.sample_rate = self.model.preprocessor_config.sample_rate
        print(f"Parakeet-MLX model loaded! Sample rate: {self.sample_rate}Hz")
        self.transcriber = None

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio using streaming MLX model.

        CRITICAL: Maintains zero-file-I/O architecture.
        Audio flows: numpy array → MLX array → model (no disk writes).

        Args:
            audio: Audio data as numpy float32 array
            sample_rate: Sample rate in Hz (unused, model has fixed rate)

        Returns:
            str: Transcribed text
        """
        import mlx.core as mx

        # Convert numpy → MLX array (in-memory, no I/O!)
        audio_mlx = mx.array(audio.astype(np.float32))

        # Initialize streaming transcriber
        transcriber = self.model.transcribe_stream(context_size=(256, 256))
        transcriber.__enter__()

        # Add audio and get result (streaming, no file I/O!)
        transcriber.add_audio(audio_mlx)
        result = transcriber.result
        transcription = result.text.strip()

        # Cleanup
        transcriber.__exit__(None, None, None)

        return transcription

    def supports_streaming(self) -> bool:
        """Parakeet-MLX supports streaming."""
        return True

    def get_backend_name(self) -> str:
        """Get backend name."""
        return "Parakeet-MLX (Apple Silicon)"


class NeMoProvider(TranscriptionProvider):
    """Linux CUDA optimized STT using NVIDIA NeMo.

    Features:
    - GPU-accelerated batch transcription
    - Direct numpy array input (zero file I/O!)
    - Automatic CUDA detection and usage
    - ~50-100ms latency (GPU dependent)
    """

    def __init__(self):
        """Initialize NeMo ASR model."""
        from nemo.collections.asr.models import ASRModel
        print("Loading NeMo ASR model...")
        print("NeMo will automatically detect and use available GPU")
        self.model = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v2")
        self.model.eval()
        print("NeMo model loaded!")

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio using NeMo.

        CRITICAL: Maintains zero-file-I/O architecture.
        NeMo accepts numpy arrays directly (no disk writes).

        Args:
            audio: Audio data as numpy float32 array
            sample_rate: Sample rate in Hz

        Returns:
            str: Transcribed text
        """
        # NeMo accepts numpy arrays directly as a list (zero file I/O!)
        hypotheses = self.model.transcribe(audio=[audio.astype(np.float32)])

        # Extract text from NeMo output
        if hypotheses and len(hypotheses) > 0:
            hypothesis = hypotheses[0]
            return hypothesis.text if hasattr(hypothesis, 'text') else str(hypothesis)

        return ""

    def supports_streaming(self) -> bool:
        """NeMo does not support streaming in current implementation."""
        return False

    def get_backend_name(self) -> str:
        """Get backend name."""
        return "NeMo (CUDA)"
