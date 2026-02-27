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