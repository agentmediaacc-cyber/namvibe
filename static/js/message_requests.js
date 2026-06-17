(function () {
  'use strict';

  function loadFriendRequests() {
    var list = document.getElementById('friendRequestsList');
    var empty = document.getElementById('friendRequestsEmpty');
    if (!list) return;

    list.innerHTML = '<div style="text-align:center;padding:30px;color:#aaa"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    if (empty) empty.style.display = 'none';

    fetch('/messages/api/friend-requests', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok || !data.requests || data.requests.length === 0) {
          list.innerHTML = '';
          if (empty) empty.style.display = '';
          updateBadge(0);
          return;
        }
        list.innerHTML = '';
        data.requests.forEach(function (req) {
          list.appendChild(createRequestCard(req));
        });
        updateBadge(data.requests.length);
      })
      .catch(function () {
        list.innerHTML = '<div style="text-align:center;padding:30px;color:#aaa">Failed to load requests</div>';
      });
  }

  function createRequestCard(req) {
    var card = document.createElement('div');
    card.className = 'friend-request-card';
    card.dataset.requestId = req.id;

    var avatarHtml = req.avatar_url
      ? '<img src="' + esc(req.avatar_url) + '" alt="' + esc(req.username || '') + '">'
      : '<i class="fas fa-user"></i>';

    var verifiedBadge = req.is_verified ? '<i class="fas fa-check-circle" style="color:#1d9bf0;font-size:14px"></i>' : '';

    card.innerHTML =
      '<div class="fr-avatar">' + avatarHtml + '</div>' +
      '<div class="fr-body">' +
        '<div class="fr-name">' + esc(req.full_name || req.username || 'Unknown') + ' ' + verifiedBadge + '</div>' +
        '<div class="fr-username">@' + esc(req.username || '') + '</div>' +
        (req.message ? '<div class="fr-message">' + esc(req.message) + '</div>' : '') +
        '<div class="fr-time">' + timeAgo(req.created_at) + '</div>' +
        '<div class="fr-actions">' +
          '<button class="fr-btn fr-accept" data-request-id="' + esc(req.id) + '"><i class="fas fa-check"></i> Accept</button>' +
          '<button class="fr-btn fr-decline" data-request-id="' + esc(req.id) + '"><i class="fas fa-times"></i> Decline</button>' +
          '<a href="/profile/@' + esc(req.username || '') + '" class="fr-btn fr-profile"><i class="fas fa-user"></i> Profile</a>' +
        '</div>' +
      '</div>';

    card.querySelector('.fr-accept').addEventListener('click', function (e) {
      e.stopPropagation();
      acceptRequest(req.id, card);
    });
    card.querySelector('.fr-decline').addEventListener('click', function (e) {
      e.stopPropagation();
      declineRequest(req.id, card);
    });

    return card;
  }

  function acceptRequest(requestId, card) {
    var acceptBtn = card.querySelector('.fr-accept');
    acceptBtn.disabled = true;
    acceptBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    fetch('/api/friends/accept/' + encodeURIComponent(requestId), {
      method: 'POST', credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.querySelector('.fr-actions').innerHTML =
            '<span style="font-size:13px;color:#2ecc71;font-weight:600"><i class="fas fa-check-circle"></i> Friends now</span>';
          card.style.opacity = '0.6';
          showToast('Friend request accepted!');
          dispatchEvent(new CustomEvent('friend_request:accepted'));
          updateBadgeDecrement();
        } else {
          acceptBtn.disabled = false;
          acceptBtn.innerHTML = '<i class="fas fa-check"></i> Accept';
          showToast(data.error || 'Failed to accept');
        }
      })
      .catch(function () {
        acceptBtn.disabled = false;
        acceptBtn.innerHTML = '<i class="fas fa-check"></i> Accept';
        showToast('Network error');
      });
  }

  function declineRequest(requestId, card) {
    var declineBtn = card.querySelector('.fr-decline');
    declineBtn.disabled = true;
    declineBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    fetch('/api/friends/decline/' + encodeURIComponent(requestId), {
      method: 'POST', credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.remove();
          showToast('Request declined');
          dispatchEvent(new CustomEvent('friend_request:accepted'));
          updateBadgeDecrement();
          var list = document.getElementById('friendRequestsList');
          if (list && list.children.length === 0) {
            var empty = document.getElementById('friendRequestsEmpty');
            if (empty) empty.style.display = '';
          }
        } else {
          declineBtn.disabled = false;
          declineBtn.innerHTML = '<i class="fas fa-times"></i> Decline';
          showToast(data.error || 'Failed to decline');
        }
      })
      .catch(function () {
        declineBtn.disabled = false;
        declineBtn.innerHTML = '<i class="fas fa-times"></i> Decline';
        showToast('Network error');
      });
  }

  function updateBadge(count) {
    var badge = document.getElementById('sidebar-missed-call-badge');
    if (badge) {
      if (count > 0) {
        badge.textContent = count > 99 ? '99+' : count;
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    }

    var reqBadge = document.getElementById('msgFriendRequestBadge');
    if (reqBadge) {
      if (count > 0) {
        reqBadge.textContent = count > 99 ? '99+' : count;
        reqBadge.style.display = '';
      } else {
        reqBadge.style.display = 'none';
      }
    }
  }

  function updateBadgeDecrement() {
    var badge = document.getElementById('sidebar-missed-call-badge');
    var reqBadge = document.getElementById('msgFriendRequestBadge');
    var current = 0;
    if (badge && badge.style.display !== 'none') current = parseInt(badge.textContent) || 0;
    if (current > 0) updateBadge(current - 1);
  }

  function showToast(msg) {
    var container = document.getElementById('nvToastContainer') || createToastContainer();
    var el = document.createElement('div');
    el.className = 'nv-toast';
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(function () { el.remove(); }, 3000);
  }

  function createToastContainer() {
    var c = document.createElement('div');
    c.id = 'nvToastContainer';
    c.className = 'nv-toast-container';
    document.body.appendChild(c);
    return c;
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    var diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return new Date(dateStr).toLocaleDateString();
  }

  function esc(str) {
    if (typeof str !== 'string') return str || '';
    return str.replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  window.loadFriendRequests = loadFriendRequests;
})();
