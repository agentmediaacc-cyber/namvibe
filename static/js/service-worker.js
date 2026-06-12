/**
 * NamVibe Push Notification Service Worker
 * Phase 45: Push Notifications, Background Calls, APNS, FCM, CallKit
 */
self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(clients.claim());
});

self.addEventListener('push', function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'NamVibe', body: event.data ? event.data.text() : '' };
  }

  var title = data.title || 'NamVibe';
  var body = data.body || '';
  var icon = data.icon || '/static/img/icon-192.png';
  var badge = data.badge || '/static/img/icon-192.png';
  var clickUrl = '/';
  if (data.data && data.data.url) {
    clickUrl = data.data.url;
  }

  var options = {
    body: body,
    icon: icon,
    badge: badge,
    vibrate: [200, 100, 200],
    data: { url: clickUrl, original_data: data },
    actions: [],
    tag: 'chain-notification',
    renotify: true,
    requireInteraction: true,
  };

  // Incoming call notifications
  if (data.notification_type === 'incoming_call' || (data.data && data.data._notification_type === 'incoming_call')) {
    options.actions = [
      { action: 'accept', title: 'Accept' },
      { action: 'decline', title: 'Decline' },
    ];
    options.tag = 'chain-incoming-call';
    options.requireInteraction = true;
  }

  // Message notifications
  if (data.notification_type === 'message_received' || (data.data && data.data._notification_type === 'message_received')) {
    options.actions = [
      { action: 'open-chat', title: 'Open Chat' },
    ];
    options.tag = 'chain-message';
  }

  // Missed call notifications
  if (data.notification_type === 'missed_call' || (data.data && data.data._notification_type === 'missed_call')) {
    options.tag = 'chain-missed-call';
  }

  // Group call invite notifications
  if (data.notification_type === 'group_call_invite' || (data.data && data.data._notification_type === 'group_call_invite')) {
    options.actions = [
      { action: 'join', title: 'Join Call' },
      { action: 'decline', title: 'Decline' },
    ];
    options.tag = 'chain-group-call-invite';
  }

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();

  var url = '/';
  if (event.notification.data && event.notification.data.url) {
    url = event.notification.data.url;
  }

  // Handle action buttons
  if (event.action === 'accept' || event.action === 'join') {
    var callId = null;
    if (event.notification.data && event.notification.data.original_data && event.notification.data.original_data.call_id) {
      callId = event.notification.data.original_data.call_id;
    } else if (event.notification.data && event.notification.data.original_data && event.notification.data.original_data.data && event.notification.data.original_data.data.call_id) {
      callId = event.notification.data.original_data.data.call_id;
    }
    if (callId) {
      url = '/calls/group/' + callId;
    }
  }

  if (event.action === 'open-chat') {
    if (event.notification.data && event.notification.data.original_data && event.notification.data.original_data.url) {
      url = event.notification.data.original_data.url;
    }
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i];
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});

self.addEventListener('notificationclose', function (event) {
  // Notification was dismissed without action
});
