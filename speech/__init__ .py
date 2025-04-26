"""
Speech Module: Handles speech recognition (VOSK, Google) and synthesis (VITS).
"""

from .speech_detector import SpeechDetector
from .speech_recognition_service import listen_for_speech
from .speech_handler import speak_text
from .speech_model import speech_model

__all__ = ["SpeechDetector", "listen_for_speech", "speak_text", "speech_model"]
