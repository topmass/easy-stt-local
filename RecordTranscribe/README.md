# RecordTranscribe - SwiftUI Native App

A native macOS menu bar application for voice transcription using local ML models.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RecordTranscribe.app                      │
├─────────────────────────────────────────────────────────────┤
│  SwiftUI Interface          │  Bundled Python Environment   │
│  ─────────────────          │  ──────────────────────────   │
│  • Menu bar UI              │  • Python 3.12 runtime        │
│  • Hotkey handling          │  • MLX framework              │
│  • Audio recording          │  • Parakeet STT model         │
│  • Settings                 │  • Qwen cleanup model         │
│                             │                               │
│         ◄── JSON/stdin ──►  │  transcription_service.py    │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Xcode 15+** - Install from the Mac App Store
2. **uv** - Python package manager
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **Apple Silicon Mac** (M1/M2/M3/M4) - Required for MLX models

## Building

### Step 1: Open in Xcode

```bash
open RecordTranscribe.xcodeproj
```

### Step 2: Build the App

In Xcode:
1. Select **Product → Build** (or ⌘B)
2. Wait for the build to complete

### Step 3: Bundle Python

```bash
cd Scripts
./bundle_python.sh
```

This creates a standalone Python environment with all dependencies.

### Step 4 (Optional): Pre-download Models

To include models in the app bundle (larger but works offline):

```bash
./bundle_python.sh --with-models
```

Without this flag, models will download on first launch (~1.5GB).

### Step 5: Create DMG for Distribution

```bash
./create_dmg.sh
```

## Development

### Running from Xcode

During development, the app will look for Python in:
1. The bundled environment (if present)
2. The parent project's `.venv` directory
3. System Python (not recommended)

For the best development experience:
1. Build and run in Xcode
2. Keep the original project's venv available

### Project Structure

```
RecordTranscribe/
├── RecordTranscribe.xcodeproj/
├── RecordTranscribe/
│   ├── RecordTranscribeApp.swift    # App entry point
│   ├── RecordTranscribe.entitlements
│   ├── Views/
│   │   ├── MenuBarView.swift        # Main menu bar UI
│   │   └── SettingsView.swift       # Settings window
│   ├── Services/
│   │   ├── TranscriptionService.swift  # Python bridge
│   │   ├── AudioRecorder.swift         # Audio capture
│   │   └── HotkeyManager.swift         # Global hotkeys
│   └── Resources/
│       └── Assets.xcassets
├── PythonService/
│   └── transcription_service.py     # Python ML backend
└── Scripts/
    ├── bundle_python.sh             # Bundle Python into .app
    └── create_dmg.sh                # Create installer DMG
```

## Usage

1. **Launch** - The app appears in your menu bar (microphone icon)
2. **Record** - Double-tap Option (⌥) to start recording
3. **Stop** - Single tap Option to stop and transcribe
4. **Result** - Transcription is automatically copied to clipboard

## Settings

Access settings via the gear icon in the menu bar popover:

- **LLM Cleanup** - Enable/disable grammar cleanup
- **Auto-copy** - Automatically copy to clipboard
- **Feedback sounds** - Play audio feedback
- **Hotkey** - Change activation key

## Troubleshooting

### "Python not found" error

Run the bundle script:
```bash
cd Scripts && ./bundle_python.sh
```

### "Microphone access denied"

Grant microphone access in System Settings → Privacy & Security → Microphone

### Models downloading slowly

Pre-download models for offline use:
```bash
./bundle_python.sh --with-models
```

### App blocked by security software

The app should be properly signed if you have an Apple Developer account.
For unsigned builds, right-click and select "Open" to bypass Gatekeeper.

## License

MIT License - See parent project for details.
