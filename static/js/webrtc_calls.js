/* ============================================================
   NamVibe Phase 40 — Premium WebRTC Calling Engine
   ============================================================ */

let CHAIN_WEBRTC = {
    socket: null,
    localStream: null,
    remoteStream: null,
    peerConnection: null,
    currentCallId: null,
    currentTargetId: null,
    currentCallType: 'audio',
    isMuted: false,
    isCameraOn: true,
    isSpeakerOn: false,
    callTimer: null,
    callSeconds: 0,
    networkQuality: 'Good',
    isPiP: false,
    ringingAudio: null,
    ringingInterval: null,
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }, { urls: 'stun:global.stun.twilio.com:3478' }],
    config: {
        iceCandidatePoolSize: 10,
        iceTransportPolicy: 'all'
    }
};

function wCallInit(socket) {
    CHAIN_WEBRTC.socket = socket;
    loadICEServers();
    bindSocketEvents();
    initSoundSettings();
}

function initSoundSettings() {
    if (localStorage.getItem('chain_call_sound_enabled') === null) {
        localStorage.setItem('chain_call_sound_enabled', 'true');
    }
}

async function loadICEServers() {
    try {
        const res = await fetch('/calls/api/ice-servers');
        const data = await res.json();
        if (data && data.iceServers) {
            CHAIN_WEBRTC.iceServers = data.iceServers;
        }
    } catch (e) {
        console.warn('[wCall] Could not load ICE servers, using defaults');
    }
}

function bindSocketEvents() {
    const s = CHAIN_WEBRTC.socket;
    if (!s) return;

    s.on('call:incoming', handleIncomingCall);
    s.on('call:offer', handleRemoteOffer);
    s.on('call:answer', handleRemoteAnswer);
    s.on('call:ice-candidate', handleRemoteICE);
    s.on('call:accepted', handleCallAccepted);
    s.on('call:rejected', handleCallRejected);
    s.on('call:cancelled', handleCallCancelled);
    s.on('call:ended', handleCallEnded);
    s.on('call:busy', handleCallBusy);
    s.on('call:no-answer', handleCallNoAnswer);
    s.on('call:missed', handleCallMissed);
    s.on('call:ringing', handleRemoteRinging);
    s.on('call:mute_state', handleRemoteMute);
    s.on('call:camera_state', handleRemoteCamera);
    s.on('call:speaker_state', handleRemoteSpeaker);
    s.on('call:reconnecting', handleRemoteReconnecting);
    s.on('call:reconnected', handleRemoteReconnected);
    s.on('call:failed', handleRemoteFailed);
    s.on('call:incoming', function(data) {
        stopCallTimeoutTimer();
    });
    s.on('call:accepted', function() {
        stopCallTimeoutTimer();
    });
    s.on('call:rejected', function() {
        stopCallTimeoutTimer();
    });
    s.on('call:busy', function() {
        stopCallTimeoutTimer();
        showCallNotification('User is on another call');
    });
    s.on('call:blocked', function() {
        stopCallTimeoutTimer();
        showCallNotification('Unable to call this user');
    });
}

/* ---- Incoming Call (Phase 2 Enhanced) ---- */
function handleIncomingCall(data) {
    if (CHAIN_WEBRTC.currentCallId) {
        CHAIN_WEBRTC.socket.emit('call:busy', { call_id: data.call_id });
        return;
    }
    stopCallTimeoutTimer();
    CHAIN_WEBRTC.currentCallId = data.call_id;
    CHAIN_WEBRTC.currentTargetId = data.caller_id;
    CHAIN_WEBRTC.currentCallType = data.call_type || 'audio';

    showIncomingCallUI(data);
    startRingtone();

    CHAIN_WEBRTC.socket.emit('call:ringing', {
        call_id: data.call_id,
        target_id: data.caller_id
    });
}

function handleRemoteRinging(data) {
    const el = document.getElementById('call-status-text');
    if (el) el.textContent = 'Ringing...';
}

/* ---- Call Accepted / Rejected / Cancelled ---- */
function handleCallAccepted(data) {
    stopRingtone();
    const el = document.getElementById('call-status-text');
    if (el) el.textContent = 'Connected';
    startCallTimer();
    showActiveCallUI();
}

function handleCallRejected(data) {
    stopRingtone();
    showCallNotification('Call declined');
    cleanupCall();
}

function handleCallCancelled(data) {
    stopRingtone();
    showCallNotification('Call cancelled');
    cleanupCall();
}

function handleCallEnded(data) {
    stopRingtone();
    showCallNotification('Call ended');
    cleanupCall();
}

function handleCallBusy(data) {
    stopRingtone();
    showCallNotification('User is busy');
    cleanupCall();
}

function handleCallNoAnswer(data) {
    stopRingtone();
    showCallNotification('No answer');
    cleanupCall();
}

function handleCallMissed(data) {
    stopRingtone();
    showCallNotification('Missed call');
    cleanupCall();
}

/* ---- WebRTC Signaling ---- */
async function handleRemoteOffer(data) {
    try {
        await ensureLocalStream();
        const pc = getOrCreatePC(data.call_id);
        await pc.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp: data.sdp }));

        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        CHAIN_WEBRTC.socket.emit('call:answer', {
            target_id: data.sender_id,
            call_id: data.call_id,
            sdp: answer.sdp,
            encrypted: true
        });
    } catch (e) {
        console.error('[wCall] Handle offer error:', e);
    }
}

async function handleRemoteAnswer(data) {
    try {
        const pc = getOrCreatePC(data.call_id);
        await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: data.sdp }));
    } catch (e) {
        console.error('[wCall] Handle answer error:', e);
    }
}

function handleRemoteICE(data) {
    try {
        const pc = getOrCreatePC(data.call_id);
        if (data.candidate) {
            pc.addIceCandidate(new RTCIceCandidate(data.candidate));
        }
    } catch (e) {
        console.error('[wCall] Handle ICE error:', e);
    }
}

/* ---- Remote State Changes ---- */
function handleRemoteMute(data) {
    const indicator = document.getElementById('remote-mute-indicator');
    if (indicator) indicator.style.display = data.muted ? 'block' : 'none';
}

function handleRemoteCamera(data) {
    const el = document.getElementById('remote-video');
    if (el) el.style.display = data.enabled ? 'block' : 'none';
}

function handleRemoteSpeaker(data) {}

function handleRemoteReconnecting(data) {
    const el = document.getElementById('network-warning');
    if (el) { el.style.display = 'block'; el.textContent = 'Reconnecting...'; }
    updateNetworkQuality('Reconnecting');
    showReconnectingOverlay();
}

function handleRemoteReconnected(data) {
    const el = document.getElementById('network-warning');
    if (el) el.style.display = 'none';
    updateNetworkQuality('Good');
    hideReconnectingOverlay();
}

function handleRemoteFailed(data) {
    updateNetworkQuality('Failed');
    showCallNotification('Call failed');
    cleanupCall();
}

