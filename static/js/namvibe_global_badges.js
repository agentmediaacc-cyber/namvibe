(function () {
  'use strict';

  var POLL_INTERVAL = 60000;
  var pollTimer = null;
  var socket = null;
  var timerGuard = false;

  function init() {
    if (timerGuard) return;
    timerGuard = true;
    poll();
    pollTimer = setInterval(poll, POLL_INTERVAL);
    listenSocket();
    listenEvents();
  }

  function refreshBadge() {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
    poll();
    pollTimer = setInterval(poll, POLL_INTERVAL);
  }

  function poll() {
    fetch('/api/notifications/unread-count', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        updateAll(data.count || 0);
      })
      .catch(function () {});
  }

  function updateAll(count) {
    var badges = document.querySelectorAll('[data-notification-badge]');
    var displayCount = count > 99 ? '99+' : count;
    badges.forEach(function (el) {
      if (count > 0) {
        el.textContent = displayCount;
        el.style.display = '';
      } else {
        el.style.display = 'none';
      }
    });
  }

  function listenSocket() {
    if (typeof io === 'undefined') return;
    try {
      socket = io();
      socket.on('notification:new', function () {
        refreshBadge();
      });
      socket.on('friend_request:new', function () {
        refreshBadge();
      });
      socket.on('friend_request:accepted', function () {
        refreshBadge();
      });
    } catch (e) {}
  }

  function listenEvents() {
    document.addEventListener('notifications:read', function () {
      refreshBadge();
    });
    document.addEventListener('friend_request:accepted', function () {
      refreshBadge();
    });
    document.addEventListener('friend_request:declined', function () {
      refreshBadge();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
