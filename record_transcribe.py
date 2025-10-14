import sounddevice as sd
import numpy as np
import time
import os
import sys
import platform
import pyperclip  # For clipboard functionality
from pynput import keyboard
import subprocess

def detect_platform():
    """Detect the platform and available acceleration."""
    system = platform.system()
    machine = platform.machine()

    # Check for Apple Silicon (M1/M2/M3) - prefer Parakeet-MLX
    if system == "Darwin" and machine == "arm64":
        try:
            from parakeet_mlx import from_pretrained
            print("Detected: Apple Silicon with Parakeet-MLX support")
            return "parakeet-mlx", from_pretrained
        except ImportError:
            print("Apple Silicon detected but Parakeet-MLX not installed.")
            print("Install with: uv pip install parakeet-mlx")
            sys.exit(1)

    # Check for CUDA
    try:
        import torch
        if torch.cuda.is_available():
            try:
                import whisperx
                print("Detected: CUDA GPU with WhisperX support")
                return "cuda", (torch, whisperx)
            except ImportError:
                print("CUDA detected but WhisperX not installed.")
                print("Install with: uv pip install -e '.[cuda]'")
                sys.exit(1)
    except ImportError:
        pass

    # Fallback to CPU
    try:
        import torch
        import whisper
        print("Detected: CPU-only mode with OpenAI Whisper")
        return "cpu", (torch, whisper)
    except ImportError:
        print("No Whisper backend found.")
        print("Install with: uv pip install -e '.[cpu]'")
        sys.exit(1)

class AudioRecorder:
    def __init__(self, backend, modules):
        self.recording = False
        self.audio_data = []
        self.backend = backend
        self.sample_rate = 16000  # Standard ASR sample rate
        self.transcriber = None  # For streaming transcription

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

        elif backend == "cuda":
            self.torch, self.whisperx = modules
            print("Loading WhisperX model for CUDA...")
            self.model = self.whisperx.load_model(
                "large-v2",
                device="cuda",
                compute_type="float16"
            )
            print("WhisperX model loaded!")

        elif backend == "cpu":
            self.torch, self.whisper = modules
            print("Loading Whisper model for CPU...")
            self.model = self.whisper.load_model("base.en")
            print("Whisper model loaded!")

    def play_sound(self, sound_file):
        """Play a sound file using system audio."""
        if not os.path.exists(sound_file):
            return
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.Popen(["afplay", sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif platform.system() == "Linux":
                # Try multiple Linux audio players
                for player in ["paplay", "aplay", "ffplay"]:
                    try:
                        subprocess.Popen([player, sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
            elif platform.system() == "Windows":
                import winsound
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
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
                audio_array = np.concatenate(self.audio_data, axis=0).flatten()
                # Convert to float32 (all backends support this)
                audio_float32 = audio_array.astype(np.float32)

                try:
                    # Transcribe based on backend
                    if self.backend == "parakeet-mlx":
                        # Convert numpy array to MLX format directly (no file I/O!)
                        import mlx.core as mx

                        # Parakeet expects: int16 -> float32 normalized by 32768
                        # Our audio_array is already float32 from sounddevice
                        # Convert to MLX array format
                        audio_mlx = mx.array(audio_float32)

                        # Add audio to the streaming transcriber
                        self.transcriber.add_audio(audio_mlx)
                        # Get the final result
                        result = self.transcriber.result
                        full_transcription = result.text.strip()
                        # Close the streaming context
                        self.transcriber.__exit__(None, None, None)
                        self.transcriber = None

                    elif self.backend == "cuda":
                        # WhisperX can take numpy array directly
                        result = self.model.transcribe(audio_float32, batch_size=8)
                        full_transcription = " ".join([seg["text"] for seg in result["segments"]]).strip()

                    elif self.backend == "cpu":
                        # OpenAI Whisper can take numpy array directly
                        result = self.model.transcribe(audio_float32)
                        full_transcription = result["text"].strip()

                    # Print transcription
                    print("\nTranscription:")
                    print("-" * 50)
                    print(full_transcription)
                    print("-" * 50)

                    # Copy to clipboard
                    if full_transcription:
                        pyperclip.copy(full_transcription)
                        print("Transcription copied to clipboard!")

                        # Play stop sound after transcription is copied
                        self.play_sound(self.stop_sound)

                except Exception as e:
                    print(f"Error during transcription: {str(e)}")
                    # Clean up transcriber if error occurs
                    if self.backend == "parakeet-mlx" and self.transcriber:
                        try:
                            self.transcriber.__exit__(None, None, None)
                        except:
                            pass
                        self.transcriber = None
            else:
                print("No audio recorded!")

def main():
    # Detect platform and load appropriate backend
    backend, modules = detect_platform()

    recorder = AudioRecorder(backend, modules)
    print("Press Option (Alt) key twice quickly to start recording.")
    print("Press Option (Alt) key once to stop recording.")
    print("Press Ctrl+C to quit.")

    # Track alt key presses for double-tap detection
    last_alt_press_time = 0
    double_tap_threshold = 0.3  # seconds

    def on_press(key):
        nonlocal last_alt_press_time

        # Check if it's an alt/option key
        if key == keyboard.Key.alt or key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            current_time = time.time()

            if recorder.recording:
                # If already recording, stop with a single press
                recorder.stop_recording()
                # Reset timer
                last_alt_press_time = 0
            elif current_time - last_alt_press_time < double_tap_threshold:
                # Double tap detected, start recording
                recorder.start_recording()
                # Reset timer to prevent triple-tap from triggering again
                last_alt_press_time = 0
            else:
                # First tap
                last_alt_press_time = current_time

    # Start listening to keyboard events
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    try:
        # Keep the program running
        listener.join()
    except KeyboardInterrupt:
        print("\nQuitting...")
        listener.stop()

if __name__ == "__main__":
    main()
