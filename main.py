import signal
import sys
from bot.conversation_bot import ConversationBot
from config import CONVERSATION_DIR  # Ensure paths are centralized

bot = ConversationBot()

def signal_handler(sig, frame):
    """Handle Ctrl + C to save conversation before exiting."""
    print("\n[INFO] Exiting gracefully... Saving conversation.")
    bot.save_conversation()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)  # Capture Ctrl + C

if __name__ == "__main__":
    try:
        bot.main_loop()
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard Interrupt detected. Saving conversation...")
        bot.save_conversation()
        sys.exit(0)
