(function() {
  'use strict';

  const FEED_API = {
    forYou: '/api/feed/for-you',
    following: '/api/feed/following',
    trending: '/api/feed/trending',
    nearby: '/api/feed/nearby',
  };

  let state = {
    tab: 'forYou',
    cursors: { forYou: null, following: null, trending: null, nearby: null },
    loading: false,
    hasMore: { forYou: true, following: true, trending: true, nearby: true },
    items: { forYou: [], following: [], trending: [], nearby: [] },
    observer: null,
  };

  function escapeHtml(text) {
    if (!text) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }

  function relativeTime(dateStr) {
    if (!dateStr) return '';
    var diff = Date.now() - new Date(dateStr).getTime();
    var mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return mins + 'm';
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h';
    var days = Math.floor(hrs / 24);
    return days + 'd';
  }

  function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function csrfHeaders() {
    var headers = { 'Content-Type': 'application/json' };
    var token = getCSRF();
    if (token) headers['X-CSRFToken'] = token;
    return headers;
  }

  function showFeedError(msg) {
    var el = document.getElementById('feed-error');
    if (!el) return;
    el.innerHTML = '<p>' + escapeHtml(msg) + '</p><button onclick="window.location.reload()">Retry</button>';
    el.style.display = 'block';
  }

  function hideFeedError() {
    var el = document.getElementById('feed-error');
    if (el) el.style.display = 'none';
  }

  function showFeedEnd() {
    var el = document.getElementById('feed-end');
    if (el) el.style.display = 'block';
  }

  function hideFeedEnd() {
    var el = document.getElementById('feed-end');
    if (el) el.style.display = 'none';
  }

  function setLoading(v) {
    state.loading = v;
    var el = document.getElementById('feed-loading');
    if (el) el.style.display = v ? 'block' : 'none';
  }

  function renderPost(post) {
    var avatarHtml = post.avatar_url
      ? '<img class="feed-avatar" src="' + escapeHtml(post.avatar_url) + '" alt="" loading="lazy" onerror="this.onerror=null;this.style.display=\'none\'">'
      : '<div class="feed-avatar-fallback">' + escapeHtml((post.display_name || post.username || '?')[0].toUpperCase()) + '</div>';

    var mediaHtml = '';
    if (post.media_url) {
      if (post.media_type === 'video') {
        mediaHtml = '<video class="feed-media" src="' + escapeHtml(post.media_url) + '" controls preload="none" playsinline></video>';
      } else {
        mediaHtml = '<img class="feed-media" src="' + escapeHtml(post.media_url) + '" alt="" loading="lazy">';
      }
    }

    return '<div class="feed-card" data-id="' + escapeHtml(post.id) + '">' +
      '<div class="feed-card-header">' +
        avatarHtml +
        '<div class="feed-card-user">' + escapeHtml(post.display_name || post.username || 'User') + '</div>' +
        '<div class="feed-card-time">' + relativeTime(post.created_at) + '</div>' +
      '</div>' +
      mediaHtml +
      '<div class="feed-caption">' + escapeHtml(post.caption || '') + '</div>' +
      '<div class="feed-actions">' +
        '<button class="feed-action-btn" data-action="like" data-id="' + escapeHtml(post.id) + '">❤ ' + (post.like_count || 0) + '</button>' +
        '<button class="feed-action-btn" data-action="comment" data-id="' + escapeHtml(post.id) + '">💬 ' + (post.comment_count || 0) + '</button>' +
        '<button class="feed-action-btn" data-action="share" data-id="' + escapeHtml(post.id) + '">↗ ' + (post.share_count || 0) + '</button>' +
      '</div>' +
    '</div>';
  }

  function renderSkeleton() {
    return '<div class="feed-skeleton">' +
      '<div class="feed-skeleton-avatar"></div>' +
      '<div class="feed-skeleton-line" style="width:60%"></div>' +
      '<div class="feed-skeleton-media"></div>' +
      '<div class="feed-skeleton-line" style="width:40%"></div>' +
    '</div>';
  }

  function renderEmpty() {
    return '<div class="feed-empty">' +
      '<div class="feed-empty-icon">📭</div>' +
      '<h3>No posts yet</h3>' +
      '<p>Follow creators to see their posts here.</p>' +
    '</div>';
  }

  function switchTab(tab) {
    state.tab = tab;
    document.querySelectorAll('.feed-tab').forEach(function(el) {
      el.classList.toggle('active', el.dataset.tab === tab);
    });
    var container = document.getElementById('feed-container');
    if (!container) return;

    var items = state.items[tab] || [];
    if (items.length === 0) {
      container.innerHTML = renderSkeleton() + renderSkeleton();
      loadFeed(tab);
    } else {
      container.innerHTML = items.map(renderPost).join('');
      if (!state.hasMore[tab]) showFeedEnd();
      setupObserver();
    }
    hideFeedError();
  }

  function loadFeed(tab) {
    if (state.loading || !state.hasMore[tab]) return;
    setLoading(true);

    var url = FEED_API[tab] || FEED_API.forYou;
    var cursor = state.cursors[tab];
    if (cursor) url += '?cursor=' + encodeURIComponent(cursor);

    fetch(url, { headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        setLoading(false);
        hideFeedError();
        var posts = data.posts || data.items || data.data || [];
        var nextCursor = data.next_cursor || data.cursor || null;

        if (!posts || posts.length === 0) {
          if (state.items[tab].length === 0) {
            document.getElementById('feed-container').innerHTML = renderEmpty();
          }
          state.hasMore[tab] = false;
          showFeedEnd();
          return;
        }

        state.cursors[tab] = nextCursor;
        state.hasMore[tab] = !!nextCursor;
        state.items[tab] = state.items[tab].concat(posts);

        if (document.querySelector('.feed-tab.active').dataset.tab === tab) {
          var container = document.getElementById('feed-container');
          container.innerHTML = state.items[tab].map(renderPost).join('');
          if (!nextCursor) showFeedEnd();
          else hideFeedEnd();
          setupObserver();
        }
      })
      .catch(function(err) {
        setLoading(false);
        showFeedError('Failed to load feed. Check your connection.');
      });
  }

  function setupObserver() {
    if (state.observer) state.observer.disconnect();
    var sentinel = document.getElementById('feed-sentinel');
    if (!sentinel) return;
    state.observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          loadFeed(state.tab);
        }
      });
    }, { rootMargin: '200px' });
    state.observer.observe(sentinel);
  }

  function init() {
    // Tab click handlers
    document.querySelectorAll('.feed-tab').forEach(function(el) {
      el.addEventListener('click', function(e) {
        switchTab(el.dataset.tab);
      });
    });

    // Like/comment/share via delegation
    document.addEventListener('click', function(e) {
      var btn = e.target.closest('[data-action]');
      if (!btn) return;
      var action = btn.dataset.action;
      var id = btn.dataset.id;
      if (action === 'like') {
        fetch('/api/home/post/' + id + '/like', { method: 'POST', headers: csrfHeaders() })
          .then(function(r) { return r.json(); })
          .then(function(d) {
            if (d.ok) {
              btn.classList.toggle('liked', d.liked);
              btn.innerHTML = '❤ ' + (d.count || (d.liked ? parseInt(btn.textContent.match(/\d+/)?.[0] || 0) + 1 : Math.max(0, parseInt(btn.textContent.match(/\d+/)?.[0] || 0) - 1)));
            }
          });
      } else if (action === 'comment') {
        var commentBox = document.getElementById('comment-drawer');
        if (commentBox) {
          commentBox.classList.add('open');
          commentBox.dataset.postId = id;
        }
      } else if (action === 'share') {
        if (navigator.share) {
          navigator.share({ title: 'NamVibe', url: window.location.origin + '/posts/' + id });
        } else {
          navigator.clipboard.writeText(window.location.origin + '/posts/' + id).catch(function(){});
          alert('Link copied!');
        }
      }
    });

    // Initial load
    switchTab('forYou');
    loadFeed('forYou');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
