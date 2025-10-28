# GUI Implementation Plan

## Overview
Add a Flet-based GUI to RecordTranscribe while maintaining the existing CLI version and preserving the critical zero-file-I/O performance architecture.

**Target Platforms:** macOS (primary), Linux (secondary), Windows (future)

---

## Critical Requirements

### 1. Zero File I/O Performance (MUST PRESERVE)

**Current Speed:** ~50ms transcription latency on macOS

**Why it's fast:** Audio flows directly from `sounddevice` → numpy array → model (MLX/NeMo) without touching disk.

**Traditional (Slow) Approach:**
```
Record → Write temp.wav → Read temp.wav → Model
Time: 100-500ms+ (disk I/O bottleneck)
```

**Our (Fast) Approach:**
```
Record → numpy array → MLX/NeMo array → Model
Time: ~50ms (pure in-memory)
```

**Implementation Rules:**
- ✅ Keep audio in numpy arrays throughout pipeline
- ✅ Pass arrays directly to transcription models
- ✅ Only convert format when required (numpy → MLX)
- ❌ NEVER write to temp files (`tempfile`, `soundfile.write()`)
- ❌ NEVER use file-based audio libraries (`librosa.load()`)
- ❌ NEVER save intermediate audio states to disk

### 2. Platform-Specific Optimizations (MUST PRESERVE)

#### macOS Apple Silicon
- **Framework:** Parakeet-MLX + MLX-LM
- **Key Feature:** Streaming transcription during recording
- **Model:** `mlx-community/parakeet-tdt-0.6b-v3`
- **Cleanup:** `mlx-community/Qwen2.5-1.5B-Instruct-4bit`
- **Advantage:** Unified memory (no CPU↔GPU copies)
- **Latency:** 50ms STT + 150ms cleanup = 200ms total

#### Linux (NVIDIA GPU)
- **Framework:** NVIDIA NeMo (STT) + PyTorch/transformers (cleanup)
- **Key Feature:** GPU-accelerated batch processing
- **Model:** `nvidia/parakeet-tdt-0.6b-v2`
- **Cleanup:** Qwen2.5-1.5B via transformers + bitsandbytes (CUDA)
- **Advantage:** CUDA acceleration, direct numpy array input
- **Latency:** 50-100ms STT + 100-200ms cleanup = 150-300ms total

---

## Architecture

### Unified Codebase Structure

```
easy-stt-local/
├── record_transcribe.py          # Keep: CLI version (unchanged)
├── record_transcribe_gui.py      # New: GUI entry point
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── audio_recorder.py    # Extracted: AudioRecorder class
│   │   ├── platform_detect.py   # Extracted: detect_platform()
│   │   └── clipboard.py         # Extracted: copy_to_clipboard()
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py              # TranscriptionProvider, CleanupProvider interfaces
│   │   ├── local_stt.py         # ParakeetMLXProvider, NeMoProvider
│   │   ├── local_cleanup.py     # QwenCleanupProvider
│   │   └── cloud_providers.py   # OpenAI, Gemini (future)
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py       # Main Flet application
│   │   ├── status_indicator.py  # Status component (Idle/Recording/Processing)
│   │   ├── settings_panel.py    # Settings UI
│   │   ├── history_panel.py     # Transcription history
│   │   └── tray_icon.py         # System tray with pystray
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Config storage (~/.recordtranscribe/config.json)
│   └── assets/
│       ├── icon.png             # App icon (512x512)
│       ├── tray_icon.png        # Tray icon
│       ├── start.mp3            # Recording start sound
│       └── stop.mp3             # Recording stop sound
├── build_scripts/
│   ├── build_macos.sh           # macOS build script
│   ├── build_linux.sh           # Linux build script
│   └── build_windows.sh         # Windows (future)
├── Makefile                      # Convenience commands
├── pyproject.toml
├── README.md
├── CLAUDE.md                     # Updated with GUI info
└── ARCHITECTURE.md
```

---

## GUI Features

