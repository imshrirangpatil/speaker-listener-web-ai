# Speaker-Listener Web AI

CharismaBot is a conversational AI system that implements the Speaker-Listener Technique using voice input, emotion detection, and large language models.

Repository: [https://github.com/imshrirangpatil/speaker-listener-web-ai](https://github.com/imshrirangpatil/speaker-listener-web-ai)

# CounselorProject

## 1. How to install the software

### 1.1 paste the following in the command line

```
git clone https://github.com/imshrirangpatil/speaker-listener-web-ai.git
cd speaker-listener-web-ai
```

### 1.2 paste the following after that

```
pip install -r requirements.txt
```

## 2. How to run the software

```
python main.py
```

## 3. How to use the software

Web Application (work in progress)

* Open your preferred web browser.
* Navigate to the localhost URL provided
* Choose start the session
* Follow the on screen instructions to use other features.

## 4. Support & Questions

* Open a GitHub Issue.
* Reach out to the maintainers via [isweesin@oregonstate.edu](mailto:isweesin@oregonstate.edu) or [patilshr@oregonstate.edu](mailto:patilshr@oregonstate.edu)

## 5. Known bugs

* Sometimes the voice recording will stop if there is not voice for a period of time

# Project Structure

```
.
├── bot/
│   ├── __init__.py
│   ├── character_manager.py
│   ├── conversation_bot.py
│   ├── emotion_detector.py
│   └── response_generator.py
│
├── llm/
│   ├── __init__.py
│   ├── llm_api.py
│   ├── test_chatgpt_openai.py
│   ├── test_deep_seek.py
│   ├── test_gemini_google.py
│   └── test_grok_xai.py
│
├── speech/
│   ├── __init__.py
│   ├── speech_detector.py
│   ├── speech_handler.py
│   ├── speech_model.py
│   ├── speech_recognition_service.py
│   └── tts_outputs/
│
├── templates/
│   └── index.html
│
├── .gitignore
├── README.md
├── app.py
├── config.py
├── main.py
└── requirements.txt
```
