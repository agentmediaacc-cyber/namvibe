(function () {
  'use strict';

  var POLL_INTERVAL = 20000;
  var pollTimer = null;
  var socket = null;

  function init() {
    poll();
    pollTimer = setInterval(poll, POLL_INTERVAL);
    listenSocket();
    listenEvents();
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
        poll();
      });
      socket.on('friend_request:new', function () {
        poll();
      });
      socket.on('friend_request:accepted', function () {
        poll();
      });
    } catch (e) {}
  }

  function listenEvents() {
    document.addEventListener('notifications:read', function () {
      poll();
    });
    document.addEventListener('friend_request:accepted', function () {
      poll();
    });
    document.addEventListener('friend_request:declined', function () {
      poll();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
