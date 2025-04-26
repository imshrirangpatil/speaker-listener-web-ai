import os
import vosk
import json
import pyaudio
from config import VOSK_MODEL_PATH

class SpeechDetector:
    def __init__(self, vosk_model_path=VOSK_MODEL_PATH):
        if not os.path.exists(vosk_model_path):
            raise FileNotFoundError(f"VOSK Model not found at {vosk_model_path}. Ensure it is downloaded correctly.")

        self.model = vosk.Model(vosk_model_path)
        self.recognizer = vosk.KaldiRecognizer(self.model, 16000)

    def detect_speech(self):
        """Capture and process speech using VOSK."""
        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8192)
        stream.start_stream()

        print("Listening...")
        while True:
            data = stream.read(4096, exception_on_overflow=False)
            if len(data) == 0:
                break
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                return result.get("text", "")

        return None
