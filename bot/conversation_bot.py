import os 
import json
import random
import sys
from datetime import datetime
import pandas as pd
from bot.character_manager import select_character
from bot.emotion_detector import detect_emotion
from bot.response_generator import generate_response, paraphrase, generate_topic
from speech.speech_recognition_service import listen_for_speech
from speech.speech_handler import speak_text
from speech.speech_model import speech_model
from llm.llm_api import LLMApi
import google.generativeai as genai
from config import CONVERSATION_DIR, LLM_CONFIG
import traceback
import socketio
# from app import emit_bot_role
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase (only once)
if not firebase_admin._apps:
    cred = credentials.Certificate("./firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
from uuid import uuid4

import os

sio = socketio.Client()
SERVER_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:5000")
sio.connect(SERVER_URL)   # let Socket.IO pick ws or polling automatically

# Local only
# sio = socketio.Client()
# sio.connect("http://127.0.0.1:5000", transports=["websocket"])

class ConversationBot:
    def __init__(self, character_type=None, llm_provider="gemini"):
        if llm_provider not in LLM_CONFIG:
            raise ValueError(f"Invalid LLM provider: {llm_provider}")
        self.llm_provider = llm_provider
        self.llm_api = LLMApi(provider=self.llm_provider)
        self.conversation_history = []
        self.session_filename = os.path.join(CONVERSATION_DIR, f"conversation_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        if character_type:
            self.character_type = character_type
            self.character = {"type": character_type}
        else:
            self.character = select_character()
            self.character_type = self.character["type"]

        self.current_emotion = "neutral"
        self.bot_role = "speaker"       # Bot starts as speaker
        self.user_role = "listener"     # User starts as listener
        self.turn_count = 0
        self.session_id = f"session_{uuid4().hex}"

    def listener_mode(self):
        try:
            self.emit_mic_activated(False)
            speak_text("Hello! I am Charisma Bot. You have the floor; I am listening.")
            self.emit_message("Hello! I am Charisma Bot. You have the floor; I am listening.", "bot")

            while True:
                self.emit_mic_activated(True)
                user_input = listen_for_speech()
                self.emit_mic_activated(False)

                if not user_input:
                    speak_text("I didn't catch that. Could you please repeat?")
                    self.emit_message("I didn't catch that. Could you please repeat?", "bot")
                    continue

                self.emit_message(user_input, "user")

                if self.is_goodbye(user_input):
                    speak_text("It was nice talking to you! Goodbye!")
                    self.emit_message("It was nice talking to you! Goodbye!", "bot")
                    self.save_conversation()
                    return False

                if self.is_confirmation(user_input):
                    followup = speak_text(self.generate_follow_up_response())
                    # speak_text(followup)
                    self.emit_message(followup, "bot")
                    continue

                self.current_emotion = detect_emotion(user_input)

                # self.conversation_history.append({
                #     "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                #     "speaker": "user",
                #     "message": user_input,
                #     "emotion": self.current_emotion
                # })

                paraphrased = paraphrase(user_input)
                speak_text(paraphrased)
                self.emit_message(paraphrased, "bot")
                speak_text("Did I understand correctly?")
                self.emit_message("Did I understand correctly?", "bot")
                confirmation = listen_for_speech()
                if confirmation:
                    self.emit_message(confirmation, "user")

                if confirmation and self.is_confirmation(confirmation):
                    response = generate_response(user_input, self.character_type)
                    speak_text(response)
                    self.emit_message(response, "bot")

                    # self.conversation_history.append({
                    #     "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    #     "speaker": "bot",
                    #     "message": response,
                    #     "emotion": self.current_emotion
                    # })

                    self.turn_count += 1
                else:
                    speak_text("I apologize. Could you please repeat that?")
                    self.emit_message("I apologize. Could you please repeat that?", "bot")

                self.save_conversation()

                if self.turn_count >= 1:
                    self.switch_roles()
                    return True

        except Exception as e:
            print(f"Error in listener mode: {e}")
            self.save_conversation()
            return False

    def speaker_mode(self):
        try:
            self.emit_mic_activated(False)
            speak_text("Hello! I am Charisma Bot. I will talk first, and you will listen.")
            self.emit_message("Hello! I am Charisma Bot. I will talk first, and you will listen.", "bot")

            while True:
                current_statement = generate_topic(self.character_type)
                speak_text(current_statement)
                self.emit_message(current_statement, "bot")
                
                self.emit_mic_activated(True)
                user_response = listen_for_speech()
                self.emit_mic_activated(False)

                if not user_response:
                    speak_text("I didn't catch that. Could you please repeat?")
                    self.emit_message("I didn't catch that. Could you please repeat?", "bot")
                    continue

                self.emit_message(user_response, "user")

                if self.is_goodbye(user_response):
                    speak_text("It was nice talking to you! Goodbye!")
                    self.emit_message("It was nice talking to you! Goodbye!", "bot")
                    self.save_conversation()
                    return False

                similarity_prompt = f"""
                Compare these statements and rate their similarity on a scale of 0 to 10:
                Original: {current_statement}
                Paraphrase: {user_response}
                Consider partial matches and key concepts.
                Only respond with a number between 0 and 10.
                """
                similarity_check = self.llm_api.generate_response([{"role": "user", "content": similarity_prompt}])
                try:
                    similarity_score = float(similarity_check.strip())
                except ValueError:
                    similarity_score = 0

                if similarity_score >= 5:
                    speak_text("That's correct! Let's continue our discussion.")
                    self.emit_message("That's correct! Let's continue our discussion.", "bot")
                    # self.conversation_history.append({
                    #     "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    #     "speaker": "bot",
                    #     "statement": current_statement,
                    #     "listener_paraphrase": user_response,
                    #     "emotion": self.current_emotion
                    # })
                    self.turn_count += 1
                else:
                    speak_text("That's not quite what I said. Please try to paraphrase again.")
                    self.emit_message("That's not quite what I said. Please try to paraphrase again.", "bot")
                    continue

                if self.turn_count >= 1:
                    self.switch_roles()
                    return True

        except Exception as e:
            print(f"Error in speaker mode: {e}")
            self.save_conversation()
            return False

        return True

    # def switch_roles(self):
    #     """Switch roles after structured conversation turns with additional safeguards."""
    #     self.save_conversation()
    #     previous_role = self.speaker_listener_role
    #     self.speaker_listener_role = "speaker" if self.speaker_listener_role == "listener" else "listener"
    #     print(f"Switching roles from {previous_role} to {self.speaker_listener_role}.")
    #     speak_text(f"Let's switch roles. I will now be the {self.speaker_listener_role}.")
        
    #     # EMIT NEW ROLE TO FRONTEND
    #     self.emit_role(self.speaker_listener_role)

    #     self.turn_count = 0

    def switch_roles(self):
        """Switch bot and user roles after each round."""
        self.save_conversation()

        # Swap bot and user roles
        previous_bot_role = self.bot_role
        self.bot_role = "listener" if self.bot_role == "speaker" else "speaker"
        self.user_role = "speaker" if self.bot_role == "listener" else "listener"

        # print(f"Switching roles: Bot = {self.bot_role}, User = {self.user_role}")
        speak_text(f"Let's switch roles. I will now be the {self.bot_role}, and you will be the {self.user_role}.")
        self.emit_message(f"Let's switch roles. I will now be the {self.bot_role}, and you will be the {self.user_role}.", "bot")
        self.turn_count = 0
    
    def emit_mic_activated(self, activated):
        try:
            if sio.connected:
                sio.emit("mic_activated", {
                    "activated": activated
                })
        except Exception as e:
            print(f"[ERROR] Failed to emitmic activated: {e}")

    def emit_message(self, message, sender):
        try:
            if sio.connected:
                # print(f"[EMIT] Sending message: {message} as {sender}")
                sio.emit("new_message", {
                    "text": message,
                    "sender": sender
                })

                self.conversation_history.append({
                    "speaker": sender,
                    "message": message,
                    "emotion": self.current_emotion  # optional but useful
                })
            
            db.collection("sessions").document(self.session_id).set({
                "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bot_character": self.character_type,
                "history": self.conversation_history
            })

        except Exception as e:
            print(f"[ERROR] Failed to emit message: {e}")

    def integrated_mode(self):
        while True:
            if self.bot_role == "listener":
                if not self.listener_mode():
                    break
            else:
                if not self.speaker_mode():
                    break
            self.save_conversation()

    def is_confirmation(self, text):
        confirmation_phrases = ["yes", "correct", "right", "that is correct", "yes that is correct", "affirmative", "indeed"]
        if not text:
            return False
        text_lower = text.lower()
        return any(text_lower.startswith(phrase) or text_lower == phrase for phrase in confirmation_phrases)

    def is_goodbye(self, text):
        return any(word in text.lower() for word in ['goodbye', 'bye', 'ok bye', 'exit', 'quit'])

    def generate_follow_up_response(self):
        prompts = [
            "Please continue sharing your thoughts.",
            "I'd love to hear more about it.",
            "Feel free to elaborate on that.",
            "Please go on, I'm listening attentively."
        ]
        return random.choice(prompts)

    def save_conversation(self):
        if not self.conversation_history:
            return

        conversation_data = {
            "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bot_character": self.character_type,
            "history": self.conversation_history
        }

        try:
            with open(self.session_filename, "w", encoding="utf-8") as f:
                json.dump(conversation_data, f, indent=4)
            print(f"[LOCAL] Session saved to {self.session_filename}")
        except Exception as e:
            print(f"[LOCAL ERROR] Failed to save conversation: {e}")

    # def save_conversation(self):
    #     if not self.conversation_history:
    #         return

    #     conversation_data = {
    #         "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #         "bot_character": self.character_type,
    #         "history": self.conversation_history
    #     }

    #     try:
    #         with open(self.session_filename, "w", encoding="utf-8") as f:
    #             json.dump(conversation_data, f, indent=4)
    #     except Exception as e:
    #         print(f"Error saving conversation: {e}")

    def signal_handler(sig, frame):
        print("\n[INFO] Exiting gracefully... Saving conversation.")
        bot.save_conversation(final=True)
        sys.exit(0)

    def main_loop(self):
        try:
            self.integrated_mode()
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard Interrupt detected. Saving conversation...")
            self.save_conversation(final=True)
            sys.exit(0)

if __name__ == "__main__":
    bot = ConversationBot()
    bot.main_loop()
