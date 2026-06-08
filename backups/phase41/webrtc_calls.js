/* ============================================================
   CHAIN Phase 40 — Premium WebRTC Calling Engine
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
}

/* ---- Incoming Call ---- */
function handleIncomingCall(data) {
    if (CHAIN_WEBRTC.currentCallId) {
        CHAIN_WEBRTC.socket.emit('call:busy', { call_id: data.call_id });
        return;
    }
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
            sdp: answer.sdp
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
}

function handleRemoteReconnected(data) {
    const el = document.getElementById('network-warning');
    if (el) el.style.display = 'none';
}

function handleRemoteFailed(data) {
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
                candidate: event.candidate
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
            CHAIN_WEBRTC.socket.emit('call:reconnecting', {
                call_id: CHAIN_WEBRTC.currentCallId,
                target_id: CHAIN_WEBRTC.currentTargetId
            });
            const warn = document.getElementById('network-warning');
            if (warn) warn.style.display = 'block';
        } else if (state === 'connected') {
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

/* ---- Start Call ---- */
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
            call_type: CHAIN_WEBRTC.currentCallType
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

/* ---- Ringtone ---- */
function startRingtone() {
    stopRingtone();
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        function playBeep() {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 440;
            gain.gain.value = 0.1;
            osc.start();
            setTimeout(() => osc.stop(), 400);
        }
        playBeep();
        CHAIN_WEBRTC.ringingInterval = setInterval(playBeep, 1500);
        if (navigator.vibrate) navigator.vibrate([400, 100, 400]);
    } catch (e) {}
}

function stopRingtone() {
    if (CHAIN_WEBRTC.ringingInterval) {
        clearInterval(CHAIN_WEBRTC.ringingInterval);
        CHAIN_WEBRTC.ringingInterval = null;
    }
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
    const callScreen = document.getElementById('callScreen');
    if (callScreen) callScreen.classList.remove('active');
}

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
