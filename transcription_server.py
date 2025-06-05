# transcription_server.py

import os
import io
import json
import wave
from flask import Flask, request, jsonify

from openai_transcription_service import transcribe_with_openai

app = Flask(__name__)

@app.route("/transcribe", methods=["POST"])
def transcribe_endpoint():
    """
    Accepts a multipart/form-data POST with a single key "file".
    Saves it to memory (BytesIO), optionally validates format, then calls OpenAI →
    transcription, then returns JSON { "transcription": "..." }.
    """
    temp_filename = None

    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        uploaded = request.files["file"]

        # Read the raw bytes into memory
        audio_bytes = uploaded.read()
        audio_buffer = io.BytesIO(audio_bytes)

        # Quick sanity‐check: must be 16kHz mono WAV (16‐bit). If not, OpenAI may accept MP3/etc.
        # OPTIONAL: we can check with wave.open() if it’s WAV. If you only want to accept WAV:
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()

                if not (channels == 1 and sampwidth == 2 and framerate == 16000):
                    # We allow non‐16kHz formats, because OpenAI can accept MP3/MP4 etc.
                    # If you want to strictly enforce WAV‐16k, uncomment below:
                    # return jsonify({"error": "Audio must be mono PCM16‐bit 16 kHz WAV"}), 400
                    pass
        except wave.Error:
            # Not a WAV or unreadable as WAV. OpenAI supports mp3/mp4/webm/etc., so we skip.
            pass

        # Call OpenAI transcription:
        # By default, use gpt-4o-transcribe. If you prefer whisper-1, change model_name.
        transcription = transcribe_with_openai(
            audio_buffer,
            model_name="gpt-4o-transcribe",
            response_format="text",
            prompt=None
        )

        return jsonify({"transcription": transcription})

    except Exception as e:
        print(f"[transcription_server] internal error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # You can choose any port—Render usually uses $PORT
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
