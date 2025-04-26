import os
import torch
from transformers import VitsTokenizer, VitsModel, set_seed
from config import VITS_DIR, DEFAULT_VITS_MODEL, VITS_VOICES

class SpeechModel:
    def __init__(self, model_name=DEFAULT_VITS_MODEL, speaker_id=None):
        """Initialize the VITS model, downloading if necessary."""
        self.model_name = model_name
        self.speaker_id = speaker_id  # Add speaker selection support
        self.model_path = os.path.join(VITS_DIR, model_name.replace("/", "_"))  # Store model in VITS_DIR
        
        # Download and load the model if not already available
        self.tokenizer = VitsTokenizer.from_pretrained(model_name)
        self.model = VitsModel.from_pretrained(model_name)

        print(f"VITS Model loaded successfully: {model_name}")

    def text_to_speech(self, text, output_path="output.wav"):
        """Convert text to speech and save as a .wav file."""
        inputs = self.tokenizer(text=text, return_tensors="pt")

        set_seed(555)  # Ensure deterministic output
        with torch.no_grad():
            outputs = self.model(**inputs, speaker_id=self.speaker_id) # Pass speaker_id

        waveform = outputs.waveform[0].numpy()

        # Save as .wav
        from scipy.io.wavfile import write
        write(output_path, rate=self.model.config.sampling_rate, data=waveform)

        print(f"Speech saved at {output_path}")

# Instantiate the model once at import time
speech_model = SpeechModel()
