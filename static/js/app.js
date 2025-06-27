// app.js

// -------------------------
// Socket.IO setup
// -------------------------
let sessionId = null;
let shouldStopRecording = false;
const socket = io({
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    autoConnect: true,
    transports: ['polling', 'websocket'],
    upgrade: true,
    forceNew: false,
    rememberUpgrade: true
});

socket.on('connect', () => {
    console.log('[CLIENT] Socket connected:', socket.id);
    console.log('[CLIENT] Socket transport:', socket.io.engine.transport.name);
    console.log('[CLIENT] Socket ready state:', socket.io.engine.readyState);
});

socket.on('disconnect', (reason) => {
    console.log('[CLIENT] Socket disconnected:', reason);
    console.log('[CLIENT] Socket transport before disconnect:', socket.io.engine.transport.name);
    if (reason === 'io server disconnect') {
        setTimeout(() => socket.connect(), 1000);
    }
});

socket.on('connect_error', (error) => {
    console.log('[CLIENT] Connection error:', error);
    console.log('[CLIENT] Error details:', {
        type: error.type,
        description: error.description,
        context: error.context
    });
    showNotification('Connection error. Retrying...', 'warning');
});

socket.on('reconnect_attempt', (attempt) => {
    console.log('[CLIENT] Reconnection attempt:', attempt);
    if (attempt <= 3) {
        showNotification(`Reconnecting... (${attempt}/5)`, 'info');
    }
});

socket.on('reconnect', (attempt) => {
    console.log('[CLIENT] Reconnected after', attempt, 'attempts');
    showNotification('Reconnected successfully!', 'success');
});

socket.on('reconnect_failed', () => {
    console.log('[CLIENT] Failed to reconnect');
    showNotification('Connection failed. Please refresh the page.', 'error');
});

socket.on('reconnect_error', (error) => {
    console.log('[CLIENT] Reconnection error:', error);
});

socket.on('upgrade', () => {
    console.log('[CLIENT] Transport upgraded to:', socket.io.engine.transport.name);
});

socket.on('upgradeError', (error) => {
    console.log('[CLIENT] Transport upgrade error:', error);
});

socket.on('session_assigned', (data) => {
    sessionId = data.session_id;
    console.log('[CLIENT] Session assigned:', sessionId);
});

socket.on('session_ended', (data) => {
    console.log('[CLIENT] Session ended:', data.session_id);
    showNotification('Session ended. Returning to setup...', 'info');
    resetToSetup();
});

<<<<<<< HEAD
// DOM elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const micButton = document.getElementById('mic-button');
const startButton = document.getElementById('create-button');
const characterSelect = document.getElementById('characterSelect');
const setupUI = document.getElementById('setup-ui');
const sessionUI = document.getElementById('session-ui');
=======
socket.on('session_updated', (data) => {
    console.log('[CLIENT] Session updated:', data.session_id);
    sessionId = data.session_id;
});
>>>>>>> origin/master

socket.on('connection_confirmed', (data) => {
    console.log('[CLIENT] Connection confirmed for session:', data.session_id);
});

// -------------------------
// DOM elements
// -------------------------
const chatMessages     = document.getElementById('chat-messages');
const messageInput     = document.getElementById('message-input');
const sendButton       = document.getElementById('send-button');
const micButton        = document.getElementById('mic-button');
const startButton      = document.getElementById('create-button');
const characterSelect  = document.getElementById('characterSelect');
const setupUI          = document.getElementById('setup-ui');
const sessionUI        = document.getElementById('initially-hidden');

// -------------------------
// Audio context & queue
// -------------------------
let audioContext = null;
let audioQueue = [];
let isPlayingAudio = false;
let isBotSpeaking = false;

// -------------------------
// Speech recognition
// -------------------------
let recognition = null;
let isListening = false;

