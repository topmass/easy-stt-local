"""Audio recording and transcription core logic."""
import os
import platform
import subprocess
import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Handles audio recording and transcription with platform-specific backends.

    This class maintains the critical zero-file-I/O architecture for maximum performance.
    Audio flows: sounddevice → numpy array → model (MLX/NeMo) without touching disk.
    """

    def __init__(self, backend, modules, enable_cleanup=False, cleanup_model=None,
                 cleanup_tokenizer=None, cleanup_prompt=None):
        """Initialize audio recorder with platform-specific backend.

        Args:
            backend: str, either "parakeet-mlx" or "nemo"
            modules: Module or tuple of modules for backend initialization
            enable_cleanup: bool, whether to enable LLM cleanup
            cleanup_model: Optional cleanup model instance
            cleanup_tokenizer: Optional cleanup tokenizer instance
            cleanup_prompt: Optional cleanup prompt string
        """
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
        """Play a sound file using system audio player.

        Args:
            sound_file: Path to sound file to play
        """
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
        """Sounddevice callback to capture audio frames.

        Args:
            indata: Input audio data
            frames: Number of frames
            time: Timestamp info
            status: Status flags
        """
        if self.recording:
            self.audio_data.extend(indata.copy())

    def start_recording(self):
        """Start the recording process.

        For Parakeet-MLX: Initializes streaming transcriber for real-time processing.
        """
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
        """Stop recording and transcribe audio.

        CRITICAL: Maintains zero-file-I/O architecture.
        Audio stays in memory: numpy array → MLX/NeMo array → model.
        Never writes to temp files for maximum performance (~50ms latency).

        Returns:
            str or None: Transcribed text, or None if no audio/error
        """
        if self.recording:
            print("Recording stopped. Transcribing...")
            self.recording = False
            self.stream.stop()
            self.stream.close()

            # Process audio data
            if len(self.audio_data) > 0:
                # Concatenate and convert to float32 (ZERO FILE I/O!)
                audio_array = np.concatenate(self.audio_data, axis=0).flatten()
                audio_float32 = audio_array.astype(np.float32)

                try:
                    print("Transcribing audio...")

                    # Transcribe based on backend (direct array processing, no file I/O!)
                    if self.backend == "parakeet-mlx":
                        # Parakeet-MLX: Stream audio in one batch (in-memory)
                        import mlx.core as mx

                        # Convert to MLX array (in-memory conversion, no I/O)
                        audio_mlx = mx.array(audio_float32)

                        # Add all audio at once to the streaming transcriber
                        self.transcriber.add_audio(audio_mlx)

                        # Get the result
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

                    return full_transcription

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
                    return None
            else:
                print("No audio recorded!")
                return None
        return None
