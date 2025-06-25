# import eventlet
# eventlet.monkey_patch()
import speech_recognition as sr
import time
from flask_socketio import SocketIO
from uuid import uuid4
import os
from threading import Event
from speech.groq_stt_tts import groq_text_to_speech
import base64


# Initialize socket without Redis to prevent retry latency if unused
socketio = SocketIO(cors_allowed_origins="*")

recognizer = sr.Recognizer()

def listen_for_speech():
    """Capture speech input using Google Speech Recognition"""
    try:
        with sr.Microphone() as source:
            # Notify frontend: start listening
            socketio.emit('listening', {'active': True})

            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=45, phrase_time_limit=30)
            text = recognizer.recognize_google(audio)

            # Notify frontend: done listening
            socketio.emit('listening', {'active': False})

            return text

    except sr.UnknownValueError:
        socketio.emit('listening', {'active': False})
        return None
    except sr.RequestError as e:
        socketio.emit('listening', {'active': False})
        return None

def speak_text(text):
    """
    Generate TTS audio using Groq and stream it as base64 without creating local files.
    """
    try:
        # Get audio data directly as bytes from Groq
        audio_bytes = groq_text_to_speech(text, return_bytes=True)
        
        if audio_bytes:
            # Convert to base64 for streaming
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            # Emit message and audio stream to frontend
            socketio.emit("new_message", {"text": text, "sender": "bot"})
            socketio.emit("play_audio_base64", {
                "audio_base64": audio_base64, 
                "mime": "audio/wav"
            })

            # Event sync: wait until frontend signals audio playback finished
            playback_done = Event()

            def handle_audio_end(data=None):
                playback_done.set()

            socketio.on_event("bot_audio_ended", handle_audio_end)

            playback_done.wait(timeout=20)  # Extended wait max to 20s fallback

            return "streamed"
        else:
            return None

    except Exception as e:
        return None
