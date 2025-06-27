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
        # ALWAYS paraphrase - never shortcut with "Yes, that's right"
        # This is essential for the Speaker-Listener Technique
        
        is_question = user_input.strip().endswith('?')
        paraphrased = paraphrase(user_input)
        
        # Check if paraphrased already has template phrases to avoid duplication
        template_starters = ["it sounds like", "i hear you saying", "what i hear", "if i understand"]
        already_has_template = any(paraphrased.lower().startswith(starter) for starter in template_starters)
        
        if already_has_template:
            # Paraphrase function already provided a complete response
            # Remove any quotes that might be causing duplication
            paraphrased = paraphrased.replace('"', '').replace('"', '').replace('"', '')
            # Clean up any double template phrases like "It sounds like: It sounds like"
            paraphrased = re.sub(r'(It sounds like[:\s]*){2,}', 'It sounds like: ', paraphrased, flags=re.IGNORECASE)
            paraphrased = re.sub(r'(What I hear[:\s]*){2,}', 'What I hear: ', paraphrased, flags=re.IGNORECASE)
            paraphrased = re.sub(r'(If I understand[:\s]*){2,}', 'If I understand: ', paraphrased, flags=re.IGNORECASE)
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
            # Brief combined introduction (reduce from 2 messages to 1)
            if not self.role_explained:
                self.send_and_wait("Let's switch roles now! I'm ready to listen. Take your time.")
                self.role_explained = True
                
            last_paraphrase = None
            max_listener_attempts = 3  # Prevent infinite loops
            listener_attempt = 0
            
            while listener_attempt < max_listener_attempts:
                listener_attempt += 1
                print(f"[BOT] Listener attempt {listener_attempt}/{max_listener_attempts}")
            
                self.emit_mic_activated(True)
                user_input = self.listen()
                self.emit_mic_activated(False)
                
                if not user_input or len(user_input.strip()) < 5:
                    if listener_attempt >= max_listener_attempts:
                        self.send_and_wait("Let's continue with our conversation.")
                        self.listener_turns_completed += 1
                        break
                    self.send_and_wait("Could you share more?")
                    continue
                    
                if self.is_goodbye(user_input):
                    self.send_and_wait("Goodbye! Thanks for practicing with me.")
                    return False
                    
                self.current_emotion = detect_emotion(user_input)
                # Handle "So you said?" or similar
                if user_input.strip().lower() in ["so you said?", "so you said", "what did you say?", "what did you say"] and last_paraphrase:
                    self.send_and_wait(f"{last_paraphrase}")
                    continue
                
                # ALWAYS paraphrase user input - this is the core of listener mode
                try:
                    paraphrased = self.paraphrase_for_listener(user_input)
                    print(f"[BOT] Paraphrased: {paraphrased}")
                    last_paraphrase = paraphrased
                    self.send_and_wait(paraphrased)
                except Exception as e:
                    print(f"[BOT] Error in paraphrasing: {e}")
                    # NEVER use verbatim repetition - create a proper paraphrase fallback
                    paraphrased = self.create_fallback_paraphrase(user_input)
                    last_paraphrase = paraphrased
                    self.send_and_wait(paraphrased)
                # Brief confirmation prompt
                self.send_and_wait("Did I get that right?")
                
                print(f"[BOT] Waiting for confirmation from user")
                self.emit_mic_activated(True)
                confirmation = self.listen()
                self.emit_mic_activated(False)
                print(f"[BOT] Received confirmation: {confirmation}")
                # Check for feedback FIRST, before checking confirmation
                if confirmation and self.is_feedback_about_paraphrasing(confirmation):
                    # User is giving feedback about paraphrasing quality
                    print(f"[BOT] User gave paraphrasing feedback: {confirmation}")
                    self.send_and_wait("You're absolutely right. Let me paraphrase that better:")
                    # Try to generate a better paraphrase
                    better_paraphrase = self.improve_paraphrase(user_input, confirmation)
                    self.send_and_wait(better_paraphrase)
                    self.send_and_wait("Does that capture it better?")
                    
                    self.emit_mic_activated(True)
                    final_confirmation = self.listen()
                    self.emit_mic_activated(False)
                    
                    if final_confirmation and self.is_confirmation(final_confirmation):
                        self.send_and_wait("Great! Thank you for the feedback.")
                    else:
                        self.send_and_wait("Thank you for your patience.")
                    
                    self.listener_turns_completed += 1
                    break
                elif self.is_confirmation(confirmation):
                    self.send_and_wait("Thank you!")
                    self.listener_turns_completed += 1
                    break
                elif confirmation and len(confirmation.strip()) > 2:
                    # User gave a substantive response but it wasn't a clear confirmation
                    print(f"[BOT] User gave non-confirmation response: {confirmation}")
                    if listener_attempt >= max_listener_attempts:
                        self.send_and_wait("Let's continue with our conversation.")
                        self.listener_turns_completed += 1
                        break
                    self.send_and_wait("Let me try again to understand what you said.")
                    continue  # Go back to the beginning of the loop
                else:
                    # Brief retry
                    self.send_and_wait("Could you say it again?")
                    self.emit_mic_activated(True)
                    retry_input = self.listen()
                    self.emit_mic_activated(False)
                    if retry_input and len(retry_input.strip()) >= 5:
                        try:
                            paraphrased = self.paraphrase_for_listener(retry_input)
                            print(f"[BOT] Retry paraphrased: {paraphrased}")
                            last_paraphrase = paraphrased
                            self.send_and_wait(paraphrased)
                        except Exception as e:
                            print(f"[BOT] Error in retry paraphrasing: {e}")
                            # NEVER use verbatim repetition - create a proper paraphrase fallback
                            paraphrased = self.create_fallback_paraphrase(retry_input)
                            last_paraphrase = paraphrased
                            self.send_and_wait(paraphrased)
                        self.send_and_wait("Did I get that right?")
                        self.emit_mic_activated(True)
                        retry_confirmation = self.listen()
                        self.emit_mic_activated(False)
                        if retry_confirmation and self.is_confirmation(retry_confirmation):
                            self.send_and_wait("Thank you!")
                            self.listener_turns_completed += 1
                            break
                        else:
                            self.send_and_wait("Let's continue.")
                            self.listener_turns_completed += 1
                            break
                    else:
                        self.send_and_wait("Let's continue.")
                        self.listener_turns_completed += 1
                        break
                    
            # Safety check: if we exit the loop without completing, force completion
            if listener_attempt >= max_listener_attempts and self.listener_turns_completed == 0:
                print(f"[BOT] Listener mode timed out, forcing completion")
                self.send_and_wait("Thank you for sharing.")
                self.listener_turns_completed += 1
            
            # FIXED: Require minimum 2-3 complete rounds before ending
            min_rounds_each_role = 2
            if (self.speaker_turns_completed >= min_rounds_each_role and 
                self.listener_turns_completed >= min_rounds_each_role):
                # End with understanding validation, NOT problem-solving
                self.send_and_wait("Great practice! We both had a chance to feel heard and understood.")
                self.save_conversation()
                return False
            else:
                self.switch_roles()
            return True
        except Exception as e:
            print(f"[BOT] Exception in listener_mode: {e}")
            import traceback
            print(f"[BOT] Traceback: {traceback.format_exc()}")
            # Try to continue gracefully
            try:
                self.send_and_wait("I apologize, let's continue our conversation.")
                self.listener_turns_completed += 1
                self.switch_roles()
                return True
            except:
                return False

    def speaker_mode(self):
        try:
            print("[BOT] Entering speaker mode")
            self.emit_mic_activated(False)
            if not self.role_explained:
                self.send_and_wait("I'll start as speaker. You listen and repeat what you heard.")
                self.role_explained = True
            
            i_statement = self.generate_i_statement()
            # Ensure I-statement is complete (ends with a period)
            if not i_statement.strip().endswith(('.', '!', '?')):
                i_statement = i_statement.strip() + '.'
            
            # Store the I-statement for later comparison
            self.current_i_statement = i_statement.strip()
            
            # Send the I-statement with quotes to make it clear
            self.send_and_wait(f'"{self.current_i_statement}"')
            
            # Brief prompt - combine with short pause
            self.add_natural_pause("thinking")
            # self.send_and_wait("What did you hear?")
            
            self.emit_mic_activated(True)
            user_response = self.listen()
            self.emit_mic_activated(False)
            
            # Simple retry logic - only one attempt
            if not user_response or len(user_response.strip()) < 5:
                self.send_and_wait("Could you repeat what I said?")
                self.emit_mic_activated(True)
                user_response = self.listen()
                self.emit_mic_activated(False)
                if not user_response or len(user_response.strip()) < 5:
                    self.send_and_wait("Let's continue.")
                    self.speaker_turns_completed += 1
                    self.switch_roles()
                    return True
            
            if self.is_goodbye(user_response):
                self.send_and_wait("Goodbye! Thanks for practicing with me.")
                return False
            
            # Check if user's paraphrase is accurate
            if self.is_accurate_paraphrase(self.current_i_statement, user_response):
                self.send_and_wait("Yes, that's correct!")
                self.speaker_turns_completed += 1
                self.switch_roles()
            else:
                # User didn't paraphrase accurately - provide feedback and correct paraphrase
                self.send_and_wait("Let me help you with that. What I said was:")
                self.send_and_wait(f'"{self.current_i_statement}"')
                # self.send_and_wait("Try to repeat back the key points: my feelings, the situation, and the impact.")
                
                # Give them another chance
                self.emit_mic_activated(True)
                retry_response = self.listen()
                self.emit_mic_activated(False)
                
                if retry_response and self.is_accurate_paraphrase(self.current_i_statement, retry_response):
                    self.send_and_wait("Much better! Thank you.")
                else:
                    # Provide a summary based on the actual I-statement that was said
                    summary = self.summarize_i_statement(self.current_i_statement)
                    self.send_and_wait(f"That's okay. {summary}")
                
                self.speaker_turns_completed += 1
                self.switch_roles()
            return True
        except Exception as e:
            print(f"Error in speaker mode: {e}")
            return False

    def summarize_i_statement(self, i_statement):
        """Create a brief summary of the I-statement for feedback purposes"""
        try:
            # Extract key emotion and topic from the I-statement
            statement_lower = i_statement.lower()
            
            if "feel" in statement_lower:
                if "valued" in statement_lower or "acknowledge" in statement_lower:
                    return "The key point was about feeling valued when efforts are acknowledged."
                elif "content" in statement_lower or "connect" in statement_lower:
                    return "The key point was about feeling content through shared experiences and connection."
                elif "happy" in statement_lower or "joy" in statement_lower:
                    return "The key point was about feeling happier through positive experiences."
                else:
                    return f"The key point was what I said about my feelings."
            elif "think" in statement_lower:
                return "The key point was about my thoughts and perspective."
            elif "believe" in statement_lower:
                return "The key point was about my beliefs and values."
            else:
                return "Let me repeat what I said to help you practice."
        except Exception as e:
            print(f"Error summarizing I-statement: {e}")
            return "Let me repeat what I said to help you practice."

    def generate_i_statement(self):
        """Generate a proper "I" statement with specific examples, but keep the topic open-ended"""
        prompt = '''Generate a proper "I" statement for a practice conversation.

Rules:
1. Start with "I feel...", "I think...", or "I believe..."
2. Do NOT mention any specific topic or issue (keep it open-ended)
3. Include a specific example or situation, but do not reference any particular subject (e.g., no chores, work, family, etc.)
4. Express emotions and thoughts clearly
5. Avoid blaming language
6. Keep it under 20 words
7. Make it personal and relatable
8. Focus on your perspective, not the other person's actions
9. Use simple, clear language
10. Do NOT suggest or hint at any particular topic

Only return the statement, nothing else.'''
        try:
            response = self.llm_api.generate_response([{"role": "user", "content": prompt}])
            if response and response.strip():
                cleaned_response = response.strip()
                # Remove any extra quotes or periods that might be malformed
                cleaned_response = cleaned_response.strip('"\'.,;:')
                # Remove double quotes at start/end if present
                if cleaned_response.startswith('"') and cleaned_response.endswith('"'):
                    cleaned_response = cleaned_response[1:-1].strip()
                # Ensure it ends with a period
                if not cleaned_response.endswith(('.', '!', '?')):
                    cleaned_response += '.'
                
                if len(cleaned_response.split()) > 30 or "?" in cleaned_response:
                    return "I feel that open communication is important. I want to make sure we both feel heard and understood."
                return cleaned_response
            else:
                return "I feel that open communication is important. I want to make sure we both feel heard and understood."
        except Exception as e:
            print(f"Error generating I statement: {e}")
            return "I feel that open communication is important. I want to make sure we both feel heard and understood."

    def send_and_wait(self, text):
        """
        Send a message to the user with optional TTS and wait for audio to finish
        """
        try:
            print(f"[BOT] send_and_wait called with: {text}")
            
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
            
            # Add user message to conversation history only (don't emit to frontend to avoid duplication)
            if user_text and user_text.strip():
                # Add to conversation history with emotion detection
                user_emotion = detect_emotion(user_text)
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
            print(f"[BOT] User input processed for session {self.session_id}")
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
            # Clearly announce who has the floor after role switch
            if self.bot_role == "listener":
                self.send_and_wait("Let's switch roles now! Now you're the speaker - please share your thoughts.")
            else:
                self.send_and_wait("Let's switch roles now! Now I'm the speaker - please listen.")
            self.add_natural_pause("transition")

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
            if sender == "bot":
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
        
        # Start directly as speaker with bot's own topic
        print(f"[BOT] Starting directly as speaker with open-ended topic")
        self.bot_role = "speaker"
        self.user_role = "listener"
        
        # Remove hardcoded topic, keep it open
        self.selected_issue = None
        
        print(f"[BOT] Bot's topic is open-ended.")
        
        # Send introduction message
        self.send_and_wait("Hi, I'm Charisma Bot. Today we'll practice the Speaker-Listener Technique")
        self.add_natural_pause("introduction")
        
        print(f"[BOT] Starting conversation rounds")
        
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
            prompt = f"What would you like to talk about today? For example: {topics}."
            self.send_and_wait(prompt)
            print("[BOT] Topic prompt sent, activating mic")
            
            self.emit_mic_activated(True)
            user_issue = self.listen()
            self.emit_mic_activated(False)
            print(f"[BOT] Received user issue: {user_issue}")
            
            # Handle "My own topic" properly
            if not user_issue or len(user_issue.strip()) < 3:
                self.send_and_wait("What topic would you like to discuss?")
                self.emit_mic_activated(True)
                user_issue = self.listen()
                self.emit_mic_activated(False)
            elif user_issue.lower().strip() in ["my own topic", "own topic", "my topic", "my own"]:
                # Keep asking until we get a specific topic
                attempts = 0
                while attempts < 3:
                    self.send_and_wait("What specific topic would you like to talk about?")
                    self.emit_mic_activated(True)
                    specific_topic = self.listen()
                    self.emit_mic_activated(False)
                    
                    if specific_topic and len(specific_topic.strip()) > 5 and specific_topic.lower().strip() not in ["my own topic", "own topic", "my topic", "my own"]:
                        user_issue = specific_topic
                        break
                    
                    attempts += 1
                    if attempts < 3:
                        self.send_and_wait("Please share a specific topic you'd like to discuss, like 'work stress' or 'family relationships'.")
                
                # If still no specific topic after 3 attempts, use a default
                if not user_issue or user_issue.lower().strip() in ["my own topic", "own topic", "my topic", "my own"]:
                    user_issue = "communication and understanding"
            
            cleaned_issue = self.clean_issue_choice(user_issue)
            print(f"[BOT] Cleaned issue: {cleaned_issue}")
            
            self.selected_issue = self.clean_and_paraphrase_issue(cleaned_issue, natural=True)
            
            print(f"[BOT] Final selected issue: {self.selected_issue}")
            # Combine confirmation and role assignment into one message
            self.send_and_wait(f"Thanks for sharing. We'll talk about: {self.selected_issue}")
            self.add_natural_pause("thinking")
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
        """Suggest common issues to discuss in the Speaker-Listener Technique"""
        suggestions = [
            "household chores, work-life balance, making decisions, or your own topic"
        ]
        return random.choice(suggestions)

    def is_confirmation(self, text):
        confirmation_phrases = ["yes", "correct", "right", "that is correct", "yes that is correct", 
                               "affirmative", "indeed", "uh yes", "uh, yes", "um yes", "um, yes", 
                               "yeah", "yep", "yup", "that's right", "exactly"]
        negation_phrases = ["no", "not", "incorrect", "wrong", "that's not right", "nope", "that's wrong"]
        if not text:
            return False
        text_lower = text.lower().strip()
        
        # Handle feedback with corrections (these are NOT simple confirmations)
        feedback_phrases = ["but you should", "you should have", "but it should", "however you", "except you"]
        if any(phrase in text_lower for phrase in feedback_phrases):
            return False  # This is feedback, not confirmation
        
        # If both yes and no/negation present, treat as ambiguous
        if any(yes in text_lower for yes in confirmation_phrases) and any(no in text_lower for no in negation_phrases):
            return None  # ambiguous
        
        # Check for clear confirmations
        return any(phrase in text_lower for phrase in confirmation_phrases) and not any(no in text_lower for no in negation_phrases)

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

    def signal_handler(self, sig, frame):
        """Handle Ctrl + C to save conversation before exiting."""
        print(f"\n[INFO] Session {self.session_id}: Exiting gracefully... Saving conversation.")
        self.save_conversation()
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
        user_input_lower = user_input.lower().strip()
        
        # Paraphrase markers that indicate user is trying to repeat back
        paraphrase_markers = [
            'you said', 'you feel', 'you think', 'you believe', 'you mentioned',
            'i heard you say', 'what i heard', 'you talked about', 'you were saying'
        ]
        
        # Check if input contains paraphrase markers
        has_markers = any(marker in user_input_lower for marker in paraphrase_markers)
        
        # Check if input is substantial enough to be a paraphrase (more than 10 words)
        is_substantial = len(user_input.split()) >= 10
        
        # Check if it's not just a simple confirmation (including hesitant ones)
        simple_confirmations = ['yes', 'correct', 'right', 'that is correct', 'yes that is correct', 
                              'uh yes', 'uh, yes', 'um yes', 'um, yes', 'yeah', 'yep', 'yup']
        is_simple_confirmation = any(conf in user_input_lower for conf in simple_confirmations)
        
        # It's a paraphrase if it has markers and is substantial, or if it's clearly referencing what was said
        return (has_markers and is_substantial) or (is_substantial and not is_simple_confirmation)

    def is_accurate_paraphrase(self, original_statement, user_paraphrase):
        """Check if user's paraphrase accurately captures the original statement's meaning"""
        try:
            # Clean inputs
            original_clean = original_statement.lower().strip().strip('".')
            user_clean = user_paraphrase.lower().strip()
            
            print(f"[BOT] Checking paraphrase accuracy:")
            print(f"[BOT] Original: {original_clean}")
            print(f"[BOT] User said: {user_clean}")
            
            # STRICT: Immediately reject obvious nonsense content
            nonsense_patterns = [
                'mangoes', 'apples', 'bananas', 'oranges',  # Fruit nonsense
                'blah', 'bla', 'whatever', 'random', 'nonsense',
                'asdfgh', 'qwerty', 'xyz', 'abc',  # Random typing
                'test', 'testing', '123', 'hello world'  # Test inputs
            ]
            
            # Check for repeated nonsense words (like "mangoes, mangoes, mangoes")
            words = user_clean.split()
            if len(words) >= 3:
                # Check if same word repeated 3+ times
                for i in range(len(words) - 2):
                    if words[i] == words[i+1] == words[i+2] and len(words[i]) > 2:
                        print(f"[BOT] Detected repeated nonsense word: {words[i]}")
                        return False
            
            # Check for any nonsense content
            if any(pattern in user_clean for pattern in nonsense_patterns):
                print(f"[BOT] Detected nonsense content in paraphrase")
                return False
            
            # STRICT: Reject if too short to be meaningful
            if len(user_clean.split()) < 5:  # Increased from 5
                print(f"[BOT] Paraphrase too short: {len(user_clean.split())} words (minimum 8)")
                return False
            
            # STRICT: Check for grammatical completeness - reject broken sentences
            broken_patterns = [
                'to.', 'to,', 'and.', 'but.', 'or.', 'closer to.', 'back to.', 
                'with.', 'from.', 'about.', 'like.', 'such.', 'when.',
                'i i ', 'you you ', 'the the ', 'and and ', 'but but ',
                ' closer to', ' back to', ' such like', ' you such',
                'exploding', 'exploading',  # Common speech recognition errors
                'explode the', 'exploding the'  # "exploring" misheard as "exploding"
            ]
            if any(pattern in user_clean for pattern in broken_patterns):
                print(f"[BOT] Detected incomplete/broken sentence structure or speech recognition errors")
                return False
            
            # STRICT: Must contain key perspective transformation words
            required_perspective_indicators = [
                'you feel', 'you said', 'you think', 'you believe', 'you mentioned',
                'you talked about', 'you were saying', 'you expressed', 'you shared'
            ]
            
            has_perspective_transformation = any(indicator in user_clean for indicator in required_perspective_indicators)
            if not has_perspective_transformation:
                print(f"[BOT] Paraphrase lacks proper perspective transformation")
                return False
            
            # Extract key concepts from original statement
            original_concepts = self.extract_key_concepts(original_clean)
            user_concepts = self.extract_key_concepts(user_clean)
            
            print(f"[BOT] Original concepts: {original_concepts}")
            print(f"[BOT] User concepts: {user_concepts}")
            
            # STRICT: Check if user captured at least 60% of key concepts (increased from 50%)
            if not original_concepts:
                return len(user_concepts) > 0  # Basic check
            
            overlap = len(set(original_concepts) & set(user_concepts))
            coverage = overlap / len(original_concepts) if original_concepts else 0
            
            print(f"[BOT] Concept overlap: {overlap}/{len(original_concepts)} = {coverage:.2f}")
            
            # STRICT: Require at least 60% concept coverage for accuracy
            is_accurate = coverage >= 0.6
            print(f"[BOT] Paraphrase accuracy result: {is_accurate} (required: 60% coverage)")
            return is_accurate
            
        except Exception as e:
            print(f"[BOT] Error checking paraphrase accuracy: {e}")
            # Conservative fallback - if we can't check, assume it needs work
            return len(user_paraphrase.split()) >= 10

    def extract_key_concepts(self, text):
        """Extract key concepts from text for similarity checking"""
        try:
            # Remove common stop words and extract meaningful terms
            stop_words = {
                'i', 'you', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
                'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can',
                'that', 'this', 'these', 'those', 'my', 'your', 'his', 'her', 'our', 'their'
            }
            
            words = text.lower().split()
            concepts = [word.strip('.,!?";:()[]{}') for word in words 
                       if word.strip('.,!?";:()[]{}') not in stop_words 
                       and len(word.strip('.,!?";:()[]{}')) > 2]
            
            return list(set(concepts))  # Remove duplicates
            
        except Exception as e:
            print(f"Error extracting concepts: {e}")
            return []

    def is_feedback_about_paraphrasing(self, text):
        """Detect if user is giving feedback about paraphrasing quality"""
        feedback_indicators = [
            "but you should", "you should have", "in your perspective", "from your perspective",
            "you should say", "you didn't paraphrase", "not paraphrasing", "just repeating",
            "that's not paraphrasing", "you're just saying", "you repeated", "say it differently"
        ]
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in feedback_indicators)

    def improve_paraphrase(self, original_user_input, user_feedback):
        """Generate an improved paraphrase based on user feedback"""
        try:
            # Use the paraphrase function but with specific instructions based on feedback
            improved = paraphrase(original_user_input)
            
            # If the feedback mentions perspective, ensure we transform pronouns properly
            if "perspective" in user_feedback.lower() or "your" in user_feedback.lower():
                # Transform "I" statements to "you" statements properly
                transformed = original_user_input.lower()
                transformed = transformed.replace("i want you to know", "you want me to understand")
                transformed = transformed.replace("i have been", "you've been")  
                transformed = transformed.replace("i am", "you are")
                transformed = transformed.replace("i'm", "you're")
                transformed = transformed.replace("i feel", "you feel")
                transformed = transformed.replace("i don't know", "you're uncertain")
                
                return f"It sounds like {transformed}."
            
            return improved
            
        except Exception as e:
            print(f"Error improving paraphrase: {e}")
            return "I hear you sharing something important, and I want to understand it better."

    def create_fallback_paraphrase(self, user_input):
        """Create a proper paraphrase fallback that NEVER repeats verbatim"""
        try:
            text_lower = user_input.lower().strip()
            
            # Specific transformations for common patterns - ensure proper pronoun transformation
            if text_lower.startswith('i have been'):
                content = text_lower[11:].strip()
                return f"I hear you saying that you've been {content}."
            elif text_lower.startswith('i want you to know'):
                content = text_lower[18:].strip()
                return f"It sounds like you want me to understand that {content}."
            elif text_lower.startswith('i am ') or text_lower.startswith("i'm "):
                if text_lower.startswith("i'm "):
                    content = text_lower[4:].strip()
                else:
                    content = text_lower[5:].strip()
                return f"What I understand is that you're {content}."
            elif text_lower.startswith('i feel'):
                content = text_lower[6:].strip()
                return f"It sounds like you're feeling {content}."
            elif text_lower.startswith('i think'):
                content = text_lower[7:].strip()
                return f"I hear you expressing the belief that {content}."
            elif text_lower.startswith('i need'):
                content = text_lower[6:].strip()
                return f"I hear you saying that you need {content}."
            elif text_lower.startswith('i want'):
                content = text_lower[6:].strip()
                return f"I understand that you're hoping {content}."
            elif text_lower.startswith('i love'):
                content = text_lower[6:].strip()
                return f"It sounds like you're expressing that you love {content}."
            elif text_lower.startswith('i don\'t know'):
                content = text_lower[12:].strip()
                # Transform "how i will do" to "how you will do"
                content = content.replace('i will', 'you will').replace('i can', 'you can').replace('i am', 'you are')
                return f"I understand you're feeling uncertain about {content}."
            elif text_lower.startswith('i don\'t'):
                content = text_lower[7:].strip()
                return f"I understand you're saying that you don't {content}."
            elif '?' in text_lower:
                return f"I hear you asking about something important to you."
            else:
                # Generic transformation that changes structure and ensures pronoun transformation
                transformed = text_lower.replace('i ', 'you ').replace('my ', 'your ').replace(' me ', ' you ').replace(' me.', ' you.').replace(' me,', ' you,')
                # Additional pronoun transformations
                transformed = transformed.replace('i will', 'you will').replace('i can', 'you can').replace('i don\'t', 'you don\'t')
                # Clean up any awkward constructions and repeated words
                transformed = transformed.replace('you am', 'you are').replace('you\'m', 'you\'re')
                # Fix repeated words like "you you you"
                import re
                transformed = re.sub(r'\b(\w+)(\s+\1)+\b', r'\1', transformed)
                # Ensure proper capitalization - capitalize first word and after periods
                if transformed:
                    # Split into sentences and capitalize each
                    sentences = transformed.split('. ')
                    capitalized_sentences = []
                    for sentence in sentences:
                        if sentence:
                            sentence = sentence.strip()
                            if sentence and not sentence[0].isupper():
                                sentence = sentence[0].upper() + sentence[1:]
                            capitalized_sentences.append(sentence)
                    transformed = '. '.join(capitalized_sentences)
                    
                return f"What I'm hearing is that {transformed}."
                
        except Exception as e:
            print(f"Error in fallback paraphrase: {e}")
            return "I hear you sharing something meaningful, and I want to understand it correctly."

if __name__ == "__main__":
    bot = ConversationBot()
    bot.main_loop()
