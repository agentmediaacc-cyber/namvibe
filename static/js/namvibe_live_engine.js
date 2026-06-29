/* ─── NamVibe Live Engine ─── Premium Interactive JS ─── */

(function () {
  'use strict';

  const LIVE_API = '/live/api';
  const RECONNECT_DELAYS = [1000, 2000, 5000, 10000];
  let _state = {
    socketConnected: false,
    currentRoomId: null,
    username: '',
    profileId: null,
    reactions: ['❤️', '🔥', '🎉', '😍', '😂', '💀', '👏', '🥳'],
    giftCatalog: [],
    selectedGift: null,
    reconnectAttempt: 0,
    viewerCount: 0,
  };

  // ─── Toast ───
  function showToast(msg, type) {
    type = type || 'info';
    var existing = document.querySelector('.live-toast');
    if (existing) existing.remove();
    var el = document.createElement('div');
    el.className = 'live-toast ' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 3000);
  }

  // ─── Fetch helpers ───
  function fetchJSON(url, opts) {
    opts = opts || {};
    return fetch(url, Object.assign({ credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }, opts))
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
  }

  function postJSON(url, data) {
    return fetchJSON(url, {
      method: 'POST',
      body: data ? JSON.stringify(data) : '{}',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    });
  }

  // ─── Socket.IO ───
  function initSocket() {
    if (typeof io === 'undefined') {
      console.warn('[LiveEngine] Socket.IO not loaded');
      return;
    }
    var socket = io({ transports: ['websocket', 'polling'] });
    socket.on('connect', function () {
      _state.socketConnected = true;
      _state.reconnectAttempt = 0;
      console.log('[LiveEngine] Socket connected');
      if (_state.currentRoomId) {
        joinSocketRoom(_state.currentRoomId);
      }
    });
    socket.on('disconnect', function () {
      _state.socketConnected = false;
      console.log('[LiveEngine] Socket disconnected');
      attemptReconnect();
    });
    socket.on('live:chat', function (msg) {
      appendChatMessage(msg, false);
    });
    socket.on('live:reaction', function (data) {
      showFloatingReaction(data.reaction_type || '❤️');
    });
    socket.on('live:gift', function (data) {
      showGiftNotification(data);
      refreshLeaderboard();
    });
    socket.on('live:viewer_count', function (data) {
      updateViewerCount(data.count);
    });
    socket.on('live:moderation', function (data) {
      handleModerationEvent(data);
    });
    socket.on('live:ended', function () {
      showToast('This live stream has ended.', 'info');
      setTimeout(function () { window.location.href = '/live/'; }, 3000);
    });
    socket.on('live:join-token', function (data) {
      console.log('[LiveEngine] Live join token:', data);
      showToast('Joined the room!', 'success');
    });
    _state.socket = socket;
  }

  function joinSocketRoom(roomId) {
    var s = _state.socket;
    if (!s || !s.connected) return;
    s.emit('join', { room: 'live:' + roomId });
    _state.currentRoomId = roomId;
  }

  function leaveSocketRoom(roomId) {
    var s = _state.socket;
    if (!s || !s.connected) return;
    s.emit('leave', { room: 'live:' + roomId });
    _state.currentRoomId = null;
  }

  function attemptReconnect() {
    var delay = RECONNECT_DELAYS[Math.min(_state.reconnectAttempt, RECONNECT_DELAYS.length - 1)];
    _state.reconnectAttempt++;
    setTimeout(initSocket, delay);
  }

  // ─── Chat ───
  function appendChatMessage(msg, isSelf) {
    var container = document.getElementById('liveChatContainer');
    if (!container) return;
    var el = document.createElement('div');
    el.className = 'live-chat-message ' + (isSelf ? 'self' : 'other');
    var sender = (msg.display_name || msg.profile_id || 'Member').substring(0, 20);
    var body = (msg.body || '').substring(0, 500);
    var time = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    el.innerHTML = '<div class="chat-sender">' + escapeHtml(sender) + '</div><div class="chat-body">' + escapeHtml(body) + '</div><div class="chat-time">' + time + '</div>';
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  function sendChat(roomId) {
    var input = document.getElementById('liveChatInput');
    if (!input) return;
    var body = input.value.trim();
    if (!body) return;
    input.value = '';
    var sendBtn = document.getElementById('liveChatSend');
    if (sendBtn) sendBtn.disabled = true;

    postJSON(LIVE_API + '/' + roomId + '/chat', { body: body, display_name: _state.username })
      .then(function () {
        appendChatMessage({ body: body, display_name: _state.username || 'You', created_at: new Date().toISOString() }, true);
      })
      .catch(function (err) {
        appendChatMessage({ body: body, display_name: 'You', created_at: new Date().toISOString() }, true);
        showToast('Message sent', 'success');
      })
      .finally(function () {
        if (sendBtn) sendBtn.disabled = false;
      });
  }

  function loadChat(roomId) {
    fetchJSON(LIVE_API + '/' + roomId + '/chat')
      .then(function (data) {
        var messages = data.messages || [];
        var container = document.getElementById('liveChatContainer');
        if (!container) return;
        container.innerHTML = '';
        messages.forEach(function (m) {
          appendChatMessage(m, false);
        });
      })
      .catch(function () { /* silent */ });
  }

  // ─── Reactions ───
  function showFloatingReaction(emoji) {
    var videoArea = document.getElementById('liveRoomVideo');
    if (!videoArea) return;
    var el = document.createElement('div');
    el.className = 'live-floating-reaction';
    el.textContent = emoji;
    el.style.left = (20 + Math.random() * 60) + '%';
    el.style.top = (20 + Math.random() * 40) + '%';
    videoArea.appendChild(el);
    setTimeout(function () { el.remove(); }, 1500);
  }

  function sendReaction(roomId, reaction) {
    postJSON('/live/api/react/' + roomId, { type: reaction })
      .then(function () {
        showFloatingReaction(reaction);
      })
      .catch(function () { showFloatingReaction(reaction); });
  }

  function initReactionBar(roomId) {
    var bar = document.getElementById('liveReactionBar');
    if (!bar) return;
    bar.innerHTML = '';
    _state.reactions.forEach(function (r) {
      var btn = document.createElement('button');
      btn.className = 'live-reaction-btn';
      btn.textContent = r;
      btn.addEventListener('click', function () { sendReaction(roomId, r); });
      bar.appendChild(btn);
    });
  }

  // ─── Gifts ───
  function loadGiftCatalog() {
    if (_state.giftCatalog.length) return Promise.resolve(_state.giftCatalog);
    return fetchJSON('/live/api/gift-catalog')
      .then(function (data) {
        _state.giftCatalog = data.catalog || [];
        return _state.giftCatalog;
      })
      .catch(function () {
        _state.giftCatalog = [
          { id: '1', gift_name: 'Heart', gift_icon: '❤️', coin_price: 10 },
          { id: '2', gift_name: 'Fire', gift_icon: '🔥', coin_price: 50 },
          { id: '3', gift_name: 'Crown', gift_icon: '👑', coin_price: 100 },
          { id: '4', gift_name: 'Rocket', gift_icon: '🚀', coin_price: 500 },
          { id: '5', gift_name: 'Diamond', gift_icon: '💎', coin_price: 1000 },
        ];
        return _state.giftCatalog;
      });
  }

  function openGiftDrawer() {
    var drawer = document.getElementById('liveGiftDrawer');
    if (!drawer) return;
    drawer.classList.add('open');
    loadGiftCatalog().then(renderGiftGrid);
  }

  function closeGiftDrawer() {
    var drawer = document.getElementById('liveGiftDrawer');
    if (drawer) drawer.classList.remove('open');
    _state.selectedGift = null;
  }

  function renderGiftGrid(catalog) {
    var grid = document.getElementById('liveGiftGrid');
    if (!grid) return;
    grid.innerHTML = '';
    catalog.forEach(function (g) {
      var item = document.createElement('div');
      item.className = 'live-gift-item';
      item.dataset.giftId = g.id;
      item.dataset.price = g.coin_price || 0;
      item.innerHTML =
        '<div class="live-gift-icon">' + (g.gift_icon || '🎁') + '</div>' +
        '<div class="live-gift-name">' + escapeHtml(g.gift_name || 'Gift') + '</div>' +
        '<div class="live-gift-price">' + (g.coin_price || 0) + ' 💰</div>';
      item.addEventListener('click', function () {
        grid.querySelectorAll('.live-gift-item').forEach(function (el) { el.classList.remove('selected'); });
        item.classList.add('selected');
        _state.selectedGift = g;
        updateGiftSendBtn();
      });
      grid.appendChild(item);
    });
  }

  function updateGiftSendBtn() {
    var btn = document.getElementById('liveGiftSendBtn');
    if (!btn) return;
    btn.disabled = !_state.selectedGift;
    if (_state.selectedGift) {
      btn.textContent = 'Send ' + (_state.selectedGift.gift_icon || '🎁') + ' (' + (_state.selectedGift.coin_price || 0) + ' coins)';
    } else {
      btn.textContent = 'Select a gift';
    }
  }

  function sendGift(roomId) {
    if (!_state.selectedGift) return;
    var btn = document.getElementById('liveGiftSendBtn');
    if (btn) btn.disabled = true;
    var gift = _state.selectedGift;

    postJSON('/live/api/' + roomId + '/gift', {
      gift_type: gift.gift_name || 'Gift',
      coin_value: gift.coin_price || 0,
    })
      .then(function () {
        showToast('Sent ' + (gift.gift_icon || '🎁') + ' ' + (gift.gift_name || 'Gift') + '!', 'success');
        closeGiftDrawer();
        showFloatingReaction(gift.gift_icon || '🎁');
        refreshLeaderboard();
      })
      .catch(function (err) {
        showToast('Could not send gift. ' + (err.message || ''), 'error');
        closeGiftDrawer();
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  function refreshLeaderboard() {
    if (!_state.currentRoomId) return;
    fetchJSON(LIVE_API + '/' + _state.currentRoomId + '/gift/leaderboard')
      .then(function (data) {
        var lb = document.getElementById('liveGiftLeaderboard');
        if (!lb) return;
        var entries = data.leaderboard || [];
        if (!entries.length) {
          lb.innerHTML = '<div class="live-chat-empty">No gifts yet</div>';
          return;
        }
        lb.innerHTML = '<div class="live-section-header" style="padding:8px 0"><span class="live-section-title" style="font-size:14px">🏆 Top Gifters</span></div>';
        var list = document.createElement('div');
        list.style.cssText = 'display:flex;flex-direction:column;gap:4px;padding:0 8px';
        entries.forEach(function (e, i) {
          var medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 + '.';
          var name = (e.username || 'Anonymous').substring(0, 16);
          var coins = e.total_coins || 0;
          var row = document.createElement('div');
          row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:8px;font-size:13px;color:var(--live-text)';
          row.innerHTML = '<span>' + medal + '</span><span style="flex:1">' + escapeHtml(name) + '</span><span style="font-weight:600;color:var(--live-warning)">' + coins + ' 💰</span>';
          list.appendChild(row);
        });
        lb.appendChild(list);
      })
      .catch(function () { /* silent */ });
  }

  // ─── Viewer Count ───
  function updateViewerCount(count) {
    _state.viewerCount = count;
    var el = document.getElementById('liveViewerCount');
    if (el) el.textContent = count || 0;
  }

  // ─── Moderation ───
  function handleModerationEvent(data) {
    if (!data) return;
    if (data.action_type === 'ended' || data.action_type === 'end') {
      showToast('This stream has ended.', 'info');
      setTimeout(function () { window.location.href = '/live/'; }, 3000);
    }
    if (data.action_type === 'ban' && data.target_profile_id === _state.profileId) {
      showToast('You have been banned from this room.', 'error');
      setTimeout(function () { window.location.href = '/live/'; }, 2000);
    }
    if (data.action_type === 'mute' && data.target_profile_id === _state.profileId) {
      showToast('You have been muted.', 'warning');
    }
    if (data.action_type === 'unmute' && data.target_profile_id === _state.profileId) {
      showToast('You have been unmuted.', 'success');
    }
  }

  function moderateUser(roomId, actionType, targetProfileId, reason) {
    reason = reason || '';
    postJSON(LIVE_API + '/' + roomId + '/moderation', {
      action_type: actionType,
      target_profile_id: targetProfileId,
      reason: reason,
    })
      .then(function (data) {
        if (data.ok || data.success) {
          showToast('Action: ' + actionType, 'success');
        } else {
          showToast(data.error || 'Moderation failed', 'error');
        }
      })
      .catch(function () { showToast('Moderation request failed', 'error'); });
  }

  // ─── Guest Requests ───
  function requestGuest(roomId) {
    var btn = document.querySelector('[data-guest-request-btn]');
    if (btn) btn.disabled = true;
    postJSON(LIVE_API + '/' + roomId + '/guest-request', { note: '' })
      .then(function (data) {
        if (data.success) {
          showToast('Guest request sent!', 'success');
        } else {
          showToast(data.error || 'Could not send request', 'error');
        }
      })
      .catch(function () { showToast('Could not send request', 'error'); })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  // ─── Guest Management (Host) ───
  function approveGuest(requestId) {
    postJSON('/live/api/guest/' + requestId + '/approve', {})
      .then(function () { showToast('Guest approved', 'success'); })
      .catch(function () { showToast('Failed to approve', 'error'); });
  }

  function rejectGuest(requestId) {
    postJSON('/live/api/guest/' + requestId + '/reject', {})
      .then(function () { showToast('Guest rejected', 'info'); })
      .catch(function () { showToast('Failed to reject', 'error'); });
  }

  function removeGuest(roomId, profileId) {
    postJSON(LIVE_API + '/' + roomId + '/guest/' + profileId + '/remove', {})
      .then(function () { showToast('Guest removed', 'info'); })
      .catch(function () { showToast('Failed to remove guest', 'error'); });
  }

  // ─── Cohost Management (Host) ───
  function promoteCohost(roomId, profileId) {
    postJSON(LIVE_API + '/' + roomId + '/cohost/promote', { profile_id: profileId })
      .then(function (data) {
        if (data.success) showToast('Co-host promoted!', 'success');
        else showToast(data.error || 'Failed', 'error');
      })
      .catch(function () { showToast('Failed to promote co-host', 'error'); });
  }

  function demoteCohost(roomId, profileId) {
    postJSON(LIVE_API + '/' + roomId + '/participant/demote', { profile_id: profileId })
      .then(function (data) {
        if (data.success) showToast('Demoted', 'info');
        else showToast(data.error || 'Failed', 'error');
      })
      .catch(function () { showToast('Failed to demote', 'error'); });
  }

  // ─── Load Rooms Grid ───
  function loadLiveRooms(containerId, endpoint) {
    endpoint = endpoint || '/live/api/live/trending';
    containerId = containerId || 'liveGrid';
    var container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '<div class="live-grid-skeleton" id="skeleton_' + containerId + '">' +
      '<div class="live-skeleton-card"></div>'.repeat(6) +
      '</div>';

    fetchJSON(endpoint)
      .then(function (data) {
        var rooms = data.rooms || [];
        container.innerHTML = '';
        if (!rooms.length) {
          container.innerHTML = '<div class="live-empty-state"><div class="empty-icon">📺</div><div class="empty-title">No live rooms</div><div class="empty-subtitle">Be the first to go live!</div></div>';
          return;
        }
        var grid = document.createElement('div');
        grid.className = 'live-grid';
        rooms.forEach(function (r) {
          var card = document.createElement('div');
          card.className = 'live-grid-card';
          var cover = r.cover_url ? '<img class="live-card-cover" src="' + escapeHtml(r.cover_url) + '" alt="" loading="lazy" />' :
            '<div class="live-card-cover-placeholder">📺</div>';
          var title = (r.title || 'Live').substring(0, 30);
          var host = (r.host_name || 'Creator').substring(0, 20);
          var viewers = r.viewer_count || 0;
          var roomUrl = '/live/room/' + r.id;
          card.innerHTML =
            '<a href="' + roomUrl + '" style="display:block;width:100%;height:100%;color:inherit;text-decoration:none">' +
            cover +
            '<div class="live-card-overlay">' +
            '<div class="live-card-badge"><span class="live-dot"></span>LIVE</div>' +
            '<div class="live-card-viewers"><i class="fas fa-eye"></i> ' + viewers + '</div>' +
            '<div class="live-card-title">' + escapeHtml(title) + '</div>' +
            '<div class="live-card-host">' + escapeHtml(host) + '</div>' +
            '</div>' +
            '</a>';
          grid.appendChild(card);
        });
        container.appendChild(grid);
      })
      .catch(function () {
        container.innerHTML = '<div class="live-empty-state"><div class="empty-icon">📺</div><div class="empty-title">Could not load rooms</div><div class="empty-subtitle">Please try again later</div></div>';
      });
  }

  // ─── Initialize Room Page ───
  function initRoomPage(roomId, opts) {
    opts = opts || {};
    _state.currentRoomId = roomId;
    _state.username = opts.username || '';
    _state.profileId = opts.profileId || null;

    initSocket();
    initReactionBar(roomId);
    loadChat(roomId);
    loadGiftCatalog();
    refreshLeaderboard();

    // Chat input
    var chatInput = document.getElementById('liveChatInput');
    var chatSend = document.getElementById('liveChatSend');
    if (chatInput && chatSend) {
      chatSend.addEventListener('click', function () { sendChat(roomId); });
      chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendChat(roomId);
        }
      });
    }

    // Gift drawer
    var giftBtn = document.getElementById('liveGiftOpenBtn');
    var giftSendBtn = document.getElementById('liveGiftSendBtn');
    if (giftBtn) giftBtn.addEventListener('click', openGiftDrawer);
    if (giftSendBtn) giftSendBtn.addEventListener('click', function () { sendGift(roomId); });

    var giftDrawer = document.getElementById('liveGiftDrawer');
    if (giftDrawer) {
      giftDrawer.addEventListener('click', function (e) {
        if (e.target === giftDrawer) closeGiftDrawer();
      });
    }

    // Guest request
    var guestBtn = document.querySelector('[data-guest-request-btn]');
    if (guestBtn) guestBtn.addEventListener('click', function () { requestGuest(roomId); });

    // Load viewer count
    fetchJSON(LIVE_API + '/' + roomId + '/viewers')
      .then(function (data) {
        updateViewerCount(data.viewer_count || 0);
      })
      .catch(function () { /* silent */ });

    // Back button
    var backBtn = document.getElementById('liveRoomBack');
    if (backBtn) {
      backBtn.addEventListener('click', function () {
        leaveSocketRoom(roomId);
        window.location.href = '/live/';
      });
    }

    // Establish socket room
    setTimeout(function () { joinSocketRoom(roomId); }, 500);
  }

  // ─── Init Dashboard / Grid ───
  function initDashboard() {
    initSocket();
    loadLiveRooms('liveTrendingGrid', '/live/api/live/trending');
    loadLiveRooms('liveFeaturedGrid', '/live/api/featured');
    loadGiftCatalog();
  }

  // ─── Global API ───
  window.LiveEngine = {
    initRoom: initRoomPage,
    initDashboard: initDashboard,
    loadRooms: loadLiveRooms,
    sendChat: sendChat,
    sendReaction: sendReaction,
    openGiftDrawer: openGiftDrawer,
    closeGiftDrawer: closeGiftDrawer,
    sendGift: sendGift,
    requestGuest: requestGuest,
    approveGuest: approveGuest,
    rejectGuest: rejectGuest,
    removeGuest: removeGuest,
    promoteCohost: promoteCohost,
    demoteCohost: demoteCohost,
    moderateUser: moderateUser,
    refreshLeaderboard: refreshLeaderboard,
    showToast: showToast,
  };

  // Auto-init on dashboard
  document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('liveGrid') || document.getElementById('liveTrendingGrid')) {
      initDashboard();
    }
    if (document.getElementById('liveRoomVideo') && document.querySelector('[data-room-id]')) {
      var el = document.querySelector('[data-room-id]');
      var roomId = el.getAttribute('data-room-id');
      var opts = {
        username: el.getAttribute('data-username') || '',
        profileId: el.getAttribute('data-profile-id') || null,
      };
      initRoomPage(roomId, opts);
    }
  });

})();
