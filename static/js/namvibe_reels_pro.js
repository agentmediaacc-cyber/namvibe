(function() {
  'use strict';

  var currentPlayer = null;
  var reelsData = [];
  var currentIndex = 0;
  var watchInterval = null;
  var watchStart = 0;
  var isLoading = false;
  var hasMore = true;
  var cursor = null;
  var commentsCache = {};

  function escapeHtml(t) {
    if (!t) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(t));
    return d.innerHTML;
  }

  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function csrfHeaders() {
    var h = { 'Content-Type': 'application/json' };
    var t = getCSRF();
    if (t) h['X-CSRFToken'] = t;
    return h;
  }

  function loadReels(cursorVal) {
    if (isLoading || !hasMore) return;
    isLoading = true;
    var url = '/api/reels/feed';
    if (cursorVal) url += '?cursor=' + encodeURIComponent(cursorVal);

    fetch(url, { headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        isLoading = false;
        var reels = data.reels || data.items || data.data || [];
        if (!reels.length) { hasMore = false; return; }
        cursor = data.next_cursor || data.cursor || null;
        hasMore = !!cursor;
        var container = document.getElementById('reels-viewport');
        if (!container) return;
        reels.forEach(function(reel, i) {
          reelsData.push(reel);
          container.appendChild(createReelSlide(reel, reelsData.length - 1));
        });
        if (reelsData.length > 0 && !currentPlayer) playReel(0);
      })
      .catch(function() { isLoading = false; });
  }

  function createReelSlide(reel, idx) {
    var slide = document.createElement('div');
    slide.className = 'reel-slide';
    slide.dataset.index = idx;

    var video = document.createElement('video');
    video.className = 'reel-video';
    video.src = reel.media_url || reel.video_url || '';
    video.muted = true;
    video.playsInline = true;
    video.preload = 'metadata';
    video.loop = false;
    video.setAttribute('playsinline', '');
    video.poster = reel.thumbnail_url || '';

    var overlay = document.createElement('div');
    overlay.className = 'reel-overlay';

    var info = document.createElement('div');
    info.className = 'reel-info';
    info.innerHTML =
      '<div class="reel-creator">' +
        '<img class="reel-avatar" src="' + escapeHtml(reel.avatar_url || '') + '" alt="" loading="lazy" onerror="this.onerror=null;this.style.display=\'none\'">' +
        '<span class="reel-username">' + escapeHtml(reel.display_name || reel.username || 'User') + '</span>' +
      '</div>' +
      '<div class="reel-caption">' + escapeHtml(reel.caption || '') + '</div>';

    var actions = document.createElement('div');
    actions.className = 'reel-actions';
    actions.innerHTML =
      '<button class="reel-action-btn" data-action="like" data-id="' + escapeHtml(reel.id) + '">❤ <span class="reel-count">' + (reel.like_count || 0) + '</span></button>' +
      '<button class="reel-action-btn" data-action="comment" data-id="' + escapeHtml(reel.id) + '">💬 <span class="reel-count">' + (reel.comment_count || 0) + '</span></button>' +
      '<button class="reel-action-btn" data-action="save" data-id="' + escapeHtml(reel.id) + '">🔖 <span class="reel-count">' + (reel.save_count || 0) + '</span></button>' +
      '<button class="reel-action-btn" data-action="share" data-id="' + escapeHtml(reel.id) + '">↗</button>';

    var muteBtn = document.createElement('button');
    muteBtn.className = 'reel-mute-btn';
    muteBtn.innerHTML = '🔇';
    muteBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      video.muted = !video.muted;
      muteBtn.innerHTML = video.muted ? '🔇' : '🔊';
    });

    slide.appendChild(video);
    slide.appendChild(overlay);
    slide.appendChild(info);
    slide.appendChild(actions);
    slide.appendChild(muteBtn);
    return slide;
  }

  function playReel(idx) {
    if (idx < 0 || idx >= reelsData.length) return;
    currentIndex = idx;
    pauseCurrent();

    var slides = document.querySelectorAll('.reel-slide');
    slides.forEach(function(s, i) {
      s.classList.toggle('active', i === idx);
    });

    var video = slides[idx]?.querySelector('video');
    if (video) {
      currentPlayer = video;
      video.play().catch(function() {});
      watchStart = Date.now();
      startWatchTimer();
    }
  }

  function pauseCurrent() {
    if (currentPlayer) {
      currentPlayer.pause();
      currentPlayer = null;
    }
    stopWatchTimer();
  }

  function startWatchTimer() {
    stopWatchTimer();
    watchInterval = setInterval(function() {
      if (!currentPlayer || !reelsData[currentIndex]) return;
      var reel = reelsData[currentIndex];
      var elapsed = (Date.now() - watchStart) / 1000;
      var dur = currentPlayer.duration || 30;
      var pct = dur > 0 ? Math.min(100, (elapsed / dur) * 100) : 0;
      navigator.sendBeacon('/api/reels/' + reel.id + '/watch', JSON.stringify({
        watch_seconds: elapsed,
        completion_percent: Math.round(pct),
      }));
    }, 5000);
  }

  function stopWatchTimer() {
    if (watchInterval) { clearInterval(watchInterval); watchInterval = null; }
  }

  function navigateReel(dir) {
    var next = currentIndex + dir;
    if (next < 0 || next >= reelsData.length) {
      if (dir > 0 && hasMore) loadReels(cursor);
      return;
    }
    playReel(next);
  }

  function toggleLike(btn, id) {
    fetch('/api/reels/api/reels/' + id + '/like', { method: 'POST', headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok) {
          btn.classList.toggle('liked', d.liked);
          var count = btn.querySelector('.reel-count');
          if (count) count.textContent = d.count || (d.liked ? parseInt(count.textContent || '0') + 1 : Math.max(0, parseInt(count.textContent || '0') - 1));
        }
      });
  }

  function openComments(id) {
    var drawer = document.getElementById('comment-drawer');
    if (!drawer) return;
    drawer.classList.add('open');
    drawer.dataset.reelId = id;
    var list = drawer.querySelector('.comment-list');
    if (!list) return;
    list.innerHTML = '<div class="feed-loading">Loading...</div>';

    fetch('/api/reels/api/reels/' + id + '/comments', { headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var comments = data.comments || data.data || [];
        if (!comments.length) {
          list.innerHTML = '<p class="feed-empty" style="padding:20px">No comments yet.</p>';
          return;
        }
        list.innerHTML = comments.map(function(c) {
          return '<div class="comment-item"><strong>' + escapeHtml(c.display_name || c.username || 'User') + '</strong>: ' + escapeHtml(c.body || c.text || '') + '</div>';
        }).join('');
      })
      .catch(function() { list.innerHTML = '<p class="feed-error">Failed to load comments.</p>'; });
  }

  function postComment(id) {
    var drawer = document.getElementById('comment-drawer');
    var input = drawer ? drawer.querySelector('.comment-input') : null;
    if (!input || !input.value.trim()) return;
    var body = input.value.trim();
    input.value = '';

    fetch('/api/reels/api/reels/' + id + '/comment', {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ body: body }),
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) openComments(id);
    });
  }

  function shareReel(id) {
    var url = window.location.origin + '/reels/' + id;
    if (navigator.share) {
      navigator.share({ title: 'NamVibe Reel', url: url });
    } else {
      navigator.clipboard.writeText(url).catch(function(){});
      alert('Link copied!');
    }
    fetch('/api/reels/api/reels/' + id + '/share', { method: 'POST', headers: csrfHeaders() }).catch(function(){});
  }

  function saveReel(btn, id) {
    fetch('/api/reels/api/reels/' + id + '/save', { method: 'POST', headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok) {
          btn.classList.toggle('saved', d.saved);
          var count = btn.querySelector('.reel-count');
          if (count) count.textContent = d.count || (d.saved ? parseInt(count.textContent || '0') + 1 : Math.max(0, parseInt(count.textContent || '0') - 1));
        }
      });
  }

  document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    var action = btn.dataset.action;
    var id = btn.dataset.id;
    if (action === 'like') toggleLike(btn, id);
    else if (action === 'comment') openComments(id);
    else if (action === 'save') saveReel(btn, id);
    else if (action === 'share') shareReel(id);
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowUp') { e.preventDefault(); navigateReel(-1); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); navigateReel(1); }
    else if (e.key === 'm' && currentPlayer) { currentPlayer.muted = !currentPlayer.muted; }
  });

  var touchStartY = 0;
  document.addEventListener('touchstart', function(e) {
    touchStartY = e.touches[0].clientY;
  }, { passive: true });
  document.addEventListener('touchend', function(e) {
    var dy = e.changedTouches[0].clientY - touchStartY;
    if (Math.abs(dy) > 50) navigateReel(dy > 0 ? -1 : 1);
  }, { passive: true });

  document.addEventListener('wheel', function(e) {
    if (Math.abs(e.deltaY) > 30) navigateReel(e.deltaY > 0 ? 1 : -1);
  }, { passive: true });

  document.addEventListener('visibilitychange', function() {
    if (document.hidden) pauseCurrent();
  });

  function init() {
    loadReels(null);

    var commentForm = document.getElementById('comment-form');
    if (commentForm) {
      commentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        var drawer = document.getElementById('comment-drawer');
        if (drawer) postComment(drawer.dataset.reelId);
      });
    }

    // Close drawer
    document.querySelectorAll('.drawer-close, .drawer-backdrop').forEach(function(el) {
      el.addEventListener('click', function() {
        document.getElementById('comment-drawer')?.classList.remove('open');
      });
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
