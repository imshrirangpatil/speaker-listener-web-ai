from llm.llm_api import LLMApi

def detect_emotion(text, provider="openai"):
    """Analyze text for emotional tone using OpenAI by default."""
    try:
        llm_api = LLMApi(provider=provider)
        emotion_prompt = f"""Analyze the emotional tone of this text: '{text}'
        
        Return only one of these emotions: happy, sad, angry, anxious, excited, calm, neutral, frustrated, grateful, confused
        
        Rules:
        1. Return only the emotion word, nothing else
        2. Choose the most dominant emotion
        3. If unclear, default to 'neutral'
        4. Don't include quotes or extra text"""
        
        emotion_response = llm_api.generate_response([{"role": "user", "content": emotion_prompt}])
        
        if emotion_response:
            # Clean up the response to get just the emotion
            emotion = emotion_response.strip().lower()
            # Remove quotes and extra text
            emotion = emotion.replace('"', '').replace("'", "")
            
            # Validate it's one of our expected emotions
            valid_emotions = ['happy', 'sad', 'angry', 'anxious', 'excited', 'calm', 'neutral', 'frustrated', 'grateful', 'confused']
            if emotion in valid_emotions:
                return emotion
            else:
                return "neutral"
        else:
            return "neutral"
            
    except Exception as e:
        print(f"Error detecting emotion: {e}")
        return "neutral"

