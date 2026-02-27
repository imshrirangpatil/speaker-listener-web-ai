import os
import vosk
import json
import urllib.request
import tarfile
from config import VOSK_MODEL_PATH, VOSK_MODEL_URL  # You need to define VOSK_MODEL_URL in your config

class SpeechDetector:
    def __init__(self, vosk_model_path=VOSK_MODEL_PATH):
        self.vosk_model_path = vosk_model_path
        self.ensure_model_downloaded()
        if not os.path.exists(vosk_model_path):
            raise FileNotFoundError(f"VOSK Model not found at {vosk_model_path}")

        print(f"Loading VOSK model from: {self.vosk_model_path}")
        self.model = vosk.Model(self.vosk_model_path)
        self.recognizer = vosk.KaldiRecognizer(self.model, 16000)

    def ensure_model_downloaded(self):
        """Download and extract the VOSK model if not already present."""
        if not os.path.exists(self.vosk_model_path):
            print(f"Downloading VOSK model to {self.vosk_model_path}...")
            # os.makedirs(os.path.dirname(self.vosk_model_path), exist_ok=True)

            archive_path = self.vosk_model_path + ".zip"  # You can change to .tar.gz based on vosk model

            # Download the model archive
            urllib.request.urlretrieve(VOSK_MODEL_URL, archive_path)

            # Extract
            if archive_path.endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(os.path.dirname(self.vosk_model_path))
            elif archive_path.endswith(".tar.gz") or archive_path.endswith(".tgz"):
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    tar_ref.extractall(os.path.dirname(self.vosk_model_path))
            else:
                raise ValueError("Unsupported archive format")

            # Cleanup
            os.remove(archive_path)

            print(f"VOSK model downloaded and extracted to {self.vosk_model_path}.")
        else:
            print(f"VOSK model already cached at {self.vosk_model_path}.")