# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RecordTranscribe** is a cross-platform voice recording and transcription tool using local ASR models. It features:
- Double-tap hotkey activation for hands-free recording
- Streaming ASR transcription (Parakeet models)
- Optional LLM cleanup to remove filler words and structure output
- Automatic clipboard integration
- Platform-specific optimizations (macOS Apple Silicon, Linux CUDA)

**Current branch:** `unified-cross-platform-streaming` (development)
**Main branch:** `main`

## Development Commands

### Setup
```bash
# Install uv package manager (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Install optional LLM cleanup (macOS Apple Silicon only)
uv sync --extra cleanup

# Linux only: Install clipboard support
# Wayland: sudo pacman -S wl-clipboard (or apt/dnf equivalent)
# X11: sudo pacman -S xclip (or apt/dnf equivalent)
```

### Running the Application
```bash
# Standard mode
uv run record_transcribe.py

# With LLM cleanup enabled
uv run record_transcribe.py --cleanup

# Custom hotkey (e.g., F9 instead of Alt)
RT_HOTKEY=f9 uv run record_transcribe.py

# Adjust stop cooldown
RT_STOP_COOLDOWN=0.5 uv run record_transcribe.py
```

### Dependency Management
```bash
# Add a new dependency (all platforms)
uv add package-name

# Add platform-specific dependency
# Edit pyproject.toml manually with markers:
# "package>=1.0; sys_platform == 'linux'"
# "package>=1.0; sys_platform == 'darwin' and platform_machine == 'arm64'"

# Remove a dependency
uv remove package-name

# Update all dependencies
uv sync --upgrade
```

## Architecture

### Core Philosophy
The codebase maintains a **unified cross-platform architecture** with 86% shared code (~299 lines) and only 14% platform-specific code (~50 lines). This approach:
- Eliminates code duplication across platforms
- Ensures bug fixes and features benefit all platforms simultaneously
- Uses Python's conditional dependency markers for automatic platform-specific installation
- Follows industry standards (PyTorch, TensorFlow, NumPy patterns)

See `ARCHITECTURE.md` for detailed justification of this design decision.

### Platform-Specific Models & Optimization

The application uses different ASR backends optimized for each platform's hardware capabilities.

#### macOS Apple Silicon (M1/M2/M3/M4)

**Detection:** `platform.system() == "Darwin" and platform.machine() == "arm64"`

**STT Model:**
- Framework: Parakeet-MLX (Apple MLX framework)
- Model: `mlx-community/parakeet-tdt-0.6b-v3`
- Size: ~600MB
- Key Feature: **Streaming transcription** during recording
- Performance: ~50ms latency
- Sample Rate: 16000 Hz (auto-detected from model config)

**Cleanup Model (Optional):**
- Framework: MLX-LM
- Model: `mlx-community/Qwen2.5-1.5B-Instruct-4bit`
- Size: ~1.5GB
- Quantization: 4-bit for faster inference
- Performance: ~150ms for cleanup
- Total latency: ~200ms (STT + cleanup)

**Why MLX?**
- Native Apple Silicon optimization (faster than PyTorch on Mac)
- Unified memory architecture = no CPU↔GPU data transfers
- Metal acceleration built-in
- Lower power consumption
- Zero file I/O required (direct array processing)

**Code References:**
- Platform detection: `record_transcribe.py:88-102`
- Model initialization: `record_transcribe.py:141-148`
- Streaming setup: `record_transcribe.py:199-203`
- Transcription: `record_transcribe.py:231-247`

#### Linux (NVIDIA GPU)

**Detection:** `platform.system() == "Linux"`

**STT Model:**
- Framework: NVIDIA NeMo
- Model: `nvidia/parakeet-tdt-0.6b-v2`
- Size: ~600MB
- Key Feature: GPU-accelerated batch transcription
- Performance: ~50-100ms latency (GPU dependent)
- Requires: CUDA-capable NVIDIA GPU (~2GB VRAM minimum)

**Cleanup Model:**
- Framework: PyTorch + transformers + bitsandbytes (CUDA accelerated)
- Model: Same Qwen2.5-1.5B-Instruct (4-bit quantization)
- Alternative: Phi-3-mini for CPU-only systems
- Performance: ~100-200ms on modern NVIDIA GPUs
- Status: To be implemented (currently use cloud providers)

**Why NeMo?**
- Production-grade ASR from NVIDIA
- Excellent CUDA optimization with automatic GPU detection
- Direct numpy array input (no file I/O!)
- Well-maintained and actively developed

**Code References:**
- Platform detection: `record_transcribe.py:104-114`
- Model initialization: `record_transcribe.py:150-156`
- Transcription: `record_transcribe.py:249-258`

#### Windows

**Status:** Not fully supported (future priority)

**Challenges:**
- NeMo requires WSL2 or complex Windows CUDA setup
- No native MLX support (Apple Silicon only)
- Keyboard library differences (`keyboard` vs `pynput`)

**Recommended Approach:**
- Document WSL2 setup for Linux path
- OR: Use PyTorch + Whisper alternative in future

#### Conditional Imports Pattern

