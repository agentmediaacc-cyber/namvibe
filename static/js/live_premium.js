(function () {
  'use strict';

  var API = {
    goals: '/live/api/live/',
    earnings: '/live/api/live/earnings',
    withdraw: '/live/api/live/earnings/withdraw',
    raids: '/live/api/live/',
    giftCatalog: '/live/api/gift-catalog',
    dashboard: '/live/api/dashboard',
    featured: '/live/api/featured',
    premiumRooms: '/live/api/premium-rooms',
    mods: '/live/api/live/',
    bans: '/live/api/live/',
  };

  function $(id) { return document.getElementById(id); }

  function esc(str) { if (!str) return ''; var d = document.createElement('div'); d.appendChild(document.createTextNode(str)); return d.innerHTML; }

  function toast(msg, isError) {
    var el = document.createElement('div');
    el.className = 'lp-toast' + (isError ? ' lp-toast-error' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { if (el.parentNode) el.remove(); }, 3000);
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

  // ─── Toast Styles ───
  (function injectToastStyles() {
    if (document.getElementById('lpToastStyle')) return;
    var s = document.createElement('style');
    s.id = 'lpToastStyle';
    s.textContent = '.lp-toast{position:fixed;bottom:24px;right:24px;padding:12px 24px;border-radius:12px;background:#1a1a2e;color:#fff;font-size:14px;font-weight:600;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,.3);animation:lpToastIn .3s ease}.lp-toast-error{background:#ef4444}@keyframes lpToastIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}';
    document.head.appendChild(s);
  })();

  // ─── Tabs ───
  var tabBtns = document.querySelectorAll('.lp-tab');
  tabBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabBtns.forEach(function (b) { b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      document.querySelectorAll('.lp-panel').forEach(function (p) { p.classList.remove('is-active'); });
      var panel = document.getElementById('panel-' + btn.getAttribute('data-tab'));
      if (panel) panel.classList.add('is-active');
    });
  });

  // ─── Goals ───
  function loadGoals() {
    var container = $('lpGoalList');
    if (!container) return;
    var roomSelect = $('lpGoalRoom');
    var roomId = roomSelect ? roomSelect.value : '';
    if (!roomId) { container.innerHTML = '<div class="lp-empty"><p>Select a room to view goals.</p></div>'; return; }
    container.innerHTML = '<div class="lp-loading"><div class="lp-skeleton" style="height:60px;"></div></div>';
    fetchJSON(API.goals + roomId + '/goals', function (data) {
      if (!data || !data.goals || !data.goals.length) {
        container.innerHTML = '<div class="lp-empty"><p>No active goals. Create one below.</p></div>';
        return;
      }
      var html = '';
      data.goals.forEach(function (g) {
        var pct = g.target_amount > 0 ? Math.min(100, (g.current_amount / g.target_amount) * 100) : 0;
        var reached = g.reached_at ? '<span class="lp-goal-reached">Reached!</span>' : '';
        html += '<div class="lp-goal-card"><h4>' + esc(g.title) + '</h4><div class="lp-goal-bar"><div class="lp-goal-fill" style="width:' + pct + '%"></div></div><div class="lp-goal-meta"><span>' + Math.round(g.current_amount) + ' / ' + Math.round(g.target_amount) + ' ' + g.goal_type + '</span>' + reached + '</div></div>';
      });
      container.innerHTML = html;
    });
  }

  var goalRoomSelect = $('lpGoalRoom');
  if (goalRoomSelect) goalRoomSelect.addEventListener('change', loadGoals);

  var createGoalBtn = $('lpCreateGoalBtn');
  var goalModal = $('lpGoalModal');
  if (createGoalBtn && goalModal) {
    createGoalBtn.addEventListener('click', function () { goalModal.classList.add('is-open'); });
    goalModal.querySelectorAll('.lp-modal-close').forEach(function (b) {
      b.addEventListener('click', function () { goalModal.classList.remove('is-open'); });
    });
    $('lpGoalSave').addEventListener('click', function () {
      var title = ($('lpGoalTitle').value || '').trim();
      var target = parseFloat($('lpGoalTarget').value) || 100;
      var goalType = $('lpGoalType').value;
      var roomId = $('lpGoalRoom').value;
      if (!roomId) { toast('Select a room first', true); return; }
      if (!title) { toast('Enter a goal title', true); return; }
      postJSON(API.goals + roomId + '/goals', { title: title, target_amount: target, goal_type: goalType }, function (res) {
        if (res && res.success) { toast('Goal created!'); goalModal.classList.remove('is-open'); loadGoals(); }
        else { toast('Failed to create goal', true); }
      });
    });
  }

  setTimeout(loadGoals, 500);

  // ─── Earnings ───
  function loadEarnings() {
    var summaryEl = $('lpEarningsSummary');
    var bodyEl = $('lpEarningsBody');
    if (!summaryEl || !bodyEl) return;
    fetchJSON(API.earnings, function (data) {
      if (!data) { summaryEl.innerHTML = '<div class="lp-empty"><p>Could not load earnings.</p></div>'; return; }
      var s = data.summary || {};
      summaryEl.innerHTML = '<div class="lp-earnings-cards"><div class="lp-earnings-card"><strong>' + Math.round(s.total || 0) + '</strong><span>Total</span></div><div class="lp-earnings-card"><strong>' + Math.round(s.available || 0) + '</strong><span>Available</span></div><div class="lp-earnings-card"><strong>' + Math.round(s.pending || 0) + '</strong><span>Pending</span></div></div>';
      var earnings = data.earnings || [];
      if (!earnings.length) { bodyEl.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--px-muted);padding:24px;">No earnings yet.</td></tr>'; return; }
      var html = '';
      earnings.forEach(function (e) {
        html += '<tr><td>' + esc(e.source_type) + '</td><td>' + Math.round(e.amount || 0) + ' ' + esc(e.currency) + '</td><td>' + esc(e.status) + '</td><td>' + (e.created_at ? new Date(e.created_at).toLocaleDateString() : '') + '</td></tr>';
      });
      bodyEl.innerHTML = html;
    });
  }

  var withdrawBtn = $('lpWithdrawBtn');
  if (withdrawBtn) {
    withdrawBtn.addEventListener('click', function () {
      var amount = parseFloat($('lpWithdrawAmount').value);
      if (!amount || amount <= 0) { toast('Enter a valid amount', true); return; }
      postJSON(API.withdraw, { amount: amount }, function (res) {
        if (res && res.success) { toast(res.message || 'Withdrawn!'); loadEarnings(); }
        else { toast(res.error || 'Withdraw failed', true); }
      });
    });
  }

  setTimeout(loadEarnings, 500);

  // ─── Raids ───
  function loadRaids() {
    var outgoingEl = $('lpRaidOutgoing');
    var incomingEl = $('lpRaidIncoming');
    if (!outgoingEl || !incomingEl) return;
    var roomSelect = $('lpGoalRoom');
    var roomId = roomSelect ? roomSelect.value : '';
    if (!roomId) { outgoingEl.innerHTML = '<div class="lp-empty"><p>Select a room to view raids.</p></div>'; incomingEl.innerHTML = ''; return; }
    fetchJSON(API.raids + roomId + '/raids', function (data) {
      if (!data) { outgoingEl.innerHTML = '<div class="lp-empty"><p>Could not load raids.</p></div>'; return; }
      var raids = data.raids || [];
      if (!raids.length) { outgoingEl.innerHTML = '<div class="lp-empty"><p>No raids yet.</p></div>'; } else {
        var html = '';
        raids.forEach(function (r) { html += '<div class="lp-raid-card"><span>Raided <strong>' + esc(r.target_room_id || 'unknown') + '</strong></span><span>' + (r.viewer_count || 0) + ' viewers · ' + esc(r.status) + '</span></div>'; });
        outgoingEl.innerHTML = html;
      }
      var incoming = data.incoming || [];
      if (!incoming.length) { incomingEl.innerHTML = '<div class="lp-empty"><p>No incoming raids.</p></div>'; } else {
        var h = '';
        incoming.forEach(function (r) { h += '<div class="lp-raid-card"><span>Raiding from <strong>' + esc(r.source_room_id || 'unknown') + '</strong></span><span>' + (r.viewer_count || 0) + ' viewers</span></div>'; });
        incomingEl.innerHTML = h;
      }
    });
  }

  if ($('lpGoalRoom')) $('lpGoalRoom').addEventListener('change', loadRaids);
  setTimeout(loadRaids, 600);

  // ─── Moderation ───
  function loadModeration() {
    var modEl = $('lpModList');
    var banEl = $('lpBanList');
    if (!modEl && !banEl) return;
    var roomSelect = $('lpGoalRoom');
    var roomId = roomSelect ? roomSelect.value : '';
    if (!roomId) {
      if (modEl) modEl.innerHTML = '<div class="lp-empty"><p>Select a room to view moderators.</p></div>';
      if (banEl) banEl.innerHTML = '<div class="lp-empty"><p>Select a room to view bans.</p></div>';
      return;
    }
    if (modEl) {
      fetchJSON(API.mods + roomId + '/moderators', function (data) {
        if (!data || !data.moderators) { modEl.innerHTML = '<div class="lp-empty"><p>No moderators.</p></div>'; return; }
        var html = '';
        data.moderators.forEach(function (m) { html += '<div class="lp-mod-row"><span>' + esc(m.display_name || 'Mod') + '</span><span>' + esc(m.role) + '</span></div>'; });
        modEl.innerHTML = html || '<div class="lp-empty"><p>No moderators.</p></div>';
      });
    }
    if (banEl) {
      fetchJSON(API.bans + roomId + '/bans', function (data) {
        if (!data || !data.bans) { banEl.innerHTML = '<div class="lp-empty"><p>No bans.</p></div>'; return; }
        var html = '';
        data.bans.forEach(function (b) { html += '<div class="lp-ban-row"><span>' + esc(b.profile_id || 'unknown') + '</span><span>' + esc(b.reason || 'No reason') + '</span></div>'; });
        banEl.innerHTML = html || '<div class="lp-empty"><p>No bans.</p></div>';
      });
    }
  }

  if ($('lpGoalRoom')) $('lpGoalRoom').addEventListener('change', loadModeration);
  setTimeout(loadModeration, 700);

  // ─── Discover ───
  function loadDiscover() {
    var premiumEl = $('lpPremiumRooms');
    var featuredEl = $('lpFeaturedRooms');
    if (premiumEl) {
      fetchJSON(API.premiumRooms, function (data) {
        if (!data || !data.rooms || !data.rooms.length) { premiumEl.innerHTML = '<div class="lp-empty"><p>No premium rooms.</p></div>'; return; }
        var html = '';
        data.rooms.forEach(function (r) {
          html += '<a class="lp-room-card" href="/live/room/' + esc(r.id) + '"><div class="lp-room-media">' + (r.cover_url ? '<img src="' + esc(r.cover_url) + '">' : '<div class="lp-room-fallback"><i class="fas fa-video"></i></div>') + '<span class="lp-badge">LIVE</span></div><div class="lp-room-info"><h4>' + esc(r.title) + '</h4><p>' + esc(r.host_name) + '</p></div></a>';
        });
        premiumEl.innerHTML = html;
      });
    }
    if (featuredEl) {
      fetchJSON(API.featured, function (data) {
        if (!data || !data.rooms || !data.rooms.length) { featuredEl.innerHTML = '<div class="lp-empty"><p>No featured rooms.</p></div>'; return; }
        var html = '';
        data.rooms.forEach(function (r) {
          html += '<a class="lp-room-card" href="/live/room/' + esc(r.id) + '"><div class="lp-room-media">' + (r.cover_url ? '<img src="' + esc(r.cover_url) + '">' : '<div class="lp-room-fallback"><i class="fas fa-video"></i></div>') + '<span class="lp-badge">LIVE</span></div><div class="lp-room-info"><h4>' + esc(r.title) + '</h4><p>' + esc(r.host_name) + '</p></div></a>';
        });
        featuredEl.innerHTML = html;
      });
    }
  }

  setTimeout(loadDiscover, 800);
})();
