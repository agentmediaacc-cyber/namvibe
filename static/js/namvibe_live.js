/* ── NAMVIBE LIVE — NVC Coin Powered ── */
(function () {
  "use strict";

  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function apiPost(url, body, cb) {
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json(); }).then(function (d) { if (cb) cb(d); }).catch(function () {});
  }

  function apiGet(url, cb) {
    fetch(url).then(function (r) { return r.json(); }).then(function (d) { if (cb) cb(d); }).catch(function () {});
  }

  function toast(msg) {
    if (window.NamVibeToast && window.NamVibeToast.show)
      window.NamVibeToast.success(msg);
  }

  var socket = null;
  var currentRoom = null;
  var isHost = false;
  var mediaStream = null;
  var nvcBalance = 0;
  var liveState = {
    joined: false,
    socketBound: false,
    livekitToken: null,
    livekitWsUrl: null,
    connectionState: 'idle'
  };

  function setConnectionState(label) {
    liveState.connectionState = label;
    var el = document.getElementById('lvConnectionState');
    if (el) el.textContent = label;
  }

  /* ── Data from DB (fetched from API) ── */
  var CATEGORIES = [];
  var TIERS = [];
  var GIFTS = [];
  var GIFT_TIERS = [];
  var LIVE_TYPES = [];
  var ROOM_TYPES = [];

  function loadConfig(cb) {
    apiGet('/api/config/all', function(data) {
      if (data && data.live_categories) {
        CATEGORIES = data.live_categories.map(function(c) {
          return { id: c.slug, label: c.label, icon: c.icon, live: c.is_live };
        });
      }
      if (data && data.gift_tiers) {
        TIERS = data.gift_tiers.map(function(t) {
          var rng = t.min_nvc + '–' + (t.max_nvc >= 999999 ? '10000+' : t.max_nvc) + ' NVC';
          return { id: t.slug, label: t.label, range: rng, color: t.color };
        });
        GIFT_TIERS = data.gift_tiers.map(function(t) { return t.slug; });
      }
      if (data && data.gifts) {
        GIFTS = data.gifts.map(function(g) {
          return { emoji: g.emoji, name: g.name, price_nvc: parseFloat(g.price_nvc), tier: g.tier, premium: g.is_premium };
        });
      }
      if (data && data.live_types) {
        LIVE_TYPES = data.live_types.map(function(t) {
          return { id: t.slug, label: t.label };
        });
      }
      if (data && data.room_types) {
        ROOM_TYPES = data.room_types.map(function(t) {
          return { id: t.slug, label: t.label };
        });
      }
      if (cb) cb();
    });
  }

  /* ── SVG Icons ── */
  function icon(path) {
    return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + path + '</svg>';
  }

  /* ── Render Live Card ── */
  function renderLiveCard(room) {
    var isScheduled = room.status === 'scheduled';
    var badge = isScheduled
      ? '<span class="lv-badge-scheduled">📅 Scheduled</span>'
      : '<span class="lv-badge-live"><span></span> LIVE</span>';
    var viewerHtml = !isScheduled
      ? '<span class="lv-viewer-count">' + icon('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>') + ' ' + (room.viewer_count || 0) + '</span>'
      : '<span class="lv-time-remaining">' + (room.time_remaining || 'Soon') + '</span>';
    var catTag = room.category ? '<span class="lv-cat-tag">' + room.category + '</span>' : '';
    return '<div class="lv-card' + (isScheduled ? ' lv-scheduled' : '') + '" data-room-id="' + room.id + '">' +
      '<div class="lv-card-thumb">' +
      '<img src="' + (room.thumbnail_url || room.host_avatar || '/static/img/live-placeholder.jpg') + '" alt="" loading="lazy">' +
      badge + catTag + viewerHtml +
      '</div>' +
      '<div class="lv-card-body">' +
      '<div class="lv-card-host">' +
      '<img src="' + (room.host_avatar || '/static/img/default-avatar.png') + '" alt="">' +
      '<div><strong>' + (room.host_name || room.host_username || 'Host') + '</strong>' +
      (room.is_verified ? '<small> ✓ Verified</small>' : '') +
      '</div></div>' +
      '<div class="lv-card-title">' + (room.title || 'Untitled Stream') + '</div>' +
      '<div class="lv-card-tags">' +
      (room.tags || []).map(function (t) { return '<span>#' + t + '</span>'; }).join('') +
      '</div></div></div>';
  }

  /* ── Render Gift Button (NVC coin pricing with tier) ── */
  function renderGift(g) {
    var tierClass = 'lv-gift-' + g.tier;
    var premiumBadge = g.premium ? '<span class="lv-gift-premium">★ PREMIUM</span>' : '';
    var tierColor = '';
    for (var i = 0; i < TIERS.length; i++) {
      if (TIERS[i].id === g.tier) {
        tierColor = TIERS[i].color;
        break;
      }
    }
    var tierHtml = '<span class="lv-gift-tier" style="color:' + tierColor + '">' + g.tier.toUpperCase() + '</span>';
    return '<button class="lv-gift-btn ' + tierClass + '" data-gift="' + g.name + '" data-nvc="' + g.price_nvc + '" data-emoji="' + g.emoji + '" data-tier="' + g.tier + '">' +
      premiumBadge +
      '<span class="lv-gift-emoji">' + g.emoji + '</span>' +
      '<span class="lv-gift-name">' + g.name + '</span>' +
      '<span class="lv-gift-price">🪙 ' + g.price_nvc + ' NVC</span>' +
      tierHtml + '</button>';
  }

  /* ── Render Participant ── */
  function renderParticipant(p) {
    var roleClass = p.role === 'host' ? 'host' : p.role === 'mod' ? 'mod' : p.role === 'speaker' ? 'speaker' : '';
    return '<div class="lv-participant" data-profile-id="' + p.id + '">' +
      '<img src="' + (p.avatar_url || '/static/img/default-avatar.png') + '" alt="">' +
      '<div class="lv-participant-info"><strong>' + (p.display_name || p.username || 'User') + '</strong>' +
      '<small>' + (p.followers_count || 0) + ' followers</small></div>' +
      '<span class="lv-participant-role' + (roleClass ? ' ' + roleClass : '') + '">' + (p.role || 'viewer') + '</span></div>';
  }

  /* ── Render Chat Message ── */
  function renderChatMsg(msg) {
    if (msg.message_type === 'system') {
      return '<div class="lv-chat-msg system">' + (msg.body || '') + '</div>';
    }
    var userClass = msg.is_mod ? ' mod' : '';
    userClass += msg.is_verified ? ' verified' : '';
    var giftHtml = msg.gift_emoji ? ' <span class="lv-chat-gift">' + msg.gift_emoji + ' ' + (msg.gift_name || 'Gift') + '</span>' : '';
    var pinClass = msg.is_pinned ? ' pinned' : '';
    return '<div class="lv-chat-msg' + pinClass + '">' +
      '<span class="lv-chat-user' + userClass + '">' + (msg.sender_name || 'User') + '</span>' +
      (msg.body || '') + giftHtml + '</div>';
  }

  /* ── Render Poll ── */
  function renderPoll(poll) {
    var total = (poll.votes || []).reduce(function (a, b) { return a + b; }, 0) || 1;
    var html = '<div class="lv-poll" data-poll-id="' + poll.id + '"><h4>' + poll.question + '</h4>';
    (poll.options || []).forEach(function (opt, i) {
      var pct = Math.round(((poll.votes || [])[i] || 0) / total * 100);
      html += '<div class="lv-poll-option" data-option="' + i + '">' +
        '<div class="lv-poll-bar" style="width:' + pct + '%"></div>' +
        '<div class="lv-poll-label"><span>' + opt + '</span><span>' + pct + '%</span></div></div>';
    });
    html += '</div>';
    return html;
  }

  /* ── Render Product ── */
  function renderProduct(prod) {
    return '<div class="lv-product" data-product-id="' + prod.id + '">' +
      '<img src="' + (prod.image_url || '/static/img/default-product.png') + '" alt="" loading="lazy">' +
      '<strong>' + prod.title + '</strong>' +
      '<small>' + (prod.discount_pct ? prod.discount_pct + '% OFF ' : '') + '$' + prod.price + '</small></div>';
  }

  /* ── NVC Wallet ── */
  function loadWalletBalance(cb) {
    apiGet('/api/live/wallet/balance', function (d) {
      if (d && d.ok) {
        nvcBalance = d.balance;
        updateWalletUI();
        if (cb) cb(d.balance);
      }
    });
  }

  function updateWalletUI() {
    var el = document.querySelector('.lv-nvc-balance');
    if (el) {
      el.innerHTML = '🪙 ' + nvcBalance.toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:2}) + ' NVC';
    }
    var shortEl = document.querySelector('.lv-nvc-short');
    if (shortEl) {
      shortEl.innerHTML = '🪙 ' + Math.floor(nvcBalance);
    }
  }

  /* ── Open Buy NVC Modal ── */
  function openBuyNVC() {
    var existing = document.querySelector('.lv-nvc-modal');
    if (existing) existing.remove();

    var modal = document.createElement('div');
    modal.className = 'lv-modal lv-nvc-modal active';
    modal.innerHTML = '<div class="lv-modal-card" style="position:relative;">' +
      '<button class="lv-modal-close" id="lvNVCMClose">✕</button>' +
      '<h2>🪙 Buy NVC Coins</h2>' +
      '<p style="color:var(--lv-muted);font-size:13px;margin:0 0 16px;">Use NVC coins to send gifts, support creators, and unlock premium features.</p>' +
      '<div class="lv-nvc-packages" id="lvNVCPackages">Loading packages...</div></div>';

    document.body.appendChild(modal);

    document.getElementById('lvNVCMClose').addEventListener('click', function () { modal.remove(); });
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.remove(); });

    apiGet('/api/live/wallet/packages', function (d) {
      var packages = d && d.packages ? d.packages : [];
      var grid = document.getElementById('lvNVCPackages');
      if (!grid) return;
      if (packages.length === 0) {
        grid.innerHTML = '<div style="text-align:center;padding:20px;color:var(--lv-muted);">No packages available</div>';
        return;
      }
      grid.innerHTML = packages.map(function (p) {
        var popular = p.is_popular ? '<span class="lv-nvc-popular">POPULAR</span>' : '';
        var badge = p.badge ? '<span class="lv-nvc-badge">' + p.badge + '</span>' : '';
        return '<button class="lv-nvc-pkg" data-pkg-id="' + p.id + '">' + popular + badge +
          '<strong class="lv-nvc-pkg-name">' + p.name + '</strong>' +
          '<span class="lv-nvc-pkg-coins">🪙 ' + Math.floor(p.total_coins) + ' NVC</span>' +
          (p.bonus_coins > 0 ? '<span class="lv-nvc-pkg-bonus">+' + Math.floor(p.bonus_coins) + ' BONUS</span>' : '') +
          '<span class="lv-nvc-pkg-price">$' + p.price.toFixed(2) + '</span></button>';
      }).join('');

      grid.addEventListener('click', function (e) {
        var btn = e.target.closest('.lv-nvc-pkg');
        if (!btn) return;
        var pkgId = btn.dataset.pkgId;
        apiPost('/api/live/wallet/purchase', { package_id: parseInt(pkgId) }, function (d) {
          if (d && d.ok) {
            toast('Purchased ' + d.package_name + ' — ' + Math.floor(d.coins_added) + ' NVC added!');
            nvcBalance = d.new_balance;
            updateWalletUI();
            modal.remove();
          } else {
            toast('Purchase failed');
          }
        });
      });
    });
  }

  /* ── Open Coin Gift Modal ── */
  function openCoinGift(roomId) {
    var existing = document.querySelector('.lv-coin-gift-modal');
    if (existing) existing.remove();

    var modal = document.createElement('div');
    modal.className = 'lv-modal lv-coin-gift-modal active';
    modal.innerHTML = '<div class="lv-modal-card" style="position:relative;">' +
      '<button class="lv-modal-close" id="lvCoinClose">✕</button>' +
      '<h2>🪙 Send NVC Coins as Gift</h2>' +
      '<p style="color:var(--lv-muted);font-size:13px;margin:0 0 12px;">Your balance: 🪙 <strong id="lvCoinBalSend">' + Math.floor(nvcBalance) + '</strong> NVC</p>' +
      '<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;">' +
      '<input type="number" id="lvCoinAmount" min="1" max="' + Math.floor(nvcBalance) + '" value="10" style="flex:1;padding:12px;border:1px solid var(--lv-border);border-radius:10px;background:var(--lv-surface2);color:var(--lv-text);font-size:16px;font-weight:700;">' +
      '<span style="font-size:18px;">🪙</span></div>' +
      '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;">' +
      [10, 50, 100, 500, 1000].map(function (v) {
        return '<button class="lv-coin-preset" data-val="' + v + '">' + v + '</button>';
      }).join('') +
      '</div>' +
      '<div style="display:flex;gap:10px;">' +
      '<button class="lv-btn lv-btn-secondary" id="lvCoinCancel" style="flex:1;">Cancel</button>' +
      '<button class="lv-btn lv-btn-primary" id="lvCoinSend" style="flex:2;">Send Coins 💰</button></div></div>';

    document.body.appendChild(modal);

    document.getElementById('lvCoinClose').addEventListener('click', function () { modal.remove(); });
    document.getElementById('lvCoinCancel').addEventListener('click', function () { modal.remove(); });
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.remove(); });

    var amountInput = document.getElementById('lvCoinAmount');
    document.querySelectorAll('.lv-coin-preset').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (amountInput) amountInput.value = btn.dataset.val;
      });
    });

    document.getElementById('lvCoinSend').addEventListener('click', function () {
      var amount = parseFloat(amountInput ? amountInput.value : 10);
      if (isNaN(amount) || amount < 1) { toast('Enter a valid amount'); return; }
      if (amount > nvcBalance) { toast('Insufficient NVC coins. Buy more!'); return; }
      apiPost('/api/live/' + roomId + '/gift', {
        gift_name: Math.floor(amount) + ' NVC',
        gift_emoji: '🪙',
        amount: amount,
        is_coin_gift: true,
      }, function (d) {
        if (d && d.ok !== false) {
          toast('Sent ' + Math.floor(amount) + ' NVC coins!');
          nvcBalance = d.new_balance || (nvcBalance - amount);
          updateWalletUI();
          appendChat({ sender_name: 'You', body: 'sent ' + Math.floor(amount) + ' NVC coins', gift_emoji: '🪙', gift_name: Math.floor(amount) + ' NVC', message_type: 'gift' });
          showGiftAnimation('🪙', Math.floor(amount) + ' NVC', 'legendary');
          modal.remove();
        } else if (d && d.error === 'Insufficient NVC coins') {
          toast('Not enough NVC! Buy coins?');
        } else {
          toast('Failed to send coins');
        }
      });
    });
  }

  /* ── Load Live Hub ── */
  function loadHub() {
    var categories = document.getElementById('lvCategories');
    if (categories) {
      categories.innerHTML = CATEGORIES.map(function (c) {
        return '<button class="lv-cat-btn' + (c.id === 'all' ? ' active' : '') + (c.live ? ' live-dot' : '') + '" data-cat="' + c.id + '">' + c.icon + ' ' + c.label + '</button>';
      }).join('');

      categories.addEventListener('click', function (e) {
        var btn = e.target.closest('.lv-cat-btn');
        if (!btn) return;
        categories.querySelectorAll('.lv-cat-btn').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var cat = btn.dataset.cat;
        filterByCategory(cat);
      });
    }

    var sections = document.querySelectorAll('[data-live-section]');
    sections.forEach(function (sec) {
      var cat = sec.dataset.liveSection;
      apiGet('/api/live/rooms?category=' + cat + '&limit=12', function (d) {
        var rooms = d && d.rooms ? d.rooms : [];
        var grid = sec.querySelector('.lv-grid');
        if (grid) {
          if (rooms.length === 0) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--lv-muted);font-size:13px;">No live streams in ' + cat + ' right now</div>';
          } else {
            grid.innerHTML = rooms.map(renderLiveCard).join('');
          }
        }
      });
    });

    apiGet('/api/live/scheduled?limit=12', function (d) {
      var sched = d && d.rooms ? d.rooms : [];
      var grid = document.querySelector('[data-live-section="scheduled"] .lv-grid');
      if (grid) {
        if (sched.length === 0) {
          grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--lv-muted);font-size:13px;">No upcoming streams scheduled</div>';
        } else {
          grid.innerHTML = sched.map(renderLiveCard).join('');
        }
      }
    });

    document.addEventListener('click', function (e) {
      var card = e.target.closest('.lv-card');
      if (card) {
        var roomId = card.dataset.roomId;
        if (roomId) window.location.href = '/live/' + roomId;
      }
    });
  }

  function filterByCategory(cat) {
    var sections = document.querySelectorAll('[data-live-section]');
    sections.forEach(function (sec) {
      var secCat = sec.dataset.liveSection;
      if (cat === 'all' || secCat === cat) {
        sec.style.display = 'block';
      } else {
        sec.style.display = 'none';
      }
    });
    var sched = document.querySelector('[data-live-section="scheduled"]');
    if (sched) sched.style.display = 'block';
  }

  /* ── Open Go Live Modal ── */
  function openGoLive() {
    var existing = document.querySelector('.lv-modal');
    if (existing) existing.remove();

    var modal = document.createElement('div');
    modal.className = 'lv-modal active';
    modal.innerHTML =
      '<div class="lv-modal-card" style="position:relative;">' +
      '<button class="lv-modal-close" id="lvModalClose">✕</button>' +
      '<h2>' + icon('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>') + ' Go Live</h2>' +

      '<div class="lv-form-group"><label>Stream Title</label><input type="text" id="lvTitle" placeholder="What are you streaming?" maxlength="100"></div>' +

      '<div class="lv-form-grid">' +
      '<div class="lv-form-group"><label>Category</label><select id="lvCategory">' +
      CATEGORIES.filter(function (c) { return c.id !== 'all' && c.id !== 'new' && c.id !== 'scheduled' && c.id !== 'featured' && c.id !== 'trending' && c.id !== 'friends'; }).map(function (c) {
        return '<option value="' + c.id + '">' + c.icon + ' ' + c.label + '</option>';
      }).join('') +
      '</select></div>' +

      '<div class="lv-form-group"><label>Room Type</label><select id="lvRoomType">' +
      ROOM_TYPES.map(function (r) {
        return '<option value="' + r.id + '">' + r.label + '</option>';
      }).join('') +
      '</select></div></div>' +

      '<div class="lv-form-grid">' +
      '<div class="lv-form-group"><label>Live Type</label><select id="lvLiveType">' +
      LIVE_TYPES.map(function (t) {
        return '<option value="' + t.id + '"' + (t.id === 'public' ? ' selected' : '') + '>' + t.label + '</option>';
      }).join('') +
      '</select></div>' +

      '<div class="lv-form-group"><label>Video Quality</label><select id="lvQuality">' +
      ['480p','720p','1080p','2K','4K'].map(function (q) {
        return '<option value="' + q + '"' + (q === '1080p' ? ' selected' : '') + '>' + q + '</option>';
      }).join('') +
      '</select></div></div>' +

      '<div class="lv-form-group"><label>Description (optional)</label><textarea id="lvDescription" placeholder="Tell viewers what to expect..."></textarea></div>' +

      '<div class="lv-form-group"><label>Tags (comma separated)</label><input type="text" id="lvTags" placeholder="music, concert, live"></div>' +

      '<div class="lv-form-group"><label>Audience Controls</label><div class="lv-form-grid">' +
      '<label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--lv-muted);cursor:pointer;"><input type="checkbox" id="lvSubOnly"> Subscribers only chat</label>' +
      '<label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--lv-muted);cursor:pointer;"><input type="checkbox" id="lvFollowersOnly"> Followers only chat</label>' +
      '</div></div>' +

      '<div style="display:flex;gap:10px;margin-top:16px;">' +
      '<button class="lv-btn lv-btn-secondary" id="lvScheduleBtn" style="flex:1;">' + icon('<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>') + ' Schedule</button>' +
      '<button class="lv-btn lv-btn-primary" id="lvStartBtn" style="flex:3;">' + icon('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>') + ' Start Live Now</button>' +
      '</div></div>';

    document.body.appendChild(modal);

    document.getElementById('lvModalClose').addEventListener('click', function () { modal.remove(); });
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.remove(); });

    document.getElementById('lvStartBtn').addEventListener('click', function () {
      var data = gatherFormData();
      data.status = 'live';
      apiPost('/api/live/start', data, function (d) {
        if (d && d.room_id) {
          toast('Stream started!');
          modal.remove();
          window.location.href = '/live/' + d.room_id;
        } else {
          toast('Failed to start stream');
        }
      });
    });

    document.getElementById('lvScheduleBtn').addEventListener('click', function () {
      var data = gatherFormData();
      data.status = 'scheduled';
      apiPost('/api/live/start', data, function (d) {
        if (d && d.room_id) {
          toast('Stream scheduled!');
          modal.remove();
          window.location.reload();
        } else {
          toast('Failed to schedule stream');
        }
      });
    });
  }

  function gatherFormData() {
    var title = document.getElementById('lvTitle')?.value?.trim() || 'Untitled Stream';
    var category = document.getElementById('lvCategory')?.value || 'entertainment';
    var roomType = document.getElementById('lvRoomType')?.value || 'music';
    var liveType = document.getElementById('lvLiveType')?.value || 'public';
    var quality = document.getElementById('lvQuality')?.value || '1080p';
    var description = document.getElementById('lvDescription')?.value?.trim() || '';
    var tags = (document.getElementById('lvTags')?.value?.trim() || '').split(',').map(function (t) { return t.trim(); }).filter(Boolean);
    var subOnly = document.getElementById('lvSubOnly')?.checked || false;
    var followersOnly = document.getElementById('lvFollowersOnly')?.checked || false;
    return { title: title, category: category, room_type: roomType, live_type: liveType, video_quality: quality, description: description, tags: tags, sub_only_chat: subOnly, followers_only: followersOnly };
  }

  /* ── Live Room ── */
  function initRoom(roomId) {
    currentRoom = roomId;
    socket = window.chainSocket || (typeof io !== 'undefined' ? io() : null);
    bindLiveSocket(roomId);
    var chatInput = document.getElementById('lvChatInput');
    var chatSend = document.getElementById('lvChatSend');
    var giftBtn = document.getElementById('lvGiftBtn');
    var emojiBtn = document.getElementById('lvEmojiBtn');
    var startBtn = document.querySelector('[data-action="start-live-session"]');
    var reactionBtn = document.querySelector('[data-action="send-reaction"]');

    /* Load NVC balance */
    loadWalletBalance();

    /* Tab switching */
    var tabs = document.querySelectorAll('.lv-room-tab');
    tabs.forEach(function (t) {
      t.addEventListener('click', function () {
        tabs.forEach(function (b) { b.classList.remove('active'); });
        t.classList.add('active');
        var panel = t.dataset.panel;
        document.querySelectorAll('.lv-room-panel').forEach(function (p) { p.style.display = 'none'; });
        var target = document.getElementById('panel-' + panel);
        if (target) target.style.display = panel === 'chat' ? 'flex' : panel === 'gifts' ? 'flex' : 'block';
      });
    });

    /* Send chat */
    function sendChat() {
      var text = chatInput ? chatInput.value.trim() : '';
      if (!text) return;
      if (chatInput) chatInput.value = '';
      apiPost('/api/live/' + roomId + '/chat', { body: text }, function (d) {
        if (!(d && d.ok)) {
          toast((d && d.error) || 'Could not send message');
        }
      });
    }
    if (chatSend) chatSend.addEventListener('click', sendChat);
    if (chatInput) chatInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendChat(); });

    /* Gift button -> switch to gifts tab */
    if (giftBtn) {
      giftBtn.addEventListener('click', function () {
        switchTab('gifts');
      });
    }

    function switchTab(panelId) {
      tabs.forEach(function (b) { b.classList.remove('active'); });
      var tab = document.querySelector('[data-panel="' + panelId + '"]');
      if (tab) tab.classList.add('active');
      document.querySelectorAll('.lv-room-panel').forEach(function (p) { p.style.display = 'none'; });
      var target = document.getElementById('panel-' + panelId);
      if (target) target.style.display = panelId === 'chat' ? 'flex' : panelId === 'gifts' ? 'flex' : 'block';
    }

    /* Emoji picker */
    if (emojiBtn && window.NamVibeEmojiPicker) {
      emojiBtn.addEventListener('click', function () {
        window.NamVibeEmojiPicker.show(emojiBtn, function (emoji) {
          if (chatInput) {
            chatInput.value += emoji;
            chatInput.focus();
          }
        });
      });
    }

    /* ── Gift Grid with Tiered Catalog ── */
    var giftGrid = document.querySelector('#panel-gifts .lv-gifts');
    if (giftGrid) {
      renderGiftGrid(giftGrid, roomId);
    }

    function renderGiftGrid(grid, rid) {
      /* Tier filter buttons */
      var filterHtml = '<div class="lv-gift-tier-tabs">' +
        TIERS.map(function (t) {
          return '<button class="lv-gift-tier-btn' + (t.id === 'bronze' ? ' active' : '') + '" data-tier="' + t.id + '" style="--tier-color:' + t.color + '">' +
            '<span class="lv-gift-tier-dot" style="background:' + t.color + '"></span>' +
            t.label + ' <small>' + t.range + '</small></button>';
        }).join('') +
        '<button class="lv-gift-tier-btn lv-coin-gift-btn" id="lvCoinGiftBtn" title="Send NVC coins as gift">🪙 Send Coins</button>' +
        '</div>' +
        '<div class="lv-gift-wallet-bar">' +
        '<span class="lv-nvc-balance" style="cursor:pointer;" id="lvNVCDisplay">🪙 0 NVC</span>' +
        '<button class="lv-btn lv-btn-primary" id="lvBuyNVCTop" style="font-size:11px;padding:6px 14px;border-radius:20px;">Buy Coins</button>' +
        '</div>' +
        '<div class="lv-gift-grid"></div>';

      grid.innerHTML = filterHtml;

      var gridContainer = grid.querySelector('.lv-gift-grid');
      var activeTier = 'bronze';

      function showTier(tierId) {
        activeTier = tierId;
        var filtered = GIFTS.filter(function (g) { return g.tier === tierId; });
        if (gridContainer) {
          gridContainer.innerHTML = filtered.map(renderGift).join('');
        }
        grid.querySelectorAll('.lv-gift-tier-btn').forEach(function (b) { b.classList.remove('active'); });
        var active = grid.querySelector('[data-tier="' + tierId + '"]');
        if (active) active.classList.add('active');
      }

      showTier('bronze');

      grid.addEventListener('click', function (e) {
        var tierBtn = e.target.closest('.lv-gift-tier-btn[data-tier]');
        if (tierBtn) {
          showTier(tierBtn.dataset.tier);
          return;
        }

        /* Buy coins button */
        if (e.target.closest('#lvBuyNVCTop')) {
          openBuyNVC();
          return;
        }

        /* Send coin gift */
        if (e.target.closest('#lvCoinGiftBtn')) {
          openCoinGift(rid);
          return;
        }

        /* NVC balance click */
        if (e.target.closest('#lvNVCDisplay')) {
          openBuyNVC();
          return;
        }

        /* Gift button click */
        var btn = e.target.closest('.lv-gift-btn');
        if (!btn) return;
        var emoji = btn.dataset.emoji;
        var name = btn.dataset.gift;
        var nvc = parseFloat(btn.dataset.nvc);
        var tierType = btn.dataset.tier || 'bronze';

        if (nvc > nvcBalance) {
          toast('Not enough NVC! Balance: ' + Math.floor(nvcBalance) + ', needed: ' + Math.floor(nvc));
          return;
        }

        apiPost('/api/live/' + rid + '/gift', {
          gift_name: name,
          gift_emoji: emoji,
          amount: nvc,
          is_coin_gift: false,
        }, function (d) {
          if (d && d.ok !== false) {
            nvcBalance = d.new_balance || (nvcBalance - nvc);
            updateWalletUI();
            showGiftAnimation(emoji, name, tierType);
            appendChat({ sender_name: 'You', body: 'sent ', gift_emoji: emoji, gift_name: name, message_type: 'gift' });
            toast('Sent ' + emoji + ' ' + name + '!');
          } else if (d && d.error === 'Insufficient NVC coins') {
            toast('Not enough NVC! Balance: ' + Math.floor(nvcBalance));
          } else {
            toast('Failed to send gift');
          }
        });
      });
    }

    /* Room controls */
    if (startBtn) {
      startBtn.addEventListener('click', function () {
        startLiveSession(roomId);
      });
    }

    var endBtn = document.querySelector('[data-action="end-live"]');
    if (endBtn) {
      endBtn.addEventListener('click', function () {
        if (confirm('End this live stream?')) {
          apiPost('/api/live/' + roomId + '/end', {}, function () {
            toast('Stream ended');
            window.location.href = '/live/';
          });
        }
      });
    }

    var micBtn = document.querySelector('[data-action="toggle-mic"]');
    if (micBtn) {
      micBtn.addEventListener('click', function () {
        if (mediaStream) {
          var audioTracks = mediaStream.getAudioTracks();
          audioTracks.forEach(function (t) { t.enabled = !t.enabled; });
          micBtn.innerHTML = audioTracks[0]?.enabled
            ? icon('<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>')
            : icon('<line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>');
        }
      });
    }

    var camBtn = document.querySelector('[data-action="toggle-cam"]');
    if (camBtn) {
      camBtn.addEventListener('click', function () {
        if (mediaStream) {
          var videoTracks = mediaStream.getVideoTracks();
          videoTracks.forEach(function (t) { t.enabled = !t.enabled; });
          camBtn.innerHTML = videoTracks[0]?.enabled
            ? icon('<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>')
            : icon('<line x1="1" y1="1" x2="23" y2="23"/><path d="M21 8l-5 4 5 4V8z"/><rect x="3" y="6" width="13" height="12" rx="2"/>');
        }
      });
    }

    if (reactionBtn) {
      reactionBtn.addEventListener('click', function () {
        sendReaction(roomId, reactionBtn.dataset.reaction || 'heart');
      });
    }

    /* Load chat history */
    apiGet('/api/live/' + roomId + '/chat?limit=50', function (d) {
      var msgs = d && d.messages ? d.messages : [];
      var chatBox = document.getElementById('lvChatBox');
      if (chatBox) {
        if (msgs.length === 0) {
          chatBox.innerHTML = '<div class="lv-chat-msg system">Welcome to the stream! Say hello 👋</div>';
        } else {
          chatBox.innerHTML = msgs.map(renderChatMsg).join('');
          chatBox.scrollTop = chatBox.scrollHeight;
        }
      }
    });

    /* Load participants */
    apiGet('/api/live/' + roomId + '/participants?limit=50', function (d) {
      var participants = d && d.participants ? d.participants : [];
      var list = document.getElementById('lvParticipantList');
      if (list) {
        if (participants.length === 0) {
          list.innerHTML = '<div style="padding:12px;color:var(--lv-muted);font-size:13px;text-align:center;">No participants yet</div>';
        } else {
          list.innerHTML = participants.map(renderParticipant).join('');
        }
        var count = document.querySelector('.lv-room-tab[data-panel="participants"] .lv-count');
        if (count) count.textContent = participants.length;
      }
    });

    /* Load polls */
    apiGet('/api/live/' + roomId + '/polls', function (d) {
      var polls = d && d.polls ? d.polls : [];
      var container = document.getElementById('panel-polls');
      if (container && polls.length > 0) {
        container.innerHTML = polls.map(renderPoll).join('');
        container.addEventListener('click', function (e) {
          var opt = e.target.closest('.lv-poll-option');
          if (!opt) return;
          var pollId = opt.closest('.lv-poll')?.dataset.pollId;
          var option = opt.dataset.option;
          apiPost('/api/live/' + roomId + '/vote', { poll_id: pollId, option: option }, function () {
            toast('Vote recorded!');
          });
        });
      }
    });

    /* Load products */
    apiGet('/api/live/' + roomId + '/products', function (d) {
      var prods = d && d.products ? d.products : [];
      var container = document.getElementById('lvProducts');
      if (container) {
        if (prods.length > 0) {
          container.innerHTML = prods.map(renderProduct).join('');
        } else {
          container.style.display = 'none';
        }
      }
    });

    /* Polling */
    var lastChatId = 0;
    setInterval(function () {
      apiGet('/api/live/' + roomId + '/chat?after=' + lastChatId + '&limit=20', function (d) {
        var msgs = d && d.messages ? d.messages : [];
        msgs.forEach(function (msg) {
          appendChat(msg);
          if (msg.id > lastChatId) lastChatId = msg.id;
        });
      });
    }, 3000);

    setInterval(function () {
      apiGet('/api/live/' + roomId + '/stats', function (d) {
        if (d) {
          var countEl = document.querySelector('.lv-room-tab[data-panel="participants"] .lv-count');
          if (countEl && d.participant_count != null) countEl.textContent = d.participant_count;
          var viewerEl = document.getElementById('lvViewerCount');
          if (viewerEl && d.viewer_count != null) viewerEl.textContent = d.viewer_count;
        }
      });
    }, 10000);

    /* Refresh NVC balance periodically */
    setInterval(function () { loadWalletBalance(); }, 30000);
  }

  function appendChat(msg) {
    var chatBox = document.getElementById('lvChatBox');
    if (!chatBox) return;
    if (msg.id && document.querySelector('[data-msg-id="' + msg.id + '"]')) return;
    var el = document.createElement('div');
    el.innerHTML = renderChatMsg(msg);
    el.firstChild?.setAttribute('data-msg-id', msg.id || '');
    chatBox.appendChild(el.firstChild || el);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function bindLiveSocket(roomId) {
    if (!socket || liveState.socketBound) return;
    liveState.socketBound = true;

    socket.on('live:viewers', function (payload) {
      if (!payload || payload.room_id && payload.room_id !== roomId) return;
      var viewerEl = document.getElementById('lvViewerCount');
      if (viewerEl && payload.count != null) viewerEl.textContent = payload.count;
    });

    socket.on('live:chat', function (payload) {
      if (payload) appendChat(payload);
    });

    socket.on('live:reaction', function (payload) {
      if (!payload) return;
      showGiftAnimation(payload.reaction_type === 'heart' ? '❤️' : '🔥', payload.reaction_type || 'reaction', 'bronze');
    });

    socket.on('live:room_ended', function (payload) {
      if (!payload || payload.room_id !== roomId) return;
      setConnectionState('Stream ended');
      stopLocalMedia();
      toast('This live stream has ended');
    });
  }

  function joinSocketRoom(roomId) {
    if (!socket || liveState.joined) return;
    socket.emit('join_live_room', { room_id: roomId });
    liveState.joined = true;
  }

  function leaveSocketRoom(roomId) {
    if (!socket || !liveState.joined) return;
    socket.emit('leave_live_room', { room_id: roomId });
    liveState.joined = false;
  }

  function stopLocalMedia() {
    if (!mediaStream) return;
    mediaStream.getTracks().forEach(function (track) { track.stop(); });
    mediaStream = null;
  }

  function sendReaction(roomId, reactionType) {
    if (!socket) return;
    socket.emit('live_reaction', { room_id: roomId, reaction_type: reactionType || 'heart' });
  }

  function startLiveSession(roomId) {
    setConnectionState(isHost ? 'Requesting camera and microphone…' : 'Joining stream…');
    if (isHost) {
      startWebcam(function (ok) {
        if (ok) requestProviderSession(roomId, 'host');
      });
    } else {
      requestProviderSession(roomId, 'viewer');
    }
  }

  function requestProviderSession(roomId, role) {
    joinSocketRoom(roomId);
    apiPost('/api/live/livekit-token', { room_id: roomId, role: role }, function (d) {
      if (d && d.ok && d.token) {
        liveState.livekitToken = d.token;
        liveState.livekitWsUrl = d.ws_url || '';
        setConnectionState('Connected');
        return;
      }
      apiGet('/api/live/webrtc-config', function () {
        setConnectionState(role === 'host' ? 'Broadcast ready' : 'Connected');
      });
    });
  }

  /* ── Premium Tiered Gift Animations ── */
  function showGiftAnimation(emoji, name, tier) {
    var animClass = 'lv-gift-anim';
    switch (tier) {
      case 'bronze': animClass += ' lv-anim-bronze'; break;
      case 'silver': animClass += ' lv-anim-silver'; break;
      case 'gold': animClass += ' lv-anim-gold'; break;
      case 'diamond': animClass += ' lv-anim-diamond'; break;
      case 'legendary': animClass += ' lv-anim-legendary'; break;
    }

    var el = document.createElement('div');
    el.className = animClass;
    el.innerHTML = '<span class="lv-gift-fly-emoji">' + emoji + '</span>';
    el.style.left = (Math.random() * 40 + 30) + '%';
    el.style.bottom = '10%';
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 2500);

    var notif = document.createElement('div');
    notif.className = 'lv-gift-notif';
    if (tier === 'legendary' || tier === 'diamond') {
      notif.classList.add('lv-gift-notif-premium');
    }
    notif.innerHTML = '<span class="lv-gift-notif-icon">' + emoji + '</span> <strong>' + name + '</strong>';
    if (tier === 'legendary') {
      notif.innerHTML += ' <span class="lv-gift-legendary-badge">★ LEGENDARY</span>';
    } else if (tier === 'diamond') {
      notif.innerHTML += ' <span class="lv-gift-diamond-badge">♦ PREMIUM</span>';
    }
    document.body.appendChild(notif);
    setTimeout(function () { notif.remove(); }, 3500);

    /* Screen flash for legendary */
    if (tier === 'legendary') {
      var flash = document.createElement('div');
      flash.className = 'lv-gift-flash';
      document.body.appendChild(flash);
      setTimeout(function () { flash.remove(); }, 600);
    }
  }

  function startWebcam(done) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      toast('Camera not available');
      setConnectionState('Camera not available');
      if (done) done(false);
      return;
    }
    var videoEl = document.querySelector('.lv-room-video video') || document.querySelector('.lv-room-video');
    navigator.mediaDevices.getUserMedia({ video: isHost ? { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } } : false, audio: true })
      .then(function (stream) {
        mediaStream = stream;
        if (videoEl && videoEl.tagName === 'VIDEO') {
          videoEl.srcObject = stream;
          videoEl.muted = true;
          videoEl.setAttribute('playsinline', 'playsinline');
          videoEl.style.display = 'block';
          videoEl.play();
        } else if (videoEl) {
          var vid = document.createElement('video');
          vid.srcObject = stream;
          vid.autoplay = true;
          vid.muted = true;
          vid.playsInline = true;
          vid.style.width = '100%';
          vid.style.height = '100%';
          vid.style.objectFit = 'cover';
          videoEl.innerHTML = '';
          videoEl.appendChild(vid);
        }
        var placeholder = document.getElementById('lvStreamPlaceholder');
        if (placeholder) placeholder.style.display = 'none';
        setConnectionState('Media ready');
        if (done) done(true);
      })
      .catch(function (error) {
        toast('Camera or microphone permission denied');
        setConnectionState((error && error.message) || 'Media permission denied');
        if (done) done(false);
      });
  }

  /* ── Init ── */
  function boot() {
    if (document.querySelector('[data-room-id]')) loadHub();
    if (document.getElementById('lvChatBox')) {
      var roomRoot = document.querySelector('[data-live-room-id]');
      if (roomRoot && roomRoot.dataset.liveRoomId) {
        isHost = roomRoot.dataset.liveIsHost === 'true';
        initRoom(roomRoot.dataset.liveRoomId);
      }
    }
  }

  if (document.querySelector('.lv-app')) {
    loadConfig(boot);
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (document.querySelector('.lv-app') && !document.getElementById('lvChatBox')) {
      loadConfig(function() { loadHub(); });
    }
    var goLiveBtn = document.querySelector('[data-action="go-live"]');
    if (goLiveBtn) goLiveBtn.addEventListener('click', openGoLive);

    var scheduleBtn = document.querySelector('[data-action="schedule-live"]');
    if (scheduleBtn) scheduleBtn.addEventListener('click', openGoLive);
    window.addEventListener('beforeunload', function () {
      if (currentRoom) leaveSocketRoom(currentRoom);
      stopLocalMedia();
    });
  });

  window.NamVibeLive = {
    loadHub: loadHub,
    initRoom: initRoom,
    openGoLive: openGoLive,
    openBuyNVC: openBuyNVC,
    loadWalletBalance: loadWalletBalance,
  };

})();
