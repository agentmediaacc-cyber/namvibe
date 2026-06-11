/* CHAIN Phase 59 — Premium Homepage: Real Feed API + Infinite Scroll + Actions */

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
          '<div class="post-author-name">' + escapeHtml(item.display_name || 'CHAIN') + ' ' + verified + ' ' + label + '</div>' +
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
          '<span><strong>' + (item.comments_count || 0) + '</strong> comments</span>' +
          '<span><strong>' + (item.view_count || 0) + '</strong> views</span>' +
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
          '<div class="post-avatar" style="background:linear-gradient(135deg,#7c3aed,#2563eb);"><span>A</span></div>' +
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

})();