### 1. Hybrid Window + System Tray
- Main window that can minimize to system tray/menu bar
- Tray icon with context menu:
  - "Show/Hide Window"
  - "Start Recording" (hotkey alternative)
  - "Settings"
  - "Quit"
- Uses `pystray` + Flet integration

### 2. Status Indicator
Visual state display:
- **Idle:** Gray microphone - "Ready to record"
- **Recording:** Red pulsing microphone - "Recording..."
- **Processing:** Orange spinner - "Transcribing..."
- **Success:** Green checkmark (brief) - "Copied to clipboard"
- **Error:** Red X with error message

### 3. Settings Panel
- **STT Model Selection:**
  - macOS: Parakeet-MLX (default), OpenAI Whisper API, Gemini
  - Linux: NeMo (default), OpenAI Whisper API, Gemini
- **Cleanup Model Selection:**
  - macOS: Qwen2.5-1.5B (default), None, OpenAI GPT-4o-mini, Gemini
  - Linux: None (default), OpenAI GPT-4o-mini, Gemini
- **Hotkey Configuration:**
  - Dropdown: Alt (default), F9, F10, F11, F12, etc.
  - Test button to verify
- **Other Settings:**
  - Stop cooldown slider (0.1s - 1.0s)
  - Enable/disable sound effects
  - Theme (light/dark/system)

### 4. Transcription History
- Scrollable list (last 20-50 transcriptions)
- Each entry shows:
  - Timestamp
  - First 50 chars (expandable)
  - Copy button
  - Cleanup indicator badge
- Persisted to `~/.recordtranscribe/history.json`

### 5. Manual Recording Controls
- Large "Start Recording" button
- "Stop Recording" button (appears when active)
- Keyboard shortcuts work in parallel

---

## Model Provider Abstraction

### Base Interfaces

```python
# src/models/base.py
from abc import ABC, abstractmethod
import numpy as np

class TranscriptionProvider(ABC):
    """Base interface for STT providers."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio array to text. NO FILE I/O!"""
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Does this provider support streaming transcription?"""
        pass

class CleanupProvider(ABC):
    """Base interface for text cleanup providers."""

    @abstractmethod
    def cleanup(self, text: str) -> str:
        """Clean up transcription text."""
        pass
```

### Local Providers

```python
# src/models/local_stt.py
class ParakeetMLXProvider(TranscriptionProvider):
    """macOS Apple Silicon optimized STT."""

    def __init__(self):
        from parakeet_mlx import from_pretrained
        self.model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")
        self.transcriber = None  # For streaming

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        import mlx.core as mx
        audio_mlx = mx.array(audio.astype(np.float32))
        # Stream to model (zero file I/O!)
        self.transcriber = self.model.transcribe_stream(context_size=(256, 256))
        self.transcriber.__enter__()
        self.transcriber.add_audio(audio_mlx)
        result = self.transcriber.result.text.strip()
        self.transcriber.__exit__(None, None, None)
        return result

    def supports_streaming(self) -> bool:
        return True

class NeMoProvider(TranscriptionProvider):
    """Linux CUDA optimized STT."""

    def __init__(self):
        from nemo.collections.asr.models import ASRModel
        self.model = ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
        self.model.eval()

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        # NeMo accepts numpy arrays directly (zero file I/O!)
        hypotheses = self.model.transcribe(audio=[audio.astype(np.float32)])
        return hypotheses[0].text if hypotheses else ""

    def supports_streaming(self) -> bool:
        return False

# src/models/local_cleanup.py
class QwenCleanupProvider(CleanupProvider):
    """macOS Apple Silicon cleanup using MLX."""

    def __init__(self, prompt_file: str = "cleanup_prompt.txt"):
        from mlx_lm import load
        self.model, self.tokenizer = load("mlx-community/Qwen2.5-1.5B-Instruct-4bit")
        with open(prompt_file) as f:
            self.base_prompt = f.read().strip()

    def cleanup(self, text: str) -> str:
        from mlx_lm import generate
        import re

        messages = [
            {"role": "system", "content": self.base_prompt},
            {"role": "user", "content": f"Transcription to clean:\n{text}"}
        ]

        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        response = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=2048, verbose=False)

        # Extract from <output> tags
        match = re.search(r'<output>\s*(.*?)\s*</output>', response, re.DOTALL)
        return match.group(1).strip() if match else response.strip()
```

