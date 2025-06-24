from llm.llm_api import LLMApi

llm_api = LLMApi(provider="openai")

def generate_response(user_input, character_type):
    """Generate an AI-powered response based on user input and personality."""
    personality_tone = {
        "pessimistic": "realistic but not overly negative",
        "optimistic": "positive and encouraging",
        "neutral": "balanced and objective"
    }

    prompt = f"""
    Generate a response under 20 words that:
    1. Acknowledges the user's input: '{user_input}'
    2. Is clear, simple, and easy to understand
    3. Uses natural, warm, and conversational language
    4. Is a declarative statement
    5. Aligns with a {personality_tone[character_type]} personality
    6. Adds a relevant comment to continue the conversation
    7. Never uses question marks or interrogative forms
    8. No meta-text or explanations. Only the response statement itself.
    9. Avoids robotic or formulaic language. Be friendly.
    """

    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        if response and len(response.split()) > 2:
            short_resp = " ".join(response.strip().split()[:20])
            return short_resp
        else:
            return "I appreciate your message. Let's keep chatting."
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I appreciate your input. Let's continue."

def paraphrase(text):
    """Simple paraphrasing of text."""
    try:
        # Remove filler words and clean up text
        filler_words = ['um', 'uh', 'like', 'you know', 'well']
        cleaned_text = text.lower()
        for word in filler_words:
            cleaned_text = cleaned_text.replace(word, '')
        
        # Basic paraphrasing templates
        if cleaned_text.startswith('i think'):
            cleaned_text = cleaned_text.replace('i think', '').strip()
            return f"You believe that{cleaned_text}"
        elif cleaned_text.startswith('i feel'):
            cleaned_text = cleaned_text.replace('i feel', '').strip()
            return f"You're feeling{cleaned_text}"
        elif cleaned_text.startswith('i want'):
            cleaned_text = cleaned_text.replace('i want', '').strip()
            return f"You would like{cleaned_text}"
        else:
            return f"You said that {cleaned_text}"
            
    except Exception as e:
        return text  # Return original text if paraphrasing fails

def generate_topic(character_type):
    """Generate a topic-related statement based on the user's personality type."""
    personality_tone = {
        "pessimistic": "realistic but not overly negative",
        "optimistic": "positive and hopeful",
        "neutral": "balanced and objective"
    }

    prompt = f"""
    Generate a statement under 20 words that is:
    1. Clear, simple, and thought-provoking
    2. Declarative, not a question
    3. {personality_tone[character_type]} personality
    4. No meta-text or explanations.
    """

    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        statement = response.strip() if response else "Personal growth comes from understanding different perspectives."
        if '?' in statement or len(statement.split()) > 20:
            return "Personal growth comes from understanding different perspectives."
        return statement
    except Exception as e:
        print(f"Error generating topic: {str(e)}")
        return "Exploring new perspectives can be enriching."

def generate_validation_response(user_input, emotion):
    """Generate a validation response that shows empathy and understanding, matching the user's emotional tone."""
    prompt = f"""Generate a brief, empathetic response under 15 words that validates the user's feelings about: {user_input}\nDetected emotion: {emotion}\nNo questions. Show empathy. Match the user's emotional tone. Use warm, natural language. Avoid robotic or formulaic language. Only the response."""
    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        if response and response.strip():
            short_resp = " ".join(response.strip().split()[:15])
            return short_resp
        else:
            return "Thank you for sharing."
    except Exception as e:
        print(f"Error generating validation response: {str(e)}")
        return "Thank you for sharing."

def generate_problem_solving(issue, user_solution, character_type):
    prompt = f"""Generate a collaborative response under 20 words to this solution: {user_solution}\nIssue: {issue}\nUse 'we' statements. Be positive, warm, and friendly. No questions. Avoid robotic or formulaic language."""
    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        if response and response.strip():
            short_resp = " ".join(response.strip().split()[:20])
            return short_resp
        else:
            return "Let's work on this together."
    except Exception as e:
        print(f"Error generating problem-solving response: {str(e)}")
        return "Let's work on this together."

def detect_hardship(text):
    """Detect if the text indicates hardship or difficulty."""
    try:
        hardship_indicators = [
            'difficult', 'hard', 'struggle', 'challenging', 'tough', 
            'worried', 'anxious', 'scared', 'afraid', 'nervous',
            'sad', 'depressed', 'unhappy', 'hurt', 'pain',
            'frustrated', 'angry', 'upset', 'mad', 'annoyed'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in hardship_indicators)
        
    except Exception as e:
        return False

def generate_empathetic_response(text):
    """Generate an empathetic response to user's hardship."""
    try:
        emotion = detect_emotion(text)
        
        responses = {
            'sad': "I hear the sadness in what you're saying. It's okay to feel this way.",
            'angry': "I can sense your frustration. These feelings are valid.",
            'anxious': "It's natural to feel worried about this. You're not alone.",
            'happy': "I'm glad you're feeling positive about this!",
            'neutral': "Thank you for sharing that with me. I'm here to listen and support you."
        }
        
        base_response = responses.get(emotion, "I appreciate you sharing that with me.")
        return f"{base_response} Let's work through this together."
        
    except Exception as e:
        return "I hear you, and I'm here to support you. Let's work through this together."

def detect_emotion(text):
    """Detect the primary emotion in text."""
    try:
        # Simple keyword-based emotion detection
        emotions = {
            'happy': ['happy', 'joy', 'excited', 'great', 'wonderful', 'love', 'glad'],
            'sad': ['sad', 'unhappy', 'depressed', 'down', 'hurt', 'pain'],
            'angry': ['angry', 'mad', 'frustrated', 'annoyed', 'upset'],
            'anxious': ['worried', 'anxious', 'nervous', 'scared', 'afraid'],
            'neutral': []
        }
        
        text_lower = text.lower()
        for emotion, keywords in emotions.items():
            if any(keyword in text_lower for keyword in keywords):
                return emotion
        return 'neutral'
        
    except Exception as e:
        return 'neutral'

def generate_collaborative_response(user_input):
    """Generate a collaborative response that builds on the user's ideas."""
    try:
        # Analyze user input for key themes
        themes = extract_themes(user_input)
        
        # Generate response based on themes
        if "communication" in themes:
            return "I hear you. Open communication is key. Let's keep practicing these listening skills together."
        elif "understanding" in themes:
            return "Building understanding takes time and patience. I appreciate your willingness to share and listen."
        elif "improvement" in themes:
            return "That's a great approach to improvement. Small steps can lead to big changes."
        else:
            return "I appreciate your insights. Working together like this helps us both grow and understand each other better."
            
    except Exception as e:
        return "Thank you for sharing your thoughts. Let's keep working together to find solutions."

def extract_themes(text):
    """Extract key themes from text."""
    try:
        themes = set()
        
        # Theme keywords
        theme_keywords = {
            'communication': ['talk', 'speak', 'listen', 'understand', 'share'],
            'understanding': ['understand', 'learn', 'know', 'realize'],
            'improvement': ['better', 'improve', 'change', 'grow', 'develop']
        }
        
        text_lower = text.lower()
        for theme, keywords in theme_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                themes.add(theme)
        
        return themes
        
    except Exception as e:
        return set()
