#!/usr/bin/env python3
"""
Transcription Service for RecordTranscribe SwiftUI App

A JSON-over-stdin/stdout service that handles:
- MLX model loading (Parakeet for STT, Qwen for cleanup)
- Audio transcription
- Optional LLM cleanup

Protocol:
- Input: JSON commands on stdin (one per line)
- Output: JSON responses on stdout (one per line)

Commands:
- {"command": "transcribe", "audio": "<base64>", "sample_rate": 16000}
- {"command": "transcribe", "audio": "<base64>", "cleanup": true}
- {"command": "status"}
- {"command": "shutdown"}

Responses:
- {"type": "ready", "backend": "parakeet-mlx"}
- {"type": "transcription", "text": "...", "cleanup_used": false}
- {"type": "status", "status": "idle"|"transcribing"}
- {"type": "error", "message": "..."}
"""

import sys
import json
import base64
import platform
import numpy as np
from pathlib import Path
from typing import Optional

# Ensure unbuffered output
sys.stdout.reconfigure(line_buffering=True)


def send_message(msg: dict):
    """Send a JSON message to stdout."""
    print(json.dumps(msg), flush=True)


def send_error(message: str):
    """Send an error message."""
    send_message({"type": "error", "message": message})


def detect_platform() -> dict:
    """Detect platform and return configuration."""
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin" and machine == "arm64":
        return {
            "backend": "parakeet-mlx",
            "model": "mlx-community/parakeet-tdt-0.6b-v3",
            "cleanup_model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
        }
    elif system == "Linux":
        return {
            "backend": "nemo",
            "model": "nvidia/parakeet-tdt-0.6b-v2",
            "cleanup_model": None  # TODO: Add Linux cleanup support
        }
    else:
        return {
            "backend": "unsupported",
            "model": None,
            "cleanup_model": None
        }


