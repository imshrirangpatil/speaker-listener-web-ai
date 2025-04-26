"""
Bot Module: Handles chatbot functionalities including conversation flow, personality management, and emotion detection.
"""

from .character_manager import select_character
from .conversation_bot import ConversationBot
from .emotion_detector import detect_emotion
from .response_generator import generate_response, paraphrase, generate_topic

__all__ = ["ConversationBot", "select_character", "detect_emotion", "generate_response", "paraphrase", "generate_topic"]