Platform-specific modules are only imported on their target platforms:

```python
if backend == "parakeet-mlx":
    import mlx.core as mx
    from parakeet_mlx import from_pretrained
elif backend == "nemo":
    from nemo.collections.asr.models import ASRModel
    import torch
```

This prevents dependency errors and keeps package sizes minimal per platform.

### File Structure
```
record_transcribe.py          # Main application (479 lines)
├── Platform detection        # Lines 88-119
├── AudioRecorder class       # Lines 158-306
├── Transcription backends    # Lines 141-156
└── Hotkey handling           # Lines 384-476

cleanup_prompt.txt            # LLM cleanup prompt (PARA framework)
pyproject.toml               # Dependencies and project metadata
soundfx/                     # Audio feedback (start.mp3, stop.mp3)
```

### Platform-Specific Backends

**macOS Apple Silicon (M1/M2/M3/M4):**
- Model: `mlx-community/parakeet-tdt-0.6b-v3`
- Framework: Parakeet-MLX (streaming capability)
- Optimization: MLX framework for Apple Silicon
- No file I/O required (streams audio chunks)

**Linux:**
- Model: `nvidia/parakeet-tdt-0.6b-v2`
- Framework: NVIDIA NeMo with CUDA acceleration
- Optimization: GPU-accelerated transcription
- Direct numpy array input (no file I/O)

**Windows:**
- Uses `keyboard` library instead of `pynput` for hotkey handling
- Other platforms use `pynput` for cross-platform keyboard events

### Key Components

**Platform Detection (lines 88-119):**
- Detects OS and architecture at runtime
- Returns appropriate backend configuration
- Raises error for unsupported platforms

**AudioRecorder Class (lines 158-306):**
- `start_recording()`: Initializes audio stream, plays start sound, sets up streaming transcriber
- Recording callback: Continuously captures audio frames
- `stop_recording()`: Processes audio, transcribes, optionally cleans up, copies to clipboard
- Platform-specific transcription calls based on detected backend

**Hotkey Handling (lines 384-476):**
- Double-tap detection with 300ms threshold to start recording
- Single tap to stop recording
- Cooldown period (default 0.25s) prevents accidental re-triggers
- Different implementations for Linux/macOS (pynput) vs Windows (keyboard)

**Clipboard Integration (lines 320-351):**
- macOS: `pbcopy` command
- Linux Wayland: `wl-copy`
- Linux X11: `xclip`
- Automatic platform detection and fallback

**LLM Cleanup (optional):**
- Model: Qwen2.5-1.5B-Instruct-4bit (switched from DeepSeek R1)
- Uses PARA framework: Point, Action, Result, Ask
- Removes filler words, fixes grammar, structures output
- ~150ms processing time on Apple Silicon
- Controlled via `cleanup_prompt.txt`

## Important Patterns

### Conditional Imports
Platform-specific modules are imported conditionally to avoid dependency errors:
```python
if platform.system() == "Darwin" and platform.machine() == "arm64":
    from parakeet_mlx import StreamingParakeet
elif platform.system() == "Linux":
    import nemo.collections.asr as nemo_asr
```

### Platform-Specific Dependencies
Use environment markers in `pyproject.toml`:
```toml
dependencies = [
    "parakeet-mlx>=0.1.0; sys_platform == 'darwin' and platform_machine == 'arm64'",
    "nemo-toolkit[asr]>=2.0.0; sys_platform == 'linux'",
]
```

### Error Handling
- Graceful fallbacks for missing audio effects
- Comprehensive exception handling during transcription
- Clear error messages for unsupported platforms
- Clipboard availability checks before copying

## Common Workflows

### Adding a New Feature
1. Implement in shared code section (avoid platform-specific if possible)
2. If platform-specific, add to appropriate backend detection section
3. Test on all supported platforms (macOS, Linux, Windows)
4. Update relevant documentation (README.md, this file)

### Changing ASR Models
1. Update model path in `detect_platform()` function (lines 88-119)
2. Update model name in `main()` initialization (lines 353-382)
3. Test transcription quality
4. Update documentation with new model details

### Modifying LLM Cleanup Behavior
1. Edit `cleanup_prompt.txt` with new instructions
2. Adjust `max_tokens` in `stop_recording()` if needed (currently 2048)
3. Test with various speech patterns
4. Consider token limits for very long transcriptions

### Debugging Recording Issues
- Check audio device availability: `python -c "import sounddevice; print(sounddevice.query_devices())"`
- Verify hotkey conflicts: Try different key with `RT_HOTKEY=f9`
- Test audio capture: Monitor terminal output during recording
- Check backend initialization errors in startup logs

## Dependencies

### Core (all platforms)
- `pynput>=1.8.1` - Keyboard event listening (Linux/macOS)
- `sounddevice>=0.5.2` - Audio input capture
- `numpy>=1.26.0` - Audio array processing

### macOS Apple Silicon
- `parakeet-mlx>=0.1.0` - Streaming ASR model
- `mlx-lm>=0.19.0` - LLM cleanup (optional, via `--extra cleanup`)

