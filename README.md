# Speaker-Listener Web AI

CharismaBot is a conversational AI system that implements the Speaker-Listener Technique using voice input, emotion detection, and large language models.


# CounselorProject

## 1. How to install the software

### 1.1 paste the following in the command line

```
git clone https://github.com/imshrirangpatil/speaker-listener-web-ai.git
cd speaker-listener-web-ai
```

### 1.2 creatre a virtual environment
```
python -m venv charisma
source charisma/bin/activate # macOs or Linux
charisma/Scripts\activate # Windows

```


### 1.3 paste the following after that

```
pip install -r requirements.txt
```

## 2. How to run the software

### 2.1 enter the API to your provider
```
echo 'export OPENAI_API_KEY='YOUR_OPENAI_KEY''  >> ~/.zshrc  # can be any of the following:
* OPENAI_API_KEY (default)
* GROK_API_KEY
* DEEPSEEK_API-KEY
* GEMINI_API_KEY
```
```
source ~/.zshrc # if zsh terminal
source ~/.bashrc # if bash terminal
```
### 2.2 run the main driver
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

* The app is in the beta phase, please create a GitHub issue in case your encounter any bug.

# Project Structure

```
├── app.py
├── bot
│   ├── __init__.py
│   ├── character_manager.py
│   ├── conversation_bot.py
│   ├── emotion_detector.py
│   └── response_generator.py
├── config.py
├── Dockerfile
├── Dockerfile.vosk
├── llm
│   ├── __init__.py
│   ├── llm_api.py
│   └── test_chatgpt_openai.py
├── main.py
├── Procfile
├── README.md
├── render.yaml
├── requirements.txt
├── speech
│   ├── __init__ .py
│   ├── groq_stt_tts.py
│   ├── openai_transcription_service.py
│   ├── speech_detector.py
│   ├── speech_handler.py
│   ├── speech_model.py
│   └── speech_recognition_service.py
├── start.sh
├── static
│   ├── charisma-logo.png
│   ├── css
│   │   └── style.css
│   └── js
│       └── app.js
├── templates
│   ├── charisma.html
│   ├── chat.html
│   ├── index.html
│   └── start.html
├── test_incomplete_input.py
├── test_speaker_listener.py
├── test_tts.py
├── vosk_server.py
└── wsgi.py

```