/* ---- Media / PeerConnection ---- */
async function ensureLocalStream() {
    if (CHAIN_WEBRTC.localStream) return CHAIN_WEBRTC.localStream;
    const constraints = {
        audio: true,
        video: CHAIN_WEBRTC.currentCallType === 'video' ? { width: { ideal: 640 }, height: { ideal: 480 } } : false
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    CHAIN_WEBRTC.localStream = stream;

    const localVideo = document.getElementById('local-video');
    if (localVideo) localVideo.srcObject = stream;

    return stream;
}

function getOrCreatePC(callId) {
    if (CHAIN_WEBRTC.peerConnection) return CHAIN_WEBRTC.peerConnection;

    CHAIN_WEBRTC.config.iceServers = CHAIN_WEBRTC.iceServers;
    const pc = new RTCPeerConnection(CHAIN_WEBRTC.config);
    CHAIN_WEBRTC.peerConnection = pc;

    pc.onicecandidate = (event) => {
        if (event.candidate && CHAIN_WEBRTC.currentTargetId && CHAIN_WEBRTC.currentCallId) {
            CHAIN_WEBRTC.socket.emit('call:ice-candidate', {
                target_id: CHAIN_WEBRTC.currentTargetId,
                call_id: CHAIN_WEBRTC.currentCallId,
                candidate: event.candidate,
                encrypted: true
            });
        }
    };

    pc.ontrack = (event) => {
        CHAIN_WEBRTC.remoteStream = event.streams[0];
        const remoteVideo = document.getElementById('remote-video');
        if (remoteVideo) remoteVideo.srcObject = event.streams[0];
    };

    pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        if (state === 'disconnected' || state === 'failed') {
            updateNetworkQuality(state === 'failed' ? 'Failed' : 'Reconnecting');
            CHAIN_WEBRTC.socket.emit('call:reconnecting', {
                call_id: CHAIN_WEBRTC.currentCallId,
                target_id: CHAIN_WEBRTC.currentTargetId
            });
            const warn = document.getElementById('network-warning');
            if (warn) warn.style.display = 'block';
        } else if (state === 'connected') {
            updateNetworkQuality('Good');
            CHAIN_WEBRTC.socket.emit('call:reconnected', {
                call_id: CHAIN_WEBRTC.currentCallId,
                target_id: CHAIN_WEBRTC.currentTargetId
            });
            const warn = document.getElementById('network-warning');
            if (warn) warn.style.display = 'none';
        }
    };

    if (CHAIN_WEBRTC.localStream) {
        CHAIN_WEBRTC.localStream.getTracks().forEach(track => {
            pc.addTrack(track, CHAIN_WEBRTC.localStream);
        });
    }

    return pc;
}

/* ---- Start Call (Phase 2 Enhanced) ---- */
async function wStartCall(targetId, threadId, callType) {
    if (CHAIN_WEBRTC.currentCallId) {
        showCallNotification('Already in a call');
        return;
    }

    CHAIN_WEBRTC.currentTargetId = targetId;
    CHAIN_WEBRTC.currentCallType = callType || 'audio';

    CHAIN_WEBRTC.socket.emit('call:start', {
        target_id: targetId,
        thread_id: threadId,
        call_type: callType
    });

    // Start ringback tone and timeout for caller
    startRingbackTone();
    startCallTimeoutTimer(CHAIN_WEBRTC.currentCallId, 15);
}

/* ---- Accept / Reject / End Call ---- */
async function wAcceptCall() {
    if (!CHAIN_WEBRTC.currentCallId) return;
    stopRingtone();

    try {
        await ensureLocalStream();
        const pc = getOrCreatePC(CHAIN_WEBRTC.currentCallId);

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        CHAIN_WEBRTC.socket.emit('call:accept', {
            call_id: CHAIN_WEBRTC.currentCallId,
            target_id: CHAIN_WEBRTC.currentTargetId
        });

        CHAIN_WEBRTC.socket.emit('call:offer', {
            target_id: CHAIN_WEBRTC.currentTargetId,
            call_id: CHAIN_WEBRTC.currentCallId,
            sdp: offer.sdp,
            call_type: CHAIN_WEBRTC.currentCallType,
            encrypted: true
        });
    } catch (e) {
        console.error('[wCall] Accept error:', e);
    }
}

function wRejectCall() {
    if (!CHAIN_WEBRTC.currentCallId) return;
    stopRingtone();
    CHAIN_WEBRTC.socket.emit('call:reject', {
        call_id: CHAIN_WEBRTC.currentCallId,
        target_id: CHAIN_WEBRTC.currentTargetId
    });
    cleanupCall();
}

function wEndCall() {
    if (!CHAIN_WEBRTC.currentCallId) return;
    CHAIN_WEBRTC.socket.emit('call:end', {
        call_id: CHAIN_WEBRTC.currentCallId,
        target_id: CHAIN_WEBRTC.currentTargetId
    });
    cleanupCall();
}

/* ---- Media Controls ---- */
function wToggleMute() {
    if (CHAIN_WEBRTC.localStream) {
        CHAIN_WEBRTC.isMuted = !CHAIN_WEBRTC.isMuted;
        CHAIN_WEBRTC.localStream.getAudioTracks().forEach(t => t.enabled = !CHAIN_WEBRTC.isMuted);
        CHAIN_WEBRTC.socket.emit('call:mute', {
            call_id: CHAIN_WEBRTC.currentCallId,
            target_id: CHAIN_WEBRTC.currentTargetId,
            muted: CHAIN_WEBRTC.isMuted
        });
        updateMuteButton();
    }
}

function wToggleCamera() {
    if (CHAIN_WEBRTC.localStream) {
        CHAIN_WEBRTC.isCameraOn = !CHAIN_WEBRTC.isCameraOn;
        CHAIN_WEBRTC.localStream.getVideoTracks().forEach(t => t.enabled = CHAIN_WEBRTC.isCameraOn);
        CHAIN_WEBRTC.socket.emit('call:camera-toggle', {
            call_id: CHAIN_WEBRTC.currentCallId,
            target_id: CHAIN_WEBRTC.currentTargetId,
            enabled: CHAIN_WEBRTC.isCameraOn
        });
        updateCameraButton();
    }
}

function wToggleSpeaker() {
    CHAIN_WEBRTC.isSpeakerOn = !CHAIN_WEBRTC.isSpeakerOn;
    CHAIN_WEBRTC.socket.emit('call:speaker-toggle', {
        call_id: CHAIN_WEBRTC.currentCallId,
        target_id: CHAIN_WEBRTC.currentTargetId,
        enabled: CHAIN_WEBRTC.isSpeakerOn
    });
    updateSpeakerButton();
}

/* ---- Phase 2: Premium Ringtone Engine ---- */
function startRingtone() {
    stopRingtone();
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        let gainVal = 0.1;
        const savedPref = localStorage.getItem('chain_call_sound_enabled');
        if (savedPref === 'false') { stopRingtone(); return; }
        function playBeep() {
            if (localStorage.getItem('chain_call_sound_enabled') === 'false') return;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 440;
            gain.gain.setValueAtTime(gainVal, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
            osc.start();
            setTimeout(() => { try { osc.stop(); } catch(e) {} }, 600);
        }
        playBeep();
        CHAIN_WEBRTC.ringingInterval = setInterval(playBeep, 1200);
        if (navigator.vibrate) navigator.vibrate([400, 100, 400, 100, 400, 100, 400]);
        if ('Notification' in window && Notification.permission === 'granted') {
            try { new Notification('Incoming ' + (CHAIN_WEBRTC.currentCallType || 'call') + ' call', { body: 'Someone is calling...', silent: true }); } catch(e) {}
        }
    } catch (e) {}
}

function startRingbackTone() {
    stopRingtone();
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const savedPref = localStorage.getItem('chain_call_sound_enabled');
        if (savedPref === 'false') return;
        function playRingback() {
            if (localStorage.getItem('chain_call_sound_enabled') === 'false') return;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 420;
            gain.gain.setValueAtTime(0.08, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
            osc.start();
            setTimeout(() => { try { osc.stop(); } catch(e) {} }, 400);
        }
        playRingback();
        CHAIN_WEBRTC.ringingInterval = setInterval(playRingback, 1800);
    } catch (e) {}
}

function playTestSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 440;
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1);
        osc.start();
        setTimeout(() => { try { osc.stop(); } catch(e) {} }, 1000);
        const btn = document.getElementById('testSoundBtn');
        if (btn) { btn.textContent = 'Playing...'; setTimeout(() => { btn.textContent = 'Test Sound'; }, 1200); }
    } catch (e) {}
}

/* ---- Vibration Fallback ---- */
function vibrateRing() {
    if (navigator.vibrate) {
        navigator.vibrate([400, 100, 400, 100, 400, 100, 400, 100, 400]);
    }
}

function stopRingtone() {
    if (CHAIN_WEBRTC.ringingInterval) {
        clearInterval(CHAIN_WEBRTC.ringingInterval);
        CHAIN_WEBRTC.ringingInterval = null;
    }
}

/* ---- Phase 2: Auto Timeout ---- */
let _callTimeoutTimer = null;

function startCallTimeoutTimer(callId, seconds) {
    stopCallTimeoutTimer();
    const timeoutSeconds = seconds || 15;
    _callTimeoutTimer = setTimeout(function() {
        if (CHAIN_WEBRTC.currentCallId === callId && CHAIN_WEBRTC.currentCallId) {
            CHAIN_WEBRTC.socket.emit('call:timeout', { call_id: callId });
            CHAIN_WEBRTC.socket.emit('call:end', { call_id: callId, target_id: CHAIN_WEBRTC.currentTargetId, reason: 'timeout' });
            showCallNotification('No answer');
            cleanupCall();
        }
    }, timeoutSeconds * 1000);
}

function stopCallTimeoutTimer() {
    if (_callTimeoutTimer) {
        clearTimeout(_callTimeoutTimer);
        _callTimeoutTimer = null;
    }
}

/* ---- Phase 2: ICE Restart ---- */
function wRestartICE() {
    const pc = CHAIN_WEBRTC.peerConnection;
    if (!pc) return;
    pc.restartIce();
    CHAIN_WEBRTC.socket.emit('call:reconnecting', {
        call_id: CHAIN_WEBRTC.currentCallId,
        target_id: CHAIN_WEBRTC.currentTargetId
    });
}

/* ---- Phase 2: Switch Camera ---- */
function wSwitchCamera() {
    if (!CHAIN_WEBRTC.localStream) return;
    const videoTracks = CHAIN_WEBRTC.localStream.getVideoTracks();
    if (videoTracks.length === 0) return;
    const track = videoTracks[0];
    const settings = track.getSettings();
    const newFacing = settings.facingMode === 'user' ? 'environment' : 'user';
    navigator.mediaDevices.getUserMedia({ audio: true, video: { facingMode: newFacing } })
        .then(function(newStream) {
            const newTrack = newStream.getVideoTracks()[0];
            if (newTrack) {
                track.stop();
                CHAIN_WEBRTC.localStream.removeTrack(track);
                CHAIN_WEBRTC.localStream.addTrack(newTrack);
                const pc = CHAIN_WEBRTC.peerConnection;
                if (pc) {
                    const sender = pc.getSenders().find(function(s) { return s.track && s.track.kind === 'video'; });
                    if (sender) sender.replaceTrack(newTrack);
                }
                const localVideo = document.getElementById('local-video');
                if (localVideo && localVideo.srcObject) {
                    localVideo.srcObject = CHAIN_WEBRTC.localStream;
                }
            }
        })
        .catch(function(e) { console.warn('[wCall] Camera switch error:', e); });
}

/* ---- Timer ---- */
function startCallTimer() {
    stopCallTimer();
    CHAIN_WEBRTC.callSeconds = 0;
    CHAIN_WEBRTC.callTimer = setInterval(() => {
        CHAIN_WEBRTC.callSeconds++;
        const el = document.getElementById('call-timer');
        if (el) {
            const m = String(Math.floor(CHAIN_WEBRTC.callSeconds / 60)).padStart(2, '0');
            const s = String(CHAIN_WEBRTC.callSeconds % 60).padStart(2, '0');
            el.textContent = m + ':' + s;
        }
    }, 1000);
}

function stopCallTimer() {
    if (CHAIN_WEBRTC.callTimer) {
        clearInterval(CHAIN_WEBRTC.callTimer);
        CHAIN_WEBRTC.callTimer = null;
    }
}

/* ---- Cleanup ---- */
function cleanupCall() {
    stopRingtone();
    stopCallTimer();
    stopCallTimeoutTimer();

    if (CHAIN_WEBRTC.peerConnection) {
        CHAIN_WEBRTC.peerConnection.close();
        CHAIN_WEBRTC.peerConnection = null;
    }
    if (CHAIN_WEBRTC.localStream) {
        CHAIN_WEBRTC.localStream.getTracks().forEach(t => t.stop());
        CHAIN_WEBRTC.localStream = null;
    }
    CHAIN_WEBRTC.remoteStream = null;
    CHAIN_WEBRTC.currentCallId = null;
    CHAIN_WEBRTC.currentTargetId = null;
    CHAIN_WEBRTC.isMuted = false;
    CHAIN_WEBRTC.isCameraOn = true;
    CHAIN_WEBRTC.isSpeakerOn = false;

    hideCallUI();
}

