// Socket.IO connection with reconnection settings
const socket = io({
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    autoConnect: true
});

// Socket connection event handlers
socket.on('connect', () => {
    console.log('[CLIENT] Socket connected:', socket.id);
});

socket.on('disconnect', (reason) => {
    console.log('[CLIENT] Socket disconnected:', reason);
    if (reason === 'io server disconnect') {
        // Server initiated disconnect, try reconnecting
        socket.connect();
    }
});

socket.on('connect_error', (error) => {
    console.log('[CLIENT] Connection error:', error);
});

// DOM elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const micButton = document.getElementById('mic-button');
const startButton = document.getElementById('start-button');
const characterSelect = document.getElementById('character-select');
const setupUI = document.getElementById('setup-ui');
const sessionUI = document.getElementById('session-ui');

// Audio context for playing audio
let audioContext;
let audioQueue = [];
let isPlayingAudio = false;

// Speech recognition
let recognition;
let isListening = false;

// Initialize audio context
function initAudioContext() {
    console.log('[CLIENT] Initializing audio context...');
    if (!audioContext) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            console.log('[CLIENT] Audio context created successfully');
            console.log('[CLIENT] Audio context state:', audioContext.state);
            
            // Resume audio context if suspended (needed for Chrome)
            if (audioContext.state === 'suspended') {
                console.log('[CLIENT] Audio context suspended, attempting to resume...');
                audioContext.resume().then(() => {
                    console.log('[CLIENT] Audio context resumed successfully');
                }).catch(error => {
                    console.error('[CLIENT] Failed to resume audio context:', error);
                });
            }
        } catch (error) {
            console.error('[CLIENT] Failed to create audio context:', error);
        }
    } else {
        console.log('[CLIENT] Audio context already exists');
    }
}

// Play audio from base64 data
function playAudioFromBase64(audioBase64, mimeType = 'audio/wav') {
    return new Promise((resolve, reject) => {
        console.log('[CLIENT] Starting audio playback from base64...');
        console.log('[CLIENT] Audio context state:', audioContext ? audioContext.state : 'no context');
        
        try {
            // Convert base64 to array buffer
            console.log('[CLIENT] Converting base64 to array buffer...');
            const binaryString = atob(audioBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            console.log('[CLIENT] Array buffer created, size:', bytes.length);
            
            // Decode audio
            console.log('[CLIENT] Decoding audio data...');
            audioContext.decodeAudioData(bytes.buffer, (buffer) => {
                console.log('[CLIENT] Audio decoded successfully, duration:', buffer.duration);
                
                // Create audio source
                const source = audioContext.createBufferSource();
                source.buffer = buffer;
                source.connect(audioContext.destination);
                
                // Play audio
                console.log('[CLIENT] Starting audio playback...');
                source.start(0);
                
                // Handle completion
                source.onended = () => {
                    console.log('[CLIENT] Audio playback completed');
                    socket.emit('bot_audio_ended');
                    resolve();
                };
                
                console.log('[CLIENT] Audio playback started successfully');
            }, (error) => {
                console.error('[CLIENT] Audio decode error:', error);
                reject(error);
            });
        } catch (error) {
            console.error('[CLIENT] Audio play error:', error);
            reject(error);
        }
    });
}

// Queue and play audio
async function queueAndPlayAudio(audioBase64, mimeType) {
    console.log('[CLIENT] Queueing audio, queue length:', audioQueue.length);
    audioQueue.push({ audioBase64, mimeType });
    
    if (!isPlayingAudio) {
        console.log('[CLIENT] Starting audio playback...');
        await playNextAudio();
    } else {
        console.log('[CLIENT] Audio already playing, queued for later');
    }
}

async function playNextAudio() {
    if (audioQueue.length === 0) {
        console.log('[CLIENT] Audio queue empty, stopping playback');
        isPlayingAudio = false;
        return;
    }
    
    isPlayingAudio = true;
    const { audioBase64, mimeType } = audioQueue.shift();
    console.log('[CLIENT] Playing next audio, remaining in queue:', audioQueue.length);
    
    try {
        await playAudioFromBase64(audioBase64, mimeType);
        await playNextAudio(); // Play next in queue
    } catch (error) {
        console.error('[CLIENT] Audio playback failed:', error);
        await playNextAudio(); // Continue with next audio
    }
}

// Initialize speech recognition
function initSpeechRecognition() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        
        recognition.onstart = () => {
            console.log('[CLIENT] Speech recognition started');
            isListening = true;
            if (micButton) micButton.classList.add('listening');
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('[CLIENT] Speech recognized:', transcript);
            
            // Send to server
            socket.emit('user_speech', { text: transcript });
            
            // Add to chat
            addMessage(transcript, 'user');
            
            // Update input field
            if (messageInput) messageInput.value = transcript;
        };
        
        recognition.onerror = (event) => {
            console.error('[CLIENT] Speech recognition error:', event.error);
            isListening = false;
            if (micButton) micButton.classList.remove('listening');
        };
        
        recognition.onend = () => {
            console.log('[CLIENT] Speech recognition ended');
            isListening = false;
            if (micButton) micButton.classList.remove('listening');
        };
    } else {
        console.error('[CLIENT] Speech recognition not supported');
        if (micButton) micButton.style.display = 'none';
    }
}

