(function () {
  'use strict';

  var pollTimer = null;
  var socket = null;
  var timerGuard = false;

  function init() {
    if (timerGuard) return;
    timerGuard = true;
    poll();
    listenSocket();
    listenEvents();
    // No standalone polling timer — rely on main.js and socket events.
    // Listen for a custom event dispatched by main.js after its poll completes.
    document.addEventListener('notif:badge-update', function (e) {
      updateAll(e.detail ? e.detail.count : 0);
    });
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) poll();
    });
  }

  function refreshBadge() {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
    poll();
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
      socket.on('notifications:unread-count', function (data) {
        updateAll((data && data.count) || 0);
      });
    } catch (e) {}
  }

  function listenEvents() {
    document.addEventListener('notif:refresh', function () {
      refreshBadge();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