/* ---- UI Helpers ---- */
function showIncomingCallUI(data) {
    const overlay = document.getElementById('call-overlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
    const statusEl = document.getElementById('call-status-text');
    if (statusEl) statusEl.textContent = 'Incoming ' + (data.call_type || 'audio') + ' call';
    const nameEl = overlay.querySelector('p');
    if (nameEl) nameEl.textContent = 'Someone is calling...';
    const timerEl = document.getElementById('call-timer');
    if (timerEl) timerEl.style.display = 'none';
    const answerBtn = document.getElementById('answer-btn');
    if (answerBtn) answerBtn.style.display = 'flex';
    const controls = overlay.querySelectorAll('.call-controls .call-control-btn:not(#answer-btn):not(.end-call)');
    controls.forEach(b => b.style.display = 'none');
    const endBtn = overlay.querySelector('.end-call');
    if (endBtn) endBtn.style.display = 'none';
}

function showActiveCallUI() {
    const overlay = document.getElementById('call-overlay');
    if (!overlay) return;
    const statusEl = document.getElementById('call-status-text');
    if (statusEl) statusEl.textContent = 'Connected';
    updateNetworkQuality('Good');
    const timerEl = document.getElementById('call-timer');
    if (timerEl) timerEl.style.display = 'block';
    const answerBtn = document.getElementById('answer-btn');
    if (answerBtn) answerBtn.style.display = 'none';
    const controls = overlay.querySelectorAll('.call-controls .call-control-btn:not(#answer-btn):not(.end-call)');
    controls.forEach(b => b.style.display = 'flex');
    const endBtn = overlay.querySelector('.end-call');
    if (endBtn) endBtn.style.display = 'flex';
    updateMuteButton();
    updateCameraButton();
    updateSpeakerButton();
}

function hideCallUI() {
    const overlay = document.getElementById('call-overlay');
    if (overlay) overlay.style.display = 'none';
    const mini = document.getElementById('phase54-mini-call');
    if (mini) mini.style.display = 'none';
    CHAIN_WEBRTC.isPiP = false;
    const callScreen = document.getElementById('callScreen');
    if (callScreen) callScreen.classList.remove('active');
}

const _origHideCallUI = hideCallUI;
hideCallUI = function() {
    const modal = document.getElementById('incoming-call-modal');
    if (modal) modal.style.display = 'none';
    if (_origHideCallUI) _origHideCallUI();
};

function updateMuteButton() {
    const btn = document.getElementById('muteBtn') || document.querySelector('[onclick*="toggleMute"]');
    if (btn) {
        btn.classList.toggle('active', CHAIN_WEBRTC.isMuted);
        btn.innerHTML = CHAIN_WEBRTC.isMuted ? '<i class="fas fa-microphone-slash"></i>' : '<i class="fas fa-microphone"></i>';
    }
}

function updateCameraButton() {
    const btn = document.querySelector('[onclick*="toggleCamera"]');
    if (btn) {
        btn.classList.toggle('active', !CHAIN_WEBRTC.isCameraOn);
        btn.innerHTML = CHAIN_WEBRTC.isCameraOn ? '<i class="fas fa-video"></i>' : '<i class="fas fa-video-slash"></i>';
    }
}

function updateSpeakerButton() {
    const btn = document.querySelector('[onclick*="toggleSpeaker"]');
    if (btn) {
        btn.classList.toggle('active', CHAIN_WEBRTC.isSpeakerOn);
        btn.innerHTML = CHAIN_WEBRTC.isSpeakerOn ? '<i class="fas fa-volume-up"></i>' : '<i class="fas fa-volume-off"></i>';
    }
}

function showCallNotification(msg) {
    const el = document.getElementById('call-status-text');
    if (el) el.textContent = msg;
    setTimeout(() => {
        if (el && el.textContent === msg) el.textContent = 'Call ended';
    }, 2000);
}

function updateNetworkQuality(status) {
    const normalized = ['Good', 'Weak', 'Reconnecting', 'Failed'].includes(status) ? status : 'Good';
    CHAIN_WEBRTC.networkQuality = normalized;
    const el = document.getElementById('phase54-network-quality') || document.getElementById('call-quality-status');
    if (el) {
        el.textContent = normalized;
        el.style.display = 'inline-flex';
        el.dataset.quality = normalized.toLowerCase();
    }
    const mini = document.getElementById('phase54-mini-call-status');
    if (mini) mini.textContent = normalized;
}

function toggleCallPiP() {
    const overlay = document.getElementById('call-overlay');
    const mini = document.getElementById('phase54-mini-call');
    if (!overlay || !mini) return;
    CHAIN_WEBRTC.isPiP = !CHAIN_WEBRTC.isPiP;
    overlay.classList.toggle('phase54-call-pip-active', CHAIN_WEBRTC.isPiP);
    mini.style.display = CHAIN_WEBRTC.isPiP ? 'flex' : 'none';
}

/* ---- Exposed globals for inline onclick ---- */
function initiateCall(type) {
    const targetId = window.currentTargetProfileId || document.querySelector('[data-profile-id]')?.dataset.profileId;
    if (!targetId) return;
    wStartCall(targetId, window.currentThreadId, type);
}

function answerIncomingCall() {
    wAcceptCall();
}

function endCurrentCall() {
    wEndCall();
}

function toggleMute() {
    wToggleMute();
}

function toggleCamera() {
    wToggleCamera();
}

function toggleSpeaker() {
    wToggleSpeaker();
}

/* ---- Phase 41: Background Ringing Support ---- */
function startBackgroundRingtone() {
    stopRingtone();
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        function playBeepLoop() {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 440;
            gain.gain.value = 0.15;
            osc.start();
            setTimeout(() => { try { osc.stop(); } catch(e) {} }, 600);
        }
        playBeepLoop();
        CHAIN_WEBRTC.ringingInterval = setInterval(playBeepLoop, 1200);
        if (navigator.vibrate) {
            navigator.vibrate([400, 100, 400, 100, 400]);
        }
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Incoming Call', { body: 'Someone is calling you...', silent: true });
        }
    } catch (e) {}
}

/* ---- Phase 41: Quality Monitor ---- */
function wMonitorQuality() {
    const pc = CHAIN_WEBRTC.peerConnection;
    if (!pc) return;
    const state = pc.iceConnectionState;
    const el = document.getElementById('call-quality-status');
    if (el) {
        if (state === 'connected' || state === 'completed') {
            el.textContent = 'Excellent';
            el.style.color = '#22c55e';
        } else if (state === 'checking') {
            el.textContent = 'Connecting...';
            el.style.color = '#f59e0b';
        } else if (state === 'disconnected') {
            el.textContent = 'Reconnecting...';
            el.style.color = '#ef4444';
            showReconnectingOverlay();
        } else if (state === 'failed') {
            el.textContent = 'Failed';
            el.style.color = '#ef4444';
            showCallFailedBanner();
        } else {
            el.textContent = state;
            el.style.color = '#9ca3af';
        }
    }
    const connEl = document.getElementById('call-connection-state');
    if (connEl) connEl.textContent = state;
}

function showReconnectingOverlay() {
    let overlay = document.getElementById('reconnecting-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'reconnecting-overlay';
        overlay.style.cssText = 'position:absolute;inset:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;flex-direction:column;z-index:300;';
        overlay.innerHTML = '<div style="font-size:40px;margin-bottom:12px;"><i class="fas fa-sync-alt fa-spin"></i></div><p style="color:#fff;font-size:16px;">Reconnecting...</p>';
        const container = document.getElementById('call-overlay') || document.body;
        container.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    if (CHAIN_WEBRTC.callFailedTimer) clearTimeout(CHAIN_WEBRTC.callFailedTimer);
    CHAIN_WEBRTC.callFailedTimer = setTimeout(() => {
        if (CHAIN_WEBRTC.currentCallId) {
            showCallNotification('Call failed - no connection');
            wEndCall();
        }
    }, 15000);
}

function hideReconnectingOverlay() {
    const overlay = document.getElementById('reconnecting-overlay');
    if (overlay) overlay.style.display = 'none';
    if (CHAIN_WEBRTC.callFailedTimer) {
        clearTimeout(CHAIN_WEBRTC.callFailedTimer);
        CHAIN_WEBRTC.callFailedTimer = null;
    }
}

function showCallFailedBanner() {
    let banner = document.getElementById('call-failed-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'call-failed-banner';
        banner.style.cssText = 'position:absolute;top:60px;left:0;right:0;background:#ef4444;color:#fff;text-align:center;padding:8px 16px;font-size:13px;z-index:250;';
        banner.textContent = 'Call failed due to network issues';
        const container = document.getElementById('call-overlay') || document.body;
        container.appendChild(banner);
    }
    banner.style.display = 'block';
    setTimeout(() => { if (banner) banner.style.display = 'none'; }, 5000);
}

function showWeakNetworkBanner() {
    updateNetworkQuality('Weak');
    let banner = document.getElementById('weak-network-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'weak-network-banner';
        banner.style.cssText = 'position:absolute;top:60px;left:0;right:0;background:#f59e0b;color:#000;text-align:center;padding:6px 12px;font-size:12px;z-index:250;';
        banner.textContent = 'Weak network connection';
        const container = document.getElementById('call-overlay') || document.body;
        container.appendChild(banner);
    }
    banner.style.display = 'block';
    setTimeout(() => { if (banner) banner.style.display = 'none'; }, 8000);
}

/* ---- Phase 41: Notification Badge ---- */
function wUpdateMissedCallBadge() {
    fetch('/calls/api/missed-count')
        .then(r => r.json())
        .then(data => {
            const count = data.count || 0;
            const badge = document.getElementById('missed-call-badge');
            if (badge) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = count > 0 ? 'flex' : 'none';
            }
            const sidebarBadge = document.getElementById('sidebar-missed-call-badge');
            if (sidebarBadge) {
                sidebarBadge.textContent = count > 99 ? '99+' : count;
                sidebarBadge.style.display = count > 0 ? 'flex' : 'none';
            }
        })
        .catch(() => {});
}

