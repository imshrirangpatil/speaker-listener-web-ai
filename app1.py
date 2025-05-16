from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
from threading import Thread
import subprocess
import sys
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app)

selected_character = None

def run_bot(character_type):
    # Launch bot_launcher.py as a subprocess
    subprocess.Popen([sys.executable, "bot_launcher.py", character_type])

@app.route("/", methods=["GET", "POST"])
def home():
    global selected_character
    if request.method == "POST":
        selected_character = request.form.get("characterSelect")
        print(f"Selected Character: {selected_character}", flush=True)
        return redirect(url_for('start_chat'))
    
    return render_template("index.html")

@app.route("/start")
def start_chat():
    global selected_character
    if selected_character:
        run_bot(selected_character)
        return render_template("start.html", character=selected_character)
    else:
        return redirect(url_for('home'))

@app.route("/chat")
def chat():
    return render_template("chat.html")

# WebSocket Events
@socketio.on('user_message')
def handle_user_message(data):
    user_text = data['message']
    print(f"User: {user_text}")
    emit('new_message', {'text': user_text, 'sender': 'user'}, broadcast=True)

@socketio.on('bot_message')
def handle_bot_message(data):
    bot_text = data['message']
    print(f"Bot: {bot_text}")
    emit('new_message', {'text': bot_text, 'sender': 'bot'}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)
