/**
 * CHAIN Notification Badge Updater
 * Phase 45: Real-time unread badge count
 */
(function () {
  'use strict';

  function _updateBadge() {
    if (!window.CHAIN_PUSH) return;
    window.CHAIN_PUSH.getUnreadCount().then(function (data) {
      if (data.ok && data.unread_count > 0) {
        var badge = document.querySelector('.notification-badge');
        if (badge) {
          badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
          badge.classList.remove('hidden');
        }
      }
    }).catch(function () {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _updateBadge);
  } else {
    _updateBadge();
  }

  // Periodically check for updates
  setInterval(_updateBadge, 30000);
})();