/* ---- Phase 41: Premium Call Cards ---- */
function renderCallCard(log) {
    const escaped = v => String(v || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'})[c]);
    const statusIcon = log.status === 'ended' ? 'fa-check-circle' : log.status === 'missed' ? 'fa-times-circle' : log.status === 'rejected' ? 'fa-ban' : log.status === 'failed' ? 'fa-exclamation-triangle' : 'fa-clock';
    const statusColor = log.status === 'ended' ? '#22c55e' : log.status === 'missed' ? '#ef4444' : log.status === 'rejected' ? '#f59e0b' : log.status === 'failed' ? '#ef4444' : '#9ca3af';
    const dirIcon = log.direction === 'incoming' ? 'fa-arrow-down' : 'fa-arrow-up';
    const dur = log.duration_seconds ? Math.floor(log.duration_seconds / 60) + 'm ' + (log.duration_seconds % 60) + 's' : '';
    const date = log.created_at ? new Date(log.created_at).toLocaleString() : '';
    return `<div class="call-log-card phase41" data-call-id="${escaped(log.call_id)}" data-other-id="${escaped(log.other_profile_id)}">
        <div class="clc-avatar"><i class="fas fa-user"></i></div>
        <div class="clc-body">
            <div class="clc-line1">
                <strong>${escaped(log.other_display_name || log.other_username || 'Unknown')}</strong>
                <span class="clc-status" style="color:${statusColor}"><i class="fas ${statusIcon}"></i> ${log.status}</span>
            </div>
            <div class="clc-line2">
                <i class="fas ${dirIcon}" style="color:${statusColor}"></i>
                ${log.call_type} call ${dur ? '· ' + dur : ''}
                <span class="clc-date">${date}</span>
            </div>
        </div>
        <div class="clc-actions">
            <button class="clc-btn clc-callback" data-profile-id="${escaped(log.other_profile_id)}" onclick="wRedial(this)" title="Call back"><i class="fas fa-phone"></i></button>
            <button class="clc-btn clc-msg" data-profile-id="${escaped(log.other_profile_id)}" onclick="window.location.href='/messages/start/' + this.dataset.profileId" title="Message"><i class="fas fa-comment"></i></button>
            <button class="clc-btn clc-info" data-call-id="${escaped(log.call_id)}" onclick="showCallInfo(this)" title="Info"><i class="fas fa-info-circle"></i></button>
        </div>
    </div>`;
}

function wRedial(btn) {
    const profileId = btn.getAttribute('data-profile-id');
    if (profileId && window.wStartCall) {
        wStartCall(profileId, window.currentThreadId, 'audio');
    }
}

function showCallInfo(btn) {
    const callId = btn.getAttribute('data-call-id');
    if (!callId) return;
    fetch('/calls/api/' + callId)
        .then(r => r.json())
        .then(data => {
            if (data.ok && data.call) {
                const c = data.call;
                const dur = c.duration_seconds ? Math.floor(c.duration_seconds / 60) + 'm ' + (c.duration_seconds % 60) + 's' : 'N/A';
                alert('Call Details\n'
                    + 'Type: ' + (c.call_type || 'audio') + '\n'
                    + 'Status: ' + (c.status || 'ended') + '\n'
                    + 'Started: ' + (c.started_at ? new Date(c.started_at).toLocaleString() : 'N/A') + '\n'
                    + 'Duration: ' + dur + '\n'
                    + 'Mode: ' + (c.call_mode || 'N/A'));
            } else {
                alert('Call not found');
            }
        })
        .catch(() => alert('Failed to load call details'));
}

function wLoadCallHistory(containerId) {
    const container = document.getElementById(containerId || 'call-history-list');
    if (!container) return;
    container.innerHTML = '<p style="color:#9ca3af;text-align:center;padding:20px;">Loading calls...</p>';
    fetch('/calls/api/logs')
        .then(r => r.json())
        .then(data => {
            const logs = data.logs || [];
            if (!logs.length) {
                container.innerHTML = '<p style="color:#9ca3af;text-align:center;padding:20px;">No recent calls</p>';
                return;
            }
            container.innerHTML = logs.map(renderCallCard).join('');
        })
        .catch(() => {
            container.innerHTML = '<p style="color:#ef4444;text-align:center;padding:20px;">Failed to load call history</p>';
        });
}

/* ---- Phase 41: Participant Chips ---- */
function wRenderParticipantChips(participants, containerId) {
    const container = document.getElementById(containerId || 'participant-chips');
    if (!container) return;
    if (!participants || !participants.length) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = participants.map(p => {
        const name = p.display_name || p.username || 'User';
        const muted = p.muted ? '<i class="fas fa-microphone-slash" style="color:#ef4444;font-size:9px;"></i>' : '<i class="fas fa-microphone" style="color:#22c55e;font-size:9px;"></i>';
        const cam = p.camera_enabled === false ? '<i class="fas fa-video-slash" style="color:#ef4444;font-size:9px;"></i>' : '<i class="fas fa-video" style="color:#22c55e;font-size:9px;"></i>';
        const speaking = p.speaking ? ' style="border-color:#22c55e;"' : '';
        return `<div class="participant-chip"${speaking} title="${name}">
            <div class="pc-avatar">${name.charAt(0).toUpperCase()}</div>
            <div class="pc-info">
                <span class="pc-name">${name}</span>
                <span class="pc-states">${muted} ${cam}</span>
            </div>
        </div>`;
    }).join('');
}

/* ---- Phase 41: Mark Missed Seen ---- */
function wMarkMissedSeen() {
    fetch('/calls/api/mark-missed-seen', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({notification_type: 'missed_call'}) })
        .then(() => wUpdateMissedCallBadge())
        .catch(() => {});
}

/* ---- Phase 41: Bind extra socket events ---- */
function bindPhase41SocketEvents() {
    const s = CHAIN_WEBRTC.socket;
    if (!s) return;
    s.on('call:invite', (data) => {
        showCallNotification('Call invitation received');
        if (navigator.vibrate) navigator.vibrate(500);
    });
    s.on('call:participant-joined', (data) => {
        if (data.participants) wRenderParticipantChips(data.participants, 'participant-chips');
    });
    s.on('call:participant-left', (data) => {
        if (data.participants) wRenderParticipantChips(data.participants, 'participant-chips');
    });
    s.on('call:quality-warning', (data) => {
        showWeakNetworkBanner();
    });
    s.on('call:network-weak', () => {
        showWeakNetworkBanner();
    });
    s.on('call:missed', () => {
        wUpdateMissedCallBadge();
    });
    s.on('call:log-update', () => {
        wLoadCallHistory('call-history-list');
    });
    s.on('call:notification', (data) => {
        if (data.type === 'call_invite' || data.type === 'missed_call') {
            wUpdateMissedCallBadge();
        }
    });
    s.on('call:speaking_state', (data) => {
        const chips = document.querySelectorAll('.participant-chip');
        chips.forEach(chip => {
            if (chip.title === data.profile_id) {
                chip.style.borderColor = data.speaking ? '#22c55e' : 'transparent';
            }
        });
    });
    s.on('call:reconnecting', () => {
        showReconnectingOverlay();
    });
    s.on('call:reconnected', () => {
        hideReconnectingOverlay();
    });
    s.on('call:failed', () => {
        showCallFailedBanner();
    });
}

