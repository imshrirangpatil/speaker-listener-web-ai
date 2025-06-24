import signal
import sys
import os
from bot.conversation_bot import ConversationBot
from config import CONVERSATION_DIR  # Ensure paths are centralized

# Get character type and session ID from environment variables
character_type = os.environ.get("BOT_CHARACTER", "neutral")
session_id = os.environ.get("SESSION_ID")

print(f"[BOT PROCESS] Starting bot with character: {character_type} for session: {session_id}", flush=True)
print(f"[BOT PROCESS] Initializing ConversationBot...", flush=True)

# Initialize bot with session ID
bot = ConversationBot(character_type=character_type, session_id=session_id)

def signal_handler(sig, frame):
    """Handle Ctrl + C to save conversation before exiting."""
    print(f"\n[INFO] Session {session_id}: Exiting gracefully... Saving conversation.")
    bot.save_conversation()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)  # Capture Ctrl + C

print(f"[BOT PROCESS] Bot initialized successfully for session {session_id}", flush=True)
print(f"[BOT PROCESS] Starting main loop...", flush=True)

if __name__ == "__main__":
    try:
        bot.main_loop()
    except KeyboardInterrupt:
        print(f"\n[INFO] Session {session_id}: Keyboard Interrupt detected. Saving conversation...")
        bot.save_conversation()
        sys.exit(0)