// -------------------------
// Initialize AudioContext
// -------------------------
function initAudioContext() {
    console.log('[CLIENT] Initializing audio context...');
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    if (window.AudioContext || window.webkitAudioContext) {
        if (!audioContext) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
<<<<<<< HEAD
                console.log('[CLIENT] Audio context created, state:', audioContext.state);
            } catch (error) {
                console.error('[CLIENT] Failed to create audio context:', error);
                // Don't block the interface, continue without audio context
=======
                console.log('[CLIENT] AudioContext state:', audioContext.state);
            } catch (err) {
                console.error('[CLIENT] Failed to create AudioContext:', err);
>>>>>>> origin/master
                return false;
            }
        }
        if (audioContext.state === 'suspended') {
<<<<<<< HEAD
            console.log('[CLIENT] Audio context is suspended, will resume on user interaction');
            
            // Don't block the interface - just set up listeners for later resume
            if (isSafari) {
                // Create a simple user interaction handler for Safari
                const resumeAudio = () => {
                    audioContext.resume().then(() => {
                        console.log('[CLIENT] Audio context resumed successfully for Safari');
                        // Remove listeners after successful resume
                        document.removeEventListener('click', resumeAudio);
                        document.removeEventListener('touchstart', resumeAudio);
                        document.removeEventListener('touchend', resumeAudio);
                        document.removeEventListener('keydown', resumeAudio);
                    }).catch(error => {
                        console.log('[CLIENT] Failed to resume audio context in Safari:', error);
                    });
                };
                
                // Add multiple event listeners for Safari
                document.addEventListener('click', resumeAudio, { once: true });
                document.addEventListener('touchstart', resumeAudio, { once: true });
                document.addEventListener('touchend', resumeAudio, { once: true });
                document.addEventListener('keydown', resumeAudio, { once: true });
                
                console.log('[CLIENT] Safari audio context resume listeners added');
            }
        } else {
            console.log('[CLIENT] Audio context is ready');
=======
            console.log('[CLIENT] AudioContext suspended, attempting resume...');
            const resume = () => {
                audioContext.resume().then(() => {
                    console.log('[CLIENT] AudioContext resumed');
                    document.removeEventListener('click', resume);
                    document.removeEventListener('touchstart', resume);
                    document.removeEventListener('keydown', resume);
                }).catch(err => console.error('[CLIENT] Resume failed:', err));
            };
            document.addEventListener('click', resume, { once: true });
            document.addEventListener('touchstart', resume, { once: true });
            document.addEventListener('keydown', resume, { once: true });
>>>>>>> origin/master
        }
        return true;
    } else {
        console.log('[CLIENT] Web Audio API not supported, will use HTML5 audio');
        return false;
    }
}

// -------------------------
// Play audio from base64
// -------------------------
function playAudioFromBase64(audioBase64, mimeType = 'audio/wav') {
    return new Promise((resolve, reject) => {
        console.log('[CLIENT] playAudioFromBase64 called');
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
                    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent) || isIOS;

        if (isSafari) {
            console.log('[CLIENT] Safari detected, using HTML5 <audio>');
            const audio = new Audio();
            let format = mimeType;
            if (mimeType === 'audio/wav' && !audio.canPlayType('audio/wav')) {
                console.log('[CLIENT] WAV unsupported, trying MP3');
                format = 'audio/mpeg';
            }
            audio.src = `data:${format};base64,${audioBase64}`;
            audio.preload = 'auto';

            audio.onended = () => {
                console.log('[CLIENT] HTML5 audio ended');
                isBotSpeaking = false;
                socket.emit('bot_audio_ended', { session_id: sessionId });
                resolve();
            };
            audio.onerror = (e) => {
                console.error('[CLIENT] HTML5 audio error', e);
                reject(e);
            };
            audio.play().catch(err => {
                console.error('[CLIENT] HTML5 play() failed', err);
                reject(err);
            });
            return;
        }

        // Non-Safari: try Web Audio API
        if (!audioContext || audioContext.state === 'suspended') {
            console.log('[CLIENT] AudioContext unavailable/suspended, falling back');
            playAudioFromBase64(audioBase64, mimeType).then(resolve, reject);
            return;
        }

        try {
            const bytes = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0));
            audioContext.decodeAudioData(bytes.buffer,
                (buffer) => {
                    const src = audioContext.createBufferSource();
                    src.buffer = buffer;
                    src.connect(audioContext.destination);
                    src.onended = () => {
                        console.log('[CLIENT] BufferSource ended');
                        isBotSpeaking = false;
                        socket.emit('bot_audio_ended', { session_id: sessionId });
                        resolve();
                    };
                    src.start(0);
                },
                (err) => {
                    console.error('[CLIENT] decodeAudioData error, falling back', err);
                    playAudioFromBase64(audioBase64, mimeType).then(resolve, reject);
                }
            );
        } catch (err) {
            console.error('[CLIENT] Web Audio API error, falling back', err);
            playAudioFromBase64(audioBase64, mimeType).then(resolve, reject);
        }
    });
}

