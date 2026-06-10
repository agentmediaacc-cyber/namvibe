(function () {
  'use strict';

  var API = {
    chat: '/ai/api/chat',
    creator: '/ai/api/creator',
    marketplace: '/ai/api/marketplace',
    datingSafety: '/ai/api/dating-safety',
    moderation: '/ai/api/moderation',
    messageSuggestions: '/ai/api/message-suggestions',
    captions: '/ai/api/captions',
    profileSuggestions: '/ai/api/profile-suggestions',
    search: '/ai/api/search',
    suggestions: '/ai/api/suggestions',
    feedback: '/ai/api/feedback',
  };

  function $(id) { return document.getElementById(id); }

  function esc(str) {
    if (!str) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }

  function toast(msg, type) {
    var el = $('aiToast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'ai-toast is-visible' + (type === 'error' ? ' ai-toast-error' : type === 'success' ? ' ai-toast-success' : '');
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.classList.remove('is-visible'); }, 3000);
  }

  function fetchJSON(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onload = function () { try { cb(JSON.parse(xhr.responseText)); } catch (e) { cb(null); } };
    xhr.onerror = function () { cb(null); };
    xhr.send();
  }

  function postJSON(url, body, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () { try { cb(JSON.parse(xhr.responseText)); } catch (e) { cb(null); } };
    xhr.onerror = function () { cb(null); };
    xhr.send(JSON.stringify(body));
  }

  // ─── Tabs ───
  var tabBtns = document.querySelectorAll('.ai-tab');
  tabBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabBtns.forEach(function (b) { b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      document.querySelectorAll('.ai-panel').forEach(function (p) { p.classList.remove('is-active'); });
      var panel = document.getElementById('panel-' + btn.getAttribute('data-tab'));
      if (panel) panel.classList.add('is-active');
    });
  });

  // ─── Helper: append message to chat box (caps at 100) ───
  function addMsg(boxId, text, isUser) {
    var box = $(boxId);
    if (!box) return;
    while (box.children.length >= 100) box.removeChild(box.firstChild);
    var div = document.createElement('div');
    div.className = 'ai-msg' + (isUser ? ' ai-msg-user' : ' ai-msg-assistant');
    var icon = isUser ? 'fa-user' : 'fa-robot';
    if (boxId === 'aiCreatorBox') icon = 'fa-star';
    else if (boxId === 'aiMarketplaceBox') icon = 'fa-store';
    else if (boxId === 'aiDatingBox') icon = 'fa-shield-heart';
    else if (boxId === 'aiModerationBox') icon = 'fa-gavel';
    else if (boxId === 'aiMessagesBox') icon = 'fa-envelope';
    else if (boxId === 'aiCaptionsBox') icon = 'fa-closed-captioning';
    else if (boxId === 'aiProfileBox') icon = 'fa-user-edit';
    else if (boxId === 'aiSearchBox') icon = 'fa-search';
    div.innerHTML = '<div class="ai-msg-avatar"><i class="fas ' + icon + '"></i></div><div class="ai-msg-content"><p>' + esc(text) + '</p><span class="ai-msg-label">' + (isUser ? 'You' : 'AI Suggestion') + '</span></div>';
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  // ─── Generic chat handler ───
  function bindChat(inputId, sendBtnId, boxId, endpoint, assistantType, typeSelectorId) {
    var input = $(inputId);
    var btn = $(sendBtnId);
    if (!input || !btn) return;
    function send() {
      var msg = (input.value || '').trim();
      if (!msg) { toast('Please enter a message', 'error'); return; }
      addMsg(boxId, msg, true);
      input.value = '';
      btn.disabled = true;
      var at = assistantType;
      if (typeSelectorId) {
        var sel = $(typeSelectorId);
        if (sel) at = sel.value;
      }
      var body = at
        ? { assistant_type: at, message: msg }
        : { query: msg };
      postJSON(endpoint, body, function (res) {
        btn.disabled = false;
        if (res && res.ok) {
          addMsg(boxId, res.response || res.suggestion || res.caption || 'No suggestion returned.', false);
        } else {
          addMsg(boxId, 'Sorry, I could not generate a suggestion right now.', false);
          toast(res && res.error ? res.error : 'Request failed', 'error');
        }
      });
    }
    btn.addEventListener('click', send);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') send(); });
  }

  // ─── Bind all chat panels ───
  bindChat('aiChatInput', 'aiChatSend', 'aiChatBox', API.chat, null, 'aiChatType');

  bindChat('aiCreatorInput', 'aiCreatorSend', 'aiCreatorBox', API.creator, null);
  bindChat('aiMarketplaceInput', 'aiMarketplaceSend', 'aiMarketplaceBox', API.marketplace, null);
  bindChat('aiDatingInput', 'aiDatingSend', 'aiDatingBox', API.datingSafety, null);
  bindChat('aiModerationInput', 'aiModerationSend', 'aiModerationBox', API.moderation, null);

  // ─── Messages ───
  var msgInput = $('aiMessagesInput');
  var msgBtn = $('aiMessagesSend');
  if (msgInput && msgBtn) {
    function sendMsgSuggestion() {
      var ctx = (msgInput.value || '').trim();
      if (!ctx) { toast('Describe the conversation context', 'error'); return; }
      addMsg('aiMessagesBox', 'Context: ' + ctx, true);
      msgInput.value = '';
      msgBtn.disabled = true;
      postJSON(API.messageSuggestions, { context: { description: ctx } }, function (res) {
        msgBtn.disabled = false;
        if (res && res.ok) {
          addMsg('aiMessagesBox', res.suggestion, false);
          if (res.alternatives && res.alternatives.length) {
            addMsg('aiMessagesBox', 'Alternatives:\n' + res.alternatives.join('\n'), false);
          }
        } else {
          addMsg('aiMessagesBox', 'Could not generate suggestion.', false);
        }
      });
    }
    msgBtn.addEventListener('click', sendMsgSuggestion);
    msgInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMsgSuggestion(); });
  }

  // ─── Captions ───
  var capInput = $('aiCaptionsInput');
  var capBtn = $('aiCaptionsSend');
  var capList = $('aiCaptionsList');
  if (capInput && capBtn && capList) {
    function sendCaption() {
      var ctx = (capInput.value || '').trim();
      if (!ctx) { toast('Describe your post', 'error'); return; }
      addMsg('aiCaptionsBox', 'Post: ' + ctx, true);
      capInput.value = '';
      capBtn.disabled = true;
      capList.innerHTML = '<div class="ai-loading">Generating captions...</div>';
      postJSON(API.captions, { context: { description: ctx } }, function (res) {
        capBtn.disabled = false;
        if (res && res.ok) {
          addMsg('aiCaptionsBox', res.caption, false);
          var html = '';
          if (res.alternatives && res.alternatives.length) {
            res.alternatives.forEach(function (alt) {
              html += '<div class="ai-suggestion-card"><i class="fas fa-closed-captioning ai-sug-icon"></i><div><div class="ai-sug-text">' + esc(alt) + '</div><span class="ai-sug-label">AI Suggestion</span></div></div>';
            });
          }
          capList.innerHTML = html;
        } else {
          capList.innerHTML = '<div class="ai-empty"><p>Could not generate captions.</p></div>';
        }
      });
    }
    capBtn.addEventListener('click', sendCaption);
    capInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendCaption(); });
  }

  // ─── Profile Suggestions ───
  var profileBtn = $('aiProfileGetBtn');
  var profileList = $('aiProfileList');
  if (profileBtn && profileList) {
    profileBtn.addEventListener('click', function () {
      profileBtn.disabled = true;
      profileList.innerHTML = '<div class="ai-loading">Analyzing your profile...</div>';
      postJSON(API.profileSuggestions, { profile_data: {} }, function (res) {
        profileBtn.disabled = false;
        if (res && res.ok) {
          addMsg('aiProfileBox', res.suggestion, false);
          var html = '<div class="ai-suggestion-card"><i class="fas fa-user-edit ai-sug-icon"></i><div><div class="ai-sug-text">' + esc(res.suggestion) + '</div><span class="ai-sug-label">AI Suggestion</span></div></div>';
          if (res.alternatives && res.alternatives.length) {
            res.alternatives.forEach(function (alt) {
              html += '<div class="ai-suggestion-card"><i class="fas fa-lightbulb ai-sug-icon"></i><div><div class="ai-sug-text">' + esc(alt) + '</div><span class="ai-sug-label">AI Suggestion</span></div></div>';
            });
          }
          profileList.innerHTML = html;
        } else {
          profileList.innerHTML = '<div class="ai-empty"><p>Could not generate suggestions.</p></div>';
        }
      });
    });
  }

  // ─── AI Search ───
  var searchInput = $('aiSearchInput');
  var searchBtn = $('aiSearchSend');
  if (searchInput && searchBtn) {
    function sendSearch() {
      var q = (searchInput.value || '').trim();
      if (!q) { toast('Enter a search query', 'error'); return; }
      addMsg('aiSearchBox', 'Search: ' + q, true);
      searchInput.value = '';
      searchBtn.disabled = true;
      postJSON(API.search, { query: q }, function (res) {
        searchBtn.disabled = false;
        if (res && res.ok) {
          addMsg('aiSearchBox', res.suggestion, false);
        } else {
          addMsg('aiSearchBox', 'Could not generate search suggestions.', false);
        }
      });
    }
    searchBtn.addEventListener('click', sendSearch);
    searchInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendSearch(); });
  }

  // ─── History ───
  var historyFilter = $('aiHistoryFilter');
  var historyList = $('aiHistoryList');
  if (historyFilter && historyList) {
    function loadHistory() {
      var type = historyFilter.value;
      var url = API.suggestions;
      if (type) url += '?assistant_type=' + encodeURIComponent(type);
      historyList.innerHTML = '<div class="ai-empty"><i class="fas fa-spinner fa-spin"></i><p>Loading...</p></div>';
      fetchJSON(url, function (data) {
        if (!data || !data.suggestions || !data.suggestions.length) {
          historyList.innerHTML = '<div class="ai-empty"><i class="fas fa-history"></i><p>No suggestions yet.</p></div>';
          return;
        }
        var html = '';
        data.suggestions.forEach(function (s) {
          html += '<div class="ai-suggestion-card">';
          html += '<i class="fas fa-robot ai-sug-icon"></i>';
          html += '<div><div class="ai-sug-text">' + esc(s.output_text) + '</div>';
          html += '<span class="ai-sug-label">' + esc(s.assistant_type) + ' &middot; ' + (s.created_at ? s.created_at.slice(0, 10) : '') + '</span>';
          html += '</div></div>';
        });
        historyList.innerHTML = html;
      });
    }
    historyFilter.addEventListener('change', loadHistory);
    setTimeout(loadHistory, 500);
  }

})();
