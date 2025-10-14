import os
import sys
import time
import numpy as np
import sounddevice as sd
from nemo.collections.asr.models import ASRModel
import torch
import pyperclip
import subprocess
import platform


class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.sample_rate = 16000  # ASR models expect 16kHz

        # NeMo will automatically use GPU if available
        print("NeMo will automatically detect and use available GPU")

        # Sound effect paths
        self.start_sound = os.path.join("soundfx", "start.mp3")
        self.stop_sound = os.path.join("soundfx", "stop.mp3")

        # Load NeMo ASR model
        print("Loading NeMo ASR model...")
        self.model = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v2")
        self.model.eval()
        print("Model loaded!")


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

    def start_recording(self):
        """Start the recording process."""
        if not self.recording:
            # Play start sound
            self.play_sound(self.start_sound)
                
            print("Recording started... Press left alt once to stop.")
            self.audio_data = []
            self.recording = True
            
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
                    # Save to temporary WAV file (minimal approach)
                    # NeMo's transcribe() method expects file paths
                    import tempfile
                    import soundfile as sf

                    print("Transcribing audio...")

                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                        temp_path = tmp_file.name
                        # Write audio using soundfile (supports float32 directly)
                        sf.write(temp_path, audio_float32, self.sample_rate)

                    try:
                        # Transcribe using file path
                        hypotheses = self.model.transcribe([temp_path])

                        # Extract text from NeMo output
                        full_transcription = ""
                        if hypotheses and len(hypotheses) > 0:
                            hypothesis = hypotheses[0]
                            full_transcription = hypothesis.text if hasattr(hypothesis, 'text') else str(hypothesis)

                        # Print transcription
                        print("\nTranscription:")
                        print("-" * 50)
                        print(full_transcription)
                        print("-" * 50)

                        # Copy to clipboard
                        if full_transcription:
                            if copy_to_clipboard(full_transcription):
                                print("Transcription copied to clipboard!")
                            else:
                                print("Clipboard unavailable. See README for options.")

                            # Play stop sound after transcription is copied
                            self.play_sound(self.stop_sound)
                    finally:
                        # Clean up temp file
                        try:
                            os.remove(temp_path)
                        except:
                            pass

                except Exception as e:
                    print(f"Error during transcription: {str(e)}")
                    import traceback
                    traceback.print_exc()
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
    
    # For Wayland systems
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        try:
            subprocess.run(['wl-copy'], input=text.encode(), check=True)
            print("Copied to clipboard using wl-copy")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("wl-copy not found. Install with: sudo pacman -S wl-clipboard")
            return False
    
    # For X11 systems  
    else:
        try:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
            print("Copied to clipboard using xclip")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("xclip not found. Install with: sudo pacman -S xclip")
            return False

def main():
    recorder = AudioRecorder()

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
