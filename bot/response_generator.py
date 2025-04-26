from llm.llm_api import LLMApi

llm_api = LLMApi(provider="gemini")

def generate_response(user_input, character_type):
    """Generate an AI-powered response based on user input and personality."""
    personality_tone = {
        "pessimistic": "realistic but not overly negative",
        "optimistic": "positive and encouraging",
        "neutral": "balanced and objective"
    }

    prompt = f"""
    Generate a single response statement (NOT a question) that:
    1. Is within 20 words
    2. Acknowledges the user's input: '{user_input}'
    3. Is clear, simple, and easy to understand
    4. Uses natural and conversational language
    5. Is a declarative statement
    6. Aligns with a {personality_tone[character_type]} personality
    7. Adds a relevant comment to continue the conversation
    8. Never uses question marks or interrogative forms
    9. Does NOT contain empty or nonsensical content
    Do not include any meta-text or explanations. Only provide the response statement itself.
    """

    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])

        if response and len(response.split()) > 2:  # Ensure valid response
            return response.strip()
        else:
            return "I acknowledge your message. Let's continue discussing."

    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I appreciate your input. Let's continue positively."

def paraphrase(text):
    """Paraphrase user input while maintaining meaning."""
    prompt = f"Paraphrase this text while maintaining its meaning in third person, start with 'You said': {text}"
    
    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        return response.strip() if response else text
    except Exception as e:
        print(f"Error paraphrasing text: {str(e)}")
        return text

def generate_topic(character_type):
    """Generate a topic-related statement based on the user's personality type."""
    personality_tone = {
        "pessimistic": "realistic but not overly negative",
        "optimistic": "positive and hopeful",
        "neutral": "balanced and objective"
    }

    prompt = f"""
    Generate a single meaningful statement (NOT a question) that is:
    1. Within 20 words
    2. Clear and simple thought-provoking
    3. Easy to understand and No complex vocabulary
    4. Natural and conversational
    5. Must be a declarative statement
    6. Aligns with a {personality_tone[character_type]} personality
    7. Never use question marks or interrogative forms
    Do not include any meta-text or explanations. Only provide the statement itself.
    """

    try:
        response = llm_api.generate_response([{"role": "user", "content": prompt}])
        statement = response.strip() if response else "Personal growth comes from understanding different perspectives and experiences."
        
        # Additional validation to ensure no questions
        if '?' in statement or statement.lower().startswith(('what', 'why', 'how', 'when', 'where', 'who', 'which')):
            return "Personal growth comes from understanding different perspectives and experiences."

        return statement
    except Exception as e:
        print(f"Error generating topic: {str(e)}")
        return "Exploring new perspectives can be enriching and insightful."