// -------------------------
// Audio queue management
// -------------------------
async function queueAndPlayAudio(audioBase64, mimeType) {
    audioQueue.push({ audioBase64, mimeType });
    if (!isPlayingAudio) {
        await playNextAudio();
    }
}

async function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlayingAudio = false;
        isBotSpeaking = false;
        return;
    }
    isPlayingAudio = true;
    const { audioBase64, mimeType } = audioQueue.shift();
    try {
        await playAudioFromBase64(audioBase64, mimeType);
    } catch (err) {
        console.error('[CLIENT] queue audio error', err);
    }
    await playNextAudio();
}

// -------------------------
// Speech recognition
// -------------------------
function initSpeechRecognition() {
    if (!('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
        console.error('[CLIENT] SpeechRecognition not supported');
        if (micButton) micButton.style.display = 'none';
        return;
    }
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        console.log('[CLIENT] SpeechRecognition started');
        isListening = true;
        shouldStopRecording = false;
        if (micButton) micButton.classList.add('listening');
    };

    recognition.onresult = (event) => {
        const transcript = event.results[event.results.length - 1][0].transcript.trim();
        console.log('[CLIENT] Transcript:', transcript);
        if (isBotSpeaking) return;

        const stopCmds = ['stop', 'stop recording', 'quit', 'end recording'];
        if (stopCmds.some(c => transcript.toLowerCase().includes(c))) {
            shouldStopRecording = true;
            recognition.stop();
            showNotification('Recording stopped by voice command', 'info');
            return;
        }

        if (transcript.match(/[a-zA-Z]/)) {
            socket.emit('user_speech', { text: transcript, session_id: sessionId });
            if (messageInput) messageInput.value = transcript;
            recognition.stop();
        }
    };

    recognition.onerror = (e) => {
        console.error('[CLIENT] SpeechRecognition error:', e.error);
        isListening = false;
        if (micButton) micButton.classList.remove('listening');
        if (shouldStopRecording) return;
        if (['no-speech','audio-capture'].includes(e.error)) {
            setTimeout(() => recognition.start(), 500);
        }
    };

    recognition.onend = () => {
        console.log('[CLIENT] SpeechRecognition ended');
        isListening = false;
        if (shouldStopRecording) return;
        setTimeout(() => recognition.start(), 300);
    };
}

