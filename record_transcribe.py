import os
import sys
import time
import numpy as np
import sounddevice as sd
import subprocess
import platform
import argparse


def load_cleanup_model():
    """Load DeepSeek R1 Distill for text cleanup."""
    try:
        from mlx_lm import load
        print("Loading DeepSeek-R1-Distill-Qwen-1.5B for cleanup...")
        model, tokenizer = load("mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit")
        print("Cleanup model loaded!")
        return model, tokenizer
    except ImportError:
        print("mlx-lm not installed. Install with: uv pip install mlx-lm")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to load cleanup model: {e}")
        sys.exit(1)


def load_cleanup_prompt():
    """Load the cleanup prompt from file."""
    prompt_file = "cleanup_prompt.txt"
    try:
        with open(prompt_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback default prompt
        return "Remove filler words (um, uh, ah, like, you know) and clean up this transcription while keeping the exact meaning. Output only the cleaned text."


def cleanup_transcription(text, model, tokenizer, base_prompt):
    """Clean up transcription using DeepSeek R1 Distill with streaming."""
    from mlx_lm import stream_generate

    prompt = f"{base_prompt}\n\nTranscription:\n{text}\n\nCleaned:"

    # Stream tokens and build up the cleaned text
    cleaned_text = ""
    print("\nCleaned transcription (streaming):")
    print("-" * 50)

    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=1024,
        temperature=0.3  # Lower temperature for more consistent cleanup
    ):
        # Print each token as it arrives
        print(response.text, end="", flush=True)
        cleaned_text = response.text

    print()  # New line after streaming
    print("-" * 50)

    return cleaned_text.strip()


def detect_platform():
    """Detect the platform and available ASR backend."""
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


