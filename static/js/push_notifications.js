/**
 * CHAIN Push Notifications Client
 * Phase 45: Push Notifications, Background Calls, APNS, FCM, CallKit
 *
 * Features:
 *   - Register service worker
 *   - Subscribe/unsubscribe browser push
 *   - Request notification permission
 *   - Register/remove device token
 *   - Cross-browser support (Chrome, Safari, Firefox, Edge)
 */
(function () {
  'use strict';

  var PUSH_API = '/notifications/api';
  var VAPID_KEY = null;

  /**
   * Fetch the VAPID public key from the server.
   */
  function _fetchVapidKey() {
    return fetch(PUSH_API + '/vapid-public-key')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        VAPID_KEY = data.publicKey || null;
        return VAPID_KEY;
      })
      .catch(function () {
        VAPID_KEY = null;
        return null;
      });
  }

  /**
   * Check if the browser supports notifications and service workers.
   */
  function isSupported() {
    return 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
  }

  /**
   * Check the current notification permission status.
   */
  function getPermissionStatus() {
    if (!isSupported()) {
      return 'unsupported';
    }
    return Notification.permission;
  }

  /**
   * Request notification permission from the user.
   * Returns 'granted', 'denied', or 'default'.
   */
  function requestNotificationPermission() {
    if (!isSupported()) {
      return Promise.resolve('unsupported');
    }
    if (Notification.permission === 'granted') {
      return Promise.resolve('granted');
    }
    return Notification.requestPermission().then(function (permission) {
      return permission;
    });
  }

  /**
   * Register the service worker for push notifications.
   */
  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      return Promise.reject(new Error('Service workers not supported'));
    }
    return navigator.serviceWorker.register('/static/js/service-worker.js')
      .then(function (registration) {
        return registration;
      });
  }

  /**
   * Subscribe to browser push notifications.
   * Requires VAPID keys to be configured on the server.
   */
  function subscribeBrowserPush() {
    if (!isSupported()) {
      return Promise.reject(new Error('Push not supported'));
    }
    return _fetchVapidKey().then(function (vapidKey) {
      if (!vapidKey) {
        return Promise.reject(new Error('VAPID key not available'));
      }
      return registerServiceWorker().then(function (registration) {
        return registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: _urlBase64ToUint8Array(vapidKey),
        }).then(function (subscription) {
          return subscription;
        });
      });
    });
  }

  /**
   * Register a push token on the server.
   * This sends the subscription object to the server for storage.
   */
  function registerPushToken(subscription) {
    if (!subscription) {
      return Promise.reject(new Error('No subscription'));
    }
    var sub = subscription.toJSON();
    var token = sub.endpoint;
    var platform = 'web';
    if (navigator.userAgent.indexOf('Android') !== -1) {
      platform = 'android';
    }

    return fetch(PUSH_API + '/register-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ token: token, platform: platform }),
    }).then(function (r) { return r.json(); });
  }

  /**
   * Remove a push token from the server.
   */
  function removePushToken(token) {
    return fetch(PUSH_API + '/remove-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ token: token }),
    }).then(function (r) { return r.json(); });
  }

  /**
   * Unsubscribe from push notifications and remove server token.
   */
  function unsubscribeBrowserPush() {
    return registerServiceWorker().then(function (registration) {
      return registration.pushManager.getSubscription().then(function (subscription) {
        if (subscription) {
          var token = subscription.endpoint;
          subscription.unsubscribe();
          return removePushToken(token);
        }
        return { ok: true };
      });
    });
  }

  /**
   * Get all registered push tokens from the server.
   */
  function getPushTokens() {
    return fetch(PUSH_API + '/tokens', {
      credentials: 'same-origin',
    }).then(function (r) { return r.json(); });
  }

  /**
   * Send a test notification through the server.
   */
  function sendTestNotification(title, body) {
    return fetch(PUSH_API + '/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ title: title || 'Test', body: body || 'This is a test notification' }),
    }).then(function (r) { return r.json(); });
  }

  /**
   * Fetch notification history from the server.
   */
  function getNotificationHistory(limit) {
    return fetch(PUSH_API + '/history?limit=' + (limit || 50), {
      credentials: 'same-origin',
    }).then(function (r) { return r.json(); });
  }

  /**
   * Get unread notification count.
   */
  function getUnreadCount() {
    return fetch(PUSH_API + '/unread-count', {
      credentials: 'same-origin',
    }).then(function (r) { return r.json(); });
  }

  /**
   * Mark a notification as read.
   */
  function markNotificationRead(notificationId) {
    return fetch(PUSH_API + '/mark-read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ notification_id: notificationId }),
    }).then(function (r) { return r.json(); });
  }

  /**
   * Get notification preferences.
   */
  function getPreferences() {
    return fetch(PUSH_API + '/preferences', {
      credentials: 'same-origin',
    }).then(function (r) { return r.json(); });
  }

  /**
   * Update notification preferences.
   */
  function setPreferences(prefs) {
    return fetch(PUSH_API + '/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(prefs),
    }).then(function (r) { return r.json(); });
  }

  /**
   * Convert a base64 URL-encoded string to a Uint8Array.
   * Required for the VAPID applicationServerKey.
   */
  function _urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding)
      .replace(/\-/g, '+')
      .replace(/_/g, '/');
    var rawData = window.atob(base64);
    var output = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      output[i] = rawData.charCodeAt(i);
    }
    return output;
  }

  // Expose public API
  window.CHAIN_PUSH = {
    isSupported: isSupported,
    getPermissionStatus: getPermissionStatus,
    requestNotificationPermission: requestNotificationPermission,
    registerServiceWorker: registerServiceWorker,
    subscribeBrowserPush: subscribeBrowserPush,
    registerPushToken: registerPushToken,
    unsubscribeBrowserPush: unsubscribeBrowserPush,
    removePushToken: removePushToken,
    getPushTokens: getPushTokens,
    sendTestNotification: sendTestNotification,
    getNotificationHistory: getNotificationHistory,
    getUnreadCount: getUnreadCount,
    markNotificationRead: markNotificationRead,
    getPreferences: getPreferences,
    setPreferences: setPreferences,
    VAPID_KEY: VAPID_KEY,
  };

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      _fetchVapidKey();
    });
  } else {
    _fetchVapidKey();
  }
})();
