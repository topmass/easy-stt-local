# Recordtranscribe

A voice recording and transcription tool using NVIDIA NeMo ASR models.

## Quick Start

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Install clipboard support** (Linux only):
   ```bash
   # Wayland users
   sudo pacman -S wl-clipboard    # Arch/Manjaro
   sudo apt install wl-clipboard  # Ubuntu/Debian  
   sudo dnf install wl-clipboard  # Fedora
   
   # X11 users  
   sudo pacman -S xclip          # Arch/Manjaro
   sudo apt install xclip        # Ubuntu/Debian
   sudo dnf install xclip        # Fedora
   ```

4. **Run:**
   ```bash
   uv run record_transcribe.py
   ```

## Usage

- **Start recording:** Double-press Alt key
- **Stop recording:** Single-press Alt key  
- **Quit:** Ctrl+C
- **Output:** Transcription automatically copied to clipboard

## Customization

Change hotkey to avoid conflicts:
```bash
RT_HOTKEY=f9 uv run record_transcribe.py
```

## Requirements

- NVIDIA GPU with CUDA support
- Linux, Windows, or macOS