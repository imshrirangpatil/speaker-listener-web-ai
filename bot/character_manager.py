# def select_character():
#     """Allow the user to select the bot's personality."""
#     print("\nSelect Bot's Character:")
#     print("1. Optimistic")
#     print("2. Neutral")
#     print("3. Pessimistic")

#     while True:
#         choice = input("Enter choice (1-3): ")
#         if choice in ['1', '2', '3']:
#             return {
#                 '1': 'optimistic',
#                 '2': 'neutral',
#                 '3': 'pessimistic'
#             }[choice]
#         else:
#             print("Invalid choice. Please enter 1, 2, or 3.")

# def get_personality_tone(character_type):
#     """Return personality tone based on selection."""
#     return {
#         "pessimistic": "realistic but not overly negative",
#         "optimistic": "positive and encouraging",
#         "neutral": "balanced and objective"
#     }[character_type]

# def select_character(user_choice=None):
#     """Return bot's character based on input. Defaults to neutral."""
#     characters = {
#         '1': {"type": "optimistic", "tone": "positive and encouraging"},
#         '2': {"type": "neutral", "tone": "balanced and objective"},
#         '3': {"type": "pessimistic", "tone": "realistic but not overly negative"}
#     }

#     if user_choice in characters:
#         return characters[user_choice]
#     return characters['2']  # Default to neutral if no input provided.

def select_character():
    """Allow the user to select the bot's personality."""
    print("\nSelect Bot's Character:")
    print("1. Optimistic (Positive and Encouraging)")
    print("2. Neutral (Balanced and Objective)")
    print("3. Pessimistic (Realistic but not overly negative)")

    while True:
        choice = input("Enter choice (1-3): ")
        if choice in ['1', '2', '3']:
            characters = {
                '1': {"type": "optimistic", "tone": "positive and encouraging"},
                '2': {"type": "neutral", "tone": "balanced and objective"},
                '3': {"type": "pessimistic", "tone": "realistic but not overly negative"}
            }
            return characters[choice]
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")