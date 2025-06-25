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
    # Don't connect here - wait until we have the session ID
    pass
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

@sio.event  
def session_assigned(data):
    print(f"[BOT] Received session assignment: {data}")
    # The server is assigning us a session ID - this should match our intended session

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

        # Connect to SocketIO server with session ID
        self.connect_to_server()
        
        sio.on("bot_audio_ended", self.on_audio_finished)
        sio.on("user_input", self.on_user_input)
        self.waiting_for_audio_end = False
        self.waiting_for_user_input = False
        self.user_input_received = None

    def connect_to_server(self):
        """Connect to SocketIO server with session ID"""
        try:
            # Connect with session ID parameter so server assigns us to correct room
            connect_url = f"{SERVER_URL}?session_id={self.session_id}"
            sio.connect(connect_url)
            print(f"[INFO] Connected to SocketIO server at {connect_url}")
        except Exception as e:
            print(f"[WARNING] Failed to connect to SocketIO server: {e}")
            print("[INFO] Will attempt to reconnect automatically...")

    def on_audio_finished(self, data=None):
        self.waiting_for_audio_end = False

    def wait_for_audio_to_finish(self):
        self.waiting_for_audio_end = True
        timeout = time.time() + 20  # Extended from 12 to 20 seconds for audio playback
        while self.waiting_for_audio_end and time.time() < timeout:
            time.sleep(0.1)

    def add_natural_pause(self, message_type="normal"):
        """Add natural conversational pauses for more realistic bot pacing"""
        pause_durations = {
            "introduction": 1.0,    # Longer pause after introductions
            "transition": 0.8,      # Pause when switching topics/roles  
            "thinking": 0.6,        # Brief thinking pause
            "normal": 0.4,          # Standard pause between messages
            "quick": 0.2            # Short pause for confirmations
        }
        
        duration = pause_durations.get(message_type, 0.8)
        print(f"[BOT] Adding natural pause ({message_type}): {duration}s")
        time.sleep(duration)

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
            self.add_natural_pause("introduction")
            self.send_and_wait("Today, we'll practice the Speaker-Listener Technique. We'll take turns sharing and listening to understand each other better.")
            self.add_natural_pause("normal")
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
        
        # Check if paraphrased already has template phrases to avoid duplication
        template_starters = ["it sounds like", "i hear you saying", "what i hear", "if i understand"]
        already_has_template = any(paraphrased.lower().startswith(starter) for starter in template_starters)
        
        if already_has_template:
            # Paraphrase function already provided a complete response
            # Remove any quotes that might be causing duplication
            paraphrased = paraphrased.replace('"', '').replace('"', '').replace('"', '')
            return paraphrased
        
        # If the paraphrased text contains quotes, it might be a quoted response that needs unwrapping
        if '"' in paraphrased or '"' in paraphrased or '"' in paraphrased:
            # Extract the actual content from quotes
            import re
            quoted_match = re.search(r'["""]([^"""]+)["""]', paraphrased)
            if quoted_match:
                paraphrased = quoted_match.group(1).strip()
        
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
                    f"What I hear you asking is: {paraphrased}",
                    f"If I understand you right, you're wondering: {paraphrased}",
                    f"It sounds like you're questioning: {paraphrased}"
                ]
            else:
                # It might be a rhetorical question or statement
                templates = [
                    f"What I hear you saying is: {paraphrased}",
                    f"If I understand you right: {paraphrased}",
                    f"It sounds like: {paraphrased}"
                ]
        else:
            templates = [
                f"What I hear you saying is: {paraphrased}",
                f"If I understand you right: {paraphrased}",
                f"It sounds like: {paraphrased}"
            ]
        
        result = random.choice(templates)
        # Remove any double spaces or awkward punctuation
        result = re.sub(r',?\s*:\s*', ': ', result)
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
                self.add_natural_pause("quick")
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
            # Removed intermediate save - will save at conversation end
            if self.speaker_turns_completed >= 1 and self.listener_turns_completed >= 1:
                return self.problem_solving_phase()
            else:
                self.switch_roles()
                return True
        except Exception as e:
            # Removed intermediate save - will save at conversation end
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
            self.add_natural_pause("thinking")
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
                # Removed intermediate save - will save at conversation end
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
            self.add_natural_pause("quick")
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
            # Removed intermediate save - will save at conversation end
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
            print(f"[BOT] send_and_wait called with: {text[:50]}...")
            
            # Generate TTS audio using Groq
            print(f"[BOT] Generating TTS audio")
            try:
                audio_data_url = groq_text_to_speech(text, return_bytes=False)
            except Exception as tts_error:
                print(f"[BOT] TTS error: {tts_error}")
                audio_data_url = None
            print(f"[BOT] TTS generation completed, audio_data_url: {bool(audio_data_url)}")
            
            if sio.connected:
                print(f"[BOT] SocketIO is connected")
                if audio_data_url:  # Only emit audio if TTS succeeded
                    # Extract base64 data from data URL
                    if audio_data_url.startswith("data:audio/wav;base64,"):
                        audio_base64 = audio_data_url.split(",")[1]
                        print(f"[BOT] Emitting audio to session {self.session_id}")
                        sio.emit("play_audio_base64", {
                            "audio_base64": audio_base64, 
                            "mime": "audio/wav",
                            "session_id": self.session_id
                        })
                        # Wait for audio to finish playing
                        print(f"[BOT] Waiting for audio to finish")
                        self.wait_for_audio_to_finish()
                        print(f"[BOT] Audio playback completed")
                    else:
                        # Fallback to old method
                        print(f"[BOT] Using fallback audio method")
                        sio.emit("play_audio", {
                            "url": audio_data_url,
                            "session_id": self.session_id
                        })
                        self.wait_for_audio_to_finish()
                else:
                    # TTS failed, emit a notification and continue with text only
                    print(f"[BOT] TTS failed, continuing with text only")
                    sio.emit("tts_failed", {
                        "message": "Audio unavailable - text message only",
                        "session_id": self.session_id
                    })
                    # Brief pause to simulate speech timing
                    time.sleep(len(text) * 0.05)  # Rough estimate of speech duration
                    
            else:
                print(f"[BOT] SocketIO not connected, skipping audio")
                # Brief pause
                time.sleep(1)
                
            # Always emit the text message
            print(f"[BOT] Emitting text message")
            self.emit_message(text, "bot")
            print(f"[BOT] send_and_wait completed for: {text[:50]}...")
            
        except Exception as e:
            print(f"[ERROR] Exception in send_and_wait: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            # Still emit the text message even if everything fails
            self.emit_message(text, "bot")
            # Brief pause
            time.sleep(1)

    def listen(self):
        """Listen for user input with multiple retry attempts and proactive reactivation"""
        try:
            print(f"[BOT] Starting to listen for user input for session {self.session_id}")
            
            max_attempts = 3  # Allow 3 attempts for user to respond
            attempt = 1
            
            while attempt <= max_attempts:
                print(f"[BOT] Listen attempt {attempt}/{max_attempts}")
                
                self.waiting_for_user_input = True
                self.user_input_received = None
                
                print("[BOT] Set waiting_for_user_input to True")
                
                # Set up a timeout for user input with shorter check intervals for responsiveness
                timeout = time.time() + 45  # Extended from 30 to 45 second timeout
                last_keepalive = time.time()
                keepalive_interval = 5  # Reduced from 10 to 5 seconds for more frequent microphone reactivation
                
                while self.waiting_for_user_input and time.time() < timeout:
                    time.sleep(0.1)
                    
                    # Check for user input
                    if self.user_input_received:
                        result = self.user_input_received
                        self.user_input_received = None
                        self.waiting_for_user_input = False
                        print(f"[BOT] Received user input: {result}")
                        return result
                    
                    # Send periodic keep-alive microphone signals to maintain responsiveness
                    current_time = time.time()
                    if current_time - last_keepalive > keepalive_interval:
                        print(f"[BOT] Sending microphone keep-alive signal (attempt {attempt})")
                        self.emit_mic_activated(True)
                        last_keepalive = current_time
                
                print(f"[BOT] Timeout on attempt {attempt} waiting for user input (45 seconds)")
                self.waiting_for_user_input = False
                
                # If not the last attempt, reactivate microphone and try again
                if attempt < max_attempts:
                    print(f"[BOT] Reactivating microphone for attempt {attempt + 1}")
                    self.emit_mic_activated(True)
                    time.sleep(0.5)  # Reduced from 2 seconds to 0.5 seconds for immediate reactivation
                    attempt += 1
                else:
                    print("[BOT] All attempts exhausted, using default response")
                    break
            
            # Return a default response instead of None to keep conversation flowing
            return "I'd like to talk about communication"
            
        except Exception as e:
            print(f"[ERROR] Failed to listen for speech: {e}")
            self.waiting_for_user_input = False
            return "I'd like to talk about communication"

    def on_user_input(self, data):
        """Handle user input received from web interface"""
        print(f"[BOT] Received user_input event: {data}")
        print(f"[BOT] Bot waiting for input: {self.waiting_for_user_input}")
        print(f"[BOT] Bot session ID: {self.session_id}")
        
        if self.waiting_for_user_input:
            # Check if message is for this session
            message_session_id = data.get('session_id') if isinstance(data, dict) else None
            print(f"[BOT] Message session ID: {message_session_id}")
            
            if message_session_id and message_session_id != self.session_id:
                print(f"[BOT] Ignoring message for different session: {message_session_id} != {self.session_id}")
                return  # Ignore messages for other sessions
            
            user_text = data.get('text', '') if isinstance(data, dict) else str(data)
            print(f"[BOT] Processing user input: {user_text}")
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
                
                # Real-time Firebase save disabled to prevent overwrites
                # Final save will happen in save_conversation() with unique timestamp
                print(f"[BOT] User message added to conversation history for session {self.session_id}")
        else:
            print("[BOT] Not waiting for user input, ignoring message")

    def switch_roles(self):
        # Removed intermediate save - will save at conversation end
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
        self.add_natural_pause("transition")
        self.send_and_wait(self.get_friendly_phrase())

    def emit_mic_activated(self, activated):
        """Emit mic activation status to specific session."""
        try:
            if sio.connected:
                sio.emit('mic_activated', {
                    'activated': activated,
                    'session_id': self.session_id
                })
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
                print(f"[BOT] Emitting message: {message[:50]}... from {sender} for session {self.session_id}")
                # Send to specific session room instead of broadcasting
                sio.emit("new_message", {
                    "text": message, 
                    "sender": sender,
                    "session_id": self.session_id
                })
                print(f"[BOT] Message emitted successfully")

            # Save to Firebase with unique document ID - only at end of conversation to avoid overwrites
            # Real-time saves disabled to prevent multiple users overwriting same document
            # Final save will happen in save_conversation() with unique timestamp

        except Exception as e:
            print(f"[ERROR] Failed to emit message: {e}")

    def integrated_mode(self):
        print(f"[BOT] Starting integrated_mode for session {self.session_id}")
        conversation_rounds = 0
        max_rounds = 5  # Limit conversation to prevent infinite loops
        
        # Start with issue selection phase
        print(f"[BOT] Starting issue selection phase")
        if not self.issue_selection_phase():
            print(f"[BOT] Issue selection phase failed, ending conversation")
            return
        
        print(f"[BOT] Issue selection completed, starting conversation rounds")
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
        
        if conversation_rounds >= max_rounds:
            self.send_and_wait("Thank you for this wonderful conversation! Let's wrap up here.")
            print("[BOT] Conversation completed - reached maximum rounds")
        
        # Removed save_conversation() - it's handled by problem_solving_phase at conversation end
        print(f"[BOT] Integrated mode completed for session {self.session_id}")

    def issue_selection_phase(self):
        try:
            print("[BOT] Starting issue selection phase")
            self.send_friendly_introduction()
            print("[BOT] Introduction sent")
            
            topics = self.generate_issue_suggestions()
            prompt = f"What would you like to talk about today? For example: {topics}, or your own topic."
            self.send_and_wait(prompt)
            print("[BOT] Topic prompt sent, activating mic")
            
            self.emit_mic_activated(True)
            user_issue = self.listen()
            self.emit_mic_activated(False)
            print(f"[BOT] Received user issue: {user_issue}")
            
            if not user_issue or len(user_issue.strip()) < 3:
                self.send_and_wait("Please tell me more about your issue.")
                self.emit_mic_activated(True)
                user_issue = self.listen()
                self.emit_mic_activated(False)
            
            cleaned_issue = self.clean_issue_choice(user_issue)
            print(f"[BOT] Cleaned issue: {cleaned_issue}")
            
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
            
            print(f"[BOT] Final selected issue: {self.selected_issue}")
            self.send_and_wait(f"Thanks for sharing. We'll talk about: {self.selected_issue}")
            self.add_natural_pause("thinking")
            self.send_and_wait("I'll start as speaker. You listen.")
            self.add_natural_pause("transition")
            print("[BOT] Issue selection phase completed successfully")
            return True
        except Exception as e:
            print(f"Error in issue selection phase: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
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
        """Clean and properly summarize the user's selected issue using LLM."""
        cleaned = user_input.strip()
        if len(cleaned) < 5 or cleaned.lower() in ["yes", "no", "ok", "okay"]:
            return "a personal topic you'd like to discuss" if natural else "a personal issue you'd like to discuss"
        
        # Use LLM for intelligent issue summarization
        prompt = f"""Summarize this topic into a clear, natural phrase for conversation:

User input: "{cleaned}"

Create a summary that:
1. Captures the main topic clearly
2. Uses natural, grammatically correct language
3. Keeps it under 12 words
4. Makes it suitable for "We'll talk about: [summary]"
5. Avoids awkward phrasing or repetition
6. Uses proper capitalization and spacing
7. Focuses on the core issue or topic

Examples:
- "homework and how hard working it is" → "managing homework workload and stress"
- "balancing work and life" → "work-life balance"
- "my relationship problems" → "relationship challenges"

Only return the clean summary, nothing else."""

        try:
            response = self.llm_api.generate_response([{"role": "user", "content": prompt}])
            
            if response and response.strip():
                summary = response.strip()
                
                # Ensure proper capitalization
                if summary and not summary[0].isupper():
                    summary = summary[0].lower() + summary[1:]
                
                # Remove any quotes or extra punctuation
                summary = summary.strip('"\'.,;:')
                
                # Ensure it's not too long
                if len(summary.split()) <= 12:
                    return summary
                else:
                    # Truncate if too long
                    return ' '.join(summary.split()[:12])
            else:
                # Fallback - clean the original input
                return self.clean_issue_fallback(cleaned)
                
        except Exception as e:
            print(f"Error in issue summarization: {e}")
            return self.clean_issue_fallback(cleaned)
    
    def clean_issue_fallback(self, user_input):
        """Fallback method to clean user input when LLM fails."""
        cleaned = user_input.lower().strip()
        
        # Remove common prefixes
        prefixes_to_remove = [
            "i would like to talk about ",
            "i want to talk about ",
            "i'd like to discuss ",
            "i want to discuss ",
            "talking about ",
            "discuss ",
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        
        # Basic cleanup
        if not cleaned or len(cleaned) < 3:
            return "communication and understanding"
        
        # Ensure it doesn't start with articles unless necessary
        if cleaned.startswith("the "):
            cleaned = cleaned[4:]
        
        return cleaned

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
            self.add_natural_pause("transition")
            self.send_and_wait("That was a great conversation! Thanks for practicing with me. Come back anytime you want to talk.")
            self.save_conversation()
            return False
        except Exception as e:
            print(f"Error in problem-solving phase: {e}")
            # Removed intermediate save - will save at conversation end
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
            
            # Save to Firebase with unique document ID that includes timestamp
            if db is not None:
                # Create unique document ID: session_id + timestamp to prevent overwrites
                firebase_doc_id = f"{self.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                print(f"[FIREBASE] Saving conversation to document ID: {firebase_doc_id}")
                db.collection("conversations").document(firebase_doc_id).set(conversation_data)
                print(f"[FIREBASE] Conversation saved successfully to document: {firebase_doc_id}")
                
                # Also save to sessions collection for compatibility (but with unique ID)
                sessions_doc_id = f"session_{self.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                db.collection("sessions").document(sessions_doc_id).set(conversation_data)
                print(f"[FIREBASE] Session also saved to sessions collection: {sessions_doc_id}")
            else:
                print("[FIREBASE] Firebase not available - skipping cloud save")
                
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
            print(f"[BOT] main_loop started for session {self.session_id}")
            print(f"[BOT] About to call integrated_mode()")
            self.integrated_mode()
            print(f"[BOT] integrated_mode() completed")
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard Interrupt detected. Saving conversation...")
            self.save_conversation()
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Exception in main_loop: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            self.save_conversation()
            sys.exit(1)

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
