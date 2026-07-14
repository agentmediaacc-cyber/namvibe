(function () {
  if (window.NamVibeCallsPro) return;

  const CALL_TIMEOUT_SECONDS = 15;
  const RECONNECT_TIMEOUT_SECONDS = 20;
  const state = {
    call: null,
    localStream: null,
    remoteStream: null,
    peerConnection: null,
    pendingCandidates: [],
    ringingTimer: null,
    ringingAudio: null,
    reconnectTimer: null,
    timeoutTimer: null,
    callTimer: null,
    callDuration: 0,
    muted: false,
    cameraEnabled: true,
    speakerEnabled: false,
    isIncoming: false,
    isRinging: false,
    reconnecting: false,
  };

  function $(id) { return document.getElementById(id); }
  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }

  function uuid() {
    return crypto.randomUUID ? crypto.randomUUID() : "call_" + Date.now() + "_" + Math.random().toString(16).slice(2);
  }

  function csrfHeaders() {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || window.chainCsrfToken?.();
    return token ? { "X-CSRFToken": token } : {};
  }

  function formatDuration(secs) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function showToast(message) {
    let toast = $("call-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "call-toast";
      toast.style.cssText = "position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:99999;padding:12px 18px;border-radius:999px;background:#111827;color:#fff;font-size:14px;box-shadow:0 12px 30px rgba(0,0,0,.28);max-width:90vw;text-align:center";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { toast.hidden = true; }, 3500);
  }

  function showOverlay(id) {
    qsa(".call-overlay").forEach(el => el.style.display = "none");
    const el = $(id);
    if (el) el.style.display = "flex";
  }

  async function getIceConfig() {
    try {
      const res = await fetch("/calls/api/ice-servers", { credentials: "same-origin" });
      return await res.json();
    } catch (_) {
      return { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
    }
  }

  async function startCall(targetProfileId, callType, threadId) {
    if (state.call) {
      showToast("You are already in a call");
      return;
    }
    state.isIncoming = false;

    try {
      state.localStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: callType === "video",
      });
    } catch (err) {
      showToast("Microphone" + (callType === "video" ? "/camera" : "") + " access denied");
      return;
    }

    showOverlay("call-overlay-outgoing");
    const localVideo = $("call-local-video");
    if (localVideo) localVideo.srcObject = state.localStream;
    startRinging("outgoing");
    startTimeoutTimer();

    try {
      const res = await fetch("/calls/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeaders() },
        credentials: "same-origin",
        body: JSON.stringify({ receiver_id: targetProfileId, thread_id: threadId, call_type: callType }),
      });
      const json = await res.json();
      if (!json.ok) {
        stopRinging();
        clearTimeoutTimer();
        cleanupMedia();
        if (json.status === "busy") {
          showToast("User is busy");
          showOverlay(null);
          return;
        }
        showToast(json.error || "Call failed");
        showOverlay(null);
        return;
      }
      state.call = json.call;
      const socket = window.socket || window.io?.();
      if (socket) {
        socket.emit("call:start", {
          call_id: state.call.id,
          target_id: targetProfileId,
          call_type: callType,
        });
      }
    } catch (_) {
      stopRinging();
      clearTimeoutTimer();
      cleanupMedia();
      showToast("Could not start call");
      showOverlay(null);
    }
  }

  function acceptCall(callId, callerProfileId, callType) {
    if (state.call) {
      showToast("You are already in a call");
      return;
    }
    state.isIncoming = true;
    state.call = { id: callId };

    stopRinging();
    clearTimeoutTimer();

    (async () => {
      try {
        state.localStream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: callType === "video",
        });
      } catch (_) {
        showToast("Microphone access denied");
        return;
      }

      showOverlay("call-overlay-connected");
      const localVideo = $("call-local-video");
      if (localVideo) localVideo.srcObject = state.localStream;

      try {
        const res = await fetch("/calls/api/" + callId + "/accept", {
          method: "POST",
          headers: csrfHeaders(),
          credentials: "same-origin",
        });
        const json = await res.json();
        if (json.ok) {
          state.call = json.call;
          startCallTimer();
          const socket = window.socket || window.io?.();
          if (socket) {
            socket.emit("call:accept", { call_id: callId });
          }
        }
      } catch (_) {
        showToast("Could not accept call");
      }
    })();
  }

  function rejectCall(callId) {
    stopRinging();
    clearTimeoutTimer();
    showOverlay(null);
    fetch("/calls/api/" + callId + "/reject", {
      method: "POST", headers: csrfHeaders(), credentials: "same-origin",
    }).catch(function () {});
    const socket = window.socket || window.io?.();
    if (socket) socket.emit("call:reject", { call_id: callId });
  }

  function cancelCall() {
    if (!state.call) return;
    stopRinging();
    clearTimeoutTimer();
    const callId = state.call.id;
    cleanupCall();
    showOverlay(null);
    fetch("/calls/api/" + callId + "/cancel", {
      method: "POST", headers: csrfHeaders(), credentials: "same-origin",
    }).catch(function () {});
    const socket = window.socket || window.io?.();
    if (socket) socket.emit("call:cancel", { call_id: callId });
  }

  function endCall() {
    if (!state.call) return;
    stopRinging();
    clearTimeoutTimer();
    stopCallTimer();
    const callId = state.call.id;
    cleanupCall();
    showOverlay(null);
    fetch("/calls/api/" + callId + "/end", {
      method: "POST", headers: csrfHeaders(), credentials: "same-origin",
    }).catch(function () {});
    const socket = window.socket || window.io?.();
    if (socket) socket.emit("call:end", { call_id: callId, reason: "hung_up" });
  }

  function toggleMute() {
    if (!state.localStream) return;
    state.muted = !state.muted;
    state.localStream.getAudioTracks().forEach(function (track) { track.enabled = !state.muted; });
    const btn = $("call-mute-btn");
    if (btn) btn.dataset.muted = String(state.muted);
    const socket = window.socket || window.io?.();
    if (socket && state.call) {
      socket.emit("call:mute-state", { call_id: state.call.id, muted: state.muted });
    }
  }

  function toggleCamera() {
    if (!state.localStream) return;
    state.cameraEnabled = !state.cameraEnabled;
    state.localStream.getVideoTracks().forEach(function (track) { track.enabled = state.cameraEnabled; });
    const btn = $("call-camera-btn");
    if (btn) btn.dataset.cameraEnabled = String(state.cameraEnabled);
    const socket = window.socket || window.io?.();
    if (socket && state.call) {
      socket.emit("call:camera-state", { call_id: state.call.id, camera_enabled: state.cameraEnabled });
    }
  }

  function toggleSpeaker() {
    state.speakerEnabled = !state.speakerEnabled;
    const btn = $("call-speaker-btn");
    if (btn) btn.dataset.speakerEnabled = String(state.speakerEnabled);
    const remoteAudio = $("call-remote-audio");
    if (remoteAudio && typeof remoteAudio.setSinkId === "function") {
      remoteAudio.setSinkId(state.speakerEnabled ? "speaker" : "default").catch(function () {
        showToast("Speaker mode not supported on this device");
      });
    } else {
      showToast("Speaker mode not supported on this device");
    }
  }

  async function switchCamera() {
    if (!state.localStream) return;
    const videoTrack = state.localStream.getVideoTracks()[0];
    if (!videoTrack) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(function (d) { return d.kind === "videoinput"; });
      if (videoDevices.length < 2) {
        showToast("No camera to switch to");
        return;
      }
      const facingMode = videoTrack.getSettings().facingMode === "user" ? "environment" : "user";
      const newStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: facingMode },
      });
      const newTrack = newStream.getVideoTracks()[0];
      state.localStream.removeTrack(videoTrack);
      state.localStream.addTrack(newTrack);
      const sender = state.peerConnection?.getSenders()?.find(function (s) {
        return s.track?.kind === "video";
      });
      if (sender) sender.replaceTrack(newTrack).catch(function () {});
      const localVideo = $("call-local-video");
      if (localVideo) localVideo.srcObject = state.localStream;
      videoTrack.stop();
      const socket = window.socket || window.io?.();
      if (socket && state.call) {
        socket.emit("call:switch-camera", { call_id: state.call.id, facingMode: facingMode });
      }
    } catch (_) {
      showToast("Could not switch camera");
    }
  }

  function _namvibeRingtoneUrl() {
    var cached = sessionStorage.getItem("chain_ringtone_url");
    if (cached) return Promise.resolve(cached);
    return fetch("/profile/api/ringtone")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok && d.ringtone_url) {
          sessionStorage.setItem("chain_ringtone_url", d.ringtone_url);
          sessionStorage.setItem("chain_ringtone_name", d.ringtone);
          return d.ringtone_url;
        }
        return null;
      })
      .catch(function() { return null; });
  }

  function _namvibeSynthRing(type) {
    try {
      var audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
      var osc = audioCtx.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(type === "outgoing" ? 440 : 550, audioCtx.currentTime);
      var gain = audioCtx.createGain();
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      var interval = setInterval(function () {
        gain.gain.setValueAtTime(gain.gain.value > 0 ? 0 : 0.3, audioCtx.currentTime);
      }, 500);
      state.ringingTimer = { ctx: audioCtx, osc: osc, interval: interval };
    } catch (_) {
      var toast = $("call-ringtone-unlock");
      if (toast) toast.hidden = false;
    }
  }

  function startRinging(type) {
    state.isRinging = true;
    if (type === "outgoing") { _namvibeSynthRing("outgoing"); return; }
    _namvibeRingtoneUrl().then(function(url) {
      if (!url) { _namvibeSynthRing("incoming"); return; }
      var audio = new Audio(url);
      audio.loop = true;
      audio.volume = 0.4;
      audio.play().catch(function() { _namvibeSynthRing("incoming"); });
      state.ringingAudio = audio;
    });
  }

  function stopRinging() {
    state.isRinging = false;
    if (state.ringingTimer) {
      clearInterval(state.ringingTimer.interval);
      try { state.ringingTimer.osc.stop(); } catch (_) {}
      try { state.ringingTimer.ctx.close(); } catch (_) {}
      state.ringingTimer = null;
    }
    if (state.ringingAudio) {
      try { state.ringingAudio.pause(); state.ringingAudio.currentTime = 0; } catch (_) {}
      state.ringingAudio = null;
    }
    var toast = $("call-ringtone-unlock");
    if (toast) toast.hidden = true;
  }

  function startTimeoutTimer() {
    clearTimeoutTimer();
    state.timeoutTimer = setTimeout(function () {
      if (state.call && !state.call.accepted_at) {
        showToast("Call timed out");
        stopRinging();
        cleanupCall();
        showOverlay(null);
        const socket = window.socket || window.io?.();
        if (socket) socket.emit("call:end", { call_id: state.call.id, reason: "timeout" });
      }
    }, CALL_TIMEOUT_SECONDS * 1000);
  }

  function clearTimeoutTimer() {
    if (state.timeoutTimer) { clearTimeout(state.timeoutTimer); state.timeoutTimer = null; }
  }

  function startCallTimer() {
    state.callDuration = 0;
    state.callTimer = setInterval(function () {
      state.callDuration++;
      var el = $("call-timer");
      if (el) el.textContent = formatDuration(state.callDuration);
    }, 1000);
  }

  function stopCallTimer() {
    if (state.callTimer) { clearInterval(state.callTimer); state.callTimer = null; }
  }

  function cleanupMedia() {
    if (state.localStream) {
      state.localStream.getTracks().forEach(function (t) { t.stop(); });
      state.localStream = null;
    }
    if (state.remoteStream) {
      state.remoteStream.getTracks().forEach(function (t) { t.stop(); });
      state.remoteStream = null;
    }
    if (state.peerConnection) {
      state.peerConnection.close();
      state.peerConnection = null;
    }
    state.pendingCandidates = [];
  }

  function cleanupCall() {
    stopRinging();
    clearTimeoutTimer();
    stopCallTimer();
    cleanupMedia();
    if (state.reconnectTimer) { clearTimeout(state.reconnectTimer); state.reconnectTimer = null; }
    state.call = null;
    state.muted = false;
    state.cameraEnabled = true;
    state.speakerEnabled = false;
    state.reconnecting = false;
    qsa(".call-overlay").forEach(function (el) { el.style.display = "none"; });
  }

  function wireSocket() {
    var socket = window.socket || window.io?.();
    if (!socket) return;
    window.socket = socket;

    socket.on("call:incoming", function (data) {
      if (state.call) {
        showToast("User is busy");
        socket.emit("call:busy", { call_id: data.call_id });
        return;
      }
      state.isIncoming = true;
      state.call = { id: data.call_id, caller_profile_id: data.caller_profile_id, call_type: data.call_type };
      var overlay = $("call-overlay-incoming");
      if (overlay) {
        overlay.querySelector("[data-caller-name]").textContent = data.caller_display_name || "Incoming Call";
        overlay.querySelector("[data-call-type]").textContent = data.call_type === "video" ? "Video Call" : "Audio Call";
        overlay.style.display = "flex";
      }
      startRinging("incoming");
      startTimeoutTimer();
    });

    socket.on("call:ringing", function (data) {
    });

    socket.on("call:accepted", function (data) {
      stopRinging();
      clearTimeoutTimer();
      showOverlay("call-overlay-connected");
      startCallTimer();
      state.call.accepted_at = data.accepted_at;
    });

    socket.on("call:rejected", function (data) {
      stopRinging();
      clearTimeoutTimer();
      showToast("Call rejected");
      cleanupCall();
    });

    socket.on("call:cancelled", function (data) {
      stopRinging();
      clearTimeoutTimer();
      showToast("Call cancelled");
      cleanupCall();
    });

    socket.on("call:ended", function (data) {
      showToast("Call ended");
      cleanupCall();
    });

    socket.on("call:missed", function (data) {
      stopRinging();
      clearTimeoutTimer();
      showToast("Missed call");
      cleanupCall();
    });

    socket.on("call:busy", function (data) {
      stopRinging();
      clearTimeoutTimer();
      showToast("User is busy");
      cleanupCall();
    });

    socket.on("call:failed", function (data) {
      stopRinging();
      clearTimeoutTimer();
      showToast("Call failed");
      cleanupCall();
    });

    socket.on("call:offer", function (data) { });
    socket.on("call:answer", function (data) { });
    socket.on("call:ice-candidate", function (data) { });

    socket.on("call:mute-state", function (data) {
      var indicator = $("call-remote-mute");
      if (indicator) indicator.hidden = !data.muted;
    });

    socket.on("call:camera-state", function (data) {
      var indicator = $("call-remote-camera");
      if (indicator) indicator.hidden = data.camera_enabled;
    });

    socket.on("call:reconnecting", function () {
      state.reconnecting = true;
      showOverlay("call-overlay-reconnecting");
      if (state.reconnectTimer) clearTimeout(state.reconnectTimer);
      state.reconnectTimer = setTimeout(function () {
        state.reconnecting = false;
        showToast("Reconnection failed");
        cleanupCall();
      }, RECONNECT_TIMEOUT_SECONDS * 1000);
    });

    socket.on("call:reconnected", function () {
      state.reconnecting = false;
      if (state.reconnectTimer) { clearTimeout(state.reconnectTimer); state.reconnectTimer = null; }
      if (state.call && state.call.accepted_at) {
        showOverlay("call-overlay-connected");
      }
      showToast("Call reconnected");
    });

    socket.on("call:reconnect_failed", function () {
      state.reconnecting = false;
      showToast("Reconnection failed");
      cleanupCall();
    });

    socket.on("calls:history:update", function () { });
  }

  function wireButtons() {
    var acceptBtn = qs("[data-call-accept]");
    if (acceptBtn) {
      acceptBtn.addEventListener("click", function () {
        var callId = acceptBtn.dataset.callId || state.call?.id;
        var callerId = acceptBtn.dataset.callerId || state.call?.caller_profile_id;
        var callType = acceptBtn.dataset.callType || state.call?.call_type || "audio";
        acceptCall(callId, callerId, callType);
      });
    }

    var rejectBtn = qs("[data-call-reject]");
    if (rejectBtn) {
      rejectBtn.addEventListener("click", function () {
        rejectCall(rejectBtn.dataset.callId || state.call?.id);
      });
    }

    var cancelBtn = qs("[data-call-cancel]");
    if (cancelBtn) cancelBtn.addEventListener("click", cancelCall);

    var endBtn = qs("[data-call-end]");
    if (endBtn) endBtn.addEventListener("click", endCall);

    var muteBtn = $("call-mute-btn");
    if (muteBtn) muteBtn.addEventListener("click", toggleMute);

    var cameraBtn = $("call-camera-btn");
    if (cameraBtn) cameraBtn.addEventListener("click", toggleCamera);

    var speakerBtn = $("call-speaker-btn");
    if (speakerBtn) speakerBtn.addEventListener("click", toggleSpeaker);

    var switchCamBtn = $("call-switch-camera-btn");
    if (switchCamBtn) switchCamBtn.addEventListener("click", switchCamera);

    var unlockBtn = $("call-ringtone-unlock-btn");
    if (unlockBtn) {
      unlockBtn.addEventListener("click", function () {
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        ctx.resume().then(function () { ctx.close(); });
        var el = $("call-ringtone-unlock");
        if (el) el.hidden = true;
      });
    }

    qsa("[data-call-action]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var action = btn.dataset.callAction;
        if (action === "start-audio") {
          startCall(btn.dataset.targetId, "audio", btn.dataset.threadId);
        } else if (action === "start-video") {
          startCall(btn.dataset.targetId, "video", btn.dataset.threadId);
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireSocket();
    wireButtons();
    var socket = window.socket || window.io?.();
    if (socket && window.myProfileId) {
      socket.emit("join:user", { profile_id: window.myProfileId });
    }
  });

  window.NamVibeCallsPro = {
    startCall: startCall,
    acceptCall: acceptCall,
    rejectCall: rejectCall,
    cancelCall: cancelCall,
    endCall: endCall,
    toggleMute: toggleMute,
    toggleCamera: toggleCamera,
    toggleSpeaker: toggleSpeaker,
    switchCamera: switchCamera,
  };
})();