### Cloud Providers (Future)

```python
# src/models/cloud_providers.py
class OpenAIWhisperProvider(TranscriptionProvider):
    """OpenAI Whisper API for STT."""

    def __init__(self, api_key: str):
        import openai
        self.client = openai.OpenAI(api_key=api_key)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        # Note: OpenAI API requires file upload (unavoidable)
        # But we minimize by using in-memory buffer
        import io
        import soundfile as sf

        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format='WAV')
        buffer.seek(0)

        response = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer
        )
        return response.text

    def supports_streaming(self) -> bool:
        return False

# Similar for Gemini, GPT-4o-mini cleanup, etc.
```

---

## Configuration System

```python
# src/config/settings.py
import json
from pathlib import Path
from typing import Optional

class Settings:
    """Application settings with persistence."""

    DEFAULT_CONFIG = {
        "hotkey": "alt",
        "stop_cooldown": 0.25,
        "sound_effects_enabled": True,
        "stt_provider": "auto",  # auto-detect based on platform
        "cleanup_provider": "auto",  # auto-detect based on platform
        "cleanup_enabled": False,
        "theme": "system",
        "openai_api_key": None,
        "gemini_api_key": None,
    }

    def __init__(self):
        self.config_dir = Path.home() / ".recordtranscribe"
        self.config_file = self.config_dir / "config.json"
        self.config = self._load()

    def _load(self) -> dict:
        if self.config_file.exists():
            with open(self.config_file) as f:
                return {**self.DEFAULT_CONFIG, **json.load(f)}
        return self.DEFAULT_CONFIG.copy()

    def save(self):
        self.config_dir.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save()
```

---

## Build & Distribution

### Dependencies Update

```toml
# pyproject.toml
[project]
version = "0.5.0"  # Bump for GUI version

dependencies = [
    # Existing dependencies...
    "pynput>=1.8.1",
    "sounddevice>=0.5.2",
    "numpy>=1.26.0",

    # Platform-specific ASR
    "parakeet-mlx>=0.1.0; sys_platform == 'darwin' and platform_machine == 'arm64'",
    "torch>=2.8.0; sys_platform == 'linux'",
    "nemo-toolkit[asr]>=2.0.0; sys_platform == 'linux'",

    # GUI dependencies
    "flet>=0.24.0",
    "pystray>=0.19.5",
    "pillow>=10.0.0",
]

[project.scripts]
recordtranscribe = "record_transcribe:main"            # CLI
recordtranscribe-gui = "record_transcribe_gui:main"    # GUI

[project.optional-dependencies]
cleanup = [
    "mlx-lm>=0.19.0; sys_platform == 'darwin' and platform_machine == 'arm64'",
]
cloud = [
    "openai>=1.0.0",
    "google-generativeai>=0.3.0",
]
```

### Build Scripts

```bash
# build_scripts/build_macos.sh
#!/bin/bash
set -e

echo "Building RecordTranscribe for macOS..."

uv sync --extra cleanup

flet build macos \
  --project "RecordTranscribe" \
  --product "RecordTranscribe" \
  --org "com.recordtranscribe" \
  --build-version "0.5.0" \
  --build-number 1 \
  -o dist/macos

cd dist/macos
zip -r ../RecordTranscribe-0.5.0-macos-arm64.zip RecordTranscribe.app
cd ../..

echo "✅ Build complete: dist/RecordTranscribe-0.5.0-macos-arm64.zip"
```

```bash
# build_scripts/build_linux.sh
#!/bin/bash
set -e

echo "Building RecordTranscribe for Linux..."

uv sync

flet build linux \
  --project "recordtranscribe" \
  --product "RecordTranscribe" \
  --org "com.recordtranscribe" \
  --build-version "0.5.0" \
  --build-number 1 \
  -o dist/linux

cd dist/linux
tar -czf ../RecordTranscribe-0.5.0-linux-x64.tar.gz recordtranscribe
cd ../..

echo "✅ Build complete: dist/RecordTranscribe-0.5.0-linux-x64.tar.gz"
```

