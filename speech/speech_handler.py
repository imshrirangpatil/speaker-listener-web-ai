# import eventlet
# eventlet.monkey_patch()
import speech_recognition as sr
import pyttsx3
import time
from flask_socketio import SocketIO

socketio = SocketIO(message_queue='redis://')

recognizer = sr.Recognizer()
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 0.9)  # Soften the voice for a soothing tone

def listen_for_speech():
    """Capture speech input using Google Speech Recognition"""
    try:
        with sr.Microphone() as source:
            print("Listening...")

            # Notify frontend: start listening
            socketio.emit('listening', {'active': True})

            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=20, phrase_time_limit=20)
            text = recognizer.recognize_google(audio)

            print(f"You said: {text}")

            # Notify frontend: done listening
            socketio.emit('listening', {'active': False})

            return text

    except sr.UnknownValueError:
        print("Could not understand audio")
        socketio.emit('listening', {'active': False})
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        socketio.emit('listening', {'active': False})
        return None

def speak_text(text, voice="female"):
    """Convert text to speech"""
    print(f"AI: {text}")
    engine.say(text)
    engine.runAndWait()
    time.sleep(1)
