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

socket.on('session_updated', (data) => {
    console.log('[CLIENT] Session updated:', data.session_id);
    sessionId = data.session_id;
});

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
                console.log('[CLIENT] AudioContext state:', audioContext.state);
            } catch (err) {
                console.error('[CLIENT] Failed to create AudioContext:', err);
                return false;
            }
        }
        if (audioContext.state === 'suspended') {
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
        }
        return true;
    } else {
        console.error('[CLIENT] Web Audio API not supported');
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
    setTimeout(() => {
        note.style.opacity = '0';
        setTimeout(() => note.remove(), 300);
    }, type==='error'?5000:3000);
}

function resetToSetup() {
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
            }
        });
    }

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
