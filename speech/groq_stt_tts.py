import os
import io
import base64
from io import BytesIO
from dotenv import load_dotenv

from dotenv import load_dotenv
load_dotenv()
# Import OpenAI for TTS
try:
    from openai import OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        OPENAI_AVAILABLE = True
    else:
        openai_client = None
        OPENAI_AVAILABLE = False
except ImportError:
    OPENAI_AVAILABLE = False
    openai_client = None

# Remove Groq imports and configuration
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# TTS_MODEL = "playai-tts"
# TTS_VOICE = "Fritz-PlayAI"
# TTS_RESPONSE_FORMAT = "wav"

# STT_MODEL = "distil-whisper-large-v3-en"

def groq_text_to_speech(text: str, return_bytes=False):
    """
    Converts text to speech using OpenAI TTS only.
    Args:
        text: Text to convert to speech
        return_bytes: If True, returns raw bytes. If False, returns base64 data URL.
    """
    # Use OpenAI TTS only
    if OPENAI_AVAILABLE and openai_client and OPENAI_API_KEY:
        try:
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",  # Consistent voice throughout
                input=text,
                response_format="wav"
            )
            
            audio_content = response.content
            
            if return_bytes:
                return audio_content
            else:
                audio_base64 = base64.b64encode(audio_content).decode("utf-8")
                return f"data:audio/wav;base64,{audio_base64}"
        except Exception as openai_error:
            return None
    
    # If TTS service fails, return None for text-only mode
    return None


def groq_speech_to_text(audio_input) -> str:
    """
    Placeholder function - STT is handled by OpenAI Whisper in speech_recognition_service.py
    """
    return ""
