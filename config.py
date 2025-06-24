import os
import urllib.request
import zipfile
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Define root project directory dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Ensure correct data directory
DATA_DIR = os.path.join(ROOT_DIR, "data")
MODEL_DIR = os.path.join(DATA_DIR, "models")
VOSK_DIR = os.path.join(MODEL_DIR, "vosk")
VITS_DIR = os.path.join(MODEL_DIR, "vits")
OUTPUT_AUDIO_DIR = os.path.join(DATA_DIR, "generated_audio")
CONVERSATION_DIR = os.path.join(DATA_DIR, "conversations") 

# VOSK Model Setup
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
VOSK_MODEL_PATH = os.path.join(VOSK_DIR, "vosk-model-en-us-0.22")

# VOSK Speaker Model
VOSK_SPEAKER_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip"
VOSK_SPEAKER_MODEL_PATH = os.path.join(VOSK_DIR, "vosk-model-spk-0.4")

# VITS Model
DEFAULT_VITS_MODEL = "facebook/mms-tts-eng"

VITS_VOICES = {
    "male": "male_speaker_id",  # Replace with actual speaker ID
    "female": "p228"  # Replace with actual speaker ID
}

# **LLM Configuration**
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.7,
        "max_tokens": 150
    },
    "gemini": {
        "model": "gemini-pro",
        "temperature": 0.7,
        "max_tokens": 150
    },
    "deepseek": {
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 150
    },
    "grok": {
        "model": "grok-1",
        "temperature": 0.7,
        "max_tokens": 150
    }
}
