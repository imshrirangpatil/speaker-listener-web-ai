#!/usr/bin/env python3
"""
Quick TTS Test Script
Tests TTS functionality and shows what's available
"""

import os
from speech.groq_stt_tts import groq_text_to_speech

def test_tts():
    print("🎵 Testing TTS Services...")
    print("=" * 40)
    
    # Check environment variables
    print("🔑 API Keys Status:")
    print(f"   GROQ_API_KEY: {'✅ Set' if os.getenv('GROQ_API_KEY') else '❌ Not set'}")
    print(f"   OPENAI_API_KEY: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
    print()
    
    # Test TTS with a simple message
    test_text = "Hello, this is a test of the text to speech system."
    print(f"📝 Testing TTS with: '{test_text}'")
    print()
    
    result = groq_text_to_speech(test_text)
    
    if result:
        print("✅ TTS Test Successful!")
        print(f"   Result type: {type(result)}")
        if isinstance(result, str) and result.startswith("data:audio/wav;base64,"):
            print("   Format: Base64 data URL")
            print(f"   Data length: {len(result)} characters")
        else:
            print("   Format: Raw bytes")
            print(f"   Data length: {len(result)} bytes")
    else:
        print("❌ TTS Test Failed!")
        print("   No audio data returned")
    
    print()
    print("💡 If TTS failed, check:")
    print("   1. API keys are set correctly")
    print("   2. You have sufficient credits/quota")
    print("   3. Network connection is working")

if __name__ == "__main__":
    test_tts() 