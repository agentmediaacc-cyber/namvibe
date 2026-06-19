(function () {
  'use strict';

  if (window.chainSocket) return;
  if (typeof io === 'undefined') return;

  var socket = io({
    reconnectionDelay: 1000,
    reconnectionDelayMax: 16000,
    reconnectionAttempts: Infinity,
    transports: ['websocket', 'polling'],
    timeout: 20000,
  });

  var reconnectBanner = null;
  var initialAttemptComplete = false;
  var closedByUser = false;
  var showTimer = null;

  socket.on('connect', function () {
    initialAttemptComplete = true;
    hideBanner();
  });

  socket.on('disconnect', function () {
    showBannerIfNeeded();
  });

  socket.on('connect_error', function () {
    initialAttemptComplete = true;
    showBannerIfNeeded();
  });

  socket.on('reconnect', function () {
    hideBanner();
  });

  function showBannerIfNeeded() {
    if (!initialAttemptComplete || closedByUser) return;
    clearTimeout(showTimer);
    showTimer = setTimeout(function () {
      fetch('/system/socketio-status', { credentials: 'same-origin' })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          if (data && data.ok !== false) return;
          showBanner();
        })
        .catch(showBanner);
    }, 2500);
  }

  function showBanner() {
    var b = getBanner();
    if (!b) return;
    b.classList.add('show');
    b.setAttribute('aria-hidden', 'false');
  }

  function hideBanner() {
    clearTimeout(showTimer);
    var b = getBanner();
    if (b) {
      b.classList.remove('show');
      b.setAttribute('aria-hidden', 'true');
    }
  }

  function getBanner() {
    if (reconnectBanner) return reconnectBanner;
    reconnectBanner = document.querySelector('[data-reconnect-banner]');
    if (reconnectBanner && !reconnectBanner.querySelector('[data-reconnect-close]')) {
      var close = document.createElement('button');
      close.type = 'button';
      close.setAttribute('data-reconnect-close', '1');
      close.setAttribute('aria-label', 'Hide reconnecting banner');
      close.textContent = 'Close';
      close.addEventListener('click', function () {
        closedByUser = true;
        hideBanner();
      });
      reconnectBanner.appendChild(close);
    }
    return reconnectBanner;
  }

  window.chainSocket = socket;
})();
