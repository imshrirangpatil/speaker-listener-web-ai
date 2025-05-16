import sys
from bot.conversation_bot import ConversationBot

if __name__ == "__main__":
    if len(sys.argv) > 1:
        character_type = sys.argv[1]
    else:
        character_type = "neutral"

    bot = ConversationBot(character_type=character_type)
    bot.main_loop()
