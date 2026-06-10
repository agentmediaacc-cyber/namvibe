(function () {
  'use strict';

  var S = { tab: 'all', page: 1, hasMore: true, loading: false, items: [], selected: [], socket: null };
  var D = {};
  var _toastTimer = null;

  var API = '/api/notifications';

  function init() {
    D.tabs = document.getElementById('notifTabs');
    D.list = document.getElementById('notifList');
    D.sentinel = document.getElementById('notifSentinel');
    D.skeleton = document.getElementById('notifSkeleton');
    D.empty = document.getElementById('notifEmpty');
    D.markAllBtn = document.getElementById('markAllReadBtn');
    D.bulkBtn = document.getElementById('bulkDeleteBtn');
    D.count = document.getElementById('notifCount');
    D.prefsBtn = document.getElementById('prefsBtn');
    D.toasts = document.getElementById('notifToasts');
    D.unreadBadge = document.getElementById('unreadBadge');
    D.overlay = document.getElementById('prefsOverlay');
    D.drawer = document.getElementById('prefsDrawer');
    D.prefsClose = document.getElementById('prefsClose');

    D.tabs.addEventListener('click', onTabClick);
    D.markAllBtn.addEventListener('click', onMarkAllRead);
    D.bulkBtn.addEventListener('click', onBulkDelete);
    D.prefsBtn.addEventListener('click', openPrefs);
    if (D.prefsClose) D.prefsClose.addEventListener('click', closePrefs);
    if (D.overlay) D.overlay.addEventListener('click', function (e) { if (e.target === D.overlay) closePrefs(); });

    setupScroll();
    connectSocket();
    switchTab('all');
    fetchUnread();
  }

  function onTabClick(e) {
    var btn = e.target.closest('.notif-premium-tab');
    if (!btn) return;
    switchTab(btn.dataset.tab);
  }

  function switchTab(tab) {
    S.tab = tab; S.page = 1; S.hasMore = true; S.items = []; S.selected = [];
    D.tabs.querySelectorAll('.notif-premium-tab').forEach(function (t) {
      t.classList.toggle('is-active', t.dataset.tab === tab);
    });
    D.bulkBtn.classList.add('hidden');
    showSkeleton();
    fetchTab(tab, 1, true);
  }

  function fetchTab(tab, page, replace) {
    if (S.loading) return;
    S.loading = true;
    var url = API + '?tab=' + encodeURIComponent(tab) + '&page=' + page;
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        S.loading = false;
        if (!d.ok) { showSkeleton(); return; }
        hideSkeleton();
        S.hasMore = !!d.has_more;
        if (replace) { S.items = d.items || []; D.list.innerHTML = ''; }
        else {
          var newItems = d.items || [];
          S.items = S.items.concat(newItems);
          if (S.items.length > 500) S.items = S.items.slice(-500);
        }
        (d.items || []).forEach(function (item) { D.list.appendChild(buildCard(item)); });
        updateCount();
        D.empty.classList.toggle('hidden', S.items.length > 0);
        if (!S.hasMore) D.sentinel.style.display = 'none';
        else D.sentinel.style.display = 'block';
      })
      .catch(function () { S.loading = false; hideSkeleton(); });
  }

  function buildCard(item) {
    var c = document.createElement('div');
    c.className = 'notif-card' + (item.is_read ? ' read' : ' unread');
    c.dataset.id = item.id;

    var avatarHtml = item.actor_avatar
      ? '<img src="' + esc(item.actor_avatar) + '" alt="' + esc(item.actor_username||'') + '" loading="lazy">'
      : '';
    var avatarBlock = item.actor_avatar
      ? '<div class="notif-card-avatar">' + avatarHtml + '</div>'
      : '<div class="notif-card-icon"><i class="fas ' + (item.icon||'fa-bell') + '"></i></div>';

    var actionBtn = item.is_read ? '' : '<button class="notif-card-action mark-read" data-act="read"><i class="fas fa-check"></i></button>';
    var unreadDot = item.is_read ? '' : '<div class="notif-unread-dot"></div>';
    var checkBox = '<input type="checkbox" class="notif-card-check" data-act="select" ' + (S.selected.indexOf(item.id) !== -1 ? 'checked' : '') + '>';

    c.innerHTML =
      checkBox +
      avatarBlock +
      '<div class="notif-card-body">' +
        '<p class="notif-card-title">' + esc(item.title||'') + '</p>' +
        '<p class="notif-card-preview">' + esc(item.body||item.preview||'') + '</p>' +
        '<div class="notif-card-meta">' +
          '<span class="notif-card-timestamp">' + timeAgo(item.created_at) + '</span>' +
          '<span class="notif-card-dot"></span>' +
        '</div>' +
      '</div>' +
      '<div class="notif-card-actions">' + actionBtn + '</div>' +
      unreadDot +
      '<div class="notif-swipe-bg">' +
        '<button class="n-swipe-btn n-swipe-read" data-act="swipe-read"><i class="fas fa-check"></i></button>' +
        '<button class="n-swipe-btn n-swipe-delete" data-act="swipe-delete"><i class="fas fa-trash-alt"></i></button>' +
      '</div>';

    c.addEventListener('click', function (e) {
      var a = e.target.closest('[data-act]');
      if (!a) { toggleCard(c, item.id); return; }
      e.stopPropagation();
      if (a.dataset.act === 'read') mark(item.id, c);
      else if (a.dataset.act === 'select') toggleCard(c, item.id);
      else if (a.dataset.act === 'swipe-read') mark(item.id, c);
      else if (a.dataset.act === 'swipe-delete') del(item.id, c);
    });

    setupTouch(c, item);
    return c;
  }

  function mark(id, card) {
    fetch(API + '/' + id + '/read', { method: 'POST', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          card.classList.remove('unread'); card.classList.add('read');
          var dot = card.querySelector('.notif-unread-dot'); if (dot) dot.remove();
          var btn = card.querySelector('[data-act="read"]'); if (btn) btn.remove();
          fetchUnread();
        }
      }).catch(function () {});
  }

  function del(id, card) {
    fetch(API + '/' + id + '/delete', { method: 'POST', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) { card.remove(); toast('Deleted'); fetchUnread(); }
      }).catch(function () {});
  }

  function toggleCard(card, id) {
    var idx = S.selected.indexOf(id);
    if (idx !== -1) { S.selected.splice(idx, 1); card.classList.remove('selected'); }
    else { S.selected.push(id); card.classList.add('selected'); }
    D.bulkBtn.classList.toggle('hidden', S.selected.length === 0);
    D.bulkBtn.textContent = 'Delete selected (' + S.selected.length + ')';
  }

  function onMarkAllRead() {
    fetch(API + '/read-all', { method: 'POST', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) return;
        D.list.querySelectorAll('.notif-card.unread').forEach(function (c) {
          c.classList.remove('unread'); c.classList.add('read');
          var dot = c.querySelector('.notif-unread-dot'); if (dot) dot.remove();
          var btn = c.querySelector('[data-act="read"]'); if (btn) btn.remove();
        });
        toast('All marked as read'); fetchUnread();
      }).catch(function () {});
  }

  function onBulkDelete() {
    var ids = S.selected.slice();
    if (!ids.length) return;
    fetch(API + '/delete-selected', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify({ ids: ids }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) return;
        ids.forEach(function (id) {
          var el = D.list.querySelector('.notif-card[data-id="' + id + '"]');
          if (el) el.remove();
        });
        S.selected = []; D.bulkBtn.classList.add('hidden'); toast('Deleted'); fetchUnread();
      }).catch(function () {});
  }

  function fetchUnread() {
    fetch(API + '/unread-count', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.count !== undefined && D.unreadBadge) {
          if (d.count > 0) {
            D.unreadBadge.textContent = d.count > 99 ? '99+' : d.count;
            D.unreadBadge.classList.remove('hidden');
          } else { D.unreadBadge.classList.add('hidden'); }
        }
        var headerBadge = document.querySelector('.notif-count');
        if (headerBadge) {
          if (d.count > 0) { headerBadge.textContent = d.count > 99 ? '99+' : d.count; headerBadge.style.display = ''; }
          else { headerBadge.style.display = 'none'; }
        }
      }).catch(function () {});
  }

  function updateCount() {
    D.count.textContent = S.items.length + ' notification' + (S.items.length !== 1 ? 's' : '');
  }

  function showSkeleton() { D.skeleton.style.display = 'flex'; D.empty.classList.add('hidden'); }
  function hideSkeleton() { D.skeleton.style.display = 'none'; }

  var _scrollObserver = null;
  function setupScroll() {
    if (window.IntersectionObserver) {
      _scrollObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting && !S.loading && S.hasMore) loadMore(); });
      }, { rootMargin: '200px' }).observe(D.sentinel);
    } else {
      window.addEventListener('scroll', function () {
        if (S.loading || !S.hasMore) return;
        if (D.sentinel.getBoundingClientRect().top < window.innerHeight + 200) loadMore();
      }, { passive: true });
    }
  }

  function loadMore() { if (!S.loading && S.hasMore) { S.page++; fetchTab(S.tab, S.page, false); } }

  function connectSocket() {
    if (typeof io === 'undefined') return;
    try {
      S.socket = io();
      S.socket.emit('notification:join');
      S.socket.on('notification:new', function (p) {
        if (S.tab === 'all' || S.tab === 'unread') {
          var el = buildCard(p);
          D.list.insertBefore(el, D.list.firstChild);
          S.items.unshift(p); updateCount(); D.empty.classList.add('hidden');
        }
        fetchUnread();
      });
    } catch (e) {}
  }

  function setupTouch(card, item) {
    var sx = 0, cx = 0, swiping = false;
    card.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; swiping = false; }, { passive: true });
    card.addEventListener('touchmove', function (e) {
      cx = e.touches[0].clientX; var d = sx - cx;
      if (d > 10) {
        swiping = true; card.classList.add('swiping');
        card.querySelectorAll('.notif-card-body,.notif-card-avatar,.notif-card-icon,.notif-card-actions,.notif-unread-dot,.notif-card-check').forEach(function (el) {
          el.style.transform = 'translateX(' + (-Math.min(d, 100)) + 'px)';
        });
      }
    }, { passive: true });
    card.addEventListener('touchend', function () {
      if (!swiping) return;
      var d = sx - cx; card.classList.remove('swiping');
      card.querySelectorAll('.notif-card-body,.notif-card-avatar,.notif-card-icon,.notif-card-actions,.notif-unread-dot,.notif-card-check').forEach(function (el) { el.style.transform = ''; });
      if (d > 60) { item.is_read ? del(item.id, card) : mark(item.id, card); }
      swiping = false;
    }, { passive: true });
  }

  function openPrefs() {
    D.overlay.classList.remove('hidden');
    fetch(API + '/preferences', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) return;
        renderPrefs(d.preferences || {});
      }).catch(function () { renderPrefs({}); });
  }

  function closePrefs() { D.overlay.classList.add('hidden'); }

  function renderPrefs(prefs) {
    var toggles = ['in_app_enabled', 'push_enabled', 'email_enabled', 'sms_enabled'];
    toggles.forEach(function (k) {
      var el = D.drawer.querySelector('[data-pref="' + k + '"]');
      if (el) el.classList.toggle('active', prefs[k] !== false);
    });
    var muted = prefs.muted_types || [];
    var types = ['follow','follow_accepted','mention','comment','reply','post_like','reel_like','story_reaction','story_mention','live_started','creator_subscription','wallet_transfer','wallet_received','dating_match','verification_approved','security_alert','system_announcement','new_message','message_reaction'];
    var html = '';
    types.forEach(function (t) {
      var isMuted = muted.indexOf(t) !== -1;
      html += '<div class="n-mute-type-row"><span class="n-mute-type-label">' + esc(t.replace(/_/g, ' ').replace(/\b\w/g,function(l){return l.toUpperCase()})) + '</span><button class="n-toggle' + (!isMuted ? ' active' : '') + '" data-mute="' + t + '"></button></div>';
    });
    var el = D.drawer.querySelector('#mutedTypesList');
    if (el) el.innerHTML = html;
    D.drawer.querySelectorAll('[data-pref], [data-mute]').forEach(function (b) {
      b.removeEventListener('click', savePrefs);
      b.addEventListener('click', savePrefs);
    });
  }

  function savePrefs() {
    var prefs = { in_app_enabled: false, push_enabled: false, email_enabled: false, sms_enabled: false, muted_types: [] };
    D.drawer.querySelectorAll('[data-pref]').forEach(function (b) {
      prefs[b.dataset.pref] = b.classList.contains('active');
    });
    D.drawer.querySelectorAll('[data-mute]').forEach(function (b) {
      if (!b.classList.contains('active')) prefs.muted_types.push(b.dataset.mute);
    });
    fetch(API + '/preferences', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify(prefs),
    }).catch(function () {});
  }

  function toast(msg) {
    if (_toastTimer) { clearTimeout(_toastTimer); D.toasts.innerHTML = ''; }
    var el = document.createElement('div'); el.className = 'notif-toast'; el.textContent = msg;
    D.toasts.appendChild(el);
    _toastTimer = setTimeout(function () { el.remove(); _toastTimer = null; }, 2800);
  }

  function timeAgo(s) {
    if (!s) return '';
    var diff = Math.floor((Date.now() - new Date(s).getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return new Date(s).toLocaleDateString();
  }

  function esc(s) { return typeof s !== 'string' ? (s||'') : s.replace(/[&<>"']/g,function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];}); }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
