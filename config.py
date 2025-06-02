import os
import urllib.request
import zipfile
from dotenv import load_dotenv
load_dotenv()

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

# # Create required directories
# os.makedirs(DATA_DIR, exist_ok=True)
# os.makedirs(MODEL_DIR, exist_ok=True)
# os.makedirs(VOSK_DIR, exist_ok=True)
# os.makedirs(VITS_DIR, exist_ok=True)
# os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)
# os.makedirs(CONVERSATION_DIR, exist_ok=True) 

# VOSK Model Setup
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
VOSK_MODEL_PATH = os.path.join(VOSK_DIR, "vosk-model-en-us-0.22")

# VOSK Speaker Model
VOSK_SPEAKER_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip"
VOSK_SPEAKER_MODEL_PATH = os.path.join(VOSK_DIR, "vosk-model-spk-0.4")

# # Function to download and extract models
# def download_and_extract(url, destination_folder):
#     """Download and extract a zip file if not already downloaded."""
#     print(destination_folder)
#     if not os.path.exists(destination_folder):
#         print(f"Downloading model from {url}...")
#         zip_path = destination_folder + ".zip"
#         urllib.request.urlretrieve(url, zip_path)
#         with zipfile.ZipFile(zip_path, 'r') as zip_ref:
#             zip_ref.extractall(VOSK_DIR)
#         os.remove(zip_path)  # Clean up zip file
#         print(f"Model extracted to: {destination_folder}")

# # Download VOSK models if not available
# download_and_extract(VOSK_MODEL_URL, VOSK_MODEL_PATH)
# download_and_extract(VOSK_SPEAKER_MODEL_URL, VOSK_SPEAKER_MODEL_PATH)

# VITS Model
DEFAULT_VITS_MODEL = "facebook/mms-tts-eng"

VITS_VOICES = {
    "male": "male_speaker_id",  # Replace with actual speaker ID
    "female": "p228"  # Replace with actual speaker ID
}

# **LLM Configuration**
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4",
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    "deepseek": {
        "model": "deepseek-chat",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
    },
    "gemini": {
        "model": "gemini-2.0-flash",
        "api_key": os.getenv("GEMINI_API_KEY"),
    },
    "grok": {
        "model": "grok-1",
        "api_key": os.getenv("GROK_API_KEY"),
    },
}
