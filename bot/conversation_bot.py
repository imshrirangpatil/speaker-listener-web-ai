import os 
import json
import random
import sys
from datetime import datetime
import pandas as pd
from bot.character_manager import select_character
from bot.emotion_detector import detect_emotion
from bot.response_generator import generate_response, paraphrase, generate_topic, generate_validation_response, detect_hardship, generate_empathetic_response
from speech.groq_stt_tts import groq_text_to_speech, groq_speech_to_text
from speech.speech_recognition_service import listen_for_speech
from llm.llm_api import LLMApi
from config import CONVERSATION_DIR, LLM_CONFIG
import traceback
import socketio
import firebase_admin
from firebase_admin import credentials, firestore
import time
from uuid import uuid4
import tempfile
import speech_recognition as sr
import re

# Initialize Firebase (only once)
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("./firebase_key.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("[INFO] Firebase initialized successfully")
except Exception as e:
    print(f"[WARNING] Firebase initialization failed: {e}")
    print("[INFO] Continuing without Firebase...")
    db = None

# Initialize SocketIO client with reconnection settings
sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1,
    reconnection_delay_max=5,
    logger=True,
    engineio_logger=True
)
SERVER_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:5000")

# Try to connect to SocketIO server with error handling and reconnection
try:
    sio.connect(SERVER_URL)
    print(f"[INFO] Connected to SocketIO server at {SERVER_URL}")
except Exception as e:
    print(f"[WARNING] Failed to connect to SocketIO server: {e}")
    print("[INFO] Will attempt to reconnect automatically...")

# Add connection event handlers
@sio.event
def connect():
    print("[INFO] Connected to SocketIO server")

@sio.event
def disconnect():
    print("[INFO] Disconnected from SocketIO server")

@sio.event
def connect_error(data):
    print(f"[WARNING] Connection error: {data}")

