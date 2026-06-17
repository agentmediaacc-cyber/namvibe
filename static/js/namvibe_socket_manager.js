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

  socket.on('connect', function () {
    hideBanner();
  });

  socket.on('disconnect', function () {
    showBanner();
  });

  socket.on('connect_error', function () {
    showBanner();
  });

  socket.on('reconnect', function () {
    hideBanner();
  });

  function showBanner() {
    var b = getBanner();
    if (b) b.classList.add('show');
  }

  function hideBanner() {
    var b = getBanner();
    if (b) b.classList.remove('show');
  }

  function getBanner() {
    if (reconnectBanner) return reconnectBanner;
    reconnectBanner = document.querySelector('[data-reconnect-banner]');
    return reconnectBanner;
  }

  window.chainSocket = socket;
})();
