/**
 * CHAIN Group Calls — Multi-Party Audio/Video/Screen-Share Engine
 * Phase 44
 */
(function () {
  'use strict';

  const GROUP_CALL_API = '/group-calls/api';
  let groupCallState = {
    callId: null,
    participants: {},
    localStream: null,
    peerConnections: {},
    socket: null,
    audioEnabled: true,
    videoEnabled: true,
    screenSharing: false,
    speaking: false,
    isHost: false,
    localProfileId: null,
  };

  function _api(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json(); });
  }

  function _getSocket() {
    if (groupCallState.socket) return groupCallState.socket;
    if (typeof io !== 'undefined') {
      groupCallState.socket = io();
    }
    return groupCallState.socket;
  }

  function _iceConfig() {
    return _api('/calls/api/ice-servers').then(function (data) {
      return data.iceServers || [{ urls: 'stun:stun.l.google.com:19302' }];
    });
  }

  function _createPC(participantId, stream) {
    var pc = new RTCPeerConnection({ iceServers: groupCallState._iceServers || [] });
    groupCallState.peerConnections[participantId] = pc;

    if (stream) {
      stream.getTracks().forEach(function (t) {
        pc.addTrack(t, stream);
      });
    }

    pc.onicecandidate = function (e) {
      if (e.candidate) {
        _getSocket().emit('group-call:signal', {
          call_id: groupCallState.callId,
          target_id: participantId,
          candidate: e.candidate,
          encrypted: true,
        });
      }
    };

    pc.ontrack = function (e) {
      _renderRemoteStream(participantId, e.streams[0]);
    };

    pc.oniceconnectionstatechange = function () {
      if (pc.iceConnectionState === 'disconnected' || pc.iceConnectionState === 'failed') {
        _cleanupPC(participantId);
      }
    };

    return pc;
  }

  function _cleanupPC(participantId) {
    var pc = groupCallState.peerConnections[participantId];
    if (pc) {
      pc.close();
      delete groupCallState.peerConnections[participantId];
    }
    var el = document.getElementById('gcv-' + participantId);
    if (el) el.remove();
  }

  function _renderRemoteStream(participantId, stream) {
    var container = document.getElementById('gcv-' + participantId);
    if (!container) {
      container = document.createElement('div');
      container.id = 'gcv-' + participantId;
      container.className = 'group-call-video';
      var video = document.createElement('video');
      video.id = 'gv-' + participantId;
      video.autoplay = true;
      video.playsInline = true;
      container.appendChild(video);
      var label = document.createElement('div');
      label.className = 'participant-label';
      container.appendChild(label);
      var grid = document.getElementById('group-call-grid');
      if (grid) grid.appendChild(container);
    }
    var vid = container.querySelector('video');
    if (vid && vid.srcObject !== stream) {
      vid.srcObject = stream;
    }
  }

  function _renderLocalStream() {
    var container = document.getElementById('gcv-local');
    if (!container) return;
    var vid = container.querySelector('video');
    if (!vid) {
      vid = document.createElement('video');
      vid.id = 'gv-local';
      vid.autoplay = true;
      vid.playsInline = true;
      vid.muted = true;
      container.appendChild(vid);
    }
    if (groupCallState.localStream) {
      vid.srcObject = groupCallState.localStream;
    }
  }

  function _updateControls() {
    var micBtn = document.getElementById('gc-mic-btn');
    var camBtn = document.getElementById('gc-cam-btn');
    var screenBtn = document.getElementById('gc-screen-btn');
    if (micBtn) micBtn.innerHTML = groupCallState.audioEnabled ? '<i class="fas fa-microphone"></i>' : '<i class="fas fa-microphone-slash"></i>';
    if (camBtn) camBtn.innerHTML = groupCallState.videoEnabled ? '<i class="fas fa-video"></i>' : '<i class="fas fa-video-slash"></i>';
    if (screenBtn) screenBtn.innerHTML = groupCallState.screenSharing ? '<i class="fas fa-desktop"></i>' : '<i class="fas fa-share-alt"></i>';
  }

  function _updateParticipantCount() {
    var el = document.getElementById('gc-participant-count');
    var count = Object.keys(groupCallState.participants).length;
    if (el) el.textContent = count + (count === 1 ? ' participant' : ' participants');
  }

  // --- Audio level detection ---
  function _startSpeakingDetection() {
    if (!groupCallState.localStream || !groupCallState.socket) return;
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    var analyser = ctx.createAnalyser();
    var mic = ctx.createMediaStreamSource(groupCallState.localStream);
    mic.connect(analyser);
    var data = new Uint8Array(analyser.frequencyBinCount);
    var speaking = false;
    setInterval(function () {
      analyser.getByteFrequencyData(data);
      var avg = data.reduce(function (a, b) { return a + b; }, 0) / data.length;
      var nowSpeaking = avg > 20;
      if (nowSpeaking !== speaking) {
        speaking = nowSpeaking;
        groupCallState.speaking = speaking;
        groupCallState.socket.emit('group-call:speaking', {
          call_id: groupCallState.callId,
          speaking: speaking,
        });
      }
    }, 300);
  }

  // --- Public API ---

  window.CHAIN_GROUP_CALL = {
    create: function (opts) {
      opts = opts || {};
      return _api(GROUP_CALL_API + '/create', 'POST', {
        room_name: opts.roomName || '',
        call_type: opts.callType || 'audio',
        thread_id: opts.threadId || null,
        max_participants: opts.maxParticipants || 32,
      }).then(function (data) {
        if (data.ok) {
          groupCallState.callId = data.call.id;
          groupCallState.isHost = true;
          groupCallState.localProfileId = data.call.host_profile_id;
          return CHAIN_GROUP_CALL.joinRoom(data.call.id, opts);
        }
        return data;
      });
    },

    joinRoom: function (callId, opts) {
      opts = opts || {};
      groupCallState.callId = callId;
      return _iceConfig().then(function (servers) {
        groupCallState._iceServers = servers;
        groupCallState.audioEnabled = opts.audio !== false;
        groupCallState.videoEnabled = opts.video === true;
        return _api(GROUP_CALL_API + '/' + callId, 'GET');
      }).then(function (data) {
        if (!data.ok) return data;
        groupCallState.isHost = data.call.host_profile_id === data.call.host_profile_id; // set later from profile
        return _api(GROUP_CALL_API + '/' + callId + '/join', 'POST');
      }).then(function (data) {
        if (!data.ok) return data;
        groupCallState.participants = {};
        (data.participants || []).forEach(function (p) {
          groupCallState.participants[p.profile_id] = p;
        });
        _updateParticipantCount();
        var constraints = { audio: groupCallState.audioEnabled };
        if (groupCallState.videoEnabled) {
          constraints.video = { width: { ideal: 640 }, height: { ideal: 480 } };
        }
        return navigator.mediaDevices.getUserMedia(constraints);
      }).then(function (stream) {
        groupCallState.localStream = stream;
        _renderLocalStream();
        _updateControls();
        _startSpeakingDetection();
        _initSocketHandlers();
        return { ok: true, callId: groupCallState.callId };
      }).catch(function (err) {
        console.error('[GROUP_CALL] join error:', err);
        return { ok: false, error: err.message };
      });
    },

    leave: function () {
      if (!groupCallState.callId) return;
      var sock = _getSocket();
      if (sock) sock.emit('group-call:leave', { call_id: groupCallState.callId });
      _api(GROUP_CALL_API + '/' + groupCallState.callId + '/leave', 'POST').catch(function () {});
      _cleanup();
      _showGrid(false);
    },

    end: function () {
      if (!groupCallState.callId) return;
      var sock = _getSocket();
      if (sock) sock.emit('group-call:end', { call_id: groupCallState.callId });
      _api(GROUP_CALL_API + '/' + groupCallState.callId + '/end', 'POST').catch(function () {});
      _cleanup();
      _showGrid(false);
    },

    toggleMute: function () {
      groupCallState.audioEnabled = !groupCallState.audioEnabled;
      if (groupCallState.localStream) {
        groupCallState.localStream.getAudioTracks().forEach(function (t) {
          t.enabled = groupCallState.audioEnabled;
        });
      }
      var sock = _getSocket();
      var evt = groupCallState.audioEnabled ? 'group-call:unmute' : 'group-call:mute';
      if (sock) sock.emit(evt, { call_id: groupCallState.callId });
      _api(GROUP_CALL_API + '/' + groupCallState.callId + '/' + (groupCallState.audioEnabled ? 'unmute' : 'mute'), 'POST').catch(function () {});
      _updateControls();
    },

    toggleVideo: function () {
      groupCallState.videoEnabled = !groupCallState.videoEnabled;
      if (groupCallState.localStream) {
        groupCallState.localStream.getVideoTracks().forEach(function (t) {
          t.enabled = groupCallState.videoEnabled;
        });
      }
      var sock = _getSocket();
      if (sock) sock.emit('group-call:camera-toggle', {
        call_id: groupCallState.callId,
        enabled: groupCallState.videoEnabled,
      });
      _updateControls();
    },

    toggleScreenShare: function () {
      if (groupCallState.screenSharing) {
        _stopScreenShare();
        return;
      }
      if (!navigator.mediaDevices.getDisplayMedia) {
        alert('Screen sharing not supported on this browser.');
        return;
      }
      navigator.mediaDevices.getDisplayMedia({ video: true }).then(function (stream) {
        groupCallState.screenSharing = true;
        groupCallState._screenTrack = stream.getVideoTracks()[0];
        // Replace video track in all PCs
        Object.keys(groupCallState.peerConnections).forEach(function (pid) {
          var pc = groupCallState.peerConnections[pid];
          var sender = pc.getSenders().find(function (s) { return s.track && s.track.kind === 'video'; });
          if (sender) sender.replaceTrack(stream.getVideoTracks()[0]);
        });
        // Show screen preview locally
        var localVid = document.getElementById('gv-local');
        if (localVid) localVid.srcObject = stream;
        _updateControls();
        var sock = _getSocket();
        if (sock) sock.emit('group-call:screen-share', {
          call_id: groupCallState.callId,
          sharing: true,
        });
        groupCallState._screenTrack.onended = function () {
          CHAIN_GROUP_CALL.toggleScreenShare();
        };
      }).catch(function (err) {
        console.error('[GROUP_CALL] screen share error:', err);
      });
    },

    raiseHand: function () {
      var sock = _getSocket();
      if (sock) sock.emit('group-call:raise-hand', { call_id: groupCallState.callId });
      _api(GROUP_CALL_API + '/' + groupCallState.callId + '/raise-hand', 'POST').catch(function () {});
    },

    lowerHand: function () {
      var sock = _getSocket();
      if (sock) sock.emit('group-call:lower-hand', { call_id: groupCallState.callId });
      _api(GROUP_CALL_API + '/' + groupCallState.callId + '/lower-hand', 'POST').catch(function () {});
    },

    invite: function (profileId) {
      var sock = _getSocket();
      if (sock) sock.emit('group-call:invite', {
        call_id: groupCallState.callId,
        target_id: profileId,
      });
      _api(GROUP_CALL_API + '/' + groupCallState.callId + '/invite', 'POST', {
        profile_id: profileId,
      }).catch(function () {});
    },

    getState: function () {
      return groupCallState;
    },
  };

  function _stopScreenShare() {
    if (groupCallState._screenTrack) {
      groupCallState._screenTrack.stop();
      groupCallState._screenTrack = null;
    }
    groupCallState.screenSharing = false;
    // Restore camera track
    if (groupCallState.localStream) {
      var camTrack = groupCallState.localStream.getVideoTracks()[0];
      if (camTrack) {
        Object.keys(groupCallState.peerConnections).forEach(function (pid) {
          var pc = groupCallState.peerConnections[pid];
          var sender = pc.getSenders().find(function (s) { return s.track && s.track.kind === 'video'; });
          if (sender) sender.replaceTrack(camTrack);
        });
      }
      var localVid = document.getElementById('gv-local');
      if (localVid) localVid.srcObject = groupCallState.localStream;
    }
    _updateControls();
    var sock = _getSocket();
    if (sock) sock.emit('group-call:screen-share', {
      call_id: groupCallState.callId,
      sharing: false,
    });
  }

  function _initSocketHandlers() {
    var sock = _getSocket();
    if (!sock) return;

    sock.off('group-call:participant-joined');
    sock.off('group-call:participant-left');
    sock.off('group-call:muted');
    sock.off('group-call:unmuted');
    sock.off('group-call:hand-raised');
    sock.off('group-call:hand-lowered');
    sock.off('group-call:camera-toggled');
    sock.off('group-call:screen-shared');
    sock.off('group-call:speaking-status');
    sock.off('group-call:host-transferred');
    sock.off('group-call:ended');

    sock.on('group-call:participant-joined', function (d) {
      var pid = d.profile_id;
      if (!groupCallState.participants[pid]) {
        groupCallState.participants[pid] = { profile_id: pid, status: 'joined' };
      }
      _updateParticipantCount();
      // Create peer connection to new participant
      if (groupCallState.localStream) {
        _createPC(pid, groupCallState.localStream);
      }
    });

    sock.on('group-call:participant-left', function (d) {
      delete groupCallState.participants[d.profile_id];
      _cleanupPC(d.profile_id);
      _updateParticipantCount();
    });

    sock.on('group-call:muted', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].muted = true;
      }
    });

    sock.on('group-call:unmuted', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].muted = false;
      }
    });

    sock.on('group-call:hand-raised', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].hand_raised = true;
      }
    });

    sock.on('group-call:hand-lowered', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].hand_raised = false;
      }
    });

    sock.on('group-call:camera-toggled', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].camera_enabled = d.enabled;
      }
    });

    sock.on('group-call:screen-shared', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].screen_sharing = d.sharing;
      }
    });

    sock.on('group-call:speaking-status', function (d) {
      if (groupCallState.participants[d.profile_id]) {
        groupCallState.participants[d.profile_id].speaking = d.speaking;
      }
      var label = document.querySelector('#gcv-' + d.profile_id + ' .participant-label');
      if (label) {
        label.innerHTML = (d.speaking ? '<i class="fas fa-volume-up" style="color:#22c55e"></i> Speaking' : '');
      }
    });

    sock.on('group-call:host-transferred', function (d) {
      groupCallState.isHost = d.to_id === groupCallState.localProfileId;
      if (groupCallState.participants[d.from_id]) groupCallState.participants[d.from_id].role = 'participant';
      if (groupCallState.participants[d.to_id]) groupCallState.participants[d.to_id].role = 'host';
    });

    sock.on('group-call:ended', function () {
      _cleanup();
      _showGrid(false);
      alert('Group call ended by host.');
    });
  }

  function _cleanup() {
    Object.keys(groupCallState.peerConnections).forEach(function (pid) {
      _cleanupPC(pid);
    });
    if (groupCallState.localStream) {
      groupCallState.localStream.getTracks().forEach(function (t) { t.stop(); });
      groupCallState.localStream = null;
    }
    groupCallState.callId = null;
    groupCallState.participants = {};
    groupCallState.isHost = false;
    groupCallState.speaking = false;
    groupCallState.screenSharing = false;
    groupCallState._screenTrack = null;
  }

  function _showGrid(visible) {
    var el = document.getElementById('group-call-container');
    if (el) el.style.display = visible ? 'flex' : 'none';
  }

  // Expose UI helper
  window.CHAIN_GROUP_CALL.showGrid = function () { _showGrid(true); };
  window.CHAIN_GROUP_CALL.hideGrid = function () { _showGrid(false); };

})();
