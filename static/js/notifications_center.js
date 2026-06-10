(function () {
  'use strict';

  var state = {
    tab: 'unread',
    page: 1,
    hasMore: true,
    loading: false,
    items: [],
    selected: new Set(),
    bulkMode: false,
    socket: null,
  };

  var DOM = {};
  var TOAST_TIMER = null;

  function init() {
    DOM.tabs = document.getElementById('notifCenterTabs');
    DOM.list = document.getElementById('notifCenterList');
    DOM.sentinel = document.getElementById('notifSentinel');
    DOM.skeleton = document.getElementById('notifSkeleton');
    DOM.emptyState = document.getElementById('notifEmptyState');
    DOM.markAllBtn = document.getElementById('markAllReadBtn');
    DOM.bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
    DOM.countLabel = document.getElementById('notifCountLabel');
    DOM.settingsBtn = document.getElementById('notifCenterSettings');
    DOM.toastContainer = document.getElementById('notifToastContainer');
    DOM.unreadBadge = document.getElementById('unreadTabBadge');

    DOM.tabs.addEventListener('click', onTabClick);
    DOM.markAllBtn.addEventListener('click', onMarkAllRead);
    DOM.bulkDeleteBtn.addEventListener('click', onBulkDelete);
    DOM.settingsBtn.addEventListener('click', toggleSettingsModal);

    setupInfiniteScroll();
    connectSocket();

    switchTab('unread');
    fetchUnreadCount();
    setInterval(fetchUnreadCount, 30000);
  }

  function onTabClick(e) {
    var btn = e.target.closest('.notif-tab');
    if (!btn) return;
    var tab = btn.dataset.tab;
    switchTab(tab);
  }

  function switchTab(tab) {
    state.tab = tab;
    state.page = 1;
    state.hasMore = true;
    state.items = [];
    state.selected.clear();
    updateBulkMode();

    document.querySelectorAll('.notif-tab').forEach(function (t) {
      t.classList.toggle('active', t.dataset.tab === tab);
    });

    showSkeleton();
    fetchTab(tab, 1, true);
  }

  function fetchTab(tab, page, replace) {
    if (state.loading) return;
    state.loading = true;

    var url = '/api/notifications/center/list?tab=' + encodeURIComponent(tab) + '&page=' + page;

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
          renderItems(state.items, true);
        } else {
          state.items = state.items.concat(data.items || []);
          renderItems(data.items || [], false);
        }
        updateCountLabel();
        updateEmptyState();
        updateInfiniteScroll();
      })
      .catch(function () {
        state.loading = false;
        hideSkeleton();
      });
  }

  function renderItems(items, replace) {
    if (replace) {
      DOM.list.innerHTML = '';
    }
    items.forEach(function (item) {
      var el = createCard(item);
      DOM.list.appendChild(el);
    });
  }

  function createCard(item) {
    var card = document.createElement('div');
    card.className = 'notif-card' + (item.is_read ? ' read' : ' unread');
    card.dataset.id = item.id;

    var isRead = item.is_read;

    var avatarHtml = '';
    if (item.actor_avatar) {
      avatarHtml = '<img src="' + escapeHtml(item.actor_avatar) + '" alt="' + escapeHtml(item.actor_username || '') + '" loading="lazy">';
    }
    var avatarContainer = item.actor_avatar
      ? '<div class="notif-card-avatar">' + avatarHtml + '</div>'
      : '<div class="notif-card-icon"><i class="fas ' + (item.icon || 'fa-bell') + '"></i></div>';

    var actionBtnHtml = '';
    if (!isRead) {
      actionBtnHtml = '<button class="notif-card-action-btn mark-read-btn" data-action="mark-read" title="Mark as read"><i class="fas fa-check"></i></button>';
    }

    var selectHtml = state.bulkMode
      ? '<input type="checkbox" class="notif-card-select" data-action="select" ' + (state.selected.has(item.id) ? 'checked' : '') + '>'
      : '';

    var dotHtml = isRead ? '' : '<span class="notif-card-dot"></span>';
    var unreadDot = isRead ? '' : '<div class="notif-unread-indicator"></div>';

    card.innerHTML =
      selectHtml +
      avatarContainer +
      '<div class="notif-card-body">' +
        '<p class="notif-card-title">' + escapeHtml(item.title || '') + '</p>' +
        '<p class="notif-card-preview">' + escapeHtml(item.body || '') + '</p>' +
        '<div class="notif-card-meta">' +
          '<span class="notif-card-timestamp">' + timeAgo(item.created_at) + '</span>' +
          dotHtml +
        '</div>' +
      '</div>' +
      '<div class="notif-card-actions">' + actionBtnHtml + '</div>' +
      unreadDot +
      '<div class="notif-card-swipe-bg">' +
        '<button class="notif-swipe-btn notif-swipe-read" data-action="swipe-read"><i class="fas fa-check"></i></button>' +
        '<button class="notif-swipe-btn notif-swipe-delete" data-action="swipe-delete"><i class="fas fa-trash"></i></button>' +
      '</div>';

    card.addEventListener('click', function (e) {
      var actionEl = e.target.closest('[data-action]');
      if (!actionEl) {
        if (state.bulkMode) {
          toggleSelect(card, item.id);
        } else {
          markRead(item.id, card);
        }
        return;
      }
      var action = actionEl.dataset.action;
      if (action === 'mark-read') {
        e.stopPropagation();
        markRead(item.id, card);
      } else if (action === 'select') {
        e.stopPropagation();
        toggleSelect(card, item.id);
      } else if (action === 'swipe-read') {
        e.stopPropagation();
        markRead(item.id, card);
      } else if (action === 'swipe-delete') {
        e.stopPropagation();
        deleteSingle(item.id, card);
      }
    });

    setupSwipe(card, item);

    return card;
  }

  function markRead(id, card) {
    fetch('/api/notifications/center/read/' + id, { method: 'POST', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.classList.remove('unread');
          card.classList.add('read');
          var dot = card.querySelector('.notif-unread-indicator');
          if (dot) dot.remove();
          var actionBtn = card.querySelector('[data-action="mark-read"]');
          if (actionBtn) actionBtn.remove();
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

  function deleteSingle(id, card) {
    fetch('/api/notifications/center/delete/' + id, { method: 'POST', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          card.remove();
          showToast('Notification deleted');
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

  function toggleSelect(card, id) {
    if (state.selected.has(id)) {
      state.selected.delete(id);
      card.classList.remove('selected');
    } else {
      state.selected.add(id);
      card.classList.add('selected');
    }
    updateBulkMode();
  }

  function updateBulkMode() {
    var prev = state.bulkMode;
    state.bulkMode = state.selected.size > 0;
    if (prev !== state.bulkMode) {
      rerender();
    }
    DOM.bulkDeleteBtn.classList.toggle('hidden', state.selected.size === 0);
    DOM.bulkDeleteBtn.textContent = 'Delete selected (' + state.selected.size + ')';
  }

  function onMarkAllRead() {
    fetch('/api/notifications/center/read-all', { method: 'POST', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          document.querySelectorAll('.notif-card.unread').forEach(function (c) {
            c.classList.remove('unread');
            c.classList.add('read');
            var dot = c.querySelector('.notif-unread-indicator');
            if (dot) dot.remove();
            var btn = c.querySelector('[data-action="mark-read"]');
            if (btn) btn.remove();
          });
          showToast('All marked as read');
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

  function onBulkDelete() {
    var ids = Array.from(state.selected);
    if (!ids.length) return;
    fetch('/api/notifications/center/delete-selected', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ ids: ids }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          ids.forEach(function (id) {
            var card = document.querySelector('.notif-card[data-id="' + id + '"]');
            if (card) card.remove();
          });
          state.selected.clear();
          updateBulkMode();
          showToast('Notifications deleted');
          fetchUnreadCount();
        }
      })
      .catch(function () {});
  }

  function onMarkReadClick(id, card) {
    markRead(id, card);
  }

  function setupInfiniteScroll() {
    if (!window.IntersectionObserver) {
      window.addEventListener('scroll', function () {
        if (state.loading || !state.hasMore) return;
        var rect = DOM.sentinel.getBoundingClientRect();
        if (rect.top < window.innerHeight + 200) {
          loadMore();
        }
      }, { passive: true });
      return;
    }
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !state.loading && state.hasMore) {
          loadMore();
        }
      });
    }, { rootMargin: '200px' });
    obs.observe(DOM.sentinel);
  }

  function loadMore() {
    if (state.loading || !state.hasMore) return;
    state.page++;
    fetchTab(state.tab, state.page, false);
  }

  function updateInfiniteScroll() {
    if (!state.hasMore) {
      DOM.sentinel.style.display = 'none';
    } else {
      DOM.sentinel.style.display = 'block';
    }
  }

  function updateCountLabel() {
    var total = state.items.length;
    DOM.countLabel.textContent = total + ' notification' + (total !== 1 ? 's' : '');
  }

  function updateEmptyState() {
    if (state.items.length === 0 && !DOM.skeleton.style.display !== 'none') {
      DOM.emptyState.classList.remove('hidden');
    } else {
      DOM.emptyState.classList.add('hidden');
    }
  }

  function showSkeleton() {
    DOM.skeleton.style.display = 'flex';
    DOM.emptyState.classList.add('hidden');
  }

  function hideSkeleton() {
    DOM.skeleton.style.display = 'none';
  }

  function fetchUnreadCount() {
    fetch('/api/notifications/center/unread-count', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.count !== undefined && DOM.unreadBadge) {
          if (data.count > 0) {
            DOM.unreadBadge.textContent = data.count > 99 ? '99+' : data.count;
            DOM.unreadBadge.classList.remove('hidden');
          } else {
            DOM.unreadBadge.classList.add('hidden');
          }
        }
      })
      .catch(function () {});
  }

  function connectSocket() {
    if (typeof io === 'undefined') return;
    try {
      state.socket = io();
      state.socket.on('notification:new', function (payload) {
        if (state.tab === 'unread' || state.tab === 'all') {
          var el = createCard(payload);
          DOM.list.insertBefore(el, DOM.list.firstChild);
          state.items.unshift(payload);
          updateCountLabel();
        }
        fetchUnreadCount();
      });
    } catch (e) {}
  }

  function setupSwipe(card, item) {
    var startX = 0;
    var currentX = 0;
    var isSwiping = false;

    card.addEventListener('touchstart', function (e) {
      startX = e.touches[0].clientX;
      isSwiping = false;
    }, { passive: true });

    card.addEventListener('touchmove', function (e) {
      currentX = e.touches[0].clientX;
      var diff = startX - currentX;
      if (diff > 10) {
        isSwiping = true;
        card.classList.add('swiping');
        var content = card.querySelector('.notif-card-body, .notif-card-avatar, .notif-card-icon, .notif-card-actions, .notif-unread-indicator, .notif-card-select');
        card.querySelectorAll('.notif-card-body, .notif-card-avatar, .notif-card-icon, .notif-card-actions, .notif-unread-indicator, .notif-card-select').forEach(function (el) {
          el.style.transform = 'translateX(' + (-Math.min(diff, 100)) + 'px)';
        });
      }
    }, { passive: true });

    card.addEventListener('touchend', function () {
      if (!isSwiping) return;
      var diff = startX - currentX;
      card.classList.remove('swiping');
      card.querySelectorAll('.notif-card-body, .notif-card-avatar, .notif-card-icon, .notif-card-actions, .notif-unread-indicator, .notif-card-select').forEach(function (el) {
        el.style.transform = '';
      });
      if (diff > 60) {
        if (!item.is_read) {
          markRead(item.id, card);
        } else {
          deleteSingle(item.id, card);
        }
      }
      isSwiping = false;
    }, { passive: true });

    card.addEventListener('click', function (e) {
      if (isSwiping) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  }

  function toggleSettingsModal() {
    var existing = document.querySelector('.notif-settings-modal');
    if (existing) {
      existing.remove();
      return;
    }

    fetch('/api/notifications/center/preferences', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var prefs = data.preferences || {};
        renderSettingsModal(prefs);
      })
      .catch(function () {
        renderSettingsModal({});
      });
  }

  function renderSettingsModal(prefs) {
    var modal = document.createElement('div');
    modal.className = 'notif-settings-modal';
    modal.addEventListener('click', function (e) {
      if (e.target === modal) modal.remove();
    });

    var muted = prefs.muted_types || [];
    var email = prefs.email_enabled !== false;
    var push = prefs.push_enabled !== false;
    var inApp = prefs.in_app_enabled !== false;
    var sms = prefs.sms_enabled === true;

    var muteRows = '';
    var types = [
      'follow', 'follow_accepted', 'mention', 'comment', 'reply',
      'post_like', 'reel_like', 'story_reaction', 'story_mention',
      'live_started', 'creator_subscription', 'wallet_transfer',
      'wallet_received', 'dating_match', 'verification_approved',
      'security_alert', 'system_announcement', 'new_message', 'message_reaction',
    ];
    types.forEach(function (t) {
      var isMuted = muted.indexOf(t) !== -1;
      muteRows +=
        '<div class="notif-settings-row">' +
          '<span class="notif-settings-label">' + escapeHtml(t.replace(/_/g, ' ').replace(/\b\w/g, function (l) { return l.toUpperCase(); })) + '</span>' +
          '<button class="notif-settings-toggle' + (!isMuted ? ' active' : '') + '" data-mute-type="' + escapeHtml(t) + '"></button>' +
        '</div>';
    });

    modal.innerHTML =
      '<div class="notif-settings-panel">' +
        '<h3>Notification Settings</h3>' +
        '<p class="notif-settings-desc">Customize how and when you receive notifications.</p>' +
        '<div class="notif-settings-group">' +
          '<h4>Delivery Channels</h4>' +
          '<div class="notif-settings-row">' +
            '<span class="notif-settings-label">In-App</span>' +
            '<button class="notif-settings-toggle' + (inApp ? ' active' : '') + '" data-pref="in_app_enabled"></button>' +
          '</div>' +
          '<div class="notif-settings-row">' +
            '<span class="notif-settings-label">Push</span>' +
            '<button class="notif-settings-toggle' + (push ? ' active' : '') + '" data-pref="push_enabled"></button>' +
          '</div>' +
          '<div class="notif-settings-row">' +
            '<span class="notif-settings-label">Email</span>' +
            '<button class="notif-settings-toggle' + (email ? ' active' : '') + '" data-pref="email_enabled"></button>' +
          '</div>' +
          '<div class="notif-settings-row">' +
            '<span class="notif-settings-label">SMS <span style="color:var(--chain-muted,#888);font-size:11px;">(Coming soon)</span></span>' +
            '<button class="notif-settings-toggle' + (sms ? ' active' : '') + '" data-pref="sms_enabled"></button>' +
          '</div>' +
        '</div>' +
        '<div class="notif-settings-group">' +
          '<h4>Muted Types</h4>' +
          muteRows +
        '</div>' +
        '<button class="notif-settings-close">Close</button>' +
      '</div>';

    modal.addEventListener('click', function (e) {
      var toggle = e.target.closest('.notif-settings-toggle');
      if (toggle) {
        toggle.classList.toggle('active');
        savePreferencesFromModal(modal);
        return;
      }
      if (e.target.closest('.notif-settings-close')) {
        modal.remove();
      }
    });

    document.body.appendChild(modal);
  }

  function savePreferencesFromModal(modal) {
    var prefs = {
      email_enabled: !!modal.querySelector('[data-pref="email_enabled"].active'),
      push_enabled: !!modal.querySelector('[data-pref="push_enabled"].active'),
      in_app_enabled: !!modal.querySelector('[data-pref="in_app_enabled"].active'),
      sms_enabled: !!modal.querySelector('[data-pref="sms_enabled"].active'),
      muted_types: [],
    };
    modal.querySelectorAll('[data-mute-type]').forEach(function (btn) {
      if (!btn.classList.contains('active')) {
        prefs.muted_types.push(btn.dataset.muteType);
      }
    });
    fetch('/api/notifications/center/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(prefs),
    }).catch(function () {});
  }

  function rerender() {
    DOM.list.innerHTML = '';
    state.items.forEach(function (item) {
      DOM.list.appendChild(createCard(item));
    });
    updateEmptyState();
  }

  function showToast(msg) {
    if (TOAST_TIMER) {
      clearTimeout(TOAST_TIMER);
      DOM.toastContainer.innerHTML = '';
    }
    var el = document.createElement('div');
    el.className = 'notif-toast';
    el.textContent = msg;
    DOM.toastContainer.appendChild(el);
    TOAST_TIMER = setTimeout(function () {
      el.remove();
      TOAST_TIMER = null;
    }, 3000);
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    var now = new Date();
    var date = new Date(dateStr);
    var diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return date.toLocaleDateString();
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return str || '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
