/* NamVibe Phase 59 — Premium Homepage: Real Feed API + Infinite Scroll + Actions */

(function () {
  'use strict';

  var state = {
    activeTab: 'for_you',
    pages: {},
    loading: false,
    loadingMore: false,
    hasMore: true,
    currentPage: 1,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    initFeedTabs();
    initDismissAds();
    initMobileNav();
    initStoryScroll();
    initReconnectToast();
    initComposerFocus();
    initTabTracking();
    initAvatarFallback();
    initStoryModal();
  }

  /* ================================================================
     Feed Tab Switching — Fetch from API
  ================================================================ */
  function initFeedTabs() {
    var tabs = document.querySelectorAll('.feed-tab');
    if (!tabs.length) return;

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        var tabName = tab.getAttribute('data-tab') || tab.textContent.trim().toLowerCase().replace(/\s+/g, '_');
        // Map display names to API tab values
        var tabMap = {
          'for_you': 'for_you',
          'for you': 'for_you',
          'following': 'following',
          'public': 'public',
          'nearby': 'nearby',
          'live': 'live',
          'reels': 'reels',
          'trending': 'trending',
        };
        var apiTab = tabMap[tabName] || 'for_you';

        tabs.forEach(function (t) { t.classList.remove('is-active'); });
        tab.classList.add('is-active');
        if (window.updateActiveTab) window.updateActiveTab(tabName);

        if (state.activeTab !== apiTab) {
          state.activeTab = apiTab;
          state.currentPage = 1;
          state.hasMore = true;
          loadFeed(apiTab, 1, true);
        }
      });
    });

    // Load initial tab if feed container exists
    if (document.querySelector('.feed-items')) {
      loadFeed('for_you', 1, true);
      initInfiniteScroll();
    }
  }

  /* ================================================================
     Load Feed from API
  ================================================================ */
  function loadFeed(tab, page, replace) {
    if (state.loading) return;

    var container = document.querySelector('.feed-items');
    if (!container) return;

    state.loading = true;
    var skeleton = container.querySelector('.feed-skeleton');
    if (replace && !skeleton) {
      container.innerHTML = renderSkeleton();
    } else if (replace) {
      container.innerHTML = renderSkeleton();
    }

    var url = '/api/home/feed?tab=' + encodeURIComponent(tab) + '&page=' + page;

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        state.loading = false;
        if (!data.ok) {
          if (replace) container.innerHTML = renderEmpty('Could not load feed. Try again.');
          return;
        }
        state.hasMore = data.has_more;
        state.currentPage = data.page || page;

        var items = data.items || [];
        var html = '';
        items.forEach(function (item) { html += renderFeedItem(item); });

        if (!html) {
          html = renderEmpty('Nothing here yet. Check back soon!');
        }

        if (replace) {
          container.innerHTML = html;
        } else {
          container.insertAdjacentHTML('beforeend', html);
        }

        wirePostActions(container);
        wireFollowButtons(container);
        initDismissAdsIn(container);
      })
      .catch(function () {
        state.loading = false;
        if (replace) container.innerHTML = renderEmpty('Something went wrong. Tap to retry.');
      });
  }

  /* ================================================================
     Infinite Scroll
  ================================================================ */
  function initInfiniteScroll() {
    var sentinel = document.querySelector('.feed-sentinel');
    if (!sentinel) return;

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !state.loading && !state.loadingMore && state.hasMore) {
            loadMore();
          }
        });
      }, { rootMargin: '200px' });
      observer.observe(sentinel);
    } else {
      window.addEventListener('scroll', function () {
        if (state.loadingMore || !state.hasMore) return;
        var rect = sentinel.getBoundingClientRect();
        if (rect.top < window.innerHeight + 300) {
          loadMore();
        }
      });
    }
  }

  function loadMore() {
    if (state.loadingMore || !state.hasMore) return;
    state.loadingMore = true;

    var nextPage = (state.currentPage || 1) + 1;
    var container = document.querySelector('.feed-items');
    if (!container) { state.loadingMore = false; return; }

    var loader = document.querySelector('.feed-loader');
    if (loader) loader.style.display = 'block';

    var url = '/api/home/feed?tab=' + encodeURIComponent(state.activeTab) + '&page=' + nextPage;

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        state.loadingMore = false;
        if (loader) loader.style.display = 'none';

        if (!data.ok) return;
        state.hasMore = data.has_more;
        state.currentPage = data.page || nextPage;

        var items = data.items || [];
        var html = '';
        items.forEach(function (item) { html += renderFeedItem(item); });

        if (html) {
          container.insertAdjacentHTML('beforeend', html);
          wirePostActions(container);
          wireFollowButtons(container);
          initDismissAdsIn(container);
        }
      })
      .catch(function () {
        state.loadingMore = false;
        if (loader) loader.style.display = 'none';
      });
  }

  /* ================================================================
     Feed Item Renderer
  ================================================================ */
  function renderFeedItem(item) {
    if (!item) return '';
    var type = item.type || 'post';

    switch (type) {
      case 'live':       return renderLiveItem(item);
      case 'reel':       return renderReelItem(item);
      case 'ad':
      case 'sponsored':  return renderAdItem(item);
      case 'announcement': return renderAnnouncementItem(item);
      case 'suggested_user': return renderSuggestedUserItem(item);
      default:           return renderPostItem(item);
    }
  }

  function renderPostHeader(item) {
    var initial = (item.display_name || 'C')[0];
    var avatar = item.avatar_url
      ? '<img src="' + escapeHtml(item.avatar_url) + '" alt="' + escapeHtml(item.display_name) + '">'
      : '<span>' + escapeHtml(initial) + '</span>';
    var verified = item.verified ? '<i class="fas fa-circle-check verified-badge"></i>' : '';
    var label = item.sponsored
      ? '<span class="post-content-label sponsored">Sponsored</span>'
      : '<span class="post-content-label public">Public</span>';
    var location = item.location
      ? ' &middot; <i class="fas fa-location-dot"></i> ' + escapeHtml(item.location)
      : '';
    var timeHtml = item.created_label
      ? '<i class="far fa-clock"></i> ' + escapeHtml(item.created_label)
      : '';
    return '' +
      '<div class="post-header">' +
        '<div class="post-avatar">' + avatar + '</div>' +
        '<div class="post-author-info">' +
          '<div class="post-author-name">' + escapeHtml(item.display_name || 'NamVibe') + ' ' + verified + ' ' + label + '</div>' +
          '<div class="post-author-username">@' + escapeHtml(item.username || 'chain') + '</div>' +
          '<div class="post-time-location">' + timeHtml + location + '</div>' +
        '</div>' +
        '<button type="button" class="post-more-btn" aria-label="More"><i class="fas fa-ellipsis"></i></button>' +
      '</div>';
  }

  function renderPostItem(item) {
    var mediaHtml = '';
    if (item.video_url) {
      mediaHtml = '<div class="post-media"><video src="' + escapeHtml(item.video_url) + '" controls playsinline preload="metadata"></video></div>';
    } else if (item.media_url) {
      mediaHtml = '<div class="post-media"><img src="' + escapeHtml(item.media_url) + '" alt="" loading="lazy"></div>';
    }
    var textHtml = item.text ? '<div class="post-body"><div class="post-text post-caption">' + escapeHtml(item.text) + '</div></div>' : '';
    return '' +
      '<article id="post-' + item.id + '" class="post-card-premium" data-post-id="' + escapeHtml(item.id) + '">' +
        renderPostHeader(item) +
        textHtml +
        mediaHtml +
        '<div class="post-stats">' +
          '<span><strong data-count="likes">' + (item.likes_count || 0) + '</strong> likes</span>' +
          '<span><strong data-count="comments">' + (item.comments_count || 0) + '</strong> comments</span>' +
          '<span><strong data-count="views">' + (item.view_count || 0) + '</strong> views</span>' +
        '</div>' +
        '<div class="post-actions">' +
          '<button type="button" class="post-action-btn" data-action="like" data-id="' + escapeHtml(item.id) + '"><i class="far fa-heart"></i> Like</button>' +
          '<button type="button" class="post-action-btn" data-action="comment" data-id="' + escapeHtml(item.id) + '"><i class="far fa-comment"></i> Comment</button>' +
          '<button type="button" class="post-action-btn" data-action="share" data-id="' + escapeHtml(item.id) + '"><i class="fas fa-share"></i> Share</button>' +
          '<button type="button" class="post-action-btn" data-action="save" data-id="' + escapeHtml(item.id) + '"><i class="far fa-bookmark"></i> Save</button>' +
        '</div>' +
      '</article>';
  }

  function renderLiveItem(item) {
    var initial = (item.display_name || 'L')[0];
    var avatar = item.avatar_url
      ? '<img src="' + escapeHtml(item.avatar_url) + '" alt="">'
      : '<span>' + escapeHtml(initial) + '</span>';
    return '' +
      '<article class="post-card-premium live-card" data-type="live">' +
        '<div class="post-header">' +
          '<div class="post-avatar">' + avatar + '</div>' +
          '<div class="post-author-info">' +
            '<div class="post-author-name">' + escapeHtml(item.display_name || 'Live') + ' <span class="post-content-label trending" style="background:rgba(37, 99, 235,0.12);color:var(--hp-primary);">LIVE</span></div>' +
            '<div class="post-author-username">@' + escapeHtml(item.username || 'live') + '</div>' +
            '<div class="post-time-location">' + (item.category ? escapeHtml(item.category) : '') + ' &middot; ' + (item.view_count || 0) + ' watching</div>' +
          '</div>' +
        '</div>' +
        '<div class="post-body"><div class="post-text post-caption">' + escapeHtml(item.text || 'Live now') + '</div></div>' +
        '<div class="post-actions">' +
          '<a href="' + (item.watch_url || '#') + '" class="post-action-btn" style="text-decoration:none;color:var(--hp-primary);font-weight:700;"><i class="fas fa-video"></i> Watch Live</a>' +
        '</div>' +
      '</article>';
  }

  function renderReelItem(item) {
    var initial = (item.display_name || 'R')[0];
    var avatar = item.avatar_url
      ? '<img src="' + escapeHtml(item.avatar_url) + '" alt="">'
      : '<span>' + escapeHtml(initial) + '</span>';
    var mediaHtml = item.video_url
      ? '<div class="post-media"><video src="' + escapeHtml(item.video_url) + '" muted playsinline preload="metadata"></video></div>'
      : (item.media_url ? '<div class="post-media"><img src="' + escapeHtml(item.media_url) + '" alt="" loading="lazy"></div>' : '');
    return '' +
      '<article class="post-card-premium reel-card" data-type="reel">' +
        renderPostHeader(item) +
        '<div class="post-body"><div class="post-text post-caption">' + escapeHtml(item.text || '') + '</div></div>' +
        mediaHtml +
        '<div class="post-stats">' +
          '<span><strong>' + (item.likes_count || 0) + '</strong> likes</span>' +
          '<span><strong>' + (item.view_count || 0) + '</strong> views</span>' +
        '</div>' +
        '<div class="post-actions">' +
          '<button type="button" class="post-action-btn" data-action="like" data-id="' + escapeHtml(item.id) + '"><i class="far fa-heart"></i> Like</button>' +
          '<button type="button" class="post-action-btn" data-action="comment" data-id="' + escapeHtml(item.id) + '"><i class="far fa-comment"></i> Comment</button>' +
          '<button type="button" class="post-action-btn" data-action="share" data-id="' + escapeHtml(item.id) + '"><i class="fas fa-share"></i> Share</button>' +
        '</div>' +
      '</article>';
  }

  function renderAdItem(item) {
    var title = item.display_name || 'Sponsored';
    var body = item.text || 'Promoted content from our partners.';
    var ctaUrl = item.link_url || '#';
    return '' +
      '<div class="ad-card" data-ad-id="' + escapeHtml(item.id || '') + '">' +
        '<div class="ad-card-sponsored"><span>Sponsored</span><button type="button" class="ad-card-dismiss" aria-label="Dismiss"><i class="fas fa-times"></i></button></div>' +
        '<div class="ad-card-image"><i class="fas fa-bolt"></i></div>' +
        '<div class="ad-card-title">' + escapeHtml(title) + '</div>' +
        '<div class="ad-card-body">' + escapeHtml(body) + '</div>' +
        '<a href="' + escapeHtml(ctaUrl) + '" class="ad-card-cta">Learn More</a>' +
      '</div>';
  }

  function renderAnnouncementItem(item) {
    return '' +
      '<article class="post-card-premium" data-type="announcement">' +
        '<div class="post-header">' +
          '<div class="post-avatar" style="background:#0f766e;"><span>A</span></div>' +
          '<div class="post-author-info">' +
            '<div class="post-author-name">' + escapeHtml(item.text || 'Announcement') + ' <span class="post-content-label trending">Announcement</span></div>' +
            '<div class="post-time-location"><i class="far fa-clock"></i> ' + escapeHtml(item.created_label || '') + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="post-body"><div class="post-text post-caption">' + escapeHtml(item.text || '') + '</div></div>' +
      '</article>';
  }

  function renderSuggestedUserItem(item) {
    var initial = (item.display_name || 'U')[0];
    var avatar = item.avatar_url
      ? '<img src="' + escapeHtml(item.avatar_url) + '" alt="">'
      : '<span>' + escapeHtml(initial) + '</span>';
    var location = item.location ? '<div class="suggested-mutual">' + escapeHtml(item.location) + '</div>' : '';
    return '' +
      '<div class="suggested-card" style="padding:12px 0;border-bottom:1px solid var(--hp-border-light);">' +
        '<div class="suggested-avatar">' + avatar + '</div>' +
        '<div class="suggested-info">' +
          '<div class="suggested-name">' + escapeHtml(item.display_name || 'User') + (item.verified ? ' <i class="fas fa-circle-check verified-badge"></i>' : '') + '</div>' +
          '<div class="suggested-username">@' + escapeHtml(item.username || 'user') + '</div>' +
          location +
        '</div>' +
        '<button type="button" class="suggested-follow-btn" data-profile-id="' + escapeHtml(item.profile_id || item.id) + '">Follow</button>' +
      '</div>';
  }

  /* ================================================================
     Skeleton & Empty State Renderers
  ================================================================ */
  function renderSkeleton() {
    var html = '';
    for (var i = 0; i < 3; i++) {
      html += '' +
        '<div class="post-card-premium feed-skeleton-item">' +
          '<div class="skeleton-row" style="display:flex;gap:12px;padding:16px;">' +
            '<div class="skeleton-box" style="width:40px;height:40px;border-radius:50%;"></div>' +
            '<div style="flex:1;">' +
              '<div class="skeleton-box" style="width:60%;height:14px;margin-bottom:8px;"></div>' +
              '<div class="skeleton-box" style="width:40%;height:12px;"></div>' +
            '</div>' +
          '</div>' +
          '<div class="skeleton-box" style="height:200px;margin:0 0 16px;"></div>' +
          '<div class="skeleton-box" style="width:80%;height:14px;margin:0 auto 16px;"></div>' +
          '<div style="display:flex;gap:8px;padding:8px 16px;">' +
            '<div class="skeleton-box" style="flex:1;height:36px;border-radius:4px;"></div>' +
            '<div class="skeleton-box" style="flex:1;height:36px;border-radius:4px;"></div>' +
            '<div class="skeleton-box" style="flex:1;height:36px;border-radius:4px;"></div>' +
          '</div>' +
        '</div>';
    }
    return '<div class="feed-skeleton">' + html + '</div>';
  }

  function renderEmpty(message) {
    return '' +
      '<div class="feed-empty">' +
        '<div class="feed-empty-icon"><i class="fas fa-inbox"></i></div>' +
        '<div class="feed-empty-title">' + escapeHtml(message || 'Nothing here yet') + '</div>' +
        '<div class="feed-empty-message">Check back soon for new content.</div>' +
      '</div>';
  }

  /* ================================================================
     Wire Post Actions — Like, Save, Share
  ================================================================ */
  function wirePostActions(container) {
    if (!container) return;
    container.querySelectorAll('[data-action="like"]:not([data-wired])').forEach(function (btn) {
      btn.setAttribute('data-wired', '1');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var postId = btn.getAttribute('data-id');
        var card = btn.closest('.post-card-premium');
        var icon = btn.querySelector('i');
        var isLiked = btn.classList.toggle('is-liked');
        icon.className = isLiked ? 'fas fa-heart' : 'far fa-heart';
        var countEl = card ? card.querySelector('.post-stats [data-count="likes"]') : null;
        if (countEl) {
          var current = parseInt(countEl.textContent, 10) || 0;
          countEl.textContent = isLiked ? current + 1 : Math.max(0, current - 1);
        }
        if (postId) {
          fetch('/api/home/post/' + postId + '/like', { method: 'POST' }).catch(function () {});
        }
      });
    });

    container.querySelectorAll('[data-action="save"]:not([data-wired])').forEach(function (btn) {
      btn.setAttribute('data-wired', '1');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var postId = btn.getAttribute('data-id');
        var icon = btn.querySelector('i');
        var saved = icon.classList.contains('fas');
        icon.className = saved ? 'far fa-bookmark' : 'fas fa-bookmark';
        if (postId) {
          fetch('/api/home/post/' + postId + '/save', { method: 'POST' }).catch(function () {});
        }
      });
    });

    container.querySelectorAll('[data-action="share"]:not([data-wired])').forEach(function (btn) {
      btn.setAttribute('data-wired', '1');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var postId = btn.getAttribute('data-id');
        if (navigator.share) {
          var url = window.location.origin + '/post/' + postId;
          navigator.share({ url: url }).catch(function () {});
        }
        if (postId) {
          fetch('/api/home/post/' + postId + '/share', { method: 'POST' }).catch(function () {});
        }
      });
    });
  }

  /* ================================================================
     Wire Follow Buttons
  ================================================================ */
  function wireFollowButtons(container) {
    if (!container) return;
    container.querySelectorAll('.suggested-follow-btn:not([data-wired])').forEach(function (btn) {
      btn.setAttribute('data-wired', '1');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var profileId = btn.getAttribute('data-profile-id');
        var wasFollowing = btn.classList.toggle('is-following');
        var originalText = btn.textContent;
        btn.textContent = wasFollowing ? 'Following' : 'Follow';
        btn.disabled = true;
        var method = wasFollowing ? 'POST' : 'POST';
        var url = wasFollowing
          ? '/api/home/follow/' + profileId
          : '/api/home/unfollow/' + profileId;
        if (wasFollowing) {
          // Was following, now unfollowing — use unfollow endpoint
          fetch('/api/home/unfollow/' + profileId, { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              btn.disabled = false;
              if (!d.ok) {
                btn.classList.remove('is-following');
                btn.textContent = originalText;
              }
            })
            .catch(function () {
              btn.disabled = false;
              btn.classList.remove('is-following');
              btn.textContent = originalText;
            });
        } else {
          // Was not following, now following
          fetch('/api/home/follow/' + profileId, { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              btn.disabled = false;
              if (!d.ok) {
                btn.classList.remove('is-following');
                btn.textContent = originalText;
              }
            })
            .catch(function () {
              btn.disabled = false;
              btn.classList.remove('is-following');
              btn.textContent = originalText;
            });
        }
      });
    });
  }

  /* ================================================================
     Dismiss Ads
  ================================================================ */
  function initDismissAds() {
    document.querySelectorAll('.ad-card-dismiss').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var card = btn.closest('.ad-card');
        if (card) {
          card.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
          card.style.opacity = '0';
          card.style.transform = 'translateY(-8px)';
          setTimeout(function () { card.remove(); }, 220);
        }
      });
    });
  }

  function initDismissAdsIn(container) {
    if (!container) return;
    container.querySelectorAll('.ad-card-dismiss:not([data-wired])').forEach(function (btn) {
      btn.setAttribute('data-wired', '1');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var card = btn.closest('.ad-card');
        if (card) {
          card.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
          card.style.opacity = '0';
          card.style.transform = 'translateY(-8px)';
          setTimeout(function () { card.remove(); }, 220);
        }
      });
    });
  }

  /* ================================================================
     Mobile Nav
  ================================================================ */
  function initMobileNav() {
    var currentPath = window.location.pathname;
    document.querySelectorAll('.mobile-nav-item').forEach(function (item) {
      var href = item.getAttribute('href');
      if (href && currentPath.indexOf(href) === 0) {
        item.classList.add('is-active');
      }
    });
  }

  /* ================================================================
     Story Strip — Smooth Scroll
  ================================================================ */
  function initStoryScroll() {
    var strip = document.querySelector('.story-strip');
    if (!strip) return;
    var isDown = false;
    var startX = 0;
    var scrollLeft = 0;

    strip.addEventListener('mousedown', function (e) {
      isDown = true;
      startX = e.pageX - strip.offsetLeft;
      scrollLeft = strip.scrollLeft;
      strip.style.cursor = 'grabbing';
    });

    strip.addEventListener('mouseleave', function () {
      isDown = false;
      strip.style.cursor = 'grab';
    });

    strip.addEventListener('mouseup', function () {
      isDown = false;
      strip.style.cursor = 'grab';
    });

    strip.addEventListener('mousemove', function (e) {
      if (!isDown) return;
      e.preventDefault();
      var x = e.pageX - strip.offsetLeft;
      var walk = (x - startX) * 1.5;
      strip.scrollLeft = scrollLeft - walk;
    });
  }

  /* ================================================================
     Helpers
  ================================================================ */
  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /* ================================================================
     Hide skeleton when feed content loads
  ================================================================ */
  function hideSkeleton() {
    var skeleton = document.getElementById('feed-skeleton');
    if (skeleton) skeleton.style.display = 'none';
  }

  /* Wire hideSkeleton into feed loading */
  var _origLoadFeed = loadFeed;
  loadFeed = function(tab, page, replace) {
    hideSkeleton();
    return _origLoadFeed(tab, page, replace);
  };

  /* ================================================================
     Reconnect Toast — show/hide based on socket events
  ================================================================ */
  function initReconnectToast() {
    var banner = document.getElementById('chain-reconnect-banner') || document.querySelector('.reconnect-banner');
    if (!banner) return;
    if (window.io && !window.socket) {
      try {
        window.socket = io({
          transports: ['polling'],
          upgrade: false,
          reconnection: true,
          reconnectionAttempts: 10,
          reconnectionDelay: 1000,
          reconnectionDelayMax: 10000,
          randomizationFactor: 0.5,
        });
        window.socket.on('connect', function() { banner.classList.remove('show'); });
        window.socket.on('disconnect', function() { banner.classList.add('show'); });
        window.socket.on('connect_error', function() { banner.classList.add('show'); });
        window.socket.on('reconnect', function() { banner.classList.remove('show'); });
      } catch(e) {}
    }
  }

  /* ================================================================
     Composer focus effect
  ================================================================ */
  function initComposerFocus() {
    var placeholder = document.querySelector('.composer-placeholder');
    if (!placeholder) return;
    placeholder.addEventListener('focus', function() {
      var card = this.closest('.composer-card');
      if (card) card.classList.add('is-focused');
    });
    placeholder.addEventListener('blur', function() {
      var card = this.closest('.composer-card');
      if (card) card.classList.remove('is-focused');
    });
  }

  /* ================================================================
     Track active tab in URL hash
  ================================================================ */
  function initTabTracking() {
    window.updateActiveTab = function(tabName) {
      try {
        if (history.replaceState) {
          var url = new URL(window.location);
          url.searchParams.set('tab', tabName);
          history.replaceState(null, '', url.toString());
        }
      } catch(e) {}
    };
    // Restore tab from URL on load
    try {
      var params = new URL(window.location).searchParams;
      var savedTab = params.get('tab');
      if (savedTab) {
        var tab = document.querySelector('.feed-tab[data-tab="' + savedTab + '"]');
        if (tab) tab.click();
      }
    } catch(e) {}
  }

  /* ================================================================
     Phase 59 — Real-Time Feed Counters via Socket.IO
   ================================================================ */
  function initRealtimeCounters() {
    if (!window.io) return;
    if (window._realtimeCountersInitialized) return;
    window._realtimeCountersInitialized = true;

    function safeGetSocket() {
      if (window.socket) return window.socket;
      try {
        var s = io({
          transports: ['polling'],
          upgrade: false,
          reconnection: true,
          reconnectionAttempts: 5,
          reconnectionDelay: 2000,
        });
        window.socket = s;
        return s;
      } catch(e) { return null; }
    }

    var s = safeGetSocket();
    if (!s) return;

    s.on('like:update', function(data) {
      if (!data || !data.post_id) return;
      var card = document.getElementById('post-' + data.post_id);
      if (!card) return;
      var el = card.querySelector('[data-count="likes"]');
      if (el && data.count !== undefined) {
        el.textContent = data.count;
        el.classList.remove('counter-updated');
        void el.offsetWidth;
        el.classList.add('counter-updated');
      }
    });

    s.on('comment:update', function(data) {
      if (!data || !data.post_id) return;
      var card = document.getElementById('post-' + data.post_id);
      if (!card) return;
      var el = card.querySelector('[data-count="comments"]');
      if (el && data.count !== undefined) {
        el.textContent = data.count;
        el.classList.remove('counter-updated');
        void el.offsetWidth;
        el.classList.add('counter-updated');
      }
    });

    s.on('view:update', function(data) {
      if (!data || !data.post_id) return;
      var card = document.getElementById('post-' + data.post_id);
      if (!card) return;
      var el = card.querySelector('[data-count="views"]');
      if (el && data.count !== undefined) {
        el.textContent = data.count;
      }
    });
  }

  /* ================================================================
     Phase 59 — Save Posts Collection UI with Local Toast
   ================================================================ */
  function initSaveWithToast() {
    document.addEventListener('click', function(e) {
      var btn = e.target.closest('[data-action="save"]');
      if (!btn) return;
      var icon = btn.querySelector('i');
      if (!icon) return;
      var isSaved = icon.classList.contains('fas');
      icon.className = isSaved ? 'far fa-bookmark' : 'fas fa-bookmark';
      btn.classList.toggle('is-saved', !isSaved);

      var postId = btn.getAttribute('data-id');
      if (postId) {
        fetch('/api/home/post/' + postId + '/save', { method: 'POST' })
          .then(function(r) { return r.json(); })
          .then(function(d) {
            if (d.ok) {
              showSaveToast('Saved!');
            } else {
              showSaveToast('Saved locally');
              icon.className = 'fas fa-bookmark';
              btn.classList.add('is-saved');
            }
          })
          .catch(function() {
            showSaveToast('Saved locally');
            icon.className = 'fas fa-bookmark';
            btn.classList.add('is-saved');
          });
      } else {
        showSaveToast('Saved locally');
        icon.className = 'fas fa-bookmark';
        btn.classList.add('is-saved');
      }
    });
  }

  function showSaveToast(msg) {
    var existing = document.querySelector('.save-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.className = 'save-toast';
    toast.textContent = msg;
    document.body.appendChild(toast);
    requestAnimationFrame(function() {
      toast.classList.add('show');
    });
    setTimeout(function() {
      toast.classList.remove('show');
      setTimeout(function() { toast.remove(); }, 300);
    }, 2000);
  }

  /* ================================================================
     Phase 59 — Poll Composer UI
   ================================================================ */
  function initPollUI() {
    var pollBtn = document.querySelector('[data-action="poll"]');
    if (!pollBtn) return;

    pollBtn.addEventListener('click', function(e) {
      e.preventDefault();
      var form = document.getElementById('poll-form');
      if (!form) return;
      var isVisible = form.style.display !== 'none';
      form.style.display = isVisible ? 'none' : 'block';
      if (!isVisible) {
        document.getElementById('poll-question').focus();
      }
    });

    var cancelBtn = document.getElementById('poll-cancel');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', function() {
        var form = document.getElementById('poll-form');
        if (form) form.style.display = 'none';
      });
    }

    var addOptBtn = document.getElementById('poll-add-option');
    if (addOptBtn) {
      addOptBtn.addEventListener('click', function() {
        var container = document.getElementById('poll-extra-options');
        if (!container) return;
        var count = container.children.length + 3; // 3 = question + option1 + option2
        if (count >= 6) return; // Max 6 total options
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'poll-input';
        input.placeholder = 'Option ' + count;
        input.maxLength = 100;
        container.appendChild(input);
        input.focus();
        if (count >= 6) addOptBtn.style.display = 'none';
      });
    }

    var submitBtn = document.getElementById('poll-submit');
    if (submitBtn) {
      submitBtn.addEventListener('click', function() {
        showSaveToast('Poll drafts are not available on this page yet.');
        var form = document.getElementById('poll-form');
        if (form) form.style.display = 'none';
      });
    }
  }

  /* ================================================================
     Phase 59 — Wire Feed Counters for JS-rendered items
   ================================================================ */
  function wireCounters(container) {
    if (!container) return;
    container.querySelectorAll('[data-count="likes"]:not([data-counter-wired])').forEach(function(el) {
      el.setAttribute('data-counter-wired', '1');
    });
    container.querySelectorAll('[data-count="comments"]:not([data-counter-wired])').forEach(function(el) {
      el.setAttribute('data-counter-wired', '1');
    });
  }

  /* Override wirePostActions to call save and counter wire */
  var _origWirePostActions = wirePostActions;
  wirePostActions = function(container) {
    _origWirePostActions(container);
    wireCounters(container);
  };

  /* ================================================================
     Init Phase 59 features
   ================================================================ */
  initRealtimeCounters();
  initSaveWithToast();
  initPollUI();

  /* ================================================================
     Phase 70 — Avatar fallback on image error
   ================================================================ */
  function initAvatarFallback() {
    document.addEventListener('error', function (e) {
      var target = e.target;
      if (target.tagName !== 'IMG') return;
      var parent = target.parentElement;
      if (!parent) return;
      var initial = (target.alt || '?')[0].toUpperCase();
      if (!initial || initial === '') initial = '?';
      target.style.display = 'none';
      var fallback = document.createElement('span');
      fallback.className = 'avatar-fallback';
      fallback.textContent = initial;
      parent.appendChild(fallback);
    }, true);
  }

  /* ================================================================
     Phase 70 — Story Create Modal
   ================================================================ */
  function initStoryModal() {
    var overlay = document.getElementById('story-modal');
    var closeBtn = document.getElementById('story-modal-close');
    var cancelBtn = document.getElementById('story-btn-cancel');
    var uploadZone = document.getElementById('story-upload-zone');
    var fileInput = document.getElementById('story-file-input');
    var preview = document.getElementById('story-preview');
    var removeMedia = document.getElementById('story-remove-media');
    var captionInput = document.getElementById('story-caption');
    var postBtn = document.getElementById('story-btn-post');
    var errorEl = document.getElementById('story-error');
    var loadingEl = document.getElementById('story-loading');

    if (!overlay || !uploadZone) return;

    var selectedFile = null;

    function openModal() {
      overlay.classList.add('is-open');
      document.body.style.overflow = 'hidden';
      resetModal();
    }

    function closeModal() {
      overlay.classList.remove('is-open');
      document.body.style.overflow = '';
      selectedFile = null;
    }

    function resetModal() {
      selectedFile = null;
      preview.classList.remove('is-visible');
      preview.innerHTML = '';
      preview.appendChild(removeMedia);
      captionInput.value = '';
      errorEl.classList.remove('is-visible');
      errorEl.textContent = '';
      loadingEl.classList.remove('is-visible');
      postBtn.disabled = true;
      uploadZone.style.display = 'block';
    }

    function showError(msg) {
      errorEl.textContent = msg;
      errorEl.classList.add('is-visible');
      loadingEl.classList.remove('is-visible');
      postBtn.disabled = false;
    }

    // Open triggers
    document.querySelectorAll('[data-open-story-modal]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        openModal();
      });
    });

    // Story create button in the strip
    var storyCreateCard = document.querySelector('.story-card--create');
    if (storyCreateCard) {
      storyCreateCard.addEventListener('click', function (e) {
        e.preventDefault();
        openModal();
      });
    }

    closeBtn && closeBtn.addEventListener('click', closeModal);
    cancelBtn && cancelBtn.addEventListener('click', closeModal);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && overlay.classList.contains('is-open')) closeModal();
    });

    // Upload zone click
    uploadZone.addEventListener('click', function () {
      fileInput && fileInput.click();
    });

    fileInput && fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      handleFile(file);
    });

    // Drag & drop
    uploadZone.addEventListener('dragover', function (e) {
      e.preventDefault();
      uploadZone.classList.add('is-dragover');
    });

    uploadZone.addEventListener('dragleave', function () {
      uploadZone.classList.remove('is-dragover');
    });

    uploadZone.addEventListener('drop', function (e) {
      e.preventDefault();
      uploadZone.classList.remove('is-dragover');
      var file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    function handleFile(file) {
      if (!file.type.match(/^(image|video)\//)) {
        showError('Please select an image or video file.');
        return;
      }
      if (file.size > 100 * 1024 * 1024) {
        showError('File too large. Max 100MB.');
        return;
      }
      selectedFile = file;
      var reader = new FileReader();
      reader.onload = function (e) {
        uploadZone.style.display = 'none';
        preview.classList.add('is-visible');
        var media;
        if (file.type.startsWith('video/')) {
          media = document.createElement('video');
          media.src = e.target.result;
          media.muted = true;
          media.controls = true;
        } else {
          media = document.createElement('img');
          media.src = e.target.result;
        }
        media.style.width = '100%';
        media.style.maxHeight = '320px';
        media.style.objectFit = 'contain';
        preview.insertBefore(media, removeMedia);
        postBtn.disabled = false;
        errorEl.classList.remove('is-visible');
      };
      reader.readAsDataURL(file);
    }

    removeMedia && removeMedia.addEventListener('click', function () {
      selectedFile = null;
      fileInput.value = '';
      resetModal();
    });

    // Post story
    postBtn && postBtn.addEventListener('click', function () {
      if (!selectedFile) return;
      postBtn.disabled = true;
      loadingEl.classList.add('is-visible');
      errorEl.classList.remove('is-visible');

      var formData = new FormData();
      formData.append('media', selectedFile);
      formData.append('caption', captionInput.value || '');

      fetch('/status/create', { method: 'POST', body: formData })
        .then(function (r) {
          if (r.redirected) { window.location.href = r.url; return; }
          return r.json().catch(function () { return {}; });
        })
        .then(function (data) {
          if (data && data.ok) {
            window.location.reload();
          } else if (data && data.redirect) {
            window.location.href = data.redirect;
          } else {
            // Try POST to /api/stories/create
            return fetch('/api/stories/create', { method: 'POST', body: formData });
          }
        })
        .then(function (r) {
          if (!r) return;
          if (r.redirected) { window.location.href = r.url; return; }
          return r.json().catch(function () { return {}; });
        })
        .then(function (data) {
          if (data && data.ok) {
            window.location.reload();
          } else if (data && data.redirect) {
            window.location.href = data.redirect;
          } else {
            window.location.href = '/status/create';
          }
        })
        .catch(function () {
          window.location.href = '/status/create';
        });
    });
  }

  /* ================================================================
     Expose hideSkeleton globally for other scripts
   ================================================================ */
  window.hideFeedSkeleton = hideSkeleton;

})();
