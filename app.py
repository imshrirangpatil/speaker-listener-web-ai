from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from threading import Thread
import subprocess
from uuid import uuid4
import sys
import os
from speech.speech_model import speech_model
import time

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')

# Production-friendly SocketIO configuration
socketio = SocketIO(app, 
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    async_mode='eventlet',  # Use eventlet for production
    logger=False,  # Disable socketio logging
    engineio_logger=False,  # Disable engine logging
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1000,
    reconnection_delay_max=5000,
    allow_upgrades=True,
    transports=['polling', 'websocket']
)

# Global dictionary to track user sessions and bot processes
user_sessions = {}
bot_processes = {}

def cleanup_session(session_id):
    """Clean up session and terminate associated bot process"""
    if session_id in bot_processes:
        try:
            process = bot_processes[session_id]
            if process.poll() is None:  # Process is still running
                process.terminate()
                process.wait(timeout=5)
        except Exception as e:
            print(f"[ERROR] Failed to terminate bot process for session {session_id}: {e}")
        finally:
            del bot_processes[session_id]
    
    if session_id in user_sessions:
        del user_sessions[session_id]

def run_bot(character_type, session_id):
    """
    Launch the bot in a separate subprocess for a specific session.
    """
    print(f"[SERVER] Starting bot for session {session_id} with character: {character_type}")
    
    try:
        # Set environment variable for character type and session
        env = os.environ.copy()
        env["BOT_CHARACTER"] = character_type
        env["SESSION_ID"] = session_id
        
        # Use Popen with output capture for debugging
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
        )
        
        # Store the process for this session
        bot_processes[session_id] = process
        
        # Monitor the subprocess output in real-time
        for line in iter(process.stdout.readline, ''):
            if line.strip() and not line.startswith('[CLIENT]') and not line.startswith('[DEBUG]'):
                print(f"[BOT-{session_id[:8]}] {line.strip()}")
        
        process.wait()
        
        # Clean up when process ends
        if session_id in bot_processes:
            del bot_processes[session_id]
        
    except Exception as e:
        print(f"[ERROR] Failed to start bot for session {session_id}: {e}")
        if session_id in bot_processes:
            del bot_processes[session_id]

@app.route("/", methods=["GET"])
def home():
    """
    Serve the main page with character selection and session controls.
    """
    # Create a unique session ID for each user
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid4())
    
    return render_template("index.html", session_id=session['user_session_id'])

@app.route("/start-session", methods=["POST"])
def start_session():
    """
    Handle POST request from frontend to select a character and start bot.
    """
    data = request.get_json()
    character = data.get("character")
    
    # Get or create session ID
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid4())
    
    session_id = session['user_session_id']

    if character:
        # Clean up any existing session for this user
        cleanup_session(session_id)
        
        # Create new session
        user_sessions[session_id] = {
            'character': character,
            'created_at': time.time(),
            'active': True
        }
        
        print(f"[SERVER] Starting bot for session {session_id} with character: {character}")
        Thread(target=run_bot, args=(character, session_id)).start()
        
        return jsonify({
            "status": "success",
            "message": f"Bot started with character: {character}",
            "session_id": session_id
        })
    else:
        return jsonify({
            "status": "error",
            "message": "No character selected."
        }), 400

@socketio.on('connect')
def handle_connect():
    """Handle client connection and assign to room"""
    # Get session ID from client or create new one
    session_id = request.args.get('session_id') or str(uuid4())
    session['user_session_id'] = session_id
    
    # Join user to their own room for isolated communication
    join_room(session_id)
    
    print(f"[SERVER] Client connected to session: {session_id}")
    emit('session_assigned', {'session_id': session_id})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = session.get('user_session_id')
    if session_id:
        leave_room(session_id)
        print(f"[SERVER] Client disconnected from session: {session_id}")
        
        # Mark session as inactive (don't immediately clean up in case of reconnection)
        if session_id in user_sessions:
            user_sessions[session_id]['active'] = False

@socketio.on('end_session')
def handle_end_session():
    """Handle explicit session termination"""
    session_id = session.get('user_session_id')
    if session_id:
        print(f"[SERVER] Ending session: {session_id}")
        cleanup_session(session_id)
        emit('session_ended', {'session_id': session_id}, room=session_id)

@socketio.on('mic_activated')
def emit_mic_activated(data):
    """Emit mic activation status to the specific user session."""
    session_id = session.get('user_session_id')
    if session_id:
        activated = data.get("activated")
        if activated in [True, False]:
            emit('mic_activated', {'activated': activated}, room=session_id)

@socketio.on('user_speech')
def handle_user_speech(data):
    """Handle user speech input from the web interface."""
    session_id = session.get('user_session_id')
    if session_id:
        user_text = data.get('text', '')
        # Emit to specific session room only
        emit('new_message', {'text': user_text, 'sender': 'user'}, room=session_id)
        emit('user_input', {'text': user_text, 'session_id': session_id}, room=session_id)

@socketio.on('play_audio_base64')
def handle_play_audio_base64(data):
    """Relay audio data to specific user session."""
    target_session = data.get('session_id')
    if target_session:
        emit('play_audio_base64', data, room=target_session)
    else:
        # Fallback to current session
        session_id = session.get('user_session_id')
        if session_id:
            emit('play_audio_base64', data, room=session_id)

@socketio.on('new_message')
def handle_new_message(data):
    """Relay messages to specific user session."""
    target_session = data.get('session_id')
    if target_session:
        emit('new_message', data, room=target_session)
    else:
        # Fallback to current session
        session_id = session.get('user_session_id')
        if session_id:
            emit('new_message', data, room=session_id)

@socketio.on('bot_audio_ended')
def handle_bot_audio_ended(data=None):
    """Handle bot audio ended event for specific session"""
    session_id = session.get('user_session_id')
    if session_id:
        # Relay this to the bot process for this specific session
        emit('bot_audio_ended', {'session_id': session_id}, room=session_id)

# Cleanup inactive sessions periodically
def cleanup_inactive_sessions():
    """Clean up sessions that have been inactive for too long"""
    current_time = time.time()
    inactive_sessions = []
    
    for session_id, session_info in user_sessions.items():
        # Clean up sessions inactive for more than 30 minutes
        if not session_info.get('active', False) and (current_time - session_info['created_at']) > 1800:
            inactive_sessions.append(session_id)
    
    for session_id in inactive_sessions:
        print(f"[SERVER] Cleaning up inactive session: {session_id}")
        cleanup_session(session_id)

# Start cleanup thread
def start_cleanup_thread():
    import threading
    import time
    
    def cleanup_worker():
        while True:
            time.sleep(300)  # Check every 5 minutes
            cleanup_inactive_sessions()
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()

if __name__ == "__main__":
    start_cleanup_thread()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    
    if debug:
        # Development mode - use built-in server
        socketio.run(app, host="0.0.0.0", port=port, debug=True)
    else:
        # Production mode - use with WSGI server (gunicorn)
        socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
