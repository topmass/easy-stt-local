import os
import sys
import time
import argparse

# Suppress tokenizer parallelism warning when forking for clipboard
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import from extracted core modules
from src.core.platform_detect import detect_platform
from src.core.clipboard import copy_to_clipboard
from src.core.audio_recorder import AudioRecorder
from src.core.cleanup import load_cleanup_model, load_cleanup_prompt, cleanup_transcription


def is_window_focused():
    """Check if the current console window is focused (Windows only)."""
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes
        foreground_window = ctypes.windll.user32.GetForegroundWindow()
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        return foreground_window == console_window
    except Exception:
        return True


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Real-time speech-to-text transcription')
    parser.add_argument('--cleanup', action='store_true',
                       help='Enable LLM cleanup to remove filler words (requires mlx-lm)')
    args = parser.parse_args()

    # Detect platform and load appropriate backend
    backend, modules = detect_platform()

    # Load cleanup model if requested
    cleanup_model = None
    cleanup_tokenizer = None
    cleanup_prompt = None

    if args.cleanup:
        print("")
        cleanup_model, cleanup_tokenizer = load_cleanup_model()
        cleanup_prompt = load_cleanup_prompt()
        print("✨ Cleanup enabled: transcriptions will be cleaned of filler words")
        print("")

    recorder = AudioRecorder(
        backend,
        modules,
        enable_cleanup=args.cleanup,
        cleanup_model=cleanup_model,
        cleanup_tokenizer=cleanup_tokenizer,
        cleanup_prompt=cleanup_prompt
    )

    # Allow changing the hotkey via env vars to avoid conflicts
    hotkey = os.getenv("RT_HOTKEY", "alt").strip().lower()  # e.g., 'f9', 'alt', 'caps_lock', 's'

    print(f"Hotkey: double-press '{hotkey}' to start; single-press '{hotkey}' to stop.")
    print("Quit: use Ctrl+C to exit.")

    last_alt_press_time = 0.0
    double_tap_threshold = 0.3  # seconds
    running = True
    stop_cooldown = float(os.getenv("RT_STOP_COOLDOWN", "0.25"))
    stop_armed_at = 0.0

    if sys.platform.startswith("win"):
        # Use 'keyboard' on Windows
        import keyboard  # type: ignore

        def on_key_event(event):
            nonlocal last_alt_press_time, running, stop_armed_at
            if event.event_type != 'down':
                return

            name = (event.name or '').lower()
            target = hotkey.replace('_', ' ')

            if name == target:
                current_time = time.time()
                if recorder.recording:
                    if current_time >= stop_armed_at:
                        transcription = recorder.stop_recording()
                        if transcription:
                            # Apply cleanup if enabled
                            text_to_copy = transcription
                            if recorder.enable_cleanup and transcription:
                                try:
                                    cleaned_text = cleanup_transcription(
                                        transcription,
                                        recorder.cleanup_model,
                                        recorder.cleanup_tokenizer,
                                        recorder.cleanup_prompt
                                    )
                                    text_to_copy = cleaned_text
                                except Exception as e:
                                    print(f"Warning: Cleanup failed: {e}")
                                    print("Using raw transcription instead.")

                            # Copy to clipboard
                            if text_to_copy:
                                if copy_to_clipboard(text_to_copy):
                                    if recorder.enable_cleanup:
                                        print("\n✅ Cleaned transcription copied to clipboard!")
                                    else:
                                        print("\n✅ Transcription copied to clipboard!")
                                else:
                                    print("Clipboard unavailable. See README for options.")

                                # Play stop sound after transcription is copied
                                recorder.play_sound(recorder.stop_sound)
                    last_alt_press_time = 0.0
                elif current_time - last_alt_press_time < double_tap_threshold:
                    recorder.start_recording()
                    # Arm stop only after a short cooldown to avoid bounce
                    stop_armed_at = time.time() + stop_cooldown
                    last_alt_press_time = 0.0
                else:
                    last_alt_press_time = current_time

        keyboard.on_press(on_key_event)

        while running:
            time.sleep(0.1)
    else:
        # Use 'pynput' on Linux/macOS to avoid root and work on mac
        from pynput import keyboard as pynput_keyboard  # type: ignore

        # Build a matcher for the configured hotkey
        special = {
            'alt': {pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r},
            'ctrl': {pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r},
            'shift': {pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r},
            'caps_lock': {pynput_keyboard.Key.caps_lock},
            'f8': {pynput_keyboard.Key.f8},
            'f9': {pynput_keyboard.Key.f9},
            'f10': {pynput_keyboard.Key.f10},
        }

        def is_hotkey(k) -> bool:
            hk = hotkey
            if hk in special:
                return k in special[hk]
            # Single character keys
            if isinstance(k, pynput_keyboard.KeyCode) and k.char:
                return k.char.lower() == hk
            return False

        def on_press(key):
            nonlocal last_alt_press_time, running, stop_armed_at

            if is_hotkey(key):
                current_time = time.time()
                if recorder.recording:
                    if current_time >= stop_armed_at:
                        transcription = recorder.stop_recording()
                        if transcription:
                            # Apply cleanup if enabled
                            text_to_copy = transcription
                            if recorder.enable_cleanup and transcription:
                                try:
                                    cleaned_text = cleanup_transcription(
                                        transcription,
                                        recorder.cleanup_model,
                                        recorder.cleanup_tokenizer,
                                        recorder.cleanup_prompt
                                    )
                                    text_to_copy = cleaned_text
                                except Exception as e:
                                    print(f"Warning: Cleanup failed: {e}")
                                    print("Using raw transcription instead.")

                            # Copy to clipboard
                            if text_to_copy:
                                if copy_to_clipboard(text_to_copy):
                                    if recorder.enable_cleanup:
                                        print("\n✅ Cleaned transcription copied to clipboard!")
                                    else:
                                        print("\n✅ Transcription copied to clipboard!")
                                else:
                                    print("Clipboard unavailable. See README for options.")

                                # Play stop sound after transcription is copied
                                recorder.play_sound(recorder.stop_sound)
                    last_alt_press_time = 0.0
                elif current_time - last_alt_press_time < double_tap_threshold:
                    recorder.start_recording()
                    # Arm stop only after a short cooldown to avoid bounce
                    stop_armed_at = time.time() + stop_cooldown
                    last_alt_press_time = 0.0
                else:
                    last_alt_press_time = current_time
            else:
                pass  # No other key actions needed

        listener = pynput_keyboard.Listener(on_press=on_press)
        listener.start()
        try:
            while running:
                time.sleep(0.1)
        finally:
            listener.stop()
            listener.join()

if __name__ == "__main__":
    main()
