import speech_recognition as sr
from speech.speech_detector import SpeechDetector
from config import VOSK_MODEL_PATH, VOSK_SPEAKER_MODEL_PATH
import requests
import wave
import os

recognizer = sr.Recognizer()
# speech_detector = SpeechDetector(vosk_model_path=VOSK_MODEL_PATH)

# def listen_for_speech():
#     """Capture speech input with VOSK as primary and Google Speech as fallback."""
#     print("Listening for speech...", end=" ", flush=True)  # Avoid duplicate prints
#     print(VOSK_MODEL_PATH)
#     speech_detector = SpeechDetector(vosk_model_path=VOSK_MODEL_PATH)
    
#     recognized_text = speech_detector.detect_speech()
#     if recognized_text:
#         print(f"\nVOSK detected speech: {recognized_text}")
#         return recognized_text

#     # Fallback to Google Speech Recognition
#     try:
#         with sr.Microphone() as source:
#             print("\nSwitching to Google Speech Recognition...")
#             recognizer.adjust_for_ambient_noise(source, duration=1)
#             audio = recognizer.listen(source, timeout=30, phrase_time_limit=30)
#             # recognizer.adjust_for_ambient_noise(source, duration=2)  # More ambient noise adaptation
#             # audio = recognizer.listen(source, timeout=60, phrase_time_limit=60)  # Allow long pauses
#             text = recognizer.recognize_google(audio)
#             print(f"Google detected speech: {text}")
#             return text
#     except Exception as e:
#         print(f"Speech recognition error: {e}")
#         return None


def listen_for_speech1():
    """Record microphone input, send to Vosk server, and get text."""
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            print("Recording audio for Vosk microservice...", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=20, phrase_time_limit=20)

            # Save to temp WAV file
            with open("temp_input.wav", "wb") as f:
                f.write(audio.get_wav_data())

        # Send to Vosk microservice
        files = {"file": open("temp_input.wav", "rb")}
        response = requests.post("https://vosk-server-bpa5.onrender.com/transcribe", files=files)

        if response.status_code == 200:
            transcription = response.json().get("transcription", "")
            print(f"Vosk Server Transcription: {transcription}")
            return transcription
        else:
            print(f"Error from Vosk Server: {response.text}")
            return None

    except Exception as e:
        print(f"Speech recognition error: {e}")
        return None

def listen_for_speech():
    """Record microphone input, send to Vosk microservice, and get text."""
    recognizer = sr.Recognizer()

    RATE = 16000  # Make sure to use 16000Hz
    PHRASE_TIME_LIMIT = 10  # limit speech time

    try:
        with sr.Microphone(sample_rate=RATE) as source:
            print("Recording audio for Vosk microservice...", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=20, phrase_time_limit=PHRASE_TIME_LIMIT)

            # Save to temp WAV file
            temp_filename = "temp_input.wav"
            with open(temp_filename, "wb") as f:
                f.write(audio.get_wav_data())

        # OPTIONAL: Double-check temp file properties
        with wave.open(temp_filename, "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()

            if not (channels == 1 and sampwidth == 2 and framerate == 16000):
                print(f"Audio format issue: channels={channels}, sampwidth={sampwidth}, framerate={framerate}")
                print("Warning: This may cause Vosk server to reject the audio.")

        # Send to Vosk Microservice
        with open(temp_filename, "rb") as audio_file:
            files = {"file": audio_file}
            response = requests.post("https://vosk-server-bpa5.onrender.com/transcribe", files=files)

        # Delete temp file after sending
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

        if response.status_code == 200:
            transcription = response.json().get("transcription", "")
            print(f"Vosk Server Transcription: {transcription}")
            return transcription
        else:
            print(f"Error from Vosk Server: {response.text}")
            return None

    except sr.WaitTimeoutError:
        print("Listening timed out while waiting for phrase to start")
        return None
    except Exception as e:
        print(f"Speech recognition error: {e}")
        return None