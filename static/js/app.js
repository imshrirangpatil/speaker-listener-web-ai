// Socket.IO connection with reconnection settings
let sessionId = null;
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
        setTimeout(() => socket.connect(), 1000);
    }
});

socket.on('connect_error', (error) => {
    console.log('[CLIENT] Connection error:', error);
    // Don't automatically retry on connection errors to prevent spam
});

// Handle reconnection attempts with backoff
socket.on('reconnect_attempt', (attemptNumber) => {
    console.log('[CLIENT] Reconnection attempt:', attemptNumber);
});

socket.on('reconnect', (attemptNumber) => {
    console.log('[CLIENT] Reconnected after', attemptNumber, 'attempts');
});

// Handle session assignment
socket.on('session_assigned', (data) => {
    sessionId = data.session_id;
    console.log('[CLIENT] Session assigned:', sessionId);
});

// Handle session ended
socket.on('session_ended', (data) => {
    console.log('[CLIENT] Session ended:', data.session_id);
    alert('Session ended. Returning to setup...');
    resetToSetup();
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

// Initialize audio context with iOS compatibility
function initAudioContext() {
    console.log('[CLIENT] Initializing audio context...');
    
    // Detect Safari
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    console.log('[CLIENT] Safari detected:', isSafari);
    
    if (window.AudioContext || window.webkitAudioContext) {
        if (!audioContext) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log('[CLIENT] Audio context created, state:', audioContext.state);
            } catch (error) {
                console.error('[CLIENT] Failed to create audio context:', error);
                return false;
            }
        }
        
        // Handle suspended context (common in Safari and iOS)
        if (audioContext.state === 'suspended') {
            console.log('[CLIENT] Audio context is suspended, attempting to resume...');
            
            // Safari-specific handling
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
                        console.error('[CLIENT] Failed to resume audio context in Safari:', error);
                    });
                };
                
                // Add multiple event listeners for Safari
                document.addEventListener('click', resumeAudio, { once: true });
                document.addEventListener('touchstart', resumeAudio, { once: true });
                document.addEventListener('touchend', resumeAudio, { once: true });
                document.addEventListener('keydown', resumeAudio, { once: true });
                
                console.log('[CLIENT] Safari audio context resume listeners added');
            } else {
                // Standard resume for other browsers
                audioContext.resume().then(() => {
                    console.log('[CLIENT] Audio context resumed successfully');
                }).catch(error => {
                    console.error('[CLIENT] Failed to resume audio context:', error);
                });
            }
        } else {
            console.log('[CLIENT] Audio context is ready');
        }
        
        return true;
    } else {
        console.error('[CLIENT] Web Audio API not supported');
        return false;
    }
}