/* Override init to include Phase 41 */
const _origInit = wCallInit;
wCallInit = function(socket) {
    if (_origInit) _origInit(socket);
    bindPhase41SocketEvents();
    wUpdateMissedCallBadge();
};

/* Expose Phase 41 globals */
window.startBackgroundRingtone = startBackgroundRingtone;
window.wMonitorQuality = wMonitorQuality;
window.showReconnectingOverlay = showReconnectingOverlay;
window.hideReconnectingOverlay = hideReconnectingOverlay;
window.showWeakNetworkBanner = showWeakNetworkBanner;
window.wUpdateMissedCallBadge = wUpdateMissedCallBadge;
window.wLoadCallHistory = wLoadCallHistory;
window.wRenderParticipantChips = wRenderParticipantChips;
window.wRedial = wRedial;
window.showCallInfo = showCallInfo;
window.wMarkMissedSeen = wMarkMissedSeen;
window.renderCallCard = renderCallCard;
window.bindPhase41SocketEvents = bindPhase41SocketEvents;

/* ---- CALL + MESSAGE SCALE HARDENING ---- */

// Enhanced call state display with all states
function wUpdateCallState(state, reason) {
    const statusEl = document.getElementById('call-status-text');
    const states = {
        idle: { text: 'Ready', color: '#9ca3af' },
        ringing: { text: 'Ringing...', color: '#f59e0b' },
        connecting: { text: 'Connecting...', color: '#f59e0b' },
        connected: { text: 'Connected', color: '#22c55e' },
        reconnecting: { text: 'Reconnecting...', color: '#ef4444' },
        ended: { text: 'Call ended', color: '#9ca3af' },
        failed: { text: reason || 'Call failed', color: '#ef4444' },
        missed: { text: 'Missed call', color: '#ef4444' },
        busy: { text: 'Line busy', color: '#f59e0b' },
    };
    const s = states[state] || { text: state, color: '#9ca3af' };
    if (statusEl) {
        statusEl.textContent = s.text;
        statusEl.style.color = s.color;
    }
}

