(function () {
  'use strict';

  var S = {
    activeTab: 'tab-overview',
    currentPanel: null,
    stats: {},
  };

  function $(id) { return document.getElementById(id); }

  function toast(msg, isError) {
    var el = document.createElement('div');
    el.className = 'cr-toast' + (isError ? ' cr-toast-error' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 3000);
  }

  function esc(str) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }

  function formatCoins(cents) {
    if (!cents) return '0';
    return Math.round(cents / 100).toLocaleString();
  }

  function loader(show) {
    var el = $('crLoader');
    if (el) el.style.display = show ? 'flex' : 'none';
  }

  function switchTab(tabKey) {
    S.activeTab = tabKey;
    var tabs = document.querySelectorAll('.cr-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle('active', tabs[i].dataset.tab === tabKey);
    }
    var panels = document.querySelectorAll('.cr-panel');
    for (var j = 0; j < panels.length; j++) {
      panels[j].classList.toggle('active', panels[j].id === tabKey);
    }
    S.currentPanel = $(tabKey);
    if (tabKey === 'tab-analytics') renderAnalytics();
    if (tabKey === 'tab-earnings') renderEarnings();
    if (tabKey === 'tab-creator-profile') renderCreatorProfile();
  }

  function onTabClick(e) {
    var btn = e.currentTarget;
    switchTab(btn.dataset.tab);
  }

  function onPeriodClick(e) {
    var btns = document.querySelectorAll('.cr-period-group button');
    for (var i = 0; i < btns.length; i++) btns[i].classList.remove('active');
    e.currentTarget.classList.add('active');
    fetchDashboard();
  }

  // API calls
  function fetchDashboard() {
    loader(true);
    var period = document.querySelector('.cr-period-group button.active');
    var days = period ? parseInt(period.dataset.period, 10) : 30;
    fetch('/creator/api/dashboard')
      .then(function (r) { return r.json(); })
      .then(function (res) {
        loader(false);
        if (!res.ok) { toast('Failed to load dashboard', true); return; }
        S.stats = res.data || {};
        renderOverviewCards();
        renderQuickStats();
      })
      .catch(function () { loader(false); toast('Network error', true); });
  }

  function renderOverviewCards() {
    var s = S.stats;
    var container = $('overviewCards');
    if (!container) return;
    var earnings = s.earnings || {};
    var reels = s.reels_performance || {};
    var live = s.live_performance || {};
    var level = s.creator_level_display || 'Creator';
    var levelClass = 'cr-level-' + (s.creator_level || 'creator');

    container.innerHTML =
      '<div class="cr-card cr-card-accent cr-card-gold">' +
        '<div class="cr-card-label"><i class="fas fa-coins cr-coin-icon"></i>Total Earnings</div>' +
        '<div class="cr-card-value">' + formatCoins(earnings.total_cents) + ' <small>NAD</small></div>' +
        '<div class="cr-card-sub"><i class="fas fa-arrow-up" style="color:var(--cr-green)"></i> Lifetime revenue</div>' +
      '</div>' +
      '<div class="cr-card cr-card-accent cr-card-primary">' +
        '<div class="cr-card-label"><i class="fas fa-broadcast-tower" style="color:var(--cr-primary)"></i>Live Earnings</div>' +
        '<div class="cr-card-value">' + formatCoins(live.earnings_cents) + ' <small>NAD</small></div>' +
        '<div class="cr-card-sub">' + esc(s.total_followers || '0') + ' followers</div>' +
      '</div>' +
      '<div class="cr-card cr-card-accent cr-card-cyan">' +
        '<div class="cr-card-label"><i class="fas fa-clock" style="color:var(--cr-cyan)"></i>Total Views</div>' +
        '<div class="cr-card-value">' + esc(s.total_views || '0') + ' <small>views</small></div>' +
        '<div class="cr-card-sub">Across all content</div>' +
      '</div>' +
      '<div class="cr-card cr-card-accent cr-card-green">' +
        '<div class="cr-card-label"><i class="fas fa-star" style="color:var(--cr-green)"></i>Creator Level</div>' +
        '<div class="cr-card-value"><span class="cr-level-badge ' + levelClass + '">' + esc(level) + '</span></div>' +
        '<div class="cr-card-sub">' + esc(s.total_views || '0') + ' total views</div>' +
      '</div>';
  }

  function renderQuickStats() {
    var s = S.stats;
    var container = $('quickStats');
    if (!container) return;
    var reels = s.reels_performance || {};
    container.innerHTML =
      '<div class="cr-stat-row"><span>Engagement Rate</span><span>' + esc(reels.engagement_rate || '0') + '%</span></div>' +
      '<div class="cr-stat-row"><span>Active Subscribers</span><span>' + esc(s.subscribers || '0') + '</span></div>' +
      '<div class="cr-stat-row"><span>Reel Views</span><span>' + esc(reels.views || '0') + '</span></div>' +
      '<div class="cr-stat-row"><span>Reel Likes</span><span>' + esc(reels.likes || '0') + '</span></div>' +
      '<div class="cr-stat-row"><span>Followers</span><span>' + esc(s.total_followers || '0') + '</span></div>';
  }

  function renderAnalytics() {
    var container = $('analyticsContainer');
    if (!container) return;
    container.innerHTML = '<div class="cr-chart-area"><i class="fas fa-chart-line"></i><p>Analytics graphs would render here with Chart.js or similar library. Data available via /creator/api/analytics.</p></div>';
  }

  function renderEarnings() {
    var container = $('earningsBreakdown');
    if (!container) return;
    var breakdown = (S.stats.earnings || {}).breakdown || {};
    container.innerHTML =
      '<div class="cr-stat-row"><span><i class="fas fa-users cr-coin-icon"></i> Subscriptions</span><span>' + formatCoins(breakdown.subscriptions || 0) + ' NAD</span></div>' +
      '<div class="cr-stat-row"><span><i class="fas fa-gift" style="color:var(--cr-primary)"></i> Gifts</span><span>' + formatCoins(breakdown.gifts || 0) + ' NAD</span></div>' +
      '<div class="cr-stat-row"><span><i class="fas fa-hand-holding-heart" style="color:var(--cr-cyan)"></i> Tips</span><span>' + formatCoins(breakdown.tips || 0) + ' NAD</span></div>' +
      '<div class="cr-stat-row"><span><i class="fas fa-file-alt" style="color:var(--cr-gold)"></i> Paid Content</span><span>' + formatCoins(breakdown.content_purchase || 0) + ' NAD</span></div>';
  }

  function renderCreatorProfile() {
    fetch('/creator/api/profile/me')
      .then(function (r) { return r.json(); })
      .then(function (res) {
        var container = $('creatorProfileContainer');
        if (!container) return;
        if (!res.ok) { container.innerHTML = '<div class="cr-empty"><i class="fas fa-exclamation-circle"></i><p>Failed to load profile.</p></div>'; return; }
        var d = res.data || {};
        var levelClass = 'cr-level-' + (d.creator_level || 'creator');
        var nextHtml = '';
        if (d.next_level) {
          nextHtml = '<div class="cr-stat-row"><span>Next Level</span><span class="cr-badge cr-badge-gold">' + esc(d.next_level_display || d.next_level) + '</span></div>';
        }
        container.innerHTML =
          '<div class="cr-stat-row"><span>Username</span><span>' + esc(d.username || '') + '</span></div>' +
          '<div class="cr-stat-row"><span>Level</span><span class="cr-level-badge ' + levelClass + '">' + esc(d.creator_level_display || '') + '</span></div>' +
          nextHtml +
          '<div class="cr-stat-row"><span>Followers</span><span>' + esc(d.total_followers || '0') + '</span></div>' +
          '<div class="cr-stat-row"><span>Subscribers</span><span>' + esc(d.total_subscribers || '0') + '</span></div>' +
          '<div class="cr-stat-row"><span>Verification</span><span><span class="cr-status-dot ' + (d.verification_status === 'approved' ? 'verified' : d.verification_status === 'pending' ? 'pending' : 'none') + '"></span>' + esc(d.verification_status || 'not_submitted') + '</span></div>' +
          '<div class="cr-stat-row"><span>Verified Badge</span><span>' + esc(d.verified_badge || 'none') + '</span></div>' +
          '<div class="cr-stat-row"><span>Earnings Badge</span><span>' + esc(d.earnings_badge || 'none') + '</span></div>' +
          '<div class="cr-stat-row"><span>Supporters</span><span>' + esc(d.supporter_count || '0') + '</span></div>';
      })
      .catch(function () { /* ignore */ });
  }

  // Form submissions via existing creatorPost helper compatibility
  window.creatorPost = function (url, body) {
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.ok || res.success) {
          toast('Success!');
          fetchDashboard();
        } else {
          toast(res.error || 'Request failed', true);
        }
      })
      .catch(function () { toast('Network error', true); });
  };

  // Initialize
  document.addEventListener('DOMContentLoaded', function () {
    // Tab clicks
    var tabs = document.querySelectorAll('.cr-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', onTabClick);
    }
    // Period clicks
    var periodBtns = document.querySelectorAll('.cr-period-group button');
    for (var j = 0; j < periodBtns.length; j++) {
      periodBtns[j].addEventListener('click', onPeriodClick);
    }
    // Subscription form
    var subBtn = $('saveSubBtn');
    if (subBtn) {
      subBtn.addEventListener('click', function () {
        var tier = $('creatorSubTier');
        var price = $('creatorSubPrice');
        creatorPost('/creator/subscriptions', {
          tier: tier ? tier.value : 'standard',
          price_coins: parseInt(price ? price.value : '0', 10) || 0,
        });
      });
    }
    // Paid post form
    var postBtn = $('createPaidPostBtn');
    if (postBtn) {
      postBtn.addEventListener('click', function () {
        var title = $('paidPostTitle');
        var price = $('paidPostPrice');
        creatorPost('/creator/paid-posts', {
          title: title ? title.value : 'Paid post',
          price_coins: parseInt(price ? price.value : '0', 10) || 0,
        });
      });
    }
    // Load initial data
    fetchDashboard();
  });
})();
