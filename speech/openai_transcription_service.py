# openai_transcription_service.py

import os
import io
import openai
from config import OPENAI_API_KEY
from dotenv import load_dotenv
load_dotenv()

# Ensure your OPENAI_API_KEY is set
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in environment.")
openai.api_key = OPENAI_API_KEY


def transcribe_with_openai(
    audio_bytes: bytes,
    model: str = "gpt-4o-transcribe",
    language: str = "en",
    response_format: str = "text"
) -> str:
    """
    Send raw audio bytes to OpenAI's Transcriptions endpoint and return the transcript text.

    - audio_bytes: raw bytes of a WAV/MP3 file.
    - model: e.g. "gpt-4o-transcribe", "gpt-4o-mini-transcribe", or "whisper-1".
    - response_format: "text" (returns str) or "json" (returns the full Transcription object as dict).

    Returns:
      - If response_format == "text": returns resp.text (a str).
      - Otherwise returns the full Transcription object (as Python dict).
    """

    # Wrap bytes in a file‐like object
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"  # extension is used to infer format

    try:
        if response_format == "text":
            resp = openai.audio.transcriptions.create(
                model=model,
                file=audio_file
            )
            # The returned object has attribute 'text'
            return resp.text

        else:
            # Request JSON/verbose_json
            resp = openai.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="verbose_json"
            )
            # Convert the Transcription object to a dict for caller
            return resp.to_dict()

    except Exception as e:
        return ""
