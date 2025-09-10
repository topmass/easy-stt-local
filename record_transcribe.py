import keyboard
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import whisperx
import torch
import threading
import time
import os
import pyperclip  # For clipboard functionality
import pygame  # For playing sound effects
import ctypes

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.sample_rate = 44100
        self.device = "cuda"  # GPU only
        self.compute_type = "float16"  # Best for GPU
        
        # Sound effect paths
        self.start_sound = os.path.join("soundfx", "start.mp3")
        self.stop_sound = os.path.join("soundfx", "stop.mp3")
        
        # Initialize pygame mixer for sound playback
        try:
            pygame.mixer.init()
            print("Sound system initialized.")
        except Exception as e:
            print(f"Could not initialize sound system: {str(e)}")
        
        # Load WhisperX model
        print("Loading WhisperX model...")
        self.model = whisperx.load_model("distil-small.en", self.device, compute_type=self.compute_type)
        print("Model loaded!")

    def play_sound(self, sound_file):
        """Play a sound file using pygame."""
        try:
            pygame.mixer.music.load(sound_file)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Could not play sound {sound_file}: {str(e)}")

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
            
            # Save audio to temporary WAV file
            if len(self.audio_data) > 0:
                audio_array = np.concatenate(self.audio_data, axis=0)
                temp_wav = "temp_recording.wav"
                write(temp_wav, self.sample_rate, audio_array)
                
                try:
                    # Load and transcribe audio
                    audio = whisperx.load_audio(temp_wav)
                    result = self.model.transcribe(audio, batch_size=8)
                    
                    # Collect full transcription for clipboard
                    full_transcription = ""
                    
                    # Print transcription
                    print("\nTranscription:")
                    print("-" * 50)
                    for segment in result["segments"]:
                        print(f"{segment['text']}")
                        full_transcription += segment['text'] + " "
                    print("-" * 50)
                    
                    # Copy to clipboard
                    full_transcription = full_transcription.strip()
                    if full_transcription:
                        pyperclip.copy(full_transcription)
                        print("Transcription copied to clipboard!")
                        
                        # Play stop sound after transcription is copied
                        self.play_sound(self.stop_sound)
                    
                except Exception as e:
                    print(f"Error during transcription: {str(e)}")
                
                # Clean up temporary file
                try:
                    os.remove(temp_wav)
                except:
                    pass
            else:
                print("No audio recorded!")

def is_window_focused():
    """Check if the current console window is focused (Windows only)."""
    try:
        # Get the foreground window handle
        foreground_window = ctypes.windll.user32.GetForegroundWindow()
        
        # Get the current console window handle
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        
        # Check if the console window is the foreground window
        return foreground_window == console_window
    except Exception:
        # If there's any error, default to True for safety
        return True

def main():
    recorder = AudioRecorder()
    print("Press left alt twice quickly to start recording. Press left alt once to stop.")
    print("Press 'Q' to quit (only works when this window is focused).")
    
    # Track left alt key presses for double-tap detection
    last_alt_press_time = 0
    double_tap_threshold = 0.3  # seconds
    running = True
    
    def on_alt_press(event):
        nonlocal last_alt_press_time
        if event.name == 'alt' and event.event_type == 'down':
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
    
    def on_quit_press(event):
        nonlocal running
        # Check if Q is pressed and window is focused
        if event.name == 'q' and event.event_type == 'down' and is_window_focused():
            print("Quitting...")
            running = False
    
    # Register keyboard handlers
    keyboard.on_press(on_alt_press)
    keyboard.on_press(on_quit_press)
    
    # Keep the program running until Q is pressed while window is focused
    while running:
        time.sleep(0.1)  # Reduce CPU usage

if __name__ == "__main__":
    main()
