(function () {
  'use strict';

  var socket = null;

  function init() {
    if (window.chainRealtimeOptional === false) return;
    if (window.chainSocket) {
      socket = window.chainSocket;
      attachListeners();
      return;
    }
    if (typeof io === 'undefined') return;
    try {
      socket = io({ transports: ['websocket', 'polling'], reconnection: true });
      attachListeners();
    } catch (e) {}
  }

  function attachListeners() {
    socket.on('user:online', function (data) {
      updateOnlineDot(data.profile_id, true);
    });

    socket.on('user:offline', function (data) {
      updateOnlineDot(data.profile_id, false);
    });

    socket.on('message:typing', function (data) {
      showTypingIndicator(data.thread_id, data.profile_id, data.username);
    });

    socket.on('message:typing_stop', function (data) {
      hideTypingIndicator(data.thread_id, data.profile_id);
    });

    socket.on('message:seen', function (data) {
      updateSeenTick(data.thread_id, data.profile_id);
    });

    socket.on('call:ringing', function (data) {
      showCallingIndicator(data.thread_id, data.caller_name);
    });

    socket.on('call:missed', function (data) {
      hideCallingIndicator(data.thread_id);
    });

    socket.on('call:ended', function (data) {
      hideCallingIndicator(data.thread_id);
    });
  }

  function updateOnlineDot(profileId, isOnline) {
    var dots = document.querySelectorAll('[data-online-dot="' + profileId + '"]');
    dots.forEach(function (dot) {
      dot.className = isOnline ? 'online' : 'offline';
      dot.title = isOnline ? 'Online' : 'Offline';
    });
  }

  function showTypingIndicator(threadId, profileId, username) {
    var indicator = document.querySelector('[data-typing-indicator="' + threadId + '"]');
    if (indicator) {
      indicator.textContent = (username || 'Someone') + ' is typing...';
      indicator.style.display = 'block';
      clearTimeout(indicator._typingTimer);
      indicator._typingTimer = setTimeout(function () {
        indicator.style.display = 'none';
      }, 3000);
    }
  }

  function hideTypingIndicator(threadId, profileId) {
    var indicator = document.querySelector('[data-typing-indicator="' + threadId + '"]');
    if (indicator) {
      indicator.style.display = 'none';
      clearTimeout(indicator._typingTimer);
    }
  }

  function updateSeenTick(threadId, profileId) {
    var ticks = document.querySelectorAll('[data-seen-tick="' + threadId + '"]');
    ticks.forEach(function (tick) {
      tick.classList.add('seen');
      tick.innerHTML = '<i class="fas fa-check-double" style="color:#34c759"></i> Seen';
    });
  }

  function showCallingIndicator(threadId, callerName) {
    var indicator = document.querySelector('[data-calling-indicator="' + threadId + '"]');
    if (indicator) {
      indicator.textContent = (callerName || 'Someone') + ' is calling...';
      indicator.style.display = 'block';
    }
  }

  function hideCallingIndicator(threadId) {
    var indicator = document.querySelector('[data-calling-indicator="' + threadId + '"]');
    if (indicator) {
      indicator.style.display = 'none';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