// Add message to chat
function addMessage(text, sender) {
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    messageDiv.textContent = text;
    
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

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
function switchToSession() {
    if (setupUI) setupUI.style.display = 'none';
    if (sessionUI) sessionUI.style.display = 'block';
    addMessage('Charisma Bot is now launching...', 'system');
}

// Socket.IO event handlers
socket.on('new_message', (data) => {
    console.log('[CLIENT] New message received:', data);
    addMessage(data.text, data.sender);
});

socket.on('play_audio_base64', (data) => {
    console.log('[CLIENT] Audio received!');
    console.log('[CLIENT] Audio data type:', typeof data.audio_base64);
    console.log('[CLIENT] Audio data length:', data.audio_base64 ? data.audio_base64.length : 'null');
    console.log('[CLIENT] MIME type:', data.mime);
    console.log('[CLIENT] Audio data preview:', data.audio_base64 ? data.audio_base64.substring(0, 50) + '...' : 'null');
    
    if (data.audio_base64 && data.audio_base64.length > 0) {
        queueAndPlayAudio(data.audio_base64, data.mime);
    } else {
        console.error('[CLIENT] Audio data is empty or null');
    }
});

socket.on('play_audio', (data) => {
    console.log('[CLIENT] Audio URL received:', data.url);
    // Handle audio URL if needed
});

socket.on('mic_activated', (data) => {
    console.log('[CLIENT] Mic activation:', data.activated);
    if (micButton) {
        if (data.activated) {
            micButton.classList.add('active');
        } else {
            micButton.classList.remove('active');
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
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => document.body.removeChild(notification), 300);
    }, 3000);
}

// Event listeners
if (micButton) {
    micButton.addEventListener('click', toggleMicrophone);
}

if (sendButton) {
    sendButton.addEventListener('click', () => {
        const text = messageInput ? messageInput.value.trim() : '';
        if (text) {
            socket.emit('user_input', { text: text });
            addMessage(text, 'user');
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

if (startButton) {
    startButton.addEventListener('click', () => {
        const character = characterSelect ? characterSelect.value : 'optimistic';
        if (!character) {
            alert('Please select a character.');
            return;
        }
        
        console.log('[CLIENT] Starting session with character:', character);
        
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
                switchToSession();
                if (startButton) startButton.disabled = true;
            } else {
                alert('❌ ' + (data.message || 'Failed to start session'));
            }
        })
        .catch(error => {
            console.error('[CLIENT] Error starting session:', error);
            alert('Something went wrong starting the session.');
        });
    });
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('[CLIENT] Page loaded, initializing...');
    initAudioContext();
    initSpeechRecognition();
    
    // Show welcome message
    if (chatMessages) {
        addMessage('Welcome to Charisma Bot! Select a character and click "Start Session" to begin.', 'system');
    }
});
