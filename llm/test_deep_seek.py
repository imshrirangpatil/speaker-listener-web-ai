from llm.llm_api import LLMApi
from speech.speech_recognition_service import listen_for_speech
from speech.speech_model import speech_model

messages = [{"role": "system", "content": "You are a friendly AI counselor, providing concise and clear statements."}]
llm = LLMApi(provider="deepseek")

while True:
    user_input = listen_for_speech()
    if not user_input:
        continue
    if user_input.lower() in ["goodbye", "exit", "quit"]:
        print("Exiting chat...")
        break

    messages.append({"role": "user", "content": user_input})
    response = llm.generate_response(messages)

    if response:
        print(f"DeepSeek AI: {response}")
        speech_model(response)
        messages.append({"role": "assistant", "content": response})