// Reconnecting overlay with retry count
function showReconnectingOverlayPhase50(retryCount) {
    let overlay = document.getElementById('reconnecting-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'reconnecting-overlay';
        overlay.style.cssText = 'position:absolute;inset:0;background:rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;flex-direction:column;z-index:300;';
        overlay.innerHTML = '<div style="font-size:40px;margin-bottom:12px;"><i class="fas fa-sync-alt fa-spin"></i></div>' +
            '<p style="color:#fff;font-size:16px;margin-bottom:8px;">Reconnecting...</p>' +
            '<p id="reconnect-retry-text" style="color:#9ca3af;font-size:13px;"></p>';
        const container = document.getElementById('call-overlay') || document.body;
        container.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    const retryEl = document.getElementById('reconnect-retry-text');
    if (retryEl) retryEl.textContent = 'Attempt ' + (retryCount || 1);
    if (CHAIN_WEBRTC.callFailedTimer) clearTimeout(CHAIN_WEBRTC.callFailedTimer);
    CHAIN_WEBRTC.callFailedTimer = setTimeout(function() {
        if (CHAIN_WEBRTC.currentCallId) {
            wUpdateCallState('failed', 'Connection lost');
            if (CHAIN_WEBRTC.currentTargetId) {
                CHAIN_WEBRTC.socket.emit('call:failed', {
                    call_id: CHAIN_WEBRTC.currentCallId,
                    target_id: CHAIN_WEBRTC.currentTargetId,
                    reason: 'timeout'
                });
            }
            wEndCall();
        }
    }, 30000);
}

// Call failed reason display
function showCallFailedReason(reason) {
    let banner = document.getElementById('call-failed-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'call-failed-banner';
        banner.style.cssText = 'position:absolute;top:60px;left:0;right:0;background:#ef4444;color:#fff;text-align:center;padding:8px 16px;font-size:13px;z-index:250;';
        const container = document.getElementById('call-overlay') || document.body;
        container.appendChild(banner);
    }
    const messages = {
        'network_error': 'Call failed due to network error',
        'timeout': 'Call failed - no response',
        'declined': 'Call was declined',
        'busy': 'User is busy',
        'ice_failed': 'Connection failed - ICE negotiation failed',
        'dtls_failed': 'Connection failed - DTLS error',
        'server_error': 'Call failed due to server error',
    };
    banner.textContent = messages[reason] || 'Call failed: ' + (reason || 'unknown error');
    banner.style.display = 'block';
    setTimeout(function() { if (banner) banner.style.display = 'none'; }, 8000);
}

// Incoming call modal that appears above all pages
function showIncomingCallModal(data) {
    let modal = document.getElementById('incoming-call-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'incoming-call-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;z-index:9999;';
        modal.innerHTML = '<div style="background:#1a1a2e;border-radius:16px;padding:32px;text-align:center;max-width:360px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);">' +
            '<div style="font-size:64px;margin-bottom:16px;color:#22c55e;"><i class="fas fa-phone"></i></div>' +
            '<h2 style="color:#fff;margin:0 0 8px 0;font-size:20px;">Incoming Call</h2>' +
            '<p id="incoming-caller-name" style="color:#9ca3af;margin:0 0 24px 0;font-size:15px;">Someone is calling...</p>' +
            '<p id="incoming-call-type" style="color:#6b7280;margin:0 0 24px 0;font-size:13px;">Audio call</p>' +
            '<div style="display:flex;gap:16px;justify-content:center;">' +
            '<button id="incoming-decline-btn" style="background:#ef4444;color:#fff;border:none;border-radius:50%;width:56px;height:56px;font-size:24px;cursor:pointer;"><i class="fas fa-phone-slash"></i></button>' +
            '<button id="incoming-accept-btn" style="background:#22c55e;color:#fff;border:none;border-radius:50%;width:56px;height:56px;font-size:24px;cursor:pointer;"><i class="fas fa-phone"></i></button>' +
            '</div></div>';
        document.body.appendChild(modal);

        document.getElementById('incoming-accept-btn').addEventListener('click', function() {
            modal.style.display = 'none';
            if (window.wAcceptCall) wAcceptCall();
        });
        document.getElementById('incoming-decline-btn').addEventListener('click', function() {
            modal.style.display = 'none';
            if (window.wRejectCall) wRejectCall();
        });
    }
    modal.style.display = 'flex';
    const nameEl = document.getElementById('incoming-caller-name');
    if (nameEl) nameEl.textContent = data.caller_name || 'Someone';
    const typeEl = document.getElementById('incoming-call-type');
    if (typeEl) typeEl.textContent = (data.call_type || 'audio') + ' call';
}

// Override incoming call handler to use modal
const _origHandleIncoming = handleIncomingCall;
handleIncomingCall = function(data) {
    if (CHAIN_WEBRTC.currentCallId) {
        CHAIN_WEBRTC.socket.emit('call:busy', { call_id: data.call_id });
        return;
    }
    stopCallTimeoutTimer();
    CHAIN_WEBRTC.currentCallId = data.call_id;
    CHAIN_WEBRTC.currentTargetId = data.caller_id;
    CHAIN_WEBRTC.currentCallType = data.call_type || 'audio';
    showIncomingCallModal(data);
    startRingtone();
    CHAIN_WEBRTC.socket.emit('call:ringing', {
        call_id: data.call_id,
        target_id: data.caller_id
    });
};

// Override cleanup to hide modal
const _origCleanup = cleanupCall;
cleanupCall = function() {
    const modal = document.getElementById('incoming-call-modal');
    if (modal) modal.style.display = 'none';
    hideReconnectingOverlay();
    if (_origCleanup) _origCleanup();
};

// Override handleRemoteFailed to show reason
const _origRemoteFailed = handleRemoteFailed;
handleRemoteFailed = function(data) {
    showCallFailedReason(data.reason);
    if (_origRemoteFailed) _origRemoteFailed(data);
};

// Override handleRemoteReconnecting to show retry count
const _origRemoteReconnecting = handleRemoteReconnecting;
handleRemoteReconnecting = function(data) {
    const retryCount = data.retry_count || 1;
    showReconnectingOverlayPhase50(retryCount);
    if (_origRemoteReconnecting) _origRemoteReconnecting(data);
};

/* ---- CALL + MESSAGE SCALE HARDENING Exports ---- */
window.wUpdateCallState = wUpdateCallState;
window.showReconnectingOverlayPhase50 = showReconnectingOverlayPhase50;
window.showCallFailedReason = showCallFailedReason;
window.showIncomingCallModal = showIncomingCallModal;

/* ---- Export for Socket.IO init ---- */
window.wCallInit = wCallInit;
window.wStartCall = wStartCall;
window.wAcceptCall = wAcceptCall;
window.wRejectCall = wRejectCall;
window.wEndCall = wEndCall;
window.wToggleMute = wToggleMute;
window.wToggleCamera = wToggleCamera;
window.wToggleSpeaker = wToggleSpeaker;
window.initiateCall = initiateCall;
window.answerIncomingCall = answerIncomingCall;
window.endCurrentCall = endCurrentCall;
window.toggleMute = toggleMute;
window.toggleCamera = toggleCamera;
window.toggleSpeaker = toggleSpeaker;
window.startRingtone = startRingtone;
window.startRingbackTone = startRingbackTone;
window.playTestSound = playTestSound;
window.stopRingtone = stopRingtone;
window.startCallTimeoutTimer = startCallTimeoutTimer;
window.stopCallTimeoutTimer = stopCallTimeoutTimer;
window.wRestartICE = wRestartICE;
window.wSwitchCamera = wSwitchCamera;

/* ---- Phase 2: Screen Share ---- */
let _screenShareStream = null;
let _screenShareActive = false;

async function wToggleScreenShare() {
    if (_screenShareActive) {
        return stopScreenShare();
    }
    try {
        const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        _screenShareStream = stream;
        _screenShareActive = true;
        const pc = CHAIN_WEBRTC.peerConnection;
        if (pc) {
            const videoTrack = stream.getVideoTracks()[0];
            const sender = pc.getSenders().find(s => s.track && s.track.kind === 'video');
            if (sender) {
                await sender.replaceTrack(videoTrack);
            } else {
                pc.addTrack(videoTrack, stream);
            }
        }
        stream.getVideoTracks()[0].onended = function() {
            stopScreenShare();
        };
        const btn = document.getElementById('call-screen-share-btn');
        if (btn) {
            btn.dataset.screenSharing = 'true';
            btn.classList.add('active');
        }
        CHAIN_WEBRTC.socket.emit('call:screen-share', {
            call_id: CHAIN_WEBRTC.currentCallId,
            target_id: CHAIN_WEBRTC.currentTargetId,
            active: true
        });
    } catch (e) {
        if (e.name !== 'NotAllowedError' && e.name !== 'AbortError') {
            console.warn('[wCall] Screen share error:', e);
        }
    }
}

async function stopScreenShare() {
    if (_screenShareStream) {
        _screenShareStream.getTracks().forEach(t => t.stop());
        _screenShareStream = null;
    }
    _screenShareActive = false;
    const btn = document.getElementById('call-screen-share-btn');
    if (btn) {
        btn.dataset.screenSharing = 'false';
        btn.classList.remove('active');
    }
    if (CHAIN_WEBRTC.localStream) {
        const pc = CHAIN_WEBRTC.peerConnection;
        if (pc) {
            const videoTrack = CHAIN_WEBRTC.localStream.getVideoTracks()[0];
            const sender = pc.getSenders().find(s => s.track && s.track.kind === 'video');
            if (sender && videoTrack) {
                try { await sender.replaceTrack(videoTrack); } catch(e) {}
            }
        }
    }
    CHAIN_WEBRTC.socket.emit('call:screen-share', {
        call_id: CHAIN_WEBRTC.currentCallId,
        target_id: CHAIN_WEBRTC.currentTargetId,
        active: false
    });
}

/* ---- Phase 2: Swipe-to-Answer Gesture ---- */
let _swipeGestureActive = false;

function initSwipeToAnswer() {
    const track = document.getElementById('call-swipe-track');
    const thumb = document.getElementById('swipe-thumb');
    const container = document.getElementById('call-swipe-container');
    if (!track || !thumb) return;

    const trackHeight = track.offsetHeight || 120;
    const thumbHeight = 52;
    const maxTravel = trackHeight - thumbHeight - 8;
    let startY = 0;
    let currentOffset = 0;

    function onStart(y) {
        if (_swipeGestureActive) return;
        startY = y;
        currentOffset = 0;
        _swipeGestureActive = true;
        thumb.classList.add('active');
    }

    function onMove(y) {
        if (!_swipeGestureActive) return;
        const delta = y - startY;
        currentOffset = Math.max(0, Math.min(delta, maxTravel));
        thumb.style.bottom = (4 + currentOffset) + 'px';
        const progress = currentOffset / maxTravel;
        if (progress > 0.6) {
            thumb.style.background = 'linear-gradient(135deg, #22c55e, #15803d)';
        } else {
            thumb.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
        }
    }

    function onEnd() {
        if (!_swipeGestureActive) return;
        _swipeGestureActive = false;
        thumb.classList.remove('active');
        if (currentOffset >= maxTravel * 0.75) {
            if (window.wAcceptCall) wAcceptCall();
        }
        thumb.style.bottom = '4px';
        currentOffset = 0;
    }

    thumb.addEventListener('touchstart', function(e) {
        const touch = e.touches[0];
        onStart(touch.clientY);
    }, { passive: true });

    thumb.addEventListener('touchmove', function(e) {
        const touch = e.touches[0];
        onMove(touch.clientY);
    }, { passive: true });

    thumb.addEventListener('touchend', onEnd, { passive: true });
    thumb.addEventListener('touchcancel', onEnd, { passive: true });

    thumb.addEventListener('mousedown', function(e) { onStart(e.clientY); });
    document.addEventListener('mousemove', function(e) {
        if (_swipeGestureActive) onMove(e.clientY);
    });
    document.addEventListener('mouseup', function() {
        if (_swipeGestureActive) onEnd();
    });
}

/* ---- Phase 2: Quality Display Integration ---- */
function updateQualityDisplay(quality) {
    const badge = document.getElementById('call-quality-badge');
    const statusEl = document.getElementById('call-quality-status');
    const dot = document.getElementById('quality-dot');
    if (!badge || !statusEl || !dot) return;
    const qualities = {
        'Excellent': { color: '#22c55e', cls: 'excellent' },
        'Good': { color: '#22c55e', cls: 'good' },
        'Weak': { color: '#f59e0b', cls: 'weak' },
        'Poor': { color: '#ef4444', cls: 'poor' },
        'Reconnecting': { color: '#f59e0b', cls: 'reconnecting' },
        'Failed': { color: '#ef4444', cls: 'failed' },
    };
    const q = qualities[quality] || qualities['Good'];
    dot.className = 'quality-dot ' + q.cls;
    statusEl.textContent = quality;
}

const _origUpdateQuality = updateNetworkQuality;
updateNetworkQuality = function(status) {
    if (_origUpdateQuality) _origUpdateQuality(status);
    updateQualityDisplay(status);
};

/* ---- Phase 2: Enhanced Incoming Call UI ---- */
const _origShowIncomingUI = showIncomingCallUI;
showIncomingCallUI = function(data) {
    const incoming = document.getElementById('call-overlay-incoming');
    if (incoming) {
        incoming.style.display = 'flex';
        const nameEl = document.getElementById('caller-name-display');
        if (nameEl) nameEl.textContent = data.caller_name || 'Incoming Call';
        const typeEl = document.getElementById('call-type-display');
        if (typeEl) typeEl.textContent = (data.call_type || 'audio') + ' call';
        const rejectBtn = incoming.querySelector('[data-call-reject]');
        if (rejectBtn) rejectBtn.dataset.callId = data.call_id || '';
        const avatarEl = document.getElementById('caller-avatar-lg');
        if (avatarEl && data.caller_avatar) {
            avatarEl.innerHTML = '<img src="' + data.caller_avatar + '" alt="">';
        } else if (avatarEl) {
            avatarEl.innerHTML = '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
        }
        const outgoing = document.getElementById('call-overlay-outgoing');
        if (outgoing) outgoing.style.display = 'none';
        const connected = document.getElementById('call-overlay-connected');
        if (connected) connected.style.display = 'none';
        const reconnecting = document.getElementById('call-overlay-reconnecting');
        if (reconnecting) reconnecting.style.display = 'none';
        setTimeout(initSwipeToAnswer, 100);
    } else if (_origShowIncomingUI) {
        _origShowIncomingUI(data);
    }
};

/* ---- Phase 2: Enhanced Active Call UI ---- */
const _origShowActiveUI = showActiveCallUI;
showActiveCallUI = function() {
    const incoming = document.getElementById('call-overlay-incoming');
    if (incoming) incoming.style.display = 'none';
    const outgoing = document.getElementById('call-overlay-outgoing');
    if (outgoing) outgoing.style.display = 'none';
    const reconnecting = document.getElementById('call-overlay-reconnecting');
    if (reconnecting) reconnecting.style.display = 'none';
    const connected = document.getElementById('call-overlay-connected');
    if (connected) {
        connected.style.display = 'flex';
        const timerEl = document.getElementById('call-timer-connected');
        if (timerEl) {
            timerEl.style.display = 'block';
            const m = String(Math.floor(CHAIN_WEBRTC.callSeconds / 60)).padStart(2, '0');
            const s = String(CHAIN_WEBRTC.callSeconds % 60).padStart(2, '0');
            timerEl.textContent = m + ':' + s;
        }
        const muteBtn = document.getElementById('call-mute-btn');
        if (muteBtn) muteBtn.dataset.muted = CHAIN_WEBRTC.isMuted ? 'true' : 'false';
        const cameraBtn = document.getElementById('call-camera-btn');
        if (cameraBtn) cameraBtn.dataset.cameraEnabled = CHAIN_WEBRTC.isCameraOn ? 'true' : 'false';
        const speakerBtn = document.getElementById('call-speaker-btn');
        if (speakerBtn) speakerBtn.dataset.speakerEnabled = CHAIN_WEBRTC.isSpeakerOn ? 'true' : 'false';
    }
    if (_origShowActiveUI) _origShowActiveUI();
    updateQualityDisplay(CHAIN_WEBRTC.networkQuality || 'Good');
};

/* ---- Phase 2: Enhanced Hide Call UI ---- */
const _origHideUI = hideCallUI;
hideCallUI = function() {
    const incoming = document.getElementById('call-overlay-incoming');
    if (incoming) incoming.style.display = 'none';
    const outgoing = document.getElementById('call-overlay-outgoing');
    if (outgoing) outgoing.style.display = 'none';
    const connected = document.getElementById('call-overlay-connected');
    if (connected) connected.style.display = 'none';
    const reconnecting = document.getElementById('call-overlay-reconnecting');
    if (reconnecting) reconnecting.style.display = 'none';
    const modal = document.getElementById('incoming-call-modal');
    if (modal) modal.style.display = 'none';
    const mini = document.getElementById('phase54-mini-call');
    if (mini) mini.style.display = 'none';
    CHAIN_WEBRTC.isPiP = false;
    const callScreen = document.getElementById('callScreen');
    if (callScreen) callScreen.classList.remove('active');
};

/* ---- Phase 2: Enhanced Show Outgoing UI ---- */
function showOutgoingCallUI(data) {
    const outgoing = document.getElementById('call-overlay-outgoing');
    if (!outgoing) return;
    outgoing.style.display = 'flex';
    const incoming = document.getElementById('call-overlay-incoming');
    if (incoming) incoming.style.display = 'none';
    const connected = document.getElementById('call-overlay-connected');
    if (connected) connected.style.display = 'none';
    const reconnecting = document.getElementById('call-overlay-reconnecting');
    if (reconnecting) reconnecting.style.display = 'none';
    const nameEl = document.getElementById('outgoing-caller-name');
    if (nameEl) nameEl.textContent = data.target_name || 'Calling...';
    const statusEl = document.getElementById('call-status-text');
    if (statusEl) statusEl.textContent = 'Ringing...';
    const timerEl = document.getElementById('call-timer');
    if (timerEl) timerEl.style.display = 'none';
    const avatarEl = document.getElementById('caller-avatar-lg-outgoing');
    if (avatarEl && data.target_avatar) {
        avatarEl.innerHTML = '<img src="' + data.target_avatar + '" alt="">';
    } else if (avatarEl) {
        avatarEl.innerHTML = '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>';
    }
}

/* ---- Phase 2: Reconnecting overlay for new structure ---- */
const _origShowReconnecting = showReconnectingOverlay;
showReconnectingOverlay = function() {
    const reconnecting = document.getElementById('call-overlay-reconnecting');
    if (reconnecting) {
        reconnecting.style.display = 'flex';
        const incoming = document.getElementById('call-overlay-incoming');
        if (incoming) incoming.style.display = 'none';
        const outgoing = document.getElementById('call-overlay-outgoing');
        if (outgoing) outgoing.style.display = 'none';
    }
    if (_origShowReconnecting) _origShowReconnecting();
};

const _origHideReconnecting = hideReconnectingOverlay;
hideReconnectingOverlay = function() {
    const reconnecting = document.getElementById('call-overlay-reconnecting');
    if (reconnecting) reconnecting.style.display = 'none';
    if (_origHideReconnecting) _origHideReconnecting();
};

/* ---- Phase 2: Exports ---- */
window.wToggleScreenShare = wToggleScreenShare;
window.stopScreenShare = stopScreenShare;
window.initSwipeToAnswer = initSwipeToAnswer;
window.showOutgoingCallUI = showOutgoingCallUI;
window.updateQualityDisplay = updateQualityDisplay;

/* ---- Phase 2: Init sound settings on load ---- */
(function() {
    if (localStorage.getItem('chain_call_sound_enabled') === null) {
        localStorage.setItem('chain_call_sound_enabled', 'true');
    }
})();
