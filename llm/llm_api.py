import os
import sys
from openai import OpenAI
from dotenv import load_dotenv
import google.generativeai as genai
from config import LLM_CONFIG

load_dotenv()  # Load API keys from .env file

class LLMApi:
    def __init__(self, provider="gemini"):
        """Initialize the API client based on the selected provider"""
        if provider not in LLM_CONFIG:
            raise ValueError(f"Invalid LLM provider: {provider}")
        self.provider = provider
        self.api_key = self.get_api_key()
        self.client = self.get_client()

    def get_api_key(self):
        """Retrieve API keys based on the selected provider"""
        keys = {
            "openai": os.getenv("CHATGPT_API"),
            "deepseek": os.getenv("DEEPSEEKAPI"),
            "grok": os.getenv("GROK_API"),
            "gemini": os.getenv("GEMINI_API")
        }
        return keys.get(self.provider)

    def get_client(self):
        """Return the corresponding API client"""
        if self.provider == "openai":
            return OpenAI(api_key=self.api_key)
        elif self.provider == "deepseek":
            return OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
        elif self.provider == "grok":
            return OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        elif self.provider == "gemini":
            genai.configure(api_key=self.api_key)
            return genai
        else:
            raise ValueError("Invalid provider specified")

    def generate_response(self, messages, temperature=0.8, max_tokens=100):
        """Generate a response using the selected LLM with improved Gemini integration."""
        try:
            model_name = LLM_CONFIG[self.provider]["model"]  # Load dynamically from config

            if self.provider == "gemini":
                # Initialize the Gemini Model Correctly
                model = self.client.GenerativeModel(model_name)
                response = model.generate_content(messages[-1]["content"])  # Correct API usage
                return response.text if response else "Sorry, I didn't understand that."

            else:
                response = self.client.chat.completions.create(
                    model=model_name, messages=messages, temperature=temperature, max_tokens=max_tokens
                )
                return response.choices[0].message.content if response.choices else None

        except Exception as e:
            print(f"Error communicating with {self.provider.upper()}: {e}")
            return "Sorry, I'm having trouble processing that request."
