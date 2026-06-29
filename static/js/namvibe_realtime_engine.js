(function () {
  'use strict';

  var socket = null;
  var profileId = null;
  var heartbeatInterval = null;
  var reconnecting = false;
  var reconnectAttempts = 0;
  var maxReconnectDelay = 30000;
  var listeners = {};
  var connected = false;

  function init(opts) {
    opts = opts || {};
    profileId = opts.profileId || null;

    if (window.chainSocket && window.chainSocket.connected) {
      socket = window.chainSocket;
      connected = true;
      emit('realtime:connected', { profile_id: profileId });
      return;
    }

    if (typeof io === 'undefined') return;

    var socketUrl = opts.url || '';
    var socketOpts = {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: maxReconnectDelay,
      reconnectionAttempts: Infinity,
      timeout: 10000,
    };

    try {
      socket = socketUrl ? io(socketUrl, socketOpts) : io(socketOpts);
    } catch (e) { return; }

    socket.on('connect', function () {
      connected = true;
      reconnecting = false;
      reconnectAttempts = 0;
      if (profileId) {
        socket.emit('join', { room: 'profile:' + profileId });
      }
      startHeartbeat();
      emit('realtime:connected', { profile_id: profileId });
    });

    socket.on('disconnect', function () {
      connected = false;
      stopHeartbeat();
      emit('realtime:disconnected', {});
    });

    socket.on('reconnect_attempt', function (attempt) {
      reconnectAttempts = attempt;
      reconnecting = true;
      emit('realtime:reconnecting', { attempt: attempt });
    });

    socket.on('connect_error', function () {
      emit('realtime:error', {});
    });

    socket.on('presence:update', function (data) {
      emit('presence:update', data);
    });

    socket.on('activity:new', function (data) {
      emit('activity:new', data);
    });

    socket.on('notification:new', function (data) {
      emit('notification:new', data);
    });

    socket.on('chat:typing', function (data) {
      emit('chat:typing', data);
    });

    socket.on('chat:message', function (data) {
      emit('chat:message', data);
    });

    socket.on('call:incoming', function (data) {
      emit('call:incoming', data);
    });

    socket.on('call:state', function (data) {
      emit('call:state', data);
    });
  }

  function joinRoom(room) {
    if (socket && socket.connected) {
      socket.emit('join', { room: room });
    }
  }

  function leaveRoom(room) {
    if (socket && socket.connected) {
      socket.emit('leave', { room: room });
    }
  }

  function emitEvent(event, data) {
    if (socket && socket.connected) {
      socket.emit(event, data);
    }
  }

  function on(event, callback) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(callback);
  }

  function off(event, callback) {
    if (!listeners[event]) return;
    if (!callback) {
      delete listeners[event];
      return;
    }
    listeners[event] = listeners[event].filter(function (fn) {
      return fn !== callback;
    });
  }

  function emit(event, data) {
    var cbs = listeners[event] || [];
    for (var i = 0; i < cbs.length; i++) {
      try { cbs[i](data); } catch (e) {}
    }
  }

  function startHeartbeat() {
    stopHeartbeat();
    heartbeatInterval = setInterval(function () {
      if (socket && socket.connected) {
        socket.emit('heartbeat', { profile_id: profileId, ts: Date.now() });
      }
    }, 25000);
  }

  function stopHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  }

  function isConnected() {
    return connected;
  }

  function destroy() {
    if (socket && socket !== window.chainSocket) {
      stopHeartbeat();
      listeners = {};
      socket.removeAllListeners();
      socket.disconnect();
      socket = null;
      connected = false;
    }
  }

  window.NamVibeRealtime = {
    init: init,
    joinRoom: joinRoom,
    leaveRoom: leaveRoom,
    emit: emitEvent,
    on: on,
    off: off,
    isConnected: isConnected,
    destroy: destroy,
  };
})();