### Linux
- `torch>=2.8.0`, `torchaudio>=2.8.0`, `torchvision>=0.23.0` - PyTorch ecosystem
- `nemo-toolkit[asr]>=2.0.0` - NVIDIA NeMo ASR
- `soundfile>=0.12.1` - Audio file I/O
- `cuda-python>=12.3,<13.0` - GPU acceleration

### System Requirements
- Python >=3.12
- NVIDIA GPU with CUDA support (Linux)
- Apple Silicon M1/M2/M3/M4 (macOS, recommended)
- 2-4GB RAM for ASR models

## Configuration

### Environment Variables
- `RT_HOTKEY` - Change activation hotkey (default: "alt")
- `RT_STOP_COOLDOWN` - Debounce time for stop action (default: 0.25s)
- `TOKENIZERS_PARALLELISM` - Set to "false" to suppress tokenizer warnings

### Hotkey Options
Common alternatives to avoid conflicts:
- `f9`, `f10`, `f11`, `f12` - Function keys
- `ctrl_l`, `ctrl_r` - Control keys
- `shift` - Shift key
- Check pynput documentation for full key names

## Recent Development Focus

Recent commits show active work on:
1. **LLM cleanup optimization** - Switched from DeepSeek R1 to Qwen2.5-1.5B for better performance
2. **PARA framework integration** - Structured output format for cleaned transcriptions
3. **Token limit handling** - Increased to 2048 for long transcriptions
4. **Streaming improvements** - Refined audio chunk processing for Parakeet-MLX

## Code Style

- Single entry point: `record_transcribe.py`
- Class-based design for AudioRecorder
- Platform detection via runtime checks, not separate codebases
- Minimal external files (only audio effects and prompt template)
- Clear separation between platform-agnostic and platform-specific code
- No testing framework currently in place (manual testing workflow)

## Performance Considerations

### Critical Performance Optimization: Zero File I/O

**IMPORTANT:** The application achieves near-instant transcription (~50ms) by completely avoiding file I/O operations. This is a core architectural decision that must be preserved.

#### How It Works

**Traditional (Slow) Approach:**
1. Record audio to memory
2. Write audio to temp file (`.wav`, `.mp3`)
3. Read file from disk
4. Pass file path to model
5. Model reads file again
**Total overhead:** 100-500ms+ depending on disk speed

**Our (Fast) Approach:**
1. Record audio directly to numpy array in memory
2. Convert to model-specific format (MLX array or keep as numpy)
3. Pass memory array directly to model
**Total overhead:** <5ms (just array conversion)

#### Implementation Details

**macOS (Parakeet-MLX) - Streaming:**
```python
# record_transcribe.py:231-247
# Audio captured in memory via sounddevice callback
audio_float32 = np.concatenate(self.audio_data).flatten().astype(np.float32)

# Convert numpy → MLX array (in-memory, no I/O)
audio_mlx = mx.array(audio_float32)

# Stream directly to model (already initialized during recording start)
self.transcriber.add_audio(audio_mlx)
result = self.transcriber.result.text.strip()
```

**Linux (NeMo) - Direct Array Transcription:**
```python
# record_transcribe.py:249-258
# Audio captured in memory via sounddevice callback
audio_float32 = np.concatenate(self.audio_data).flatten().astype(np.float32)

# NeMo accepts numpy arrays directly (no file I/O!)
hypotheses = self.model.transcribe(audio=[audio_float32])
transcription = hypotheses[0].text
```

#### Why This Matters

- **Speed:** File I/O is 10-100x slower than memory operations
- **macOS with Apple Silicon:** Unified memory architecture makes this even faster (no CPU↔GPU copies)
- **Real-time feel:** Users experience ~50ms latency (feels instant)
- **Disk wear:** No temporary file writes (better for SSDs)

#### When Refactoring for GUI

**DO:**
- Keep audio in numpy arrays throughout pipeline
- Pass arrays directly to transcription models
- Only convert format when required by model (numpy → MLX)

**DON'T:**
- Write audio to temp files (e.g., `tempfile.mktemp()`)
- Use file-based audio libraries (like `librosa.load()`)
- Save intermediate audio states to disk

**Example - Preserving Performance in GUI:**
```python
# GOOD: Keep in-memory pipeline
class TranscriptionProvider:
    def transcribe(self, audio: np.ndarray) -> str:
        # Direct array processing
        return self.model.transcribe(audio)

# BAD: Introduces file I/O bottleneck
class TranscriptionProvider:
    def transcribe(self, audio: np.ndarray) -> str:
        temp_file = "temp_audio.wav"
        soundfile.write(temp_file, audio, 16000)  # SLOW!
        return self.model.transcribe(temp_file)
```

### Performance Metrics

- **Transcription latency:** ~50ms (Parakeet streaming, zero file I/O)
- **Cleanup latency:** ~150ms (Qwen2.5-1.5B on Apple Silicon)
- **Total with cleanup:** ~200ms (still feels instant)
- **Memory overhead:** ~5-10MB for typical 30s recording
- Streaming transcription starts processing during recording for faster results
- Audio chunks are processed in real-time on macOS (Parakeet-MLX)
