(function () {
  'use strict';

  var state = {
    filter: 'all',
    page: 1,
    hasMore: true,
    loading: false,
    items: [],
    socket: null,
  };

  var DOM = {};
  var toastTimer = null;

  var FILTER_API_MAP = {
    all: 'all',
    unread: 'unread',
    requests: 'activity',
  };

  function init() {
    DOM.header = document.getElementById('nvNotifsHeader');
    DOM.title = document.getElementById('nvNotifsTitle');
    DOM.unreadCount = document.getElementById('nvUnreadCount');
    DOM.filters = document.getElementById('nvFilters');
    DOM.feed = document.getElementById('nvFeed');
    DOM.sentinel = document.getElementById('nvSentinel');
    DOM.skeleton = document.getElementById('nvSkeleton');
    DOM.empty = document.getElementById('nvEmpty');
    DOM.markAllBtn = document.getElementById('nvMarkAllBtn');
    DOM.settingsBtn = document.getElementById('nvSettingsBtn');
    DOM.toastContainer = document.getElementById('nvToastContainer');

    DOM.filters.addEventListener('click', onFilterClick);
    if (DOM.markAllBtn) DOM.markAllBtn.addEventListener('click', onMarkAllRead);
    if (DOM.settingsBtn) DOM.settingsBtn.addEventListener('click', toggleSettings);

    setupInfiniteScroll();
    connectSocket();

    switchFilter('all');
    fetchUnreadCount();
    setInterval(fetchUnreadCount, 30000);
  }

  function onFilterClick(e) {
    var pill = e.target.closest('.nv-filter-pill');
    if (!pill) return;
    switchFilter(pill.dataset.filter);
  }

  function switchFilter(filter) {
    state.filter = filter;
    state.page = 1;
    state.hasMore = true;
    state.items = [];

    document.querySelectorAll('.nv-filter-pill').forEach(function (p) {
      p.classList.toggle('active', p.dataset.filter === filter);
    });

    showSkeleton();
    fetchFeed(filter, 1, true);
  }

  function fetchFeed(filter, page, replace) {
    if (state.loading) return;
    state.loading = true;

    var apiFilter = FILTER_API_MAP[filter] || 'all';
    var url = '/api/notifications?tab=' + encodeURIComponent(apiFilter) + '&page=' + page;

    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.loading = false;
        if (!data.ok) {
          showSkeleton();
          return;
        }
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
        updateInfiniteScroll();
      })
      .catch(function () {
        state.loading = false;
        hideSkeleton();
      });
  }

  function createCard(item) {
    if (item.grouped) return createGroupedCard(item);

    var card = document.createElement('div');
    card.className = 'nv-notif-card' + (item.is_read ? ' read' : ' unread');
    card.dataset.id = item.id;

    var avatarHtml = '';
    if (item.actor_avatar) {
      avatarHtml = '<img src="' + esc(item.actor_avatar) + '" alt="' + esc(item.actor_username || '') + '" loading="lazy">';
    }
    var avatarBlock = item.actor_avatar
      ? '<div class="nv-notif-avatar">' + avatarHtml + '</div>'
      : '<div class="nv-notif-avatar"><i class="fas ' + (item.icon || 'fa-bell') + '"></i></div>';

    var unreadDot = item.is_read ? '' : '<div class="nv-notif-unread-dot"></div>';
    var rightDot = item.is_read ? '' : '<div class="nv-notif-right-dot"></div>';

    var actionHtml = buildActions(item);
    var actionUrl = item.action_url || '';

    card.innerHTML =
      '<div class="nv-notif-avatar-wrap" style="position:relative;flex-shrink:0">' +
        avatarBlock + unreadDot +
      '</div>' +
      '<div class="nv-notif-body">' +
        '<p class="nv-notif-title">' + esc(item.title || '') + '</p>' +
        '<p class="nv-notif-preview">' + esc(item.body || '') + '</p>' +
        '<span class="nv-notif-time">' + timeAgo(item.created_at) + '</span>' +
        actionHtml +
      '</div>' +
      rightDot;

    card.addEventListener('click', function (e) {
      var actBtn = e.target.closest('.nv-notif-action-btn');
      if (actBtn) {
        e.stopPropagation();
        handleAction(actBtn, item, card);
        return;
      }

      if (actionUrl) {
        window.location.href = actionUrl;
      } else if (!item.is_read) {
        markRead(item.id, card);
      }
    });

    return card;
  }

  function createGroupedCard(item) {
    var card = document.createElement('div');
    card.className = 'nv-notif-card' + (item.is_read ? ' read' : ' unread');
    card.dataset.id = item.id;
    card.dataset.grouped = 'true';

    var avatars = '';
    if (item.actor_avatars && item.actor_avatars.length > 0) {
      var maxShow = Math.min(item.actor_avatars.length, 3);
      avatars = '<div class="nv-avatar-stack">';
      for (var i = 0; i < maxShow; i++) {
        avatars += '<div class="nv-avatar-stack-item" style="z-index:' + (maxShow - i) + ';margin-left:' + (i > 0 ? '-12px' : '0') + '"><img src="' + esc(item.actor_avatars[i]) + '" alt=""></div>';
      }
      if (item.actor_count > maxShow) {
        avatars += '<div class="nv-avatar-stack-item nv-avatar-stack-more" style="z-index:0;margin-left:-12px">+' + (item.actor_count - maxShow) + '</div>';
      }
      avatars += '</div>';
    }

    var groupBadge = item.group_count > 1 ? '<span class="nv-group-count">' + item.group_count + '</span>' : '';
    var unreadDot = item.is_read ? '' : '<div class="nv-notif-unread-dot"></div>';

    card.innerHTML =
      '<div class="nv-notif-avatar-wrap" style="position:relative;flex-shrink:0">' +
        (avatars || '<div class="nv-notif-avatar"><i class="fas fa-bell"></i></div>') +
        unreadDot +
      '</div>' +
      '<div class="nv-notif-body">' +
        '<p class="nv-notif-title">' + esc(item.title || '') + '</p>' +
        (item.body ? '<p class="nv-notif-preview">' + esc(item.body) + '</p>' : '') +
        '<span class="nv-notif-time">' + timeAgo(item.latest_created_at || item.created_at) + '</span>' +
        groupBadge +
      '</div>' +
      (item.is_read ? '' : '<div class="nv-notif-right-dot"></div>');

    card.addEventListener('click', function (e) {
      if (item.action_url) {
        window.location.href = item.action_url;
      } else if (!item.is_read) {
        markGroupRead(item, card);
      }
    });

    return card;
  }

  function markGroupRead(item, card) {
    var ids = item.notification_ids || [item.id];
    fetch('/api/notifications/read-group', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ ids: ids }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.classList.remove('unread');
          card.classList.add('read');
          var dot = card.querySelector('.nv-notif-unread-dot');
          if (dot) dot.remove();
          var rdot = card.querySelector('.nv-notif-right-dot');
          if (rdot) rdot.remove();
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

  function buildActions(item) {
    if ((item.event_type === 'friend_request' || item.event_type === 'follow_request') && item.entity_id) {
      return (
        '<div class="nv-notif-actions">' +
          '<button class="nv-notif-action-btn nv-action-accept" data-nv-action="accept" data-nv-type="' + item.event_type + '" data-request-id="' + esc(item.entity_id) + '" data-notif-id="' + esc(item.id) + '"><i class="fas fa-check"></i> Approve</button>' +
          '<button class="nv-notif-action-btn nv-action-decline" data-nv-action="decline" data-nv-type="' + item.event_type + '" data-request-id="' + esc(item.entity_id) + '" data-notif-id="' + esc(item.id) + '"><i class="fas fa-times"></i> Decline</button>' +
          '<a href="/profile/@' + esc(item.actor_username || '') + '" class="nv-notif-action-btn nv-action-profile"><i class="fas fa-user"></i> Profile</a>' +
        '</div>'
      );
    }

    if (item.event_type === 'friend_request_accepted' || item.event_type === 'friend_accepted' || item.event_type === 'follow_request_approved') {
      return (
        '<div class="nv-notif-actions">' +
          '<a href="/messages/" class="nv-notif-action-btn nv-action-message"><i class="fas fa-comment"></i> Message</a>' +
          '<a href="/profile/@' + esc(item.actor_username || '') + '" class="nv-notif-action-btn nv-action-profile"><i class="fas fa-user"></i> Profile</a>' +
        '</div>'
      );
    }

    return '';
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function handleAction(btn, item, card) {
    var action = btn.dataset.nvAction;
    var type = btn.dataset.nvType || 'friend_request';
    var requestId = btn.dataset.requestId;
    var notifId = btn.dataset.notifId || item.id;

    if (action === 'accept' && requestId) {
      btn.disabled = true;
      btn.textContent = '...';
      var url, fetchOpts;
      if (type === 'follow_request') {
        url = '/api/follow/approve/' + encodeURIComponent(requestId);
        fetchOpts = { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': getCsrfToken() } };
      } else {
        url = '/social/friends/accept';
        fetchOpts = { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() }, body: JSON.stringify({request_id: requestId}) };
      }
      fetch(url, fetchOpts)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok || data.success) {
            card.querySelector('.nv-notif-actions').innerHTML =
              '<div class="nv-notif-actions">' +
                '<span style="font-size:13px;color:#2ecc71;font-weight:600"><i class="fas fa-check-circle"></i> Approved</span>' +
              '</div>';
            var dot = card.querySelector('.nv-notif-unread-dot');
            if (dot) dot.remove();
            card.classList.remove('unread');
            card.classList.add('read');
            markRead(notifId, card);
            showToast(type === 'follow_request' ? 'Follow request approved!' : 'Friend request accepted!');
            fetchUnreadCount();
          } else {
            btn.disabled = false;
            btn.textContent = 'Approve';
            showToast(data.error || 'Failed to approve');
          }
        })
        .catch(function () {
          btn.disabled = false;
          btn.textContent = 'Approve';
          showToast('Network error');
        });
      return;
    }

    if (action === 'decline' && requestId) {
      btn.disabled = true;
      btn.textContent = '...';
      var url, fetchOpts;
      if (type === 'follow_request') {
        url = '/api/follow/decline/' + encodeURIComponent(requestId);
        fetchOpts = { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': getCsrfToken() } };
      } else {
        url = '/social/friends/decline';
        fetchOpts = { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() }, body: JSON.stringify({request_id: requestId}) };
      }
      fetch(url, fetchOpts)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok || data.success) {
            card.remove();
            showToast(type === 'follow_request' ? 'Follow request declined' : 'Friend request declined');
            fetchUnreadCount();
          } else {
            btn.disabled = false;
            btn.textContent = 'Decline';
            showToast(data.error || 'Failed to decline');
          }
        })
        .catch(function () {
          btn.disabled = false;
          btn.textContent = 'Decline';
          showToast('Network error');
        });
      return;
    }
  }

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
          var rdot = card.querySelector('.nv-notif-right-dot');
          if (rdot) rdot.remove();
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

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
            var rdot = c.querySelector('.nv-notif-right-dot');
            if (rdot) rdot.remove();
          });
          showToast('All marked as read');
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

  function fetchUnreadCount() {
    fetch('/api/notifications/unread-count', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var count = data.count || 0;
        if (DOM.unreadCount) {
          if (count > 0) {
            DOM.unreadCount.textContent = count + ' new';
            DOM.unreadCount.classList.remove('hidden');
          } else {
            DOM.unreadCount.classList.add('hidden');
          }
        }
        var navBadge = document.querySelector('.notif-count');
        if (navBadge) {
          if (count > 0) {
            navBadge.textContent = count > 99 ? '99+' : count;
            navBadge.style.display = '';
          } else {
            navBadge.style.display = 'none';
          }
        }
      })
      .catch(function () {});
  }

  function updateEmptyState() {
    if (state.items.length === 0 && DOM.skeleton.style.display === 'none') {
      DOM.empty.classList.remove('hidden');
    } else {
      DOM.empty.classList.add('hidden');
    }
  }

  function showSkeleton() {
    DOM.skeleton.style.display = 'flex';
    DOM.empty.classList.add('hidden');
  }

  function hideSkeleton() {
    DOM.skeleton.style.display = 'none';
    updateEmptyState();
  }

  function setupInfiniteScroll() {
    if (window.IntersectionObserver) {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !state.loading && state.hasMore) {
            loadMore();
          }
        });
      }, { rootMargin: '200px' });
      obs.observe(DOM.sentinel);
    } else {
      window.addEventListener('scroll', function () {
        if (state.loading || !state.hasMore) return;
        var rect = DOM.sentinel.getBoundingClientRect();
        if (rect.top < window.innerHeight + 200) {
          loadMore();
        }
      }, { passive: true });
    }
  }

  function updateInfiniteScroll() {
    DOM.sentinel.style.display = state.hasMore ? 'block' : 'none';
  }

  function loadMore() {
    if (state.loading || !state.hasMore) return;
    state.page++;
    fetchFeed(state.filter, state.page, false);
  }

  function connectSocket() {
    if (typeof io === 'undefined') return;
    try {
      state.socket = io();
      state.socket.on('notification:new', function (payload) {
        if (state.filter === 'all' || state.filter === 'unread') {
          var el = createCard(payload);
          el.classList.add('nv-new');
          DOM.feed.insertBefore(el, DOM.feed.firstChild);
          state.items.unshift(payload);
          DOM.empty.classList.add('hidden');
          setTimeout(function () { el.classList.remove('nv-new'); }, 500);
        }
        fetchUnreadCount();
      });
    } catch (e) {}
  }

  function toggleSettings() {
    var existing = document.querySelector('.nv-settings-overlay');
    if (existing) { existing.remove(); return; }

    fetch('/api/notifications/preferences', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) { renderSettings(data.preferences || {}); })
      .catch(function () { renderSettings({}); });
  }

  function renderSettings(prefs) {
    var overlay = document.createElement('div');
    overlay.className = 'nv-settings-overlay';
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });

    var muted = prefs.muted_types || [];
    var email = prefs.email_enabled !== false;
    var push = prefs.push_enabled !== false;
    var inApp = prefs.in_app_enabled !== false;
    var sms = prefs.sms_enabled === true;

    var muteRows = '';
    var types = ['follow','mention','comment','reply','post_like','live_started','wallet_transfer','security_alert','system_announcement'];
    types.forEach(function (t) {
      var isMuted = muted.indexOf(t) !== -1;
      muteRows +=
        '<div class="nv-settings-row">' +
          '<span class="nv-settings-label">' + esc(t.replace(/_/g, ' ').replace(/\b\w/g, function(l){ return l.toUpperCase(); })) + '</span>' +
          '<button class="nv-toggle' + (!isMuted ? ' active' : '') + '" data-mute="' + t + '"></button>' +
        '</div>';
    });

    overlay.innerHTML =
      '<div class="nv-settings-drawer">' +
        '<div class="nv-settings-header">' +
          '<h3>Notification Settings</h3>' +
          '<button class="nv-settings-close"><i class="fas fa-times"></i></button>' +
        '</div>' +
        '<div class="nv-settings-section">' +
          '<h4>Delivery</h4>' +
          '<div class="nv-settings-row"><span class="nv-settings-label">In-App</span><button class="nv-toggle' + (inApp ? ' active' : '') + '" data-pref="in_app_enabled"></button></div>' +
          '<div class="nv-settings-row"><span class="nv-settings-label">Push</span><button class="nv-toggle' + (push ? ' active' : '') + '" data-pref="push_enabled"></button></div>' +
          '<div class="nv-settings-row"><span class="nv-settings-label">Email</span><button class="nv-toggle' + (email ? ' active' : '') + '" data-pref="email_enabled"></button></div>' +
        '</div>' +
        '<div class="nv-settings-section">' +
          '<h4>Muted Types</h4>' +
          muteRows +
        '</div>' +
      '</div>';

    overlay.addEventListener('click', function (e) {
      var toggle = e.target.closest('.nv-toggle');
      if (toggle) {
        toggle.classList.toggle('active');
        savePrefs(overlay);
        return;
      }
      if (e.target.closest('.nv-settings-close')) {
        overlay.remove();
      }
    });

    document.body.appendChild(overlay);
  }

  function savePrefs(overlay) {
    var prefs = {
      email_enabled: !!overlay.querySelector('[data-pref="email_enabled"].active'),
      push_enabled: !!overlay.querySelector('[data-pref="push_enabled"].active'),
      in_app_enabled: !!overlay.querySelector('[data-pref="in_app_enabled"].active'),
      muted_types: [],
    };
    overlay.querySelectorAll('[data-mute]').forEach(function (btn) {
      if (!btn.classList.contains('active')) prefs.muted_types.push(btn.dataset.mute);
    });
    fetch('/api/notifications/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(prefs),
    }).catch(function () {});
  }

  function showToast(msg) {
    if (toastTimer) { clearTimeout(toastTimer); DOM.toastContainer.innerHTML = ''; }
    var el = document.createElement('div');
    el.className = 'nv-toast';
    el.textContent = msg;
    DOM.toastContainer.appendChild(el);
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
