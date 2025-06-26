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
    """Enhanced paraphrasing using LLM for better Speaker-Listener Technique responses."""
    try:
        # Remove filler words and clean up text
        filler_words = ['um', 'uh', 'like', 'you know', 'well']
        cleaned_text = text.strip()
        for word in filler_words:
            cleaned_text = cleaned_text.replace(f' {word} ', ' ').replace(f'{word} ', '').replace(f' {word}', '')
        
        # Use LLM for intelligent paraphrasing following Speaker-Listener Technique principles
        prompt = f"""Transform this statement into a proper Speaker-Listener Technique paraphrase:

Original: "{cleaned_text}"

CRITICAL REQUIREMENTS:
1. NEVER repeat their exact words verbatim
2. Always transform pronouns: "I" becomes "you", "my" becomes "your", "me" becomes "you"
3. Start with "I hear you saying that..." or "It sounds like you feel..." or "What I understand is..."
4. Capture the EMOTION and MAIN POINT using DIFFERENT vocabulary
5. Keep under 25 words
6. Show empathy and understanding
7. Transform the perspective completely - speak AS the listener TO the speaker

Example transformations:
- "I want you to know I'm overwhelmed" → "I hear you saying that you're feeling overwhelmed and want me to understand that"
- "I feel stressed about work" → "It sounds like you're experiencing stress related to your work situation"
- "I have been working for a while now and I need a break" → "I hear you saying that you've been working for some time and you need a break"
- "I think I love chocolates" → "It sounds like you're expressing that you love chocolates"

ABSOLUTELY FORBIDDEN:
- Using "i need" when they said "I need" (must be "you need")
- Using "i love" when they said "I love" (must be "you love") 
- Repeating any exact phrases verbatim

Only return the paraphrase, nothing else."""

        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        
        if response and response.strip():
            paraphrased = response.strip()
            
            # Critical validation - check for forbidden patterns
            original_lower = cleaned_text.lower()
            paraphrased_lower = paraphrased.lower()
            
            # Check for verbatim repetition (forbidden)
            if original_lower in paraphrased_lower or paraphrased_lower in original_lower:
                print(f"[PARAPHRASE] LLM response contains verbatim repetition, using fallback")
                return create_strict_fallback_paraphrase(cleaned_text)
            
            # Check for incorrect pronoun usage
            if ("i need" in paraphrased_lower and "i need" in original_lower) or \
               ("i love" in paraphrased_lower and "i love" in original_lower) or \
               ("i want" in paraphrased_lower and "i want" in original_lower) or \
               ("i think" in paraphrased_lower and "i think" in original_lower):
                print(f"[PARAPHRASE] LLM failed pronoun transformation, using fallback")
                return create_strict_fallback_paraphrase(cleaned_text)
            
            # Ensure proper sentence structure
            if not paraphrased.endswith(('.', '!', '?')):
                paraphrased += '.'
            
            # Capitalize first letter
            if paraphrased:
                paraphrased = paraphrased[0].upper() + paraphrased[1:]
            
            return paraphrased
        else:
            # Enhanced fallback that properly paraphrases instead of repeating
            return create_strict_fallback_paraphrase(cleaned_text)
            
    except Exception as e:
        print(f"Error in paraphrasing: {e}")
        # Safe fallback that paraphrases instead of repeating
        return create_strict_fallback_paraphrase(text)

def create_strict_fallback_paraphrase(text):
    """Create a strict paraphrase that NEVER repeats verbatim and always transforms pronouns"""
    try:
        text_lower = text.lower().strip()
        
        # Specific transformations for common patterns
        if text_lower.startswith('i have been'):
            content = text_lower[11:].strip()
            return f"I hear you saying that you've been {content}."
        elif text_lower.startswith('i feel'):
            emotion_part = text_lower[6:].strip()
            return f"It sounds like you're feeling {emotion_part}."
        elif text_lower.startswith('i think'):
            thought_part = text_lower[7:].strip()
            return f"I hear you expressing the belief that {thought_part}."
        elif text_lower.startswith('i want'):
            desire_part = text_lower[6:].strip()
            return f"I understand that you're hoping {desire_part}."
        elif text_lower.startswith('i need'):
            need_part = text_lower[6:].strip()
            return f"I hear you saying that you need {need_part}."
        elif text_lower.startswith('i love'):
            love_part = text_lower[6:].strip()
            return f"It sounds like you're expressing that you love {love_part}."
        elif text_lower.startswith('i am ') or text_lower.startswith("i'm "):
            if text_lower.startswith("i'm "):
                state_part = text_lower[4:].strip()
            else:
                state_part = text_lower[5:].strip()
            return f"I hear you saying that you're {state_part}."
        elif text_lower.startswith('i don\'t'):
            negative_part = text_lower[7:].strip()
            return f"I understand you're saying that you don't {negative_part}."
        elif '?' in text_lower:
            return f"I hear you asking about something important to you."
        else:
            # Generic transformation that changes structure and pronouns
            transformed = text_lower.replace('i ', 'you ').replace('my ', 'your ').replace(' me ', ' you ').replace(' me.', ' you.').replace(' me,', ' you,')
            # Clean up any awkward constructions
            transformed = transformed.replace('you am', 'you are').replace('you\'m', 'you\'re')
            return f"What I'm hearing is that {transformed}."
            
    except Exception as e:
        print(f"Error in strict fallback paraphrase: {e}")
        return "I hear you sharing something meaningful, and I want to understand it correctly."

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
