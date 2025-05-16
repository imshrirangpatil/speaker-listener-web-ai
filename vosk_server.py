from flask import Flask, request, jsonify
import os
import json
import wave
from vosk import Model, KaldiRecognizer
from config import VOSK_MODEL_PATH   # <-- Import it here

# Load model ONCE at server startup
model = Model(VOSK_MODEL_PATH)

app = Flask(__name__)

@app.route("/transcribe", methods=["POST"])
def transcribe():
    temp_filename = "temp_audio.wav"

    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        audio_file = request.files["file"]
        audio_file.save(temp_filename)

        wf = wave.open(temp_filename, "rb")

        # Validate format
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
            wf.close()
            os.remove(temp_filename)
            return jsonify({"error": "Audio format not supported. Must be mono PCM 16-bit 16000Hz."}), 400

        rec = KaldiRecognizer(model, wf.getframerate())

        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                results.append(rec.Result())

        results.append(rec.FinalResult())

        wf.close()  # <-- VERY IMPORTANT: Close the wave file before deleting!

        os.remove(temp_filename)  # <-- Now Windows will allow delete!

        texts = []
        for r in results:
            res = json.loads(r)
            if "text" in res:
                texts.append(res["text"])

        return jsonify({"transcription": " ".join(texts)})

    except Exception as e:
        print(f"Error in Vosk server transcribe: {e}")
        try:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except:
            pass
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(port=5001, debug=False)