class TranscriptionService:
    """Main service class handling transcription requests."""

    def __init__(self):
        self.config = detect_platform()
        self.stt_model = None
        self.cleanup_model = None
        self.cleanup_tokenizer = None
        self.sample_rate = 16000
        self._load_models()

    def _load_models(self):
        """Load STT and cleanup models based on platform."""
        backend = self.config["backend"]

        if backend == "parakeet-mlx":
            self._load_mlx_models()
        elif backend == "nemo":
            self._load_nemo_models()
        else:
            send_error(f"Unsupported platform: {platform.system()} {platform.machine()}")
            sys.exit(1)

    def _load_mlx_models(self):
        """Load MLX-based models for macOS Apple Silicon."""
        try:
            import mlx.core as mx
            from parakeet_mlx import from_pretrained

            # Load Parakeet STT model
            self.stt_model = from_pretrained(self.config["model"])
            # Sample rate is 16000 for Parakeet (set in __init__)

            # Try to load cleanup model
            try:
                from mlx_lm import load as load_lm
                send_message({"type": "status", "status": "loading_cleanup_model"})
                self.cleanup_model, self.cleanup_tokenizer = load_lm(
                    self.config["cleanup_model"]
                )
                send_message({"type": "status", "status": "cleanup_model_loaded"})
            except Exception as e:
                # Cleanup is optional - log the error
                send_message({"type": "warning", "message": f"Cleanup model failed to load: {e}"})
                self.cleanup_model = None
                self.cleanup_tokenizer = None

            send_message({
                "type": "ready",
                "backend": "parakeet-mlx",
                "cleanup_available": self.cleanup_model is not None
            })

        except ImportError as e:
            send_error(f"Failed to import MLX dependencies: {e}")
            sys.exit(1)
        except Exception as e:
            send_error(f"Failed to load MLX models: {e}")
            sys.exit(1)

    def _load_nemo_models(self):
        """Load NeMo-based models for Linux."""
        try:
            import torch
            from nemo.collections.asr.models import ASRModel

            # Load Parakeet STT model
            self.stt_model = ASRModel.from_pretrained(self.config["model"])
            self.stt_model.eval()

            if torch.cuda.is_available():
                self.stt_model = self.stt_model.cuda()

            send_message({
                "type": "ready",
                "backend": "nemo",
                "cleanup_available": False
            })

        except ImportError as e:
            send_error(f"Failed to import NeMo dependencies: {e}")
            sys.exit(1)
        except Exception as e:
            send_error(f"Failed to load NeMo models: {e}")
            sys.exit(1)

    def transcribe(self, audio_data: np.ndarray, use_cleanup: bool = False) -> tuple[str, str, bool]:
        """Transcribe audio data.

        Returns:
            tuple: (final_text, original_text, cleanup_used)
        """
        backend = self.config["backend"]

        if backend == "parakeet-mlx":
            return self._transcribe_mlx(audio_data, use_cleanup)
        elif backend == "nemo":
            return self._transcribe_nemo(audio_data, use_cleanup)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _transcribe_mlx(self, audio_data: np.ndarray, use_cleanup: bool) -> tuple[str, str, bool]:
        """Transcribe using MLX Parakeet streaming API.

        Returns:
            tuple: (final_text, original_text, cleanup_used)
        """
        import mlx.core as mx

        # Convert numpy → MLX array (in-memory, no I/O!)
        audio_mlx = mx.array(audio_data.astype(np.float32))

        # Use streaming transcriber (this is the correct API)
        transcriber = self.stt_model.transcribe_stream(context_size=(256, 256))
        transcriber.__enter__()

        # Add audio and get result
        transcriber.add_audio(audio_mlx)
        result = transcriber.result
        original_text = result.text.strip()

        # Cleanup transcriber
        transcriber.__exit__(None, None, None)

        # Apply cleanup if requested and available
        final_text = original_text
        cleanup_used = False
        if use_cleanup and self.cleanup_model is not None:
            final_text = self._apply_cleanup(original_text)
            cleanup_used = True

        return final_text, original_text, cleanup_used

    def _transcribe_nemo(self, audio_data: np.ndarray, use_cleanup: bool) -> tuple[str, str, bool]:
        """Transcribe using NeMo Parakeet.

        Returns:
            tuple: (final_text, original_text, cleanup_used)
        """
        # NeMo accepts numpy arrays directly
        hypotheses = self.stt_model.transcribe(audio=[audio_data])
        original_text = hypotheses[0].text if hasattr(hypotheses[0], 'text') else str(hypotheses[0])
        original_text = original_text.strip()
        # NeMo doesn't have cleanup support yet
        return original_text, original_text, False

    def _apply_cleanup(self, text: str) -> str:
        """Apply LLM cleanup to transcribed text."""
        import re

        if self.cleanup_model is None or self.cleanup_tokenizer is None:
            return text

        try:
            from mlx_lm import generate

            # Simple, direct cleanup prompt
            cleanup_prompt = """You are a transcription cleanup assistant. Your task is to clean up speech transcriptions.

Rules:
- Remove filler words (um, uh, like, you know, basically, actually)
- Fix grammar and punctuation
- Keep the original meaning and tone
- Output ONLY the cleaned text, nothing else
- Do NOT wrap output in tags or add any formatting"""

            # Format prompt for Qwen
            messages = [
                {"role": "system", "content": cleanup_prompt},
                {"role": "user", "content": f"Clean this transcription:\n\n{text}"}
            ]

            prompt = self.cleanup_tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            # Generate cleaned text
            cleaned = generate(
                self.cleanup_model,
                self.cleanup_tokenizer,
                prompt=prompt,
                max_tokens=2048,
                verbose=False
            )

            if cleaned:
                # Strip any XML/HTML tags the model might add
                cleaned = re.sub(r'<[^>]+>', '', cleaned)
                # Remove common wrapper patterns
                cleaned = re.sub(r'^(output|response|result):\s*', '', cleaned, flags=re.IGNORECASE)
                return cleaned.strip()
            return text

        except Exception as e:
            # If cleanup fails, return original text
            return text

    def handle_command(self, cmd: dict):
        """Handle a command from stdin."""
        command = cmd.get("command")

        if command == "transcribe":
            try:
                # Decode audio from base64
                audio_b64 = cmd.get("audio", "")
                audio_bytes = base64.b64decode(audio_b64)

                # Convert to numpy array (assuming 16-bit PCM)
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                audio_data = audio_data / 32768.0  # Normalize to [-1, 1]

                # Resample if needed
                input_sample_rate = cmd.get("sample_rate", 16000)
                if input_sample_rate != self.sample_rate:
                    # Simple resampling (for production, use librosa or scipy)
                    ratio = self.sample_rate / input_sample_rate
                    new_length = int(len(audio_data) * ratio)
                    audio_data = np.interp(
                        np.linspace(0, len(audio_data), new_length),
                        np.arange(len(audio_data)),
                        audio_data
                    )

                send_message({"type": "status", "status": "transcribing"})

                # Transcribe
                use_cleanup = cmd.get("cleanup", False)
                send_message({"type": "debug", "message": f"Cleanup requested: {use_cleanup}, available: {self.cleanup_model is not None}"})
                text, original_text, cleanup_used = self.transcribe(audio_data, use_cleanup)

                send_message({
                    "type": "transcription",
                    "text": text,
                    "original_text": original_text,
                    "cleanup_used": cleanup_used
                })

            except Exception as e:
                send_error(f"Transcription failed: {e}")

        elif command == "status":
            send_message({
                "type": "status",
                "status": "idle",
                "backend": self.config["backend"],
                "cleanup_available": self.cleanup_model is not None
            })

        elif command == "shutdown":
            send_message({"type": "shutdown", "status": "ok"})
            sys.exit(0)

        else:
            send_error(f"Unknown command: {command}")


def main():
    """Main entry point."""
    try:
        service = TranscriptionService()

        # Read commands from stdin
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                cmd = json.loads(line)
                service.handle_command(cmd)
            except json.JSONDecodeError as e:
                send_error(f"Invalid JSON: {e}")
            except Exception as e:
                send_error(f"Command failed: {e}")

    except KeyboardInterrupt:
        pass
    except Exception as e:
        send_error(f"Service crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
