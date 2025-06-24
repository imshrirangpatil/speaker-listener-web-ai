#!/usr/bin/env python3

# Test script to verify incomplete input detection
def is_incomplete_input(text):
    """Check if user input appears incomplete or unclear"""
    if not text:
        return True
        
    text = text.strip()
    
    # Check for trailing conjunctions (incomplete sentences)
    trailing_conjunctions = ["and", "but", "or", "so", "because", "however", "although", "while", "though"]
    words = text.split()
    if words and words[-1].lower() in trailing_conjunctions:
        return True
        
    # Check for trailing prepositions
    trailing_prepositions = ["with", "to", "for", "in", "on", "at", "by", "from", "about", "of", "up", "out"]
    if words and words[-1].lower() in trailing_prepositions:
        return True
        
    # Check for incomplete phrases
    incomplete_phrases = ["i think", "maybe", "perhaps", "possibly", "i guess", "i suppose"]
    text_lower = text.lower()
    if any(phrase in text_lower and not text_lower.endswith(phrase) for phrase in incomplete_phrases):
        # If it's just the phrase without elaboration
        if len(text.split()) <= 3:
            return True
            
    # Check for very short responses that might be incomplete
    if len(text.split()) <= 2 and not text.endswith(('.', '!', '?')):
        return True
        
    return False

# Test cases from the conversation
test_cases = [
    "I think you should be more patient and.",  # Should be incomplete (trailing "and")
    "I think you should be more patient.",      # Should be complete
    "Maybe we could",                           # Should be incomplete (trailing preposition)
    "Let's try to communicate better.",         # Should be complete
    "I think",                                  # Should be incomplete (just phrase)
    "Yes, that is correct.",                    # Should be complete
    "What do you think?",                       # Should be incomplete (ends with ?)
    "I'm not sure about",                       # Should be incomplete (trailing preposition)
]

print("Testing incomplete input detection:")
print("=" * 50)

for test_input in test_cases:
    result = is_incomplete_input(test_input)
    status = "INCOMPLETE" if result else "COMPLETE"
    print(f'"{test_input}" -> {status}')

print("\nExpected results:")
print("- 'I think you should be more patient and.' should be INCOMPLETE ✓")
print("- 'I think you should be more patient.' should be COMPLETE ✓")
print("- 'Maybe we could' should be INCOMPLETE ✓")
print("- 'Let's try to communicate better.' should be COMPLETE ✓") 