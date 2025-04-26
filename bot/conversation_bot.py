import os
import json
import random
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


class ConversationBot:
    def __init__(self, llm_provider="gemini"):
        """Initialize chatbot with configurable LLM provider and universal paths."""
        if llm_provider not in LLM_CONFIG:
            raise ValueError(f"Invalid LLM provider: {llm_provider}")
        self.llm_provider = llm_provider
        self.llm_api = LLMApi(provider=self.llm_provider)
        self.conversation_history = []
        self.session_filename = os.path.join(CONVERSATION_DIR, f"conversation_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        self.character = select_character()
        self.character_type = self.character["type"]
        self.current_emotion = "neutral"
        self.conversation_history = []
        self.speaker_listener_role = "listener"
        self.turn_count = 0

    def listener_mode(self):
        """Handle chatbot in listener mode, where the user speaks first."""
        try:
            speak_text("Hello! I am Charisma Bot. You have the floor; I am listening.")

            while True:
                user_input = listen_for_speech()

                if not user_input:  # If None, prompt again instead of crashing
                    speak_text("I didn't catch that. Could you please repeat?")
                    continue  # Go back to listening

                if self.is_goodbye(user_input):
                    speak_text("It was nice talking to you! Goodbye!")
                    self.save_conversation()
                    return False

                if self.is_confirmation(user_input):
                    speak_text(self.generate_follow_up_response())
                    continue

                # Analyze emotion
                self.current_emotion = detect_emotion(user_input)

                # Append to conversation history immediately
                self.conversation_history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "speaker": "user",
                    "message": user_input,
                    "emotion": self.current_emotion
                })

                # Paraphrase user input
                paraphrased = paraphrase(user_input)
                speak_text(paraphrased)

                # Confirm understanding
                speak_text("Did I understand correctly?")
                confirmation = listen_for_speech()

                if confirmation and self.is_confirmation(confirmation):  # Ensure confirmation is valid
                    response = generate_response(user_input, self.character_type)
                    speak_text(response)

                    self.conversation_history.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "speaker": "bot",
                        "message": response,
                        "emotion": self.current_emotion
                    })

                    self.turn_count += 1  # Increment turn count after successful interaction
                else:
                    speak_text("I apologize. Could you please repeat that?")

                # Save conversation at every turn
                self.save_conversation()

                if self.turn_count >= 3:  # Switch roles after 3 turns
                    self.switch_roles()
                    return True

        except Exception as e:
            print(f"Error in listener mode: {e}")
            self.save_conversation()
            return False

    def speaker_mode(self):
        """Handle chatbot in speaker mode, where the bot speaks first."""
        try:
            speak_text("Hello! I am Charisma Bot. I will talk first, and you will listen.")
            while True:
                # Generate topic for conversation
                current_statement = generate_topic(self.character_type)
                speak_text(current_statement)

                # User response
                user_response = listen_for_speech()

                if not user_response:
                    speak_text("I didn't catch that. Could you please repeat?")
                    continue

                if self.is_goodbye(user_response):
                    speak_text("It was nice talking to you!")
                    self.save_conversation()
                    return False

                # Validate paraphrase using a similarity prompt
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
                    self.conversation_history.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "speaker": "bot",
                        "statement": current_statement,
                        "listener_paraphrase": user_response,
                        "emotion": self.current_emotion
                    })
                    self.turn_count += 1  # Increment turn count after successful interaction
                else:
                    speak_text("That's not quite what I said. Please try to paraphrase again.")
                    continue  # Re-prompt without breaking the loop

                if self.turn_count >= 3:  # Switch roles after 3 turns
                    self.switch_roles()
                    return True

        except Exception as e:
            print(f"Error in speaker mode: {e}")
            self.save_conversation()
            return False

        return True

    def switch_roles(self):
        """Switch roles after structured conversation turns with additional safeguards."""
        self.save_conversation()
        previous_role = self.speaker_listener_role
        self.speaker_listener_role = "speaker" if self.speaker_listener_role == "listener" else "listener"
        print(f"Switching roles from {previous_role} to {self.speaker_listener_role}.")
        speak_text(f"Let's switch roles. I will now be the {self.speaker_listener_role}.")
        self.turn_count = 0

    def integrated_mode(self):
        """Run an interactive conversation where roles switch dynamically after structured turns."""
        while True:
            if self.speaker_listener_role == "listener":
                if not self.listener_mode():
                    break
            else:
                if not self.speaker_mode():
                    break

            self.save_conversation()

    def is_confirmation(self, text):
        """Check if the user confirms an answer safely with expanded detection."""
        confirmation_phrases = ["yes", "correct", "right", "that is correct", "yes that is correct", "affirmative", "indeed"]
        
        if not text:
            return False

        text_lower = text.lower()
        return any(text_lower.startswith(phrase) or text_lower == phrase for phrase in confirmation_phrases)

    def is_goodbye(self, text):
        """Check if the user wants to end the conversation."""
        return any(word in text.lower() for word in ['goodbye', 'bye', 'ok bye', 'exit', 'quit'])

    def generate_follow_up_response(self):
        """Generate a follow-up prompt to keep the conversation flowing."""
        prompts = [
            "Please continue sharing your thoughts.",
            "I'd love to hear more about it.",
            "Feel free to elaborate on that.",
            "Please go on, I'm listening attentively."
        ]
        return random.choice(prompts)

    def save_conversation(self):
        """Save conversation history with full details including bot character, emotions, and structured context."""
        if not self.conversation_history:
            return

        conversation_data = {
            "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bot_character": self.character_type,  # Save bot personality type
            "history": self.conversation_history
        }

        try:
            with open(self.session_filename, "w", encoding="utf-8") as f:
                json.dump(conversation_data, f, indent=4)
        except Exception as e:
            print(f"Error saving conversation: {e}")

    def signal_handler(sig, frame):
        """Handle Ctrl + C to save conversation before exiting."""
        print("\n[INFO] Exiting gracefully... Saving conversation.")
        bot.save_conversation()
        sys.exit(0)

    def main_loop(self):
        """Run the chatbot in integrated mode with safe exit handling."""
        try:
            self.integrated_mode()
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard Interrupt detected. Saving conversation...")
            self.save_conversation()
            sys.exit(0)

if __name__ == "__main__":
    bot = ConversationBot()
    bot.main_loop()
