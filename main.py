import signal
import sys
import os
from bot.conversation_bot import ConversationBot
from config import CONVERSATION_DIR  # Ensure paths are centralized

# Get character type from environment variable, default to "neutral"
character_type = os.environ.get("BOT_CHARACTER", "neutral")
print(f"[BOT PROCESS] Starting bot with character: {character_type}", flush=True)
print(f"[BOT PROCESS] Initializing ConversationBot...", flush=True)

bot = ConversationBot(character_type=character_type)

def signal_handler(sig, frame):
    """Handle Ctrl + C to save conversation before exiting."""
    print("\n[INFO] Exiting gracefully... Saving conversation.")
    bot.save_conversation()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)  # Capture Ctrl + C

print(f"[BOT PROCESS] Bot initialized successfully", flush=True)
print(f"[BOT PROCESS] Starting main loop...", flush=True)

if __name__ == "__main__":
    try:
        bot.main_loop()
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard Interrupt detected. Saving conversation...")
        bot.save_conversation()
        sys.exit(0)
