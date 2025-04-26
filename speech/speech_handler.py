import speech_recognition as sr
import pyttsx3
import time

recognizer = sr.Recognizer()
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 0.9)  # Soften the voice for a soothing tone

def listen_for_speech():
    """Capture speech input using Google Speech Recognition"""
    try:
        with sr.Microphone() as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=20, phrase_time_limit=20)
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text
    except sr.UnknownValueError:
        print("Could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return None

def speak_text(text, voice="female"):
    """Convert text to speech"""
    print(f"AI: {text}")
    engine.say(text)
    engine.runAndWait()
    time.sleep(1)