// Enhanced audio playback for iOS compatibility
function playAudioFromBase64(audioBase64, mimeType = 'audio/wav') {
    return new Promise((resolve, reject) => {
        console.log('[CLIENT] Starting audio playback from base64...');
        
        // Detect Safari (iOS and macOS)
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || 
                     (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent) || isIOS;
        
        console.log(`[CLIENT] Browser detection: isIOS=${isIOS}, isSafari=${isSafari}`);
        
        // For Safari (both iOS and macOS), use HTML5 audio only (more reliable)
        if (isSafari) {
            console.log('[CLIENT] Safari detected, using HTML5 audio...');
            
            // Create audio element
            const audio = new Audio();
            
            // Safari prefers MP3 over WAV
            let audioFormat = mimeType;
            if (mimeType === 'audio/wav' && !audio.canPlayType('audio/wav')) {
                console.log('[CLIENT] WAV not supported, trying MP3...');
                audioFormat = 'audio/mpeg';
            }
            
            audio.src = `data:${audioFormat};base64,${audioBase64}`;
            
            // Preload for Safari
            audio.preload = 'auto';
            
            audio.onended = () => {
                console.log('[CLIENT] HTML5 audio playback completed');
                socket.emit('bot_audio_ended');
                resolve();
            };
            
            audio.onerror = (error) => {
                console.error('[CLIENT] HTML5 audio error:', error);
                console.log('[CLIENT] Trying alternative audio format...');
                
                // Try with different format if original fails
                const altFormat = audioFormat === 'audio/wav' ? 'audio/mpeg' : 'audio/wav';
                audio.src = `data:${altFormat};base64,${audioBase64}`;
                
                const retryPlay = () => {
                    const retryPromise = audio.play();
                    if (retryPromise !== undefined) {
                        retryPromise.catch(retryError => {
                            console.error('[CLIENT] Retry also failed:', retryError);
                            reject(retryError);
                        });
                    }
                };
                
                // Wait a bit before retry
                setTimeout(retryPlay, 100);
            };
            
            // Enhanced play handling for Safari
            const playAudio = () => {
                const playPromise = audio.play();
                if (playPromise !== undefined) {
                    playPromise.then(() => {
                        console.log('[CLIENT] HTML5 audio started successfully');
                    }).catch(error => {
                        console.error('[CLIENT] HTML5 audio play failed:', error);
                        console.log('[CLIENT] Error type:', error.name, 'Message:', error.message);
                        
                        // Safari often requires user interaction
                        if (error.name === 'NotAllowedError' || error.message.includes('user activation')) {
                            showNotification('Click "Enable Audio" to hear the bot speak', 'warning');
                        }
                        reject(error);
                    });
                } else {
                    // Old browsers
                    console.log('[CLIENT] Audio play() returned undefined (old browser)');
                }
            };
            
            // Load and play
            audio.onloadeddata = () => {
                console.log('[CLIENT] Audio data loaded, attempting to play...');
                playAudio();
            };
            
            // Fallback if onloadeddata doesn't fire
            setTimeout(() => {
                if (audio.readyState >= 2) { // HAVE_CURRENT_DATA
                    playAudio();
                }
            }, 100);
            
            return;
        }
        
        // For non-Safari browsers, try Web Audio API first
        console.log('[CLIENT] Non-Safari browser, trying Web Audio API...');
        console.log('[CLIENT] Audio context state:', audioContext ? audioContext.state : 'no context');
        
        // Fallback to HTML5 audio for non-Safari if Web Audio API fails
        const fallbackToHTMLAudio = () => {
            console.log('[CLIENT] Falling back to HTML5 audio...');
            const audio = new Audio(`data:${mimeType};base64,${audioBase64}`);
            
            audio.onended = () => {
                console.log('[CLIENT] HTML5 audio playback completed');
                socket.emit('bot_audio_ended');
                resolve();
            };
            
            audio.onerror = (error) => {
                console.error('[CLIENT] HTML5 audio error:', error);
                reject(error);
            };
            
            const playPromise = audio.play();
            if (playPromise !== undefined) {
                playPromise.then(() => {
                    console.log('[CLIENT] HTML5 audio started successfully');
                }).catch(error => {
                    console.error('[CLIENT] HTML5 audio play failed:', error);
                    reject(error);
                });
            }
        };
        
        // Try Web Audio API first, fallback to HTML5 audio
        if (!audioContext || audioContext.state === 'suspended') {
            fallbackToHTMLAudio();
            return;
        }
        
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
                console.error('[CLIENT] Audio decode error, falling back to HTML5:', error);
                fallbackToHTMLAudio();
            });
        } catch (error) {
            console.error('[CLIENT] Web Audio API error, falling back to HTML5:', error);
            fallbackToHTMLAudio();
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
        recognition.continuous = true;  // Keep listening for multiple phrases
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        
        recognition.onstart = () => {
            console.log('[CLIENT] Speech recognition started');
            isListening = true;
            if (micButton) micButton.classList.add('listening');
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[event.results.length - 1][0].transcript.trim();
            console.log('[CLIENT] Speech recognized:', transcript);
            
            // Only process if transcript is meaningful (not empty or just punctuation)
            if (transcript.length > 0 && transcript.match(/[a-zA-Z]/)) {
                // Send to server with session ID
                socket.emit('user_speech', { text: transcript, session_id: sessionId });
                
                // DON'T add to chat here - server will emit new_message which adds it
                
                // Update input field
                if (messageInput) messageInput.value = transcript;
                
                // Stop recognition after successful capture
                recognition.stop();
            } else {
                console.log('[CLIENT] Ignoring empty or invalid transcript');
            }
        };
        
        recognition.onerror = (event) => {
            console.error('[CLIENT] Speech recognition error:', event.error);
            isListening = false;
            if (micButton) micButton.classList.remove('listening');
            
            // Auto-restart speech recognition for certain error types
            if (event.error === 'no-speech' || event.error === 'audio-capture') {
                console.log('[CLIENT] Auto-restarting speech recognition due to:', event.error);
                setTimeout(() => {
                    const voiceBubble = document.getElementById('voice-bubble');
                    const shouldRestart = (micButton && micButton.classList.contains('active')) || 
                                         (voiceBubble && voiceBubble.classList.contains('mic-on'));
                    
                    if (shouldRestart) {
                        try {
                            recognition.start();
                        } catch (error) {
                            console.log('[CLIENT] Failed to restart speech recognition:', error);
                        }
                    }
                }, 300); // Reduced from 1000ms to 300ms for faster restart
            }
        };
        
        recognition.onend = () => {
            console.log('[CLIENT] Speech recognition ended');
            isListening = false;
            if (micButton) micButton.classList.remove('listening');
            
            // Auto-restart if microphone is still supposed to be active
            const voiceBubble = document.getElementById('voice-bubble');
            const shouldRestart = (micButton && micButton.classList.contains('active')) || 
                                 (voiceBubble && voiceBubble.classList.contains('mic-on'));
            
            if (shouldRestart) {
                console.log('[CLIENT] Mic still active, restarting speech recognition...');
                setTimeout(() => {
                    try {
                        recognition.start();
                    } catch (error) {
                        console.log('[CLIENT] Failed to restart speech recognition:', error);
                    }
                }, 200); // Reduced from 500ms to 200ms for immediate restart
            }
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
function switchToSession(newSessionId) {
    if (newSessionId) {
        sessionId = newSessionId;
        console.log('[CLIENT] Session started, reconnecting socket with session ID:', sessionId);
        
        // Disconnect and reconnect with correct session ID
        socket.disconnect();
        socket.io.opts.query = { session_id: sessionId };
        socket.connect();
    }
    
    if (setupUI) setupUI.style.display = 'none';
    if (sessionUI) sessionUI.style.display = 'block';
    // Removed launching message - handled by bot conversation flow
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
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => document.body.removeChild(notification), 300);
    }, 3000);
}

