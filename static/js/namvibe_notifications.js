(function () {
  'use strict';

  var state = {
    page: 1,
    hasMore: true,
    loading: false,
    items: [],
  };

  var DOM = {};
  var toastTimer = null;
  var deleteTimer = null;
  var DELETE_DELAY = 600;

  function init() {
    DOM.feed = document.getElementById('nvFeed');
    DOM.sentinel = document.getElementById('nvSentinel');
    DOM.skeleton = document.getElementById('nvSkeleton');
    DOM.empty = document.getElementById('nvEmpty');
    DOM.toastContainer = document.getElementById('nvToastContainer');
    DOM.markAllBtn = document.querySelector('[data-action="mark-all-read"]');
    DOM.deleteModal = document.getElementById('deleteConfirmModal');
    DOM.deleteConfirm = document.getElementById('deleteConfirmAction');
    DOM.deleteCancel = document.getElementById('deleteConfirmCancel');

    if (DOM.markAllBtn) DOM.markAllBtn.addEventListener('click', onMarkAllRead);

    setupInfiniteScroll();
    fetchFeed(1, true);
    // Clear badge on page load — user has seen their notifications
    setTimeout(clearBadge, 500);
  }

  /* ── Clear badge when notifications page is opened ── */
  function clearBadge() {
    fetch('/api/notifications/read-all', {
      method: 'POST', credentials: 'same-origin',
    }).then(function () { updateBadge(); }).catch(function () {});
  }

  /* ── Feed API ── */
  function fetchFeed(page, replace) {
    if (state.loading) return;
    state.loading = true;

    var url = '/api/notifications?tab=all&page=' + page;

    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.loading = false;
        if (!data.ok) { showSkeleton(); return; }
        hideSkeleton();
        state.hasMore = data.has_more;

        if (replace) {
          state.items = data.items || [];
          DOM.feed.innerHTML = '';
        } else {
          state.items = state.items.concat(data.items || []);
        }

        (data.items || []).forEach(function (item) {
          DOM.feed.appendChild(createCard(item));
        });

        updateEmptyState();
        updateSentinel();
      })
      .catch(function () {
        state.loading = false;
        hideSkeleton();
      });
  }

  /* ── Create notification card ── */
  function createCard(item) {
    var card = document.createElement('div');
    card.className = 'nv-notif-card' + (item.is_read ? ' read' : ' unread');
    card.dataset.id = item.id;

    var senderName = item.sender_display_name || item.actor_display_name || item.actor_username || 'Someone';
    var previewText = item.preview_text || item.body || '';
    var actionText = item.action_text || item.title || 'sent a notification';
    var openUrl = item.open_url || item.action_url || (item.actor_username ? '/profile/' + item.actor_username : '');
    var avatarUrl = item.sender_avatar_url || item.actor_avatar || '';

    var avatarHtml;
    if (avatarUrl) {
      avatarHtml = '<img src="' + esc(avatarUrl) + '" alt="" loading="lazy">';
    } else {
      var initial = (senderName || '?')[0].toUpperCase();
      avatarHtml = '<span class="nv-notif-avatar-fallback">' + esc(initial) + '</span>';
    }

    var unreadDot = item.is_read ? '' : '<div class="nv-notif-unread-dot"></div>';

    card.innerHTML =
      '<div class="nv-notif-avatar-wrap">' +
        avatarHtml + unreadDot +
      '</div>' +
      '<div class="nv-notif-body">' +
        '<p class="nv-notif-title"><strong>' + esc(senderName) + '</strong> ' + esc(actionText) + '</p>' +
        '<p class="nv-notif-preview">' + esc(previewText || '') + '</p>' +
        '<span class="nv-notif-time">' + timeAgo(item.created_at) + '</span>' +
      '</div>' +
      '<button class="nv-notif-delete-btn" data-nv-action="delete">✕</button>';

    /* ── Friend request: add accept/reject buttons ── */
    if (item.event_type === 'friend_request' || item.event_type === 'follow_request') {
      var actionsDiv = document.createElement('div');
      actionsDiv.className = 'nv-notif-actions';
      actionsDiv.innerHTML =
        '<button class="nv-notif-action-btn nv-action-accept" data-nv-action="accept" data-nv-type="' + esc(item.event_type) + '" data-request-id="' + esc(item.entity_id) + '" data-notif-id="' + esc(item.id) + '">✓ Accept</button>' +
        '<button class="nv-notif-action-btn nv-action-decline" data-nv-action="decline" data-nv-type="' + esc(item.event_type) + '" data-request-id="' + esc(item.entity_id) + '" data-notif-id="' + esc(item.id) + '">✕ Decline</button>';
      card.querySelector('.nv-notif-body').appendChild(actionsDiv);
    }

    /* ── Click: mark read + navigate ── */
    card.addEventListener('click', function (e) {
      var actBtn = e.target.closest('.nv-notif-action-btn');
      var delBtn = e.target.closest('.nv-notif-delete-btn');
      if (delBtn) { e.stopPropagation(); showDeleteConfirm(item.id, card); return; }
      if (actBtn) { e.stopPropagation(); handleAction(actBtn, item, card); return; }

      if (!item.is_read) markRead(item.id, card);
      if (openUrl) {
        setTimeout(function () { window.location.href = openUrl; }, 100);
      }
    });

    /* ── Long press for delete ── */
    card.addEventListener('touchstart', function () {
      deleteTimer = setTimeout(function () { card.classList.add('show-delete'); }, DELETE_DELAY);
    }, { passive: true });
    card.addEventListener('touchend', function () { clearTimeout(deleteTimer); deleteTimer = null; });
    card.addEventListener('touchmove', function () { clearTimeout(deleteTimer); deleteTimer = null; }, { passive: true });

    card.addEventListener('mousedown', function (e) {
      if (e.target.closest('.nv-notif-action-btn') || e.target.closest('.nv-notif-delete-btn')) return;
      deleteTimer = setTimeout(function () { card.classList.add('show-delete'); }, DELETE_DELAY);
    });
    card.addEventListener('mouseup', function () { clearTimeout(deleteTimer); deleteTimer = null; });
    card.addEventListener('mouseleave', function () { clearTimeout(deleteTimer); deleteTimer = null; });

    return card;
  }

  /* ── Mark read ── */
  function markRead(id, card) {
    fetch('/notifications/api/read/' + encodeURIComponent(id), {
      method: 'POST', credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.classList.remove('unread');
          card.classList.add('read');
          var dot = card.querySelector('.nv-notif-unread-dot');
          if (dot) dot.remove();
          updateBadge();
        }
      })
      .catch(function () {});
  }

  /* ── Mark all read ── */
  function onMarkAllRead() {
    fetch('/api/notifications/read-all', {
      method: 'POST', credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          document.querySelectorAll('.nv-notif-card.unread').forEach(function (c) {
            c.classList.remove('unread');
            c.classList.add('read');
            var dot = c.querySelector('.nv-notif-unread-dot');
            if (dot) dot.remove();
          });
          showToast('All marked as read');
          updateBadge();
        }
      })
      .catch(function () {});
  }

  /* ── Handle accept/decline actions ── */
  function handleAction(btn, item, card) {
    var action = btn.dataset.nvAction;
    var type = btn.dataset.nvType || 'friend_request';
    var requestId = btn.dataset.requestId;
    var notifId = btn.dataset.notifId || item.id;

    if (action === 'accept' && requestId) {
      btn.disabled = true; btn.textContent = '...';
      var url = type === 'follow_request'
        ? '/api/follow/approve/' + encodeURIComponent(requestId)
        : '/social/friends/accept';
      var fetchOpts = type === 'follow_request'
        ? { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': getCSRF() } }
        : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() }, body: JSON.stringify({request_id: requestId}) };
      fetch(url, fetchOpts)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok || data.success) {
            var actionsEl = card.querySelector('.nv-notif-actions');
            if (actionsEl) actionsEl.innerHTML = '<span style="font-size:13px;color:#22c55e;font-weight:600">✓ Approved</span>';
            markRead(notifId, card);
            showToast(type === 'follow_request' ? 'Follow request approved!' : 'Friend request accepted!');
            updateBadge();
          } else {
            btn.disabled = false; btn.textContent = 'Accept';
            showToast(data.error || 'Failed');
          }
        })
        .catch(function () { btn.disabled = false; btn.textContent = 'Accept'; showToast('Network error'); });
      return;
    }

    if (action === 'decline' && requestId) {
      btn.disabled = true; btn.textContent = '...';
      var url = type === 'follow_request'
        ? '/api/follow/decline/' + encodeURIComponent(requestId)
        : '/social/friends/decline';
      var fetchOpts = type === 'follow_request'
        ? { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': getCSRF() } }
        : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() }, body: JSON.stringify({request_id: requestId}) };
      fetch(url, fetchOpts)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok || data.success) {
            markRead(notifId, card);
            card.remove();
            showToast(type === 'follow_request' ? 'Follow request declined' : 'Friend request declined');
            updateBadge();
          } else {
            btn.disabled = false; btn.textContent = 'Decline';
            showToast(data.error || 'Failed');
          }
        })
        .catch(function () { btn.disabled = false; btn.textContent = 'Decline'; showToast('Network error'); });
      return;
    }
  }

  /* ── Delete ── */
  function showDeleteConfirm(notifId, card) {
    if (!DOM.deleteModal) return;
    DOM.deleteModal.hidden = false;
    DOM.deleteModal.dataset.notifId = notifId;
    DOM.deleteConfirm.onclick = function () {
      deleteNotification(notifId, card);
      DOM.deleteModal.hidden = true;
    };
    DOM.deleteCancel.onclick = function () { DOM.deleteModal.hidden = true; };
    DOM.deleteModal.addEventListener('click', function (e) {
      if (e.target === DOM.deleteModal) DOM.deleteModal.hidden = true;
    });
  }

  function deleteNotification(id, card) {
    fetch('/api/notifications/' + encodeURIComponent(id) + '/delete', {
      method: 'POST', credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.remove();
          state.items = state.items.filter(function (i) { return i.id !== id; });
          updateBadge();
          updateEmptyState();
          showToast('Notification deleted');
        }
      })
      .catch(function () {});
  }

  /* ── Badge update ── */
  function updateBadge() {
    fetch('/api/notifications/unread-count', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var count = data.count || 0;
        var navBadge = document.querySelector('.notif-count');
        if (navBadge) {
          if (count > 0) { navBadge.textContent = count > 99 ? '99+' : count; navBadge.style.display = ''; }
          else { navBadge.style.display = 'none'; }
        }
      })
      .catch(function () {});
  }

  /* ── Infinite scroll ── */
  function setupInfiniteScroll() {
    if (window.IntersectionObserver) {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !state.loading && state.hasMore) loadMore();
        });
      }, { rootMargin: '200px' });
      if (DOM.sentinel) obs.observe(DOM.sentinel);
    } else {
      window.addEventListener('scroll', function () {
        if (state.loading || !state.hasMore || !DOM.sentinel) return;
        var rect = DOM.sentinel.getBoundingClientRect();
        if (rect.top < window.innerHeight + 200) loadMore();
      }, { passive: true });
    }
  }

  function updateSentinel() {
    if (DOM.sentinel) DOM.sentinel.style.display = state.hasMore ? 'block' : 'none';
  }

  function loadMore() {
    if (state.loading || !state.hasMore) return;
    state.page++;
    fetchFeed(state.page, false);
  }

  /* ── UI helpers ── */
  function updateEmptyState() {
    if (state.items.length === 0 && DOM.skeleton && DOM.skeleton.style.display === 'none') {
      if (DOM.empty) DOM.empty.classList.remove('hidden');
    } else {
      if (DOM.empty) DOM.empty.classList.add('hidden');
    }
  }

  function showSkeleton() {
    if (DOM.skeleton) DOM.skeleton.style.display = 'flex';
    if (DOM.empty) DOM.empty.classList.add('hidden');
  }

  function hideSkeleton() {
    if (DOM.skeleton) DOM.skeleton.style.display = 'none';
    updateEmptyState();
  }

  function showToast(msg) {
    if (toastTimer) { clearTimeout(toastTimer); if (DOM.toastContainer) DOM.toastContainer.innerHTML = ''; }
    var el = document.createElement('div');
    el.className = 'nv-toast';
    el.textContent = msg;
    if (DOM.toastContainer) DOM.toastContainer.appendChild(el);
    toastTimer = setTimeout(function () { el.remove(); toastTimer = null; }, 3000);
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    var diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return new Date(dateStr).toLocaleDateString();
  }

  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function esc(str) {
    if (typeof str !== 'string') return str || '';
    return str.replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