class ConversationBot:
    def __init__(self, character_type=None, llm_provider="openai", session_id=None):
        if llm_provider not in LLM_CONFIG:
            raise ValueError(f"Invalid LLM provider: {llm_provider}")
        self.llm_provider = llm_provider
        self.llm_api = LLMApi(provider=self.llm_provider)
        self.conversation_history = []
        
        # Use session ID for unique session identification
        self.session_id = session_id or f"session_{uuid4().hex}"
        self.session_filename = os.path.join(CONVERSATION_DIR, f"conversation_{self.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        if character_type:
            self.character_type = character_type
            self.character = {"type": character_type}
        else:
            self.character = select_character()
            self.character_type = self.character["type"]

        self.current_emotion = "neutral"
        self.bot_role = "speaker"
        self.user_role = "listener"
        self.turn_count = 0
        self.selected_issue = None  # Track the specific issue being discussed
        self.speaker_turns_completed = 0  # Track speaker turns
        self.listener_turns_completed = 0  # Track listener turns
        self.introduced = False  # Track if the bot has introduced itself
        self.role_explained = False  # Track if role explanations have been given

        sio.on("bot_audio_ended", self.on_audio_finished)
        sio.on("user_input", self.on_user_input)
        self.waiting_for_audio_end = False
        self.waiting_for_user_input = False
        self.user_input_received = None

    def on_audio_finished(self, data=None):
        self.waiting_for_audio_end = False

    def wait_for_audio_to_finish(self):
        self.waiting_for_audio_end = True
        timeout = time.time() + 12
        while self.waiting_for_audio_end and time.time() < timeout:
            time.sleep(0.1)

    def get_friendly_phrase(self):
        phrases = [
            "I'm here to listen.",
            "Take your time.",
            "I appreciate you sharing.",
            "Let's work together.",
            "You're doing great.",
            "Thanks for being open.",
            "Let's keep this friendly.",
            "Feel free to share more."
        ]
        return random.choice(phrases)

    def send_friendly_introduction(self):
        if not self.introduced:
            self.send_and_wait("Hi, I'm Charisma Bot, your conversation partner. Let's have a friendly chat today!")
            self.send_and_wait("Today, we'll practice the Speaker-Listener Technique. We'll take turns sharing and listening to understand each other better.")
            self.introduced = True

    def get_confirmation_prompt(self):
        prompts = [
            "Did I get that right? Please say yes or repeat.",
            "Did I understand you correctly?",
            "Let me know if I got it right.",
            "Could you clarify if I missed anything?",
            "Is that accurate? Please let me know.",
            "Does that sound right to you?",
            "Did I capture your meaning?"
        ]
        return random.choice(prompts)

    def get_clarify_prompt(self):
        prompts = [
            "Could you tell me a bit more about that?",
            "I'd love to hear more details.",
            "Can you explain that a little more?",
            "Please share a bit more.",
            "I want to make sure I understand. Could you say it again in your own words?",
            "Could you help me understand by saying it another way?",
            "Could you repeat your full statement so I can get it right?"
        ]
        return random.choice(prompts)

    def paraphrase_for_listener(self, user_input):
        # If user input is a paraphrase/confirmation, just confirm
        if self.is_user_paraphrase(user_input):
            return "Yes, that's right. Thank you!"
        
        is_question = user_input.strip().endswith('?')
        paraphrased = paraphrase(user_input)
        if paraphrased.lower().startswith("you said"):
            paraphrased = paraphrased[8:].strip(':,. ')
        # Remove unnecessary commas after templates
        paraphrased = re.sub(r'^[:.,\s]+', '', paraphrased)
        # Ensure paraphrased statement is concise (max 20 words)
        words = paraphrased.split()
        if len(words) > 20:
            paraphrased = ' '.join(words[:20])
        # If paraphrased ends with a conjunction, prompt for more detail
        trailing_conjunctions = ["and", "but", "or", "so", "because", "however", "although", "while", "though"]
        if words and words[-1].lower() in trailing_conjunctions:
            return "Could you tell me a bit more about that?"
        # Ensure paraphrased statement is a complete sentence
        if not paraphrased.endswith(('.', '!', '?')):
            paraphrased += '.'
        
        if is_question:
            # Handle questions more naturally - don't treat them as advice requests
            question_content = user_input.rstrip(' ?').lower()
            if any(word in question_content for word in ['do', 'does', 'can', 'could', 'would', 'should', 'have', 'has']):
                # It's a genuine question, paraphrase it as such
                templates = [
                    f"What I hear you asking is {paraphrased}",
                    f"If I understand you right, you're wondering {paraphrased}",
                    f"It sounds like you're questioning {paraphrased}"
                ]
            else:
                # It might be a rhetorical question or statement
                templates = [
                    f"What I hear you saying is {paraphrased}",
                    f"If I understand you right, {paraphrased}",
                    f"It sounds like you're {paraphrased}"
                ]
        else:
            templates = [
                f"What I hear you saying is {paraphrased}",
                f"If I understand you right, {paraphrased}",
                f"It sounds like you're {paraphrased}"
            ]
        
        result = random.choice(templates)
        # Remove any double spaces or awkward punctuation
        result = re.sub(r',?\s*:\s*', ', ', result)
        result = result.replace(',,', ',').replace(' :', ':').replace(' .', '.').strip()
        # Remove unnecessary comma after 'It sounds like'
        result = re.sub(r'It sounds like,', 'It sounds like', result)
        # Ensure result is a complete sentence
        if not result.endswith(('.', '!', '?')):
            result += '.'
        return result

    def listener_mode(self):
        try:
            self.emit_mic_activated(False)
            # Combine listener greeting messages
            self.send_and_wait(f"I'm listening. {self.get_friendly_phrase()}")
            if not self.role_explained:
                self.send_and_wait("As the listener, your job is to repeat what you heard, so I feel understood.")
            last_paraphrase = None
            while True:
                self.emit_mic_activated(True)
                user_input = self.listen()
                self.emit_mic_activated(False)
                if not user_input or len(user_input.strip()) < 5:
                    self.send_and_wait(self.get_clarify_prompt())
                    self.emit_mic_activated(True)
                    continue
                if self.is_goodbye(user_input):
                    self.send_and_wait("Goodbye! It was nice talking with you.")
                    self.save_conversation()
                    return False
                self.current_emotion = detect_emotion(user_input)
                # Handle "So you said?" or similar
                if user_input.strip().lower() in ["so you said?", "so you said", "what did you say?", "what did you say"] and last_paraphrase:
                    self.send_and_wait(f"Here's what I said: {last_paraphrase}")
                    self.emit_mic_activated(True)
                    continue
                paraphrased = self.paraphrase_for_listener(user_input)
                last_paraphrase = paraphrased
                self.send_and_wait(paraphrased)
                self.send_and_wait(self.get_confirmation_prompt())
                self.emit_mic_activated(True)
                confirmation = self.listen()
                self.emit_mic_activated(False)
                conf_result = self.is_confirmation(confirmation)
                if conf_result:
                    self.send_and_wait("Yes, that's right. Thank you!")
                    self.listener_turns_completed += 1
                    break
                elif conf_result is None:  # ambiguous response
                    self.send_and_wait("I heard both yes and no. Could you clarify if I understood you correctly?")
                    self.emit_mic_activated(True)
                    retry_confirmation = self.listen()
                    self.emit_mic_activated(False)
                    if retry_confirmation and self.is_confirmation(retry_confirmation):
                        self.send_and_wait("Thank you for clarifying! Let's continue.")
                        self.listener_turns_completed += 1
                        break
                    else:
                        self.send_and_wait("Let me try to understand better.")
                        self.emit_mic_activated(True)
                        retry_input = self.listen()
                        self.emit_mic_activated(False)
                        if retry_input and len(retry_input.strip()) >= 5:
                            paraphrased = self.paraphrase_for_listener(retry_input)
                            last_paraphrase = paraphrased
                            self.send_and_wait(paraphrased)
                            self.send_and_wait(self.get_confirmation_prompt())
                            self.emit_mic_activated(True)
                            retry_confirmation = self.listen()
                            self.emit_mic_activated(False)
                            if retry_confirmation and self.is_confirmation(retry_confirmation):
                                self.send_and_wait("Thank you for clarifying! Let's continue.")
                                self.listener_turns_completed += 1
                                break  # Exit the loop and proceed to problem-solving
                            else:
                                self.send_and_wait("Let's move on for now.")
                                self.listener_turns_completed += 1
                                break  # Exit the loop and proceed to problem-solving
                        else:
                            self.send_and_wait("Let's move on for now.")
                            self.listener_turns_completed += 1
                            break  # Exit the loop and proceed to problem-solving
                else:
                    # If user says "No" or gives unclear feedback, ask for clarification
                    self.send_and_wait("I want to make sure I understand you correctly. Could you please say it again in your own words?")
                    self.emit_mic_activated(True)
                    retry_input = self.listen()
                    self.emit_mic_activated(False)
                    if retry_input and len(retry_input.strip()) >= 5:
                        paraphrased = self.paraphrase_for_listener(retry_input)
                        last_paraphrase = paraphrased
                        self.send_and_wait(paraphrased)
                        self.send_and_wait(self.get_confirmation_prompt())
                        self.emit_mic_activated(True)
                        retry_confirmation = self.listen()
                        self.emit_mic_activated(False)
                        if retry_confirmation and self.is_confirmation(retry_confirmation):
                            self.send_and_wait("Thank you for clarifying! Let's continue.")
                            self.listener_turns_completed += 1
                            break  # Exit the loop and proceed to problem-solving
                        else:
                            self.send_and_wait("Let's move on for now.")
                            self.listener_turns_completed += 1
                            break  # Exit the loop and proceed to problem-solving
                    else:
                        self.send_and_wait("Let's move on for now.")
                        self.listener_turns_completed += 1
                        break  # Exit the loop and proceed to problem-solving
            self.save_conversation()
            if self.speaker_turns_completed >= 1 and self.listener_turns_completed >= 1:
                return self.problem_solving_phase()
            else:
                self.switch_roles()
                return True
        except Exception as e:
            self.save_conversation()
            return False

    def speaker_mode(self):
        try:
            print("[BOT] Entering speaker mode")
            self.emit_mic_activated(False)
            if not self.role_explained:
                self.send_and_wait("As the speaker, I'll share my thoughts. Your job is to listen and repeat what you heard.")
                self.role_explained = True
            i_statement = self.generate_i_statement()
            # Ensure I-statement is complete (ends with a period)
            if not i_statement.strip().endswith(('.', '!', '?')):
                i_statement = i_statement.strip() + '.'
            # Send the whole I-statement as one message
            self.send_and_wait(i_statement.strip())
            self.send_and_wait("Can you tell me what you heard?")
            # Activate mic immediately after prompt - no wait_for_audio_to_finish() here
            self.emit_mic_activated(True)
            user_response = self.listen()
            self.emit_mic_activated(False)
            
            # Check if user response is too short, unclear, or completely wrong
            if not user_response or len(user_response.strip()) < 5:
                self.send_and_wait("I didn't hear you clearly. Could you please repeat what I said?")
                self.emit_mic_activated(True)
                user_response = self.listen()
                self.emit_mic_activated(False)
                if not user_response or len(user_response.strip()) < 5:
                    self.send_and_wait("Let's try again. I said: " + i_statement.strip())
                    self.emit_mic_activated(True)
                    user_response = self.listen()
                    self.emit_mic_activated(False)
                    if not user_response or len(user_response.strip()) < 5:
                        self.send_and_wait("Let's move on for now.")
                        self.speaker_turns_completed += 1
                        self.switch_roles()
                        return True
            
            print(f"[USER INPUT RECEIVED] {user_response}")
            if self.is_goodbye(user_response):
                self.send_and_wait("Goodbye! It was nice talking with you.")
                self.save_conversation()
                return False
            
            # Check if user response is completely unrelated to the I-statement
            i_statement_keywords = set(i_statement.lower().split())
            user_response_keywords = set(user_response.lower().split())
            common_keywords = i_statement_keywords.intersection(user_response_keywords)
            
            # If very few keywords match, the user likely misheard
            if len(common_keywords) < 2 and len(i_statement_keywords) > 5:
                self.send_and_wait("I think you might have misheard me. I said: " + i_statement.strip())
                self.send_and_wait("Could you please repeat what I said?")
                self.emit_mic_activated(True)
                user_response = self.listen()
                self.emit_mic_activated(False)
                if not user_response or len(user_response.strip()) < 5:
                    self.send_and_wait("Let's move on for now.")
                    self.speaker_turns_completed += 1
                    self.switch_roles()
                    return True
            
            # If user input is still too short or unclear, prompt again
            if len(user_response.strip().split()) < 3:
                self.send_and_wait("Could you say a bit more about what you heard me say?")
                self.emit_mic_activated(True)
                user_response = self.listen()
                self.emit_mic_activated(False)
                if not user_response or len(user_response.strip().split()) < 3:
                    self.send_and_wait("Let's move on for now.")
                    self.speaker_turns_completed += 1
                    self.switch_roles()
                    return True
            
            paraphrased = self.paraphrase_for_listener(user_response)
            self.send_and_wait(paraphrased)
            self.send_and_wait(self.get_confirmation_prompt())
            self.emit_mic_activated(True)
            confirmation = self.listen()
            self.emit_mic_activated(False)
            
            if confirmation and self.is_confirmation(confirmation):
                self.send_and_wait("Yes, that's right. Thank you!")
                self.speaker_turns_completed += 1
                self.switch_roles()
            else:
                # Only ask for clarification if user explicitly says "No" or gives unclear feedback
                if confirmation and confirmation.strip().lower() in ["no", "not really", "not quite", "not exactly", "that is not what i said"]:
                    self.send_and_wait("I understand. Could you please repeat what I said in your own words?")
                    self.emit_mic_activated(True)
                    retry_response = self.listen()
                    self.emit_mic_activated(False)
                    if retry_response and len(retry_response.strip()) >= 5:
                        retry_paraphrased = self.paraphrase_for_listener(retry_response)
                        self.send_and_wait(retry_paraphrased)
                        self.send_and_wait(self.get_confirmation_prompt())
                        self.emit_mic_activated(True)
                        retry_confirmation = self.listen()
                        self.emit_mic_activated(False)
                        if retry_confirmation and self.is_confirmation(retry_confirmation):
                            self.send_and_wait("Thank you for clarifying! Let's continue.")
                            self.speaker_turns_completed += 1
                            self.switch_roles()
                        else:
                            self.send_and_wait("Let's move on for now.")
                            self.speaker_turns_completed += 1
                            self.switch_roles()
                    else:
                        self.send_and_wait("Let's move on for now.")
                        self.speaker_turns_completed += 1
                        self.switch_roles()
                else:
                    # If confirmation is unclear or missing, assume it's correct and continue
                    self.send_and_wait("Thank you! Let's continue.")
                    self.speaker_turns_completed += 1
                    self.switch_roles()
            return True
        except Exception as e:
            print(f"Error in speaker mode: {e}")
            self.save_conversation()
            return False

    def generate_i_statement(self):
        """Generate a proper "I" statement with specific examples about the selected issue"""
        if not self.selected_issue:
            self.selected_issue = "How to manage household responsibilities together"
            
        prompt = f"""Generate a proper "I" statement about this specific issue: {self.selected_issue}
        
        Rules:
        1. Start with "I feel..." or "I think..." or "I believe..."
        2. Focus ONLY on the specific issue: {self.selected_issue}
        3. Include specific examples or situations related to this issue
        4. Express emotions and thoughts clearly
        5. Avoid blaming language
        6. Keep it under 25 words
        7. Make it personal and relatable
        8. Focus on your perspective, not the other person's actions
        9. Use simple, clear language
        10. DO NOT mention "another issue" or "different issue"
        11. Stay focused on the topic: {self.selected_issue}
        
        Example for "household chores":
        "I feel overwhelmed when I have to do most of the household chores by myself. For example, last week I ended up doing the dishes every night, and it made me feel unappreciated."
        
        Generate a similar statement for: {self.selected_issue}
        
        Make sure the statement is clear, specific, and directly related to the selected issue."""
        
        try:
            response = self.llm_api.generate_response([{"role": "user", "content": prompt}])
            if response and response.strip():
                # Validate the response
                cleaned_response = response.strip()
                
                # Check for problematic phrases
                problematic_phrases = ["another issue", "different issue", "not previously discussed", "other issue"]
                if any(phrase in cleaned_response.lower() for phrase in problematic_phrases):
                    # Use fallback if response contains problematic phrases
                    return f"I feel that {self.selected_issue} is important for our relationship. I want to make sure we're both contributing fairly and feeling appreciated."
                
                if len(cleaned_response.split()) > 30 or "?" in cleaned_response:
                    # Use fallback if response is too long or unclear
                    return f"I feel that {self.selected_issue} is important for our relationship. I want to make sure we're both contributing fairly and feeling appreciated."
                
                return cleaned_response
            else:
                # Fallback I statement
                return f"I feel that {self.selected_issue} is important for our relationship. I want to make sure we're both contributing fairly and feeling appreciated."
        except Exception as e:
            print(f"Error generating I statement: {e}")
            return f"I feel that {self.selected_issue} is important for our relationship. I want to make sure we're both contributing fairly and feeling appreciated."

    def send_and_wait(self, text):
        """
        Send a message to the user with optional TTS and wait for audio to finish
        """
        try:
            print(f"[BOT] Sending message: {text}")
            
            # Generate TTS audio using Groq
            audio_data_url = groq_text_to_speech(text, return_bytes=False)
            
            if sio.connected:
                if audio_data_url:  # Only emit audio if TTS succeeded
                    # Extract base64 data from data URL
                    if audio_data_url.startswith("data:audio/wav;base64,"):
                        audio_base64 = audio_data_url.split(",")[1]
                        sio.emit("play_audio_base64", {
                            "audio_base64": audio_base64, 
                            "mime": "audio/wav",
                            "session_id": self.session_id
                        }, room=self.session_id)
                        # Wait for audio to finish playing
                        self.wait_for_audio_to_finish()
                    else:
                        # Fallback to old method
                        sio.emit("play_audio", {
                            "url": audio_data_url,
                            "session_id": self.session_id
                        }, room=self.session_id)
                        self.wait_for_audio_to_finish()
                else:
                    # TTS failed, emit a notification and continue with text only
                    sio.emit("tts_failed", {
                        "message": "Audio unavailable - text message only",
                        "session_id": self.session_id
                    }, room=self.session_id)
                    # Brief pause to simulate speech timing
                    time.sleep(len(text) * 0.05)  # Rough estimate of speech duration
            else:
                # Brief pause
                time.sleep(1)
                    
            # Always emit the text message
            self.emit_message(text, "bot")
            
        except Exception as e:
            # Still emit the text message even if everything fails
            self.emit_message(text, "bot")
            # Brief pause
            time.sleep(1)

    def listen(self):
        """
        Wait for user input from the web interface instead of local microphone
        """
        print("[BOT] Waiting for user input from web interface...")
        try:
            # Instead of using local microphone, wait for user input via SocketIO
            # This will be handled by the web interface
            self.waiting_for_user_input = True
            self.user_input_received = None
            
            print("[BOT] Set waiting_for_user_input to True")
            
            # Set up a timeout for user input - increased to 60 seconds
            timeout = time.time() + 60  # 60 second timeout
            while self.waiting_for_user_input and time.time() < timeout:
                time.sleep(0.1)
                if self.user_input_received:
                    result = self.user_input_received
                    self.user_input_received = None
                    self.waiting_for_user_input = False
                    print(f"[USER] {result}")
                    return result
            
            print("[BOT] Timeout waiting for user input")
            self.waiting_for_user_input = False
            return None
        except Exception as e:
            print(f"[ERROR] Failed to listen for speech: {e}")
            self.waiting_for_user_input = False
            return None

    def on_user_input(self, data):
        """Handle user input received from web interface"""
        if self.waiting_for_user_input:
            # Check if message is for this session
            message_session_id = data.get('session_id') if isinstance(data, dict) else None
            if message_session_id and message_session_id != self.session_id:
                return  # Ignore messages for other sessions
            
            user_text = data.get('text', '') if isinstance(data, dict) else str(data)
            self.user_input_received = user_text
            self.waiting_for_user_input = False
            
            # Add user message to conversation history
            if user_text and user_text.strip():
                # Detect emotion for user message
                user_emotion = detect_emotion(user_text)
                self.current_emotion = user_emotion
                
                # Add user message to conversation history
                self.conversation_history.append({
                    "speaker": "user",
                    "message": user_text.strip(),
                    "emotion": user_emotion,
                    "turn_count": self.turn_count,
                    "bot_role": self.bot_role,
                    "user_role": self.user_role,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "session_id": self.session_id
                })
                
                # Save to Firebase immediately for user messages
                if db is not None:
                    try:
                        db.collection("sessions").document(self.session_id).set({
                            "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "bot_character": self.character_type,
                            "history": self.conversation_history,
                            "current_turn": self.turn_count,
                            "bot_role": self.bot_role,
                            "user_role": self.user_role,
                            "selected_issue": self.selected_issue,
                            "speaker_turns_completed": self.speaker_turns_completed,
                            "listener_turns_completed": self.listener_turns_completed,
                            "session_id": self.session_id
                        })
                    except Exception as e:
                        pass
        else:
            print("[BOT] Not waiting for user input, ignoring message")

    def switch_roles(self):
        self.save_conversation()
        self.bot_role = "listener" if self.bot_role == "speaker" else "speaker"
        self.user_role = "speaker" if self.bot_role == "listener" else "listener"
        # Increment turn count when roles switch
        self.turn_count += 1
        
        if not self.role_explained:
            if self.bot_role == "listener":
                self.send_and_wait("Let's switch roles now! Now you are the speaker and I'll listen. As the speaker, share your thoughts. I'll listen and repeat what I hear.")
            else:
                self.send_and_wait("Let's switch roles now! Now I'm the speaker and you'll listen. As the listener, repeat what you hear so I feel understood.")
            self.role_explained = True
        else:
            # Combine role switch and reminder into single message
            if self.bot_role == "listener":
                self.send_and_wait("Let's switch roles now! Remember: as speaker, you share thoughts. As listener, I repeat what I hear.")
            else:
                self.send_and_wait("Let's switch roles now! Remember: as speaker, I share thoughts. As listener, you repeat what you hear.")
        self.send_and_wait(self.get_friendly_phrase())

    def emit_mic_activated(self, activated):
        """Emit mic activation status to specific session."""
        try:
            if sio.connected:
                sio.emit('mic_activated', {
                    'activated': activated,
                    'session_id': self.session_id
                }, room=self.session_id)
        except Exception as e:
            pass

    def emit_message(self, message, sender):
        try:
            # Add bot message to conversation history with enhanced metadata
            self.conversation_history.append({
                "speaker": sender,
                "message": message,
                "emotion": self.current_emotion,
                "turn_count": self.turn_count,
                "bot_role": self.bot_role,
                "user_role": self.user_role,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": self.session_id
            })

            if sio.connected:
                # Send to specific session room instead of broadcasting
                sio.emit("new_message", {
                    "text": message, 
                    "sender": sender,
                    "session_id": self.session_id
                }, room=self.session_id)

            # Only save to Firebase if it's available
            if db is not None:
                db.collection("sessions").document(self.session_id).set({
                    "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "bot_character": self.character_type,
                    "history": self.conversation_history,
                    "current_turn": self.turn_count,
                    "bot_role": self.bot_role,
                    "user_role": self.user_role,
                    "selected_issue": self.selected_issue,
                    "speaker_turns_completed": self.speaker_turns_completed,
                    "listener_turns_completed": self.listener_turns_completed,
                    "session_id": self.session_id
                })

        except Exception as e:
            print(f"[ERROR] Failed to emit message: {e}")

    def integrated_mode(self):
        conversation_rounds = 0
        max_rounds = 5  # Limit conversation to prevent infinite loops
        
        # Start with issue selection phase
        if not self.issue_selection_phase():
            return
        
        while conversation_rounds < max_rounds:
            print(f"[BOT] Starting conversation round {conversation_rounds + 1}/{max_rounds}")
            
            if self.bot_role == "listener":
                success = self.listener_mode()
            else:
                success = self.speaker_mode()
                
            if not success:
                print("[BOT] Conversation ended by user or error")
                break
                
            conversation_rounds += 1
            self.save_conversation()
        
        if conversation_rounds >= max_rounds:
            self.send_and_wait("Thank you for this wonderful conversation! Let's wrap up here.")
            print("[BOT] Conversation completed - reached maximum rounds")
        
        self.save_conversation()

    def issue_selection_phase(self):
        try:
            print("[BOT] Starting issue selection phase")
            self.send_friendly_introduction()
            topics = self.generate_issue_suggestions()
            prompt = f"What would you like to talk about today? For example: {topics}, or your own topic."
            self.send_and_wait(prompt)
            self.emit_mic_activated(True)
            user_issue = self.listen()
            self.emit_mic_activated(False)
            if not user_issue or len(user_issue.strip()) < 3:
                self.send_and_wait("Please tell me more about your issue.")
                self.emit_mic_activated(True)
                user_issue = self.listen()
                self.emit_mic_activated(False)
            cleaned_issue = self.clean_issue_choice(user_issue)
            vague_phrases = [
                "something else", "my own issue", "my own topic", "different issue", "other issue", "another issue", "i want to discuss", "i would like to discuss", "i'd like to discuss", "i want to talk about", "i would like to talk about"
            ]
            if any(phrase in cleaned_issue.lower() for phrase in vague_phrases):
                self.send_and_wait("Please tell me more about your topic. What would you like to discuss?")
                self.emit_mic_activated(True)
                user_issue_detail = self.listen()
                self.emit_mic_activated(False)
                if user_issue_detail and len(user_issue_detail.strip()) > 3:
                    self.selected_issue = self.clean_and_paraphrase_issue(user_issue_detail, natural=True)
                else:
                    self.selected_issue = "a topic of your choice"
            else:
                self.selected_issue = self.clean_and_paraphrase_issue(cleaned_issue, natural=True)
            self.send_and_wait(f"Thanks for sharing. We'll talk about: {self.selected_issue}")
            self.send_and_wait("I'll start as speaker. You listen.")
            return True
        except Exception as e:
            print(f"Error in issue selection phase: {e}")
            return False

    def clean_issue_choice(self, user_input):
        """Clean and format the user's issue choice"""
        # Remove common phrases that don't add meaning
        cleaned = user_input.strip().lower()
        
        # Define phrases to remove
        phrases_to_remove = [
            "i have a different issue that i would like to discuss",
            "i have a different issue i would like to discuss",
            "i have a different issue i like to discuss", 
            "i have a different issue i'd like to discuss",
            "i want to discuss",
            "i would like to discuss",
            "i'd like to discuss",
            "i want to talk about",
            "i would like to talk about"
        ]
        
        # Remove the phrases
        for phrase in phrases_to_remove:
            if cleaned.startswith(phrase):
                cleaned = cleaned[len(phrase):].strip()
                break
        
        # If nothing meaningful remains, use a default
        if not cleaned or len(cleaned) < 5:
            return "How to improve our communication and understanding"
        
        # Capitalize first letter and return
        return cleaned.capitalize()

    def clean_and_paraphrase_issue(self, user_input, natural=False):
        # Use LLM paraphrase for awkward or unclear user input
        cleaned = user_input.strip()
        if len(cleaned) < 5 or cleaned.lower() in ["yes", "no", "ok", "okay"]:
            return "a personal topic you'd like to discuss" if natural else "a personal issue you'd like to discuss"
        # Use LLM paraphrase, but keep under 12 words
        paraphrased = paraphrase(cleaned)
        if natural:
            # Remove 'You said:' and make it a natural phrase
            if paraphrased.lower().startswith("you said"):
                paraphrased = paraphrased[8:].strip(':,. ')
            paraphrased = re.sub(r'^[:.,\s]+', '', paraphrased)
            return paraphrased[0].upper() + paraphrased[1:] if paraphrased else "your personal topic"
        return paraphrased if len(paraphrased.split()) <= 12 else "Let's talk about your main concern."

    def generate_issue_suggestions(self):
        issues = [
            "household chores",
            "work-life balance",
            "making decisions",
        ]
        return ", ".join(issues)

    def problem_solving_phase(self):
        from bot.response_generator import detect_hardship, generate_empathetic_response
        try:
            print("[BOT] Entering problem-solving phase")
            self.emit_mic_activated(False)
            # Combine problem-solving introduction messages
            self.send_and_wait("Now let's work together to find a solution. What idea do you have?")
            self.emit_mic_activated(True)
            user_solutions = self.listen()
            self.emit_mic_activated(False)
            if user_solutions:
                is_incomplete = self.is_incomplete_input(user_solutions)
                if is_incomplete or len(user_solutions.strip()) < 5 or user_solutions.strip().endswith("?"):
                    self.send_and_wait("Could you share your idea or what you think might help?")
                    self.emit_mic_activated(True)
                    clarification = self.listen()
                    self.emit_mic_activated(False)
                    if not clarification or len(clarification.strip()) < 5 or self.is_incomplete_input(clarification):
                        self.send_and_wait("No worries. Let's brainstorm together. What would help you most?")
                    else:
                        if detect_hardship(clarification):
                            empathetic = generate_empathetic_response(clarification)
                            self.send_and_wait(empathetic)
                        else:
                            collaborative_response = self.generate_collaborative_response(clarification)
                            self.send_and_wait(collaborative_response)
                elif detect_hardship(user_solutions):
                    empathetic = generate_empathetic_response(user_solutions)
                    self.send_and_wait(empathetic)
                else:
                    collaborative_response = self.generate_collaborative_response(user_solutions)
                    self.send_and_wait(collaborative_response)
            else:
                self.send_and_wait("No worries. Let's brainstorm together. What would help you most?")
            self.send_and_wait("That was a great conversation! Thanks for practicing with me. Come back anytime you want to talk.")
            self.save_conversation()
            return False
        except Exception as e:
            print(f"Error in problem-solving phase: {e}")
            self.save_conversation()
            return False

    def is_incomplete_input(self, text):
        """Check if user input appears incomplete or unclear"""
        if not text:
            return True
            
        text = text.strip()
        
        # Check for trailing conjunctions (incomplete sentences)
        trailing_conjunctions = ["and", "but", "or", "so", "because", "however", "although", "while", "though"]
        words = text.split()
        if words and words[-1].lower() in trailing_conjunctions:
            return True
            
        # Check for trailing prepositions
        trailing_prepositions = ["with", "to", "for", "in", "on", "at", "by", "from", "about", "of", "up", "out"]
        if words and words[-1].lower() in trailing_prepositions:
            return True
            
        # Check for incomplete phrases
        incomplete_phrases = ["i think", "maybe", "perhaps", "possibly", "i guess", "i suppose"]
        text_lower = text.lower()
        if any(phrase in text_lower and not text_lower.endswith(phrase) for phrase in incomplete_phrases):
            # If it's just the phrase without elaboration
            if len(text.split()) <= 3:
                return True
                
        # Check for very short responses that might be incomplete
        if len(text.split()) <= 2 and not text.endswith(('.', '!', '?')):
            return True
            
        return False

    def generate_collaborative_response(self, user_solutions):
        """Generate a collaborative response to user's solutions"""
        # Check if the input is incomplete or unclear
        if self.is_incomplete_input(user_solutions):
            return "That's a good start. Let's explore that idea further together."
            
        prompt = f"""The user suggested this solution: {user_solutions}
        
        Generate a brief, collaborative response that:
        1. Acknowledges their idea positively but not overly enthusiastically
        2. Builds on their suggestion modestly
        3. Shows willingness to work together
        4. Keeps it under 20 words
        5. Uses "we" statements to show partnership
        6. Avoids being overly excited or using exclamation marks"""
        
        try:
            response = self.llm_api.generate_response([{"role": "user", "content": prompt}])
            if response and response.strip():
                return response.strip()
            else:
                return "That's a good approach. Let's work on this together."
        except Exception as e:
            print(f"Error generating collaborative response: {e}")
            return "That's a good approach. Let's work on this together."

    def is_confirmation(self, text):
        confirmation_phrases = ["yes", "correct", "right", "that is correct", "yes that is correct", "affirmative", "indeed"]
        negation_phrases = ["no", "not", "incorrect", "wrong", "that's not right", "nope"]
        if not text:
            return False
        text_lower = text.lower()
        # If both yes and no/negation present, treat as ambiguous
        if any(yes in text_lower for yes in confirmation_phrases) and any(no in text_lower for no in negation_phrases):
            return None  # ambiguous
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

    def generate_validation_response(self, user_input, emotion):
        """Generate a validating response that shows empathy and understanding."""
        emotion_responses = {
            "happy": "I can hear the joy in your voice. That sounds wonderful.",
            "sad": "I can sense that this is difficult for you. I'm here to listen.",
            "angry": "I understand this is frustrating for you. Your feelings are valid.",
            "neutral": "Thank you for sharing that with me. I appreciate your openness.",
            "anxious": "I can hear the concern in your voice. It's okay to feel this way."
        }
        
        base_response = emotion_responses.get(emotion, "Thank you for sharing that with me.")
        
        # Add a follow-up to encourage more sharing
        follow_ups = [
            "Please continue sharing your thoughts.",
            "I'd love to hear more about it.",
            "Feel free to elaborate on that.",
            "Please go on, I'm listening attentively."
        ]
        
        import random
        return f"{base_response} {random.choice(follow_ups)}"

    def save_conversation(self):
        """Save conversation to local file and Firebase with enhanced metadata"""
        try:
            # Ensure data directory exists
            os.makedirs(CONVERSATION_DIR, exist_ok=True)
            
            # Create enhanced conversation data
            conversation_data = {
                "session_id": self.session_id,
                "session_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bot_character": self.character_type,
                "selected_issue": self.selected_issue,
                "conversation_history": self.conversation_history,
                "final_stats": {
                    "total_messages": len(self.conversation_history),
                    "bot_messages": len([msg for msg in self.conversation_history if msg["speaker"] == "bot"]),
                    "user_messages": len([msg for msg in self.conversation_history if msg["speaker"] == "user"]),
                    "speaker_turns_completed": self.speaker_turns_completed,
                    "listener_turns_completed": self.listener_turns_completed,
                    "conversation_rounds": self.turn_count
                },
                "emotion_summary": {
                    "user_emotions": [msg["emotion"] for msg in self.conversation_history if msg["speaker"] == "user"],
                    "bot_emotions": [msg["emotion"] for msg in self.conversation_history if msg["speaker"] == "bot"]
                }
            }
            
            # Save to local file
            with open(self.session_filename, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
            
            print(f"[LOCAL] Session saved to {self.session_filename}")
            
            # Save to Firebase with enhanced data
            if db is not None:
                db.collection("sessions").document(self.session_id).set(conversation_data)
                print(f"[FIREBASE] Session saved to Firebase with ID: {self.session_id}")
                
        except Exception as e:
            print(f"[ERROR] Failed to save conversation: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")

    def signal_handler(sig, frame):
        print("\n[INFO] Exiting gracefully... Saving conversation.")
        bot.save_conversation()
        sys.exit(0)

    def main_loop(self):
        try:
            self.integrated_mode()
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard Interrupt detected. Saving conversation...")
            self.save_conversation()
            sys.exit(0)

    def is_user_paraphrase(self, user_input):
        # Detect if user input is a paraphrase/confirmation
        paraphrase_markers = [
            'you said', 'is that what you said', 'did i get it right', 'did i understand',
            'am i correct', 'let me know if', 'did i hear', 'did i get', 'did i understand you'
        ]
        user_input_lower = user_input.lower()
        return any(marker in user_input_lower for marker in paraphrase_markers)

if __name__ == "__main__":
    bot = ConversationBot()
    bot.main_loop()