### Makefile

```makefile
.PHONY: build-macos build-linux build-all clean run-gui run-cli

build-macos:
	@bash build_scripts/build_macos.sh

build-linux:
	@bash build_scripts/build_linux.sh

build-all: build-macos build-linux

clean:
	rm -rf dist/ build/

run-gui:
	uv run record_transcribe_gui.py

run-cli:
	uv run record_transcribe.py

run-gui-cleanup:
	uv run record_transcribe_gui.py --cleanup
```

---

## Implementation Steps

1. **Extract core logic** (`src/core/`)
   - Move `AudioRecorder` class
   - Move `detect_platform()`, `copy_to_clipboard()`
   - Keep CLI version working

2. **Create model abstraction** (`src/models/`)
   - Base provider interfaces
   - Implement local providers (Parakeet-MLX, NeMo, Qwen)
   - Preserve zero-file-I/O architecture

3. **Create config system** (`src/config/`)
   - Settings class with JSON persistence
   - Default values matching current behavior

4. **Build basic Flet GUI** (`src/gui/`)
   - Main window layout
   - Status indicator with visual states
   - Manual start/stop buttons
   - Connect to core transcription logic

5. **Add system tray** (`src/gui/tray_icon.py`)
   - Tray icon with menu
   - Window minimize/restore
   - Background operation

6. **Implement settings panel** (`src/gui/settings_panel.py`)
   - Model selection (platform-aware)
   - Hotkey configuration
   - API key inputs (encrypted storage)

7. **Add transcription history** (`src/gui/history_panel.py`)
   - JSON storage in `~/.recordtranscribe/`
   - Scrollable list UI
   - Copy functionality

8. **Create build scripts**
   - macOS: `.app` bundle → `.zip`
   - Linux: executable → `.tar.gz`

9. **Test builds**
   - Test on macOS Apple Silicon
   - Test on Linux with CUDA
   - Verify performance (50ms target)

10. **Update documentation**
    - README with GUI instructions
    - CLAUDE.md with new structure
    - Build/release process

---

## Performance Testing Checklist

After implementation, verify these critical performance metrics:

- [ ] macOS transcription latency ≤ 50ms (no file I/O!)
- [ ] macOS cleanup latency ≤ 150ms
- [ ] Linux transcription latency ≤ 100ms
- [ ] No temp files created during transcription
- [ ] Audio stays in memory (numpy → MLX/NeMo)
- [ ] Streaming works on macOS (transcriber initialized at start)
- [ ] Memory usage ≤ 10MB for 30s recording

---

## Release Artifacts

### GitHub Release v0.5.0

```
RecordTranscribe-0.5.0-macos-arm64.zip      (~15-20MB)
├── RecordTranscribe.app/
│   ├── Contents/
│   │   ├── MacOS/recordtranscribe
│   │   ├── Resources/
│   │   └── Info.plist
│   └── Includes Parakeet-MLX, MLX-LM, all dependencies

RecordTranscribe-0.5.0-linux-x64.tar.gz     (~25-30MB)
├── recordtranscribe                        (executable)
├── _internal/                              (dependencies)
└── Includes NeMo, PyTorch, CUDA runtime
```

**Installation:**
- macOS: Unzip, drag to Applications, done
- Linux: Extract, `chmod +x recordtranscribe`, run

---

## Summary

**Key Principles:**
1. ✅ Preserve zero-file-I/O architecture (critical for 50ms speed)
2. ✅ Maintain unified codebase (no platform-specific forks)
3. ✅ Keep CLI version working (backward compatibility)
4. ✅ Platform-specific builds from same code
5. ✅ No new features, just GUI wrapper

**Expected Timeline:** ~13-20 hours for full implementation

**Priority Order:** macOS → Linux → Windows (future)