// Add end session functionality
function endSession() {
    if (sessionId) {
        socket.emit('end_session');
        resetToSetup();
    }
}

function resetToSetup() {
    // Reset UI
    if (setupUI) setupUI.style.display = 'block';
    if (sessionUI) sessionUI.style.display = 'none';
    if (startButton) startButton.disabled = false;
    if (chatMessages) chatMessages.innerHTML = '';
    
    // Reset session
    sessionId = null;
    
    // Reset character selection if element exists
    const characterSelect = document.getElementById('characterSelect');
    if (characterSelect) characterSelect.value = '';
    
    // Removed welcome message from resetToSetup
}

// Event listeners
if (micButton) {
    micButton.addEventListener('click', toggleMicrophone);
}

// Add voice bubble click handler for index.html (moved to main DOMContentLoaded)

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
                sessionId = data.session_id;
                console.log('[CLIENT] Reconnecting socket with session ID:', sessionId);
                
                // Disconnect and reconnect with correct session ID
                socket.disconnect();
                socket.io.opts.query = { session_id: sessionId };
                socket.connect();
                
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

// Add end session button event listener
document.addEventListener('DOMContentLoaded', () => {
    const endButton = document.getElementById('end-button');
    if (endButton) {
        endButton.addEventListener('click', endSession);
    }
});

// Handle page unload to clean up session
window.addEventListener('beforeunload', () => {
    if (sessionId) {
        socket.emit('end_session');
    }
});

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('[CLIENT] Page loaded, initializing...');
    initAudioContext();
    initSpeechRecognition();
    
    // Removed welcome message from DOMContentLoaded
    
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
            }
        });
        
        // Initial state
        voiceBubble.innerHTML = '<span id="role-icon">👋</span>';
    }
});

// Add event listener for the Enable Audio button
const enableAudioBtn = document.getElementById('enable-audio-btn');
if (enableAudioBtn) {
    enableAudioBtn.addEventListener('click', () => {
        console.log('[CLIENT] Enable Audio button clicked');
        
        // Detect Safari for specific messaging
        const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
        
        // Initialize audio context
        const audioInitialized = initAudioContext();
        
        if (audioInitialized || isSafari) {
            // For Safari, show success even if Web Audio API fails (HTML5 audio will work)
            const message = isSafari ? 
                'Audio enabled for Safari! You should now hear the bot.' : 
                'Audio enabled! You should now hear the bot.';
            showNotification(message, 'success');
            hideEnableAudioButton();
            
            // For Safari, also test a brief silent audio to ensure permission
            if (isSafari) {
                console.log('[CLIENT] Testing Safari audio permission...');
                const testAudio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLHvr');
                testAudio.volume = 0.01; // Very quiet
                testAudio.play().then(() => {
                    console.log('[CLIENT] Safari audio permission test passed');
                }).catch((error) => {
                    console.log('[CLIENT] Safari audio permission test failed:', error);
                    showNotification('Please interact with the page to enable audio', 'warning');
                });
            }
        } else {
            showNotification('Audio not supported in this browser. Try Chrome for best results.', 'error');
        }
    });
}

function hideEnableAudioButton() {
    const enableAudioBtn = document.getElementById('enable-audio-btn');
    if (enableAudioBtn) {
        enableAudioBtn.style.display = 'none';
        console.log('[CLIENT] Enable Audio button hidden');
    }
}