// -------------------------
// UI helpers
// -------------------------
function addMessage(text, sender) {
    if (!chatMessages) return;
    const div = document.createElement('div');
    div.className = `chat-message ${sender}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

<<<<<<< HEAD
// Handle mic button click
function toggleMicrophone() {
    if (!recognition) {
        console.error('[CLIENT] Speech recognition not available');
        return;
    }
    
    if (isListening) {
        recognition.stop();
    } else {
        recognition.start();
    }
}

// Switch to session UI
function switchToSession(newSessionId) {
    console.log('[CLIENT] Switching to session UI', newSessionId ? `with session ID: ${newSessionId}` : '');
    
    if (newSessionId) {
        sessionId = newSessionId;
        console.log('[CLIENT] Session started, reconnecting socket with session ID:', sessionId);
        
        // Disconnect and reconnect with correct session ID
        socket.disconnect();
        socket.io.opts.query = { session_id: sessionId };
        socket.connect();
    }
    
    // Switch UI elements
    if (setupUI) setupUI.style.display = 'none';
    if (sessionUI) {
        sessionUI.style.display = 'block';
        sessionUI.classList.remove('hidden');
    }
    
    // Initialize voice bubble if it exists
    const voiceBubble = document.getElementById('voice-bubble');
    if (voiceBubble) {
        voiceBubble.innerHTML = '<span id="role-icon">👋</span>';
    }
    
    console.log('[CLIENT] UI switched to session view');
}

// Socket.IO event handlers - only process messages for current session
socket.on('new_message', (data) => {
    console.log('[CLIENT] New message received:', data);
    console.log('[CLIENT] Current sessionId:', sessionId);
    console.log('[CLIENT] Message session_id:', data.session_id);
    console.log('[CLIENT] Session match:', !data.session_id || data.session_id === sessionId);
    // Only process messages for current session or without session ID (for system messages)
    if (!data.session_id || data.session_id === sessionId) {
        addMessage(data.text, data.sender);
        
        // If it's a bot message, show the bot is speaking (mic off)
        if (data.sender === 'bot') {
            const voiceBubble = document.getElementById('voice-bubble');
            if (voiceBubble) {
                voiceBubble.classList.remove('mic-on', 'launching');
                voiceBubble.classList.add('mic-off');
                voiceBubble.innerHTML = '<span id="role-icon">🤖</span>';
            }
        }
    } else {
        console.log('[CLIENT] Message filtered out - session ID mismatch');
    }
});

socket.on('play_audio_base64', (data) => {
    console.log('[CLIENT] Audio received!');
    console.log('[CLIENT] Current sessionId:', sessionId);
    console.log('[CLIENT] Audio session_id:', data.session_id);
    console.log('[CLIENT] Audio data type:', typeof data.audio_base64);
    console.log('[CLIENT] Audio data length:', data.audio_base64 ? data.audio_base64.length : 'null');
    console.log('[CLIENT] MIME type:', data.mime);
    console.log('[CLIENT] Audio data preview:', data.audio_base64 ? data.audio_base64.substring(0, 50) + '...' : 'null');
    
    // Only process audio for current session or without session ID
    if (!data.session_id || data.session_id === sessionId) {
        if (data.audio_base64 && data.audio_base64.length > 0) {
            queueAndPlayAudio(data.audio_base64, data.mime);
        } else {
            console.error('[CLIENT] Audio data is empty or null');
        }
    } else {
        console.log('[CLIENT] Audio filtered out - session ID mismatch');
    }
});

socket.on('play_audio', (data) => {
    console.log('[CLIENT] Audio URL received:', data.url);
    // Handle audio URL if needed
});

socket.on('mic_activated', (data) => {
    console.log('[CLIENT] Mic activation:', data.activated);
    // Only process for current session or without session ID
    if (!data.session_id || data.session_id === sessionId) {
        // Handle microphone button if it exists (charisma.html)
        if (micButton) {
            if (data.activated) {
                micButton.classList.add('active');
            } else {
                micButton.classList.remove('active');
            }
        }
        
        // Handle voice bubble if it exists (index.html)
        const voiceBubble = document.getElementById('voice-bubble');
        if (voiceBubble) {
            if (data.activated) {
                voiceBubble.classList.remove('mic-off', 'launching');
                voiceBubble.classList.add('mic-on');
                voiceBubble.innerHTML = '<span id="role-icon">🎤</span>';
            } else {
                voiceBubble.classList.remove('mic-on', 'launching');
                voiceBubble.classList.add('mic-off');
                voiceBubble.innerHTML = '<span id="role-icon">🤖</span>';
            }
        }
        
        // Handle speech recognition
        if (data.activated) {
            // Auto-start speech recognition when mic is activated
            if (recognition && !isListening) {
                console.log('[CLIENT] Auto-starting speech recognition...');
                try {
                    recognition.start();
                } catch (error) {
                    console.log('[CLIENT] Speech recognition already running or error:', error);
                }
            }
        } else {
            // Stop speech recognition when mic is deactivated
            if (recognition && isListening) {
                console.log('[CLIENT] Auto-stopping speech recognition...');
                recognition.stop();
            }
        }
    }
});

// Handle TTS failure notifications
socket.on('tts_failed', function(data) {
    console.log('[CLIENT] TTS failed:', data.message);
    // Show a subtle notification that audio is unavailable
    showNotification(data.message, 'warning');
});

// Add notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'warning' ? '#ff9800' : '#2196f3'};
        color: white;
        padding: 10px 15px;
        border-radius: 5px;
        z-index: 1000;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Fade in
    setTimeout(() => notification.style.opacity = '1', 10);
    
    // Auto remove after 3 seconds
=======
function showNotification(message, type='info') {
    const note = document.createElement('div');
    note.className = `notification ${type}`;
    note.style.cssText = `
        position:fixed; top:20px; right:20px;
        background:${ type==='success'?'#4caf50': type==='error'?'#f44336': type==='warning'?'#ff9800':'#2196f3' };
        color:white; padding:10px; border-radius:5px; z-index:1000;
        opacity:0; transition:opacity .3s; max-width:300px; font-size:14px;`;
    note.textContent = message;
    document.body.appendChild(note);
    setTimeout(() => note.style.opacity = '1', 10);
>>>>>>> origin/master
    setTimeout(() => {
        note.style.opacity = '0';
        setTimeout(() => note.remove(), 300);
    }, type==='error'?5000:3000);
}

function resetToSetup() {
<<<<<<< HEAD
    console.log('[CLIENT] Resetting to setup UI');
    
    // Reset UI
    if (setupUI) setupUI.style.display = 'block';
    if (sessionUI) {
        sessionUI.style.display = 'none';
        sessionUI.classList.add('hidden');
    }
    if (startButton) startButton.disabled = false;
    if (chatMessages) chatMessages.innerHTML = '';
    
    // Reset session
    sessionId = null;
    
    // Reset character selection if element exists
    if (characterSelect) characterSelect.value = '';
    
    console.log('[CLIENT] Reset to setup completed');
}

// Event listeners
if (micButton) {
    micButton.addEventListener('click', toggleMicrophone);
}

if (sendButton) {
    sendButton.addEventListener('click', () => {
        const text = messageInput ? messageInput.value.trim() : '';
        if (text && sessionId) {
            socket.emit('user_speech', { text: text, session_id: sessionId });
            // DON'T add to chat here - server will emit new_message which adds it
            if (messageInput) messageInput.value = '';
        }
    });
}

if (messageInput) {
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendButton.click();
        }
    });
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('[CLIENT] Page loaded, initializing...');
    
    // Initialize audio and speech (non-blocking)
    initAudioContext();
    initSpeechRecognition();
    
    // Set up start button event listener
    const startBtn = document.getElementById('create-button');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            const character = characterSelect ? characterSelect.value : 'optimistic';
            if (!character) {
                alert('Please select a character.');
                return;
            }
            
            console.log('[CLIENT] Starting session with character:', character);
            
            // Disable button to prevent double-clicks
            startBtn.disabled = true;
            startBtn.textContent = 'Starting...';
            
            fetch('/start-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ character: character })
            })
            .then(response => response.json())
            .then(data => {
                console.log('[CLIENT] Session started:', data);
                if (data.status === 'success') {
                    sessionId = data.session_id;
                    console.log('[CLIENT] Reconnecting socket with session ID:', sessionId);
                    
                    // Disconnect and reconnect with correct session ID
                    socket.disconnect();
                    socket.io.opts.query = { session_id: sessionId };
                    socket.connect();
                    
                    switchToSession();
                } else {
                    alert('❌ ' + (data.message || 'Failed to start session'));
                    // Re-enable button on error
                    startBtn.disabled = false;
                    startBtn.textContent = 'Start a Session';
                }
            })
            .catch(error => {
                console.error('[CLIENT] Error starting session:', error);
                alert('Something went wrong starting the session.');
                // Re-enable button on error
                startBtn.disabled = false;
                startBtn.textContent = 'Start a Session';
            });
        });
    }
    
    // Set up end button event listener
    const endButton = document.getElementById('end-session-btn');
    if (endButton) {
        endButton.addEventListener('click', endSession);
    }
    
    // Add voice bubble click handler for index.html
    const voiceBubble = document.getElementById('voice-bubble');
    if (voiceBubble) {
        voiceBubble.addEventListener('click', () => {
            console.log('[CLIENT] Voice bubble clicked');
            if (recognition) {
                if (isListening) {
                    console.log('[CLIENT] Stopping speech recognition (manual)');
                    recognition.stop();
                } else {
                    console.log('[CLIENT] Starting speech recognition (manual)');
                    try {
                        recognition.start();
                    } catch (error) {
                        console.log('[CLIENT] Speech recognition error:', error);
                    }
                }
=======
    // Show setup UI
    const setupElement = document.getElementById('setup-ui');
    if (setupElement) setupElement.style.display = 'block';
    
    // Hide session UI
    const sessionElement = document.getElementById('initially-hidden');
    if (sessionElement) sessionElement.classList.add('hidden');
    
    // Reset form elements
    if (startButton) startButton.disabled = false;
    if (chatMessages) chatMessages.innerHTML = '';
    if (characterSelect) characterSelect.value = '';
    
    // Reset session ID
    sessionId = null;
}

function switchToSession(newId) {
    if (newId) {
        sessionId = newId;
        // Update session ID on server without reconnecting
        socket.emit('update_session_id', { session_id: sessionId });
        console.log('[CLIENT] Switched to session:', sessionId);
    }
    
    // Hide setup UI
    const setupElement = document.getElementById('setup-ui');
    if (setupElement) setupElement.style.display = 'none';
    
    // Show session UI
    const sessionElement = document.getElementById('initially-hidden');
    if (sessionElement) sessionElement.classList.remove('hidden');
}

function endSessionFromApp() {
    console.log('[CLIENT] Ending session from app.js:', sessionId);
    
    // Stop any ongoing speech recognition
    if (recognition && isListening) {
        shouldStopRecording = true;
        recognition.stop();
    }
    
    // Stop any playing audio
    if (isPlayingAudio) {
        audioQueue.length = 0;
        isPlayingAudio = false;
        isBotSpeaking = false;
    }
    
    // Emit end session event to server
    if (sessionId) {
        socket.emit('end_session', { session_id: sessionId });
    }
    
    // Reset to setup UI
    resetToSetup();
    
    // Show notification
    showNotification('Session ended successfully', 'info');
}

// Make function available globally with different name
window.endSessionFromApp = endSessionFromApp;

// -------------------------
// Socket message handlers
// -------------------------
socket.on('new_message', data => {
    if (!data.session_id || data.session_id === sessionId) {
        addMessage(data.text, data.sender);
        if (data.sender === 'bot') {
            isBotSpeaking = true;
        }
    }
});

socket.on('play_audio_base64', data => {
    if (!data.session_id || data.session_id === sessionId) {
        if (data.audio_base64) {
            isBotSpeaking = true;
            if (recognition && isListening) {
                shouldStopRecording = true;
                recognition.stop();
            }
            queueAndPlayAudio(data.audio_base64, data.mime);
        }
    }
});

socket.on('play_audio', data => {
    // optional handling for URLs
});

socket.on('mic_activated', data => {
    if (!data.session_id || data.session_id === sessionId) {
        if (micButton) {
            if (data.activated) micButton.classList.add('active');
            else micButton.classList.remove('active');
        }
        if (recognition) {
            if (data.activated && !isBotSpeaking && !isListening) recognition.start();
            else if (!data.activated && isListening) recognition.stop();
        }
    }
});

socket.on('tts_failed', data => {
    showNotification(data.message, 'warning');
});

// -------------------------
// UI event listeners
// -------------------------
document.addEventListener('DOMContentLoaded', () => {
    initAudioContext();
    initSpeechRecognition();

    if (sendButton) {
        sendButton.addEventListener('click', () => {
            const text = messageInput.value.trim();
            if (text && sessionId) {
                socket.emit('user_speech', { text, session_id: sessionId });
                messageInput.value = '';
>>>>>>> origin/master
            }
        });
    }
<<<<<<< HEAD
    
    console.log('[CLIENT] Page initialization completed');
});

// Handle page unload to clean up session
window.addEventListener('beforeunload', () => {
    if (sessionId) {
        socket.emit('end_session');
    }
=======

    if (messageInput) {
        messageInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') sendButton.click();
        });
    }

    if (micButton) {
        micButton.addEventListener('click', () => {
            shouldStopRecording = isListening;
            if (isListening) recognition.stop();
            else recognition.start();
        });
    }

    if (startButton) {
        startButton.addEventListener('click', () => {
            const char = characterSelect.value || 'optimistic';
            if (!char) return alert('Select a character');
            fetch('/start-session', {
                method:'POST',
                headers:{ 'Content-Type':'application/json' },
                body: JSON.stringify({ character:char })
            })
            .then(r=>r.json())
            .then(data=>{
                if (data.status==='success') {
                    switchToSession(data.session_id);
                    startButton.disabled = true;
                } else {
                    alert('Error: '+(data.message||'Failed to start'));
                }
            }).catch(e=>{
                console.error(e);
                alert('Network error');
            });
        });
    }

    const endBtn = document.getElementById('end-session-btn');
    if (endBtn) {
        endBtn.addEventListener('click', () => {
            endSessionFromApp();
        });
    }

    window.addEventListener('beforeunload', () => {
        if (sessionId) socket.emit('end_session', { session_id: sessionId });
    });
>>>>>>> origin/master
});

// -------------------------
// Connection test
// -------------------------
function testConnection() {
    fetch('/test-ws')
        .then(response => response.json())
        .then(data => {
            console.log('[CLIENT] Server test response:', data);
        })
        .catch(error => {
            console.error('[CLIENT] Server test failed:', error);
        });
}
