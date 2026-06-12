(function () {
  'use strict';

  var CHAIN_DEBUG = window.CHAIN_MESSAGE_DIAG = window.CHAIN_MESSAGE_DIAG || { version: 'phase55.1' };

  function $safe(id) {
    return document.getElementById(id);
  }

  function qs(sel, ctx) {
    return (ctx || document).querySelector(sel);
  }

  function qsa(sel, ctx) {
    return Array.from((ctx || document).querySelectorAll(sel));
  }

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[c];
    });
  }

  function safeFetch(url, opts) {
    opts = opts || {};
    opts.credentials = opts.credentials || 'same-origin';
    if (!opts.headers) opts.headers = {};
    return fetch(url, opts).catch(function (err) {
      CHAIN_DEBUG.fetchErrors = CHAIN_DEBUG.fetchErrors || [];
      CHAIN_DEBUG.fetchErrors.push({ url: url, error: err.message || String(err) });
      return { ok: false, json: function () { return Promise.resolve({}); } };
    });
  }

  function safeJson(resp) {
    try {
      return resp.json ? resp.json().catch(function () { return {}; }) : Promise.resolve({});
    } catch (e) {
      return Promise.resolve({});
    }
  }

  var _initialized = false;

  function initPremiumFeatures(opts) {
    if (_initialized) return;
    _initialized = true;

    opts = opts || {};
    var threadId = opts.threadId;
    var socket = opts.socket || { on: function () {}, emit: function () {}, connected: false };
    var sendMessage = opts.sendMessage || function () {};
    var currentTargetProfileId = opts.currentTargetProfileId || '';

    if (!threadId) {
      CHAIN_DEBUG.error = 'initPremiumFeatures: threadId required';
      return;
    }

    CHAIN_DEBUG.premium = { threadId: threadId, initialized: true };

    // ---- Disappearing Messages ----
    function showDTimerMenu() { var m = $safe('d-timer-menu'); if (m) m.style.display = 'block'; }
    function hideDTimerMenu() { var m = $safe('d-timer-menu'); if (m) m.style.display = 'none'; }
    function setDisappearingTimer(seconds) {
      safeFetch('/messages/api/thread/' + threadId + '/disappearing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timer_seconds: seconds })
      }).then(safeJson).then(function (d) {
        if (d && d.ok !== false) {
          hideDTimerMenu();
          var btn = $safe('d-timer-btn');
          if (!btn) return;
          if (seconds > 0) {
            var labels = { 86400: '24h', 604800: '7d', 2592000: '30d' };
            btn.innerHTML = '<i class="fas fa-hourglass-half" style="color:#f59e0b;"></i>';
            btn.title = 'Disappearing: ' + (labels[seconds] || seconds + 's');
          } else {
            btn.innerHTML = '<i class="fas fa-hourglass-half"></i>';
            btn.title = 'Disappearing messages';
          }
        }
      });
    }

    // ---- Thread Search ----
    var _searchResults = [];
    var _searchIdx = -1;
    function toggleSearch() {
      var bar = $safe('thread-search-bar');
      if (!bar) return;
      bar.style.display = bar.style.display === 'none' ? 'flex' : 'none';
      if (bar.style.display === 'flex') { var inp = $safe('thread-search-input'); if (inp) inp.focus(); }
    }
    function closeSearch() {
      var bar = $safe('thread-search-bar');
      if (bar) bar.style.display = 'none';
      clearHighlights();
    }
    function clearHighlights() {
      qsa('.search-highlight').forEach(function (el) {
        var parent = el.parentNode;
        if (parent) {
          parent.replaceChild(document.createTextNode(el.textContent), el);
          parent.normalize();
        }
      });
      qsa('.thread-search-result').forEach(function (el) { el.remove(); });
      var sc = $safe('search-count');
      if (sc) sc.textContent = '';
    }
    function doSearch() {
      var inp = $safe('thread-search-input');
      var q = inp ? inp.value.trim() : '';
      if (q.length < 2) { clearHighlights(); return; }
      var messages = qsa('.msg-text');
      _searchResults = [];
      clearHighlights();
      messages.forEach(function (el) {
        var text = el.textContent;
        var idx = text.toLowerCase().indexOf(q.toLowerCase());
        if (idx >= 0) {
          var group = el.closest('.msg-group');
          if (group && group.id) _searchResults.push(group.id);
          var regex = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
          el.innerHTML = text.replace(regex, '<span class="search-highlight">$1</span>');
        }
      });
      safeFetch('/messages/api/thread/' + threadId + '/search?q=' + encodeURIComponent(q)).then(safeJson).then(function () {});
      _searchIdx = _searchResults.length > 0 ? 0 : -1;
      updateSearchNav();
    }
    function debounceSearch() {
      if (window._chainSearchTimer) clearTimeout(window._chainSearchTimer);
      window._chainSearchTimer = setTimeout(doSearch, 300);
    }
    function searchNext() {
      if (_searchResults.length === 0) return;
      _searchIdx = (_searchIdx + 1) % _searchResults.length;
      scrollToSearchResult();
    }
    function searchPrev() {
      if (_searchResults.length === 0) return;
      _searchIdx = (_searchIdx - 1 + _searchResults.length) % _searchResults.length;
      scrollToSearchResult();
    }
    function scrollToSearchResult() {
      var id = _searchResults[_searchIdx];
      var el = $safe(id);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.style.background = 'rgba(124,58,237,0.1)';
        setTimeout(function () { el.style.background = ''; }, 1500);
      }
      updateSearchNav();
    }
    function updateSearchNav() {
      var sc = $safe('search-count');
      if (sc) sc.textContent = _searchResults.length > 0 ? (_searchIdx + 1) + '/' + _searchResults.length : '0/0';
    }
    function useSearchSuggestion(kind) {
      var map = { location: 'location', money: 'money', photos: 'photo image', voice: 'voice audio', links: 'http' };
      var inp = $safe('thread-search-input');
      if (inp) { inp.value = map[kind] || kind; doSearch(); }
    }

    // ---- HD Media ----
    var _selectedHDQuality = 'standard';
    function selectHDQuality(q) {
      _selectedHDQuality = q;
      qsa('.hd-opt[data-quality]').forEach(function (el) { el.classList.toggle('active', el.dataset.quality === q); });
      updateFileSizeEstimate();
    }
    function cancelHD() { var h = $safe('hd-selector'); if (h) h.style.display = 'none'; }
    function updateFileSizeEstimate() {
      var fi = $safe('file-input');
      var file = fi && fi.files ? fi.files[0] : null;
      if (!file) return;
      var size = file.size || 0;
      var factor = _selectedHDQuality === 'standard' ? 0.55 : _selectedHDQuality === 'hd' ? 0.82 : 1;
      var estimated = Math.max(1, Math.round(size * factor / 1024 / 1024 * 10) / 10);
      var badge = $safe('file-size-badge');
      if (badge) badge.textContent = (Math.round(size / 1024 / 1024 * 10) / 10) + 'MB';
      var est = $safe('file-size-estimate');
      if (est) est.textContent = 'Estimated ' + estimated + 'MB';
      var warn = $safe('file-size-warning');
      if (warn) {
        warn.style.display = size > 50 * 1024 * 1024 ? 'inline-flex' : 'none';
        warn.textContent = size > 50 * 1024 * 1024 ? 'Warning: above 50MB' : '';
      }
    }

    // ---- Voice Transcription ----
    function transcribeVoice(msgId) {
      var el = $safe('transcript-' + msgId);
      if (el && el.style.display !== 'none' && el.textContent) { el.style.display = 'none'; return; }
      safeFetch('/messages/api/messages/' + msgId + '/transcribe', { method: 'POST' }).then(safeJson).then(function (d) {
        if (!el) return;
        if (d && d.transcript) {
          el.textContent = d.transcript;
          el.style.display = 'block';
          if (d.note) el.textContent += ' (' + d.note.replace(/_/g, ' ') + ')';
        } else {
          el.textContent = 'Transcription not available yet';
          el.style.display = 'block';
        }
      });
    }
    function toggleTranscript(msgId) {
      var el = $safe('transcript-' + msgId);
      if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }
    function copyTranscript(msgId) {
      var el = $safe('transcript-' + msgId);
      var text = el ? el.textContent.trim() : '';
      if (!text) return;
      navigator.clipboard.writeText(text).catch(function () { prompt('Copy transcript:', text); });
    }

    // ---- Translate ----
    function translateMessage(msgId) {
      var languages = ['English', 'Oshiwambo', 'Afrikaans', 'Portuguese', 'French'];
      var target = prompt('Choose language:\n' + languages.join('\n'), 'English');
      if (!target) return;
      if (!languages.map(function (l) { return l.toLowerCase(); }).includes(target.toLowerCase())) {
        alert('Choose English, Oshiwambo, Afrikaans, Portuguese, or French.');
        return;
      }
      safeFetch('/messages/api/chat/ai/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: msgId, target_language: target })
      }).then(safeJson).then(function (d) {
        var text = d && (d.translated_text || d.message || 'Translation not available yet');
        if (d && d.translated_text && confirm('Replace the message text in your composer with this translation?\n\n' + text)) {
          var inp = $safe('msg-input');
          if (inp) inp.value = text;
          var send = $safe('send-btn');
          if (send) send.disabled = false;
        } else if (!d || !d.translated_text) {
          alert(text);
        }
      });
    }

    // ---- Wallet ----
    var _walletTransferType = '';
    function showWalletActions() { var w = $safe('wallet-actions'); if (w) w.style.display = 'block'; }
    function hideWalletActions() { var w = $safe('wallet-actions'); if (w) w.style.display = 'none'; }
    function walletTransfer(type) {
      _walletTransferType = type;
      var labels = { send: 'Send Money', request: 'Request Money', tip: 'Tip User', split: 'Split Bill' };
      var amount = prompt(labels[type] + ':\nEnter amount (NamVibe coins):');
      if (!amount || isNaN(amount) || Number(amount) <= 0) return;
      var note = prompt('Optional note:') || '';
      var endpoint = '/messages/api/wallet/' + type;
      safeFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, amount: Number(amount), note: note, recipient_profile_id: currentTargetProfileId || '' })
      }).then(safeJson).then(function (d) {
        var el = $safe('wallet-response');
        if (el) {
          if (d && d.ok === false && d.error) {
            el.textContent = d.error;
          } else {
            el.textContent = 'Transaction sent!';
          }
          setTimeout(function () { if (el) el.textContent = ''; }, 5000);
        }
      });
    }

    // ---- AI Tools ----
    function showAITools() { var a = $safe('ai-tools-panel'); if (a) a.style.display = 'block'; }
    function hideAITools() { var a = $safe('ai-tools-panel'); if (a) a.style.display = 'none'; }
    function aiAction(mode) {
      var respEl = $safe('ai-tools-response');
      var endpoints = {
        summarize: '/messages/api/chat/ai/summarize',
        'unread-summary': '/messages/api/chat/ai/unread-summary',
        'find-important': '/messages/api/chat/ai/find-important',
        'suggest-reply': '/messages/api/chat/ai/suggest-reply',
        translate: '/messages/api/chat/ai/translate'
      };
      var endpoint = endpoints[mode];
      if (!endpoint) return;
      if (respEl) respEl.textContent = 'Processing...';
      safeFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, context: $safe('msg-input') ? $safe('msg-input').value : '' })
      }).then(safeJson).then(function (d) {
        if ((mode === 'summarize' || mode === 'unread-summary') && d && d.summary) {
          if (confirm('AI Summary:\n\n' + d.summary + '\n\nSend to chat?')) { sendMessage(d.summary); }
          if (respEl) respEl.textContent = '';
        } else if (mode === 'suggest-reply' && d && d.suggestions && d.suggestions.length > 0) {
          var reply = d.suggestions[0];
          if (confirm('Suggested reply:\n\n' + reply + '\n\nSend?')) { sendMessage(reply); }
          if (respEl) respEl.textContent = '';
        } else if (mode === 'translate' && d && d.translated_text) {
          if (confirm('Translation:\n\n' + d.translated_text + '\n\nSend?')) { sendMessage(d.translated_text); }
          if (respEl) respEl.textContent = '';
        } else {
          if (respEl) respEl.textContent = d && (d.note ? d.note.replace(/_/g, ' ') : (d.summary || 'Done'));
          if (respEl) setTimeout(function () { if (respEl) respEl.textContent = ''; }, 4000);
        }
      });
    }
    function useAutoReply(template) {
      if (confirm('Send: "' + template + '"\n\nUse this auto-reply?')) { sendMessage(template); }
    }

    // ---- Open Camera ----
    function openCamera() {
      var input = $safe('file-input');
      if (!input) return;
      input.accept = 'image/*';
      input.capture = 'environment';
      input.click();
      input.accept = 'image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt';
    }

    // ---- Scheduled Messages ----
    function loadScheduledMessages() {
      var panel = $safe('scheduled-list-panel');
      var body = $safe('scheduled-list-body');
      if (!panel || !body) return;
      panel.style.display = 'block';
      body.innerHTML = '<div class="scheduled-empty">Loading...</div>';
      safeFetch('/messages/api/threads/' + threadId + '/scheduled').then(safeJson).then(function (d) {
        var items = d && d.scheduled ? d.scheduled : [];
        if (!items.length) { body.innerHTML = '<div class="scheduled-empty">No scheduled messages</div>'; return; }
        body.innerHTML = items.map(function (item) {
          return '<div class="scheduled-row" data-scheduled-id="' + escapeHtml(item.id) + '">' +
            '<span class="scheduled-badge">Scheduled</span>' +
            '<div class="scheduled-preview-text">' + escapeHtml(item.body || 'Scheduled message') + '</div>' +
            '<div class="scheduled-preview-time">' + (item.scheduled_for ? new Date(item.scheduled_for).toLocaleString() : '') + '</div>' +
            '<div class="scheduled-actions">' +
            '<button type="button" onclick="window.editScheduledFromList(\'' + escapeHtml(item.id) + '\')"><i class="fas fa-pen"></i> Edit time</button>' +
            '<button type="button" onclick="window.cancelScheduledFromList(\'' + escapeHtml(item.id) + '\')"><i class="fas fa-times"></i> Cancel</button>' +
            '</div></div>';
        }).join('');
      });
    }
    function hideScheduledList() { var p = $safe('scheduled-list-panel'); if (p) p.style.display = 'none'; }
    function editScheduledFromList(scheduledId) {
      var nextTime = prompt('Edit scheduled time');
      if (!nextTime) return;
      safeFetch('/messages/api/scheduled/' + scheduledId + '/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scheduled_for: new Date(nextTime).toISOString() })
      }).then(function () { loadScheduledMessages(); });
    }
    function cancelScheduledFromList(scheduledId) {
      if (!confirm('Cancel this scheduled message?')) return;
      safeFetch('/messages/api/scheduled/' + scheduledId + '/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'cancelled_by_sender' })
      }).then(function () { loadScheduledMessages(); });
    }

    // ---- Keyboard shortcuts ----
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && document.activeElement && document.activeElement.closest('.chat-container')) {
        e.preventDefault();
        toggleSearch();
      }
    });

    // ---- Socket event handlers ----
    if (socket && typeof socket.on === 'function') {
      socket.on('poll:new', function (data) {
        if (data && data.poll && data.poll.thread_id === threadId && window.appendPollMessage) {
          window.appendPollMessage(data.poll);
        }
      });
      socket.on('poll:updated', function (data) {
        if (data && data.poll && window.fetchPollResults) {
          window.fetchPollResults(data.poll.id);
        }
      });
      socket.on('live_location:start', function (data) {
        if (!data || (data.thread_id !== threadId && data.thread_id)) return;
        var link = document.createElement('div');
        link.className = 'live-location-card';
        link.innerHTML = '<div class="ll-icon"><i class="fas fa-location-dot"></i></div>' +
          '<div class="ll-info"><div>Live Location</div><div class="ll-sub">' + (data.duration_minutes || 15) + ' min</div></div>' +
          '<a href="https://maps.google.com/?q=' + data.lat + ',' + data.lng + '" target="_blank" class="ll-stop" style="text-decoration:none;">View</a>';
        var ml = $safe('message-list');
        if (ml) ml.appendChild(link);
      });
      socket.on('live_location:update', function () {});
      socket.on('live_location:stopped', function () {});
      socket.on('disappearing:updated', function (data) {
        var btn = $safe('d-timer-btn');
        if (!btn) return;
        if (data && data.timer_seconds > 0) {
          var labels = { 86400: '24h', 604800: '7d', 2592000: '30d' };
          btn.innerHTML = '<i class="fas fa-hourglass-half" style="color:#f59e0b;"></i>';
          btn.title = 'Disappearing: ' + (labels[data.timer_seconds] || data.timer_seconds + 's');
        } else {
          btn.innerHTML = '<i class="fas fa-hourglass-half"></i>';
          btn.title = 'Disappearing messages';
        }
      });
      socket.on('transcribe:result', function (data) {
        if (data && data.message_id) {
          var el = $safe('transcript-' + data.message_id);
          if (el) { el.textContent = data.transcript || 'Transcription not available yet'; el.style.display = 'block'; }
        }
      });
      socket.on('chat:suggestions', function (data) {
        if (data && data.suggestions && data.suggestions.length > 0) {
          var reply = data.suggestions[0];
          if (confirm('Suggested reply:\n\n' + reply + '\n\nSend?')) { sendMessage(reply); }
        }
      });
      socket.on('chat:summary', function (data) {
        if (data && data.summary && confirm('AI Summary:\n\n' + data.summary + '\n\nSend to chat?')) {
          sendMessage(data.summary);
        }
      });
    }

    // Expose functions globally for inline onclick handlers
    window.showDTimerMenu = showDTimerMenu;
    window.hideDTimerMenu = hideDTimerMenu;
    window.setDisappearingTimer = setDisappearingTimer;
    window.toggleSearch = toggleSearch;
    window.closeSearch = closeSearch;
    window.clearHighlights = clearHighlights;
    window.debounceSearch = debounceSearch;
    window.doSearch = doSearch;
    window.searchNext = searchNext;
    window.searchPrev = searchPrev;
    window.scrollToSearchResult = scrollToSearchResult;
    window.updateSearchNav = updateSearchNav;
    window.useSearchSuggestion = useSearchSuggestion;
    window.selectHDQuality = selectHDQuality;
    window.cancelHD = cancelHD;
    window.updateFileSizeEstimate = updateFileSizeEstimate;
    window.transcribeVoice = transcribeVoice;
    window.toggleTranscript = toggleTranscript;
    window.copyTranscript = copyTranscript;
    window.translateMessage = translateMessage;
    window.showWalletActions = showWalletActions;
    window.hideWalletActions = hideWalletActions;
    window.walletTransfer = walletTransfer;
    window.showAITools = showAITools;
    window.hideAITools = hideAITools;
    window.aiAction = aiAction;
    window.useAutoReply = useAutoReply;
    window.openCamera = openCamera;
    window.loadScheduledMessages = loadScheduledMessages;
    window.hideScheduledList = hideScheduledList;
    window.editScheduledFromList = editScheduledFromList;
    window.cancelScheduledFromList = cancelScheduledFromList;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initPremiumFeatures: initPremiumFeatures };
  } else {
    window.initPremiumFeatures = initPremiumFeatures;
  }
})();
