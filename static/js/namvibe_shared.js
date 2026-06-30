(function () {
  'use strict';

  var toastContainer = null;
  var toastCount = 0;

  function ensureContainer() {
    if (toastContainer) return toastContainer;
    toastContainer = document.getElementById('nv-shared-toast-container');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'nv-shared-toast-container';
      toastContainer.className = 'nv-toast-container';
      toastContainer.setAttribute('aria-live', 'polite');
      toastContainer.setAttribute('aria-atomic', 'true');
      document.body.appendChild(toastContainer);
    }
    return toastContainer;
  }

  function show(message, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    var container = ensureContainer();
    var id = 'nv-toast-' + (++toastCount);
    var toast = document.createElement('div');
    toast.id = id;
    toast.className = 'nv-toast nv-toast-' + type;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');

    var msgSpan = document.createElement('span');
    msgSpan.className = 'nv-toast-msg';
    msgSpan.textContent = message;

    var closeBtn = document.createElement('button');
    closeBtn.className = 'nv-toast-close';
    closeBtn.setAttribute('aria-label', 'Dismiss');
    closeBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    closeBtn.addEventListener('click', function () { dismiss(id); });

    toast.appendChild(msgSpan);
    toast.appendChild(closeBtn);
    container.appendChild(toast);

    requestAnimationFrame(function () {
      toast.classList.add('is-visible');
    });

    if (duration > 0) {
      setTimeout(function () { dismiss(id); }, duration);
    }

    return id;
  }

  function dismiss(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('is-visible');
    el.classList.add('is-hiding');
    setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, 250);
  }

  function success(msg, dur) { return show(msg, 'success', dur); }
  function error(msg, dur) { return show(msg, 'error', dur); }
  function warning(msg, dur) { return show(msg, 'warning', dur); }
  function info(msg, dur) { return show(msg, 'info', dur); }

  if (window.NamVibeToast) return;
  window.NamVibeToast = { show: show, dismiss: dismiss, success: success, error: error, warning: warning, info: info };
})();