class AudioRecorder:
    def __init__(self, backend, modules, enable_cleanup=False, cleanup_model=None, cleanup_tokenizer=None, cleanup_prompt=None):
        self.recording = False
        self.audio_data = []
        self.backend = backend
        self.sample_rate = 16000  # Standard ASR sample rate
        self.transcriber = None  # For streaming transcription (Parakeet-MLX)

        # Cleanup configuration
        self.enable_cleanup = enable_cleanup
        self.cleanup_model = cleanup_model
        self.cleanup_tokenizer = cleanup_tokenizer
        self.cleanup_prompt = cleanup_prompt

        # Sound effect paths
        self.start_sound = os.path.join("soundfx", "start.mp3")
        self.stop_sound = os.path.join("soundfx", "stop.mp3")

        # Initialize the appropriate backend
        if backend == "parakeet-mlx":
            from_pretrained = modules
            self.model_name = "mlx-community/parakeet-tdt-0.6b-v3"
            print(f"Loading Parakeet-MLX model ({self.model_name})...")
            self.model = from_pretrained(self.model_name)
            # Use the model's expected sample rate
            self.sample_rate = self.model.preprocessor_config.sample_rate
            print(f"Parakeet-MLX model loaded! Sample rate: {self.sample_rate}Hz")

        elif backend == "nemo":
            ASRModel, torch = modules
            print("Loading NeMo ASR model...")
            print("NeMo will automatically detect and use available GPU")
            self.model = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v2")
            self.model.eval()
            print("NeMo model loaded!")


    def play_sound(self, sound_file):
        """Play a sound file using system audio player."""
        if not os.path.exists(sound_file):
            return
        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.Popen(["afplay", sound_file],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            elif system == "Linux":
                # Try multiple Linux audio players
                for player in ["paplay", "aplay", "ffplay"]:
                    try:
                        subprocess.Popen([player, sound_file],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
            elif system == "Windows":
                import winsound
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass  # Silently fail if sound can't play

    def callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_data.extend(indata.copy())

            # Stream audio chunks to Parakeet-MLX in real-time
            if self.backend == "parakeet-mlx" and self.transcriber:
                try:
                    import mlx.core as mx
                    # Convert chunk to MLX and stream it
                    audio_chunk = indata.flatten().astype(np.float32)
                    audio_mlx = mx.array(audio_chunk)
                    self.transcriber.add_audio(audio_mlx)
                except Exception as e:
                    # Silently fail - we'll fallback to batch processing
                    pass

    def start_recording(self):
        """Start the recording process."""
        if not self.recording:
            # Play start sound
            self.play_sound(self.start_sound)

            print("Recording started... Press left alt once to stop.")
            self.audio_data = []
            self.recording = True

            # Initialize streaming transcriber for parakeet-mlx
            if self.backend == "parakeet-mlx":
                # Context size: (left_context, right_context) in frames
                self.transcriber = self.model.transcribe_stream(context_size=(256, 256))
                self.transcriber.__enter__()

            # Start recording stream
            self.stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                callback=self.callback
            )
            self.stream.start()
    
    def stop_recording(self):
        """Stop the recording and process the audio."""
        if self.recording:
            print("Recording stopped. Transcribing...")
            self.recording = False
            self.stream.stop()
            self.stream.close()

            # Process audio data
            if len(self.audio_data) > 0:
                # Concatenate and convert to float32
                audio_array = np.concatenate(self.audio_data, axis=0).flatten()
                audio_float32 = audio_array.astype(np.float32)

                try:
                    print("Transcribing audio...")

                    # Transcribe based on backend
                    if self.backend == "parakeet-mlx":
                        # Parakeet-MLX: Audio was already streamed during recording
                        # Just get the final result
                        result = self.transcriber.result
                        full_transcription = result.text.strip()
                        # Close the streaming context
                        self.transcriber.__exit__(None, None, None)
                        self.transcriber = None

                    elif self.backend == "nemo":
                        # NeMo: Use direct array transcription (no file I/O!)
                        # NeMo accepts numpy arrays directly as a list
                        hypotheses = self.model.transcribe(audio=[audio_float32])

                        # Extract text from NeMo output
                        full_transcription = ""
                        if hypotheses and len(hypotheses) > 0:
                            hypothesis = hypotheses[0]
                            full_transcription = hypothesis.text if hasattr(hypothesis, 'text') else str(hypothesis)

                    # Show raw transcription
                    print("\nRaw transcription:")
                    print("-" * 50)
                    print(full_transcription)
                    print("-" * 50)

                    # Apply cleanup if enabled
                    text_to_copy = full_transcription
                    if self.enable_cleanup and full_transcription:
                        try:
                            cleaned_text = cleanup_transcription(
                                full_transcription,
                                self.cleanup_model,
                                self.cleanup_tokenizer,
                                self.cleanup_prompt
                            )
                            text_to_copy = cleaned_text
                        except Exception as e:
                            print(f"Warning: Cleanup failed: {e}")
                            print("Using raw transcription instead.")

                    # Copy to clipboard (cleaned version if cleanup enabled, otherwise raw)
                    if text_to_copy:
                        if copy_to_clipboard(text_to_copy):
                            if self.enable_cleanup:
                                print("\n✅ Cleaned transcription copied to clipboard!")
                            else:
                                print("\n✅ Transcription copied to clipboard!")
                        else:
                            print("Clipboard unavailable. See README for options.")

                        # Play stop sound after transcription is copied
                        self.play_sound(self.stop_sound)

                except Exception as e:
                    print(f"Error during transcription: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Clean up transcriber if error occurs
                    if self.backend == "parakeet-mlx" and self.transcriber:
                        try:
                            self.transcriber.__exit__(None, None, None)
                        except:
                            pass
                        self.transcriber = None
            else:
                print("No audio recorded!")

def is_window_focused():
    """Check if the current console window is focused (Windows only)."""
    if not sys.platform.startswith("win"):
        return True
    try:
        foreground_window = ctypes.windll.user32.GetForegroundWindow()
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        return foreground_window == console_window
    except Exception:
        return True


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using system clipboard command."""
    import subprocess
    import os

    # macOS: use pbcopy (built-in)
    if platform.system() == "Darwin":
        try:
            subprocess.run(['pbcopy'], input=text.encode(), check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    # Linux: For Wayland systems
    elif os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        try:
            subprocess.run(['wl-copy'], input=text.encode(), check=True)
            print("Copied to clipboard using wl-copy")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("wl-copy not found. Install with: sudo pacman -S wl-clipboard")
            return False

    # Linux: For X11 systems
    else:
        try:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
            print("Copied to clipboard using xclip")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("xclip not found. Install with: sudo pacman -S xclip")
            return False

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
                        recorder.stop_recording()
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
                        recorder.stop_recording()
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
