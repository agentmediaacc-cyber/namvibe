/* Phase 60: TikTok Reels JS — full-screen swipe, double-tap like, drawers */
(function() {
  'use strict';

  const viewport = document.getElementById('reels-viewport');
  if (!viewport) return;

  /* ── State ── */
  let currentIndex = 0;
  const slides = viewport.querySelectorAll('.reel-slide');
  let activeVideo = null;
  let lastTapTime = 0;
  let touchStartY = 0;
  let watchInterval = null;
  let watchStart = 0;

  function getCurrentSlide() {
    return slides[currentIndex] || null;
  }

  /* ── Video Playback ── */
  function playVideo(slide) {
    if (!slide) return;
    const video = slide.querySelector('.reel-video');
    if (video) {
      if (activeVideo && activeVideo !== video) { activeVideo.pause(); activeVideo.currentTime = 0; }
      video.play().catch(() => {});
      activeVideo = video;
      watchStart = Date.now();
      startWatchTracking(slide);
    }
  }

  function pauseVideo() {
    if (activeVideo) { activeVideo.pause(); }
    stopWatchTracking();
  }

  /* ── Watch Time Tracking ── */
  function startWatchTracking(slide) {
    stopWatchTracking();
    watchStart = Date.now();
    watchInterval = setInterval(() => {
      const reelId = slide ? slide.dataset.reelId : null;
      if (!reelId) return;
      fetch(`/reels/api/reels/${reelId}/event`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ event_type: 'watch_time', watch_ms: Date.now() - watchStart })
      }).catch(() => {});
    }, 5000);
  }
  function stopWatchTracking() {
    if (watchInterval) { clearInterval(watchInterval); watchInterval = null; }
  }

  /* ── View Tracking ── */
  function trackView(slide) {
    const reelId = slide ? slide.dataset.reelId : null;
    if (!reelId) return;
    fetch(`/reels/api/reels/${reelId}/view`, { method: 'POST' }).catch(() => {});
  }

  /* ── Navigation ── */
  function goToSlide(index) {
    if (index < 0 || index >= slides.length) return;
    currentIndex = index;
    const slide = slides[index];
    slide.scrollIntoView({ behavior: 'smooth', block: 'start' });
    trackView(slide);
    setTimeout(() => playVideo(slide), 100);
  }

  function nextReel() { goToSlide(currentIndex + 1); }
  function prevReel() { goToSlide(currentIndex - 1); }

  /* ── Keyboard ── */
  document.addEventListener('keydown', function(e) {
    var tag = (e.target || {}).tagName || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key === 'ArrowDown') { e.preventDefault(); nextReel(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); prevReel(); }
    else if (e.key === ' ') { e.preventDefault(); const v = activeVideo; if (v) v.paused ? v.play() : v.pause(); }
  });

  /* ── Touch Swipe ── */
  viewport.addEventListener('touchstart', function(e) {
    touchStartY = e.touches[0].clientY;
  }, { passive: true });

  viewport.addEventListener('touchend', function(e) {
    const dy = e.changedTouches[0].clientY - touchStartY;
    if (Math.abs(dy) > 60) {
      if (dy < 0) nextReel();
      else prevReel();
    }
  }, { passive: true });

  /* ── Scroll Snap Detect ── */
  let scrollTimeout = null;
  viewport.addEventListener('scroll', function() {
    if (scrollTimeout) clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      const idx = Math.round(viewport.scrollTop / viewport.clientHeight);
      if (idx !== currentIndex) {
        pauseVideo();
        currentIndex = idx;
        const slide = slides[currentIndex];
        if (slide) { trackView(slide); setTimeout(() => playVideo(slide), 100); }
      }
    }, 150);
  }, { passive: true });

  /* ── Double-tap Like ── */
  viewport.addEventListener('click', function(e) {
    const now = Date.now();
    if (now - lastTapTime < 350) {
      const slide = e.target.closest('.reel-slide');
      if (!slide) return;
      const reelId = slide.dataset.reelId;
      const heart = slide.querySelector('.double-tap-heart');
      if (heart) { heart.classList.remove('is-active'); void heart.offsetWidth; heart.classList.add('is-active'); }
      if (reelId) { likeReel(reelId, slide); }
    }
    lastTapTime = now;
  });

  /* ── Like ── */
  function likeReel(reelId, slide) {
    fetch(`/reels/api/reels/${reelId}/like`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        const btn = slide ? slide.querySelector('[data-like]') : document.querySelector(`[data-like][data-reel-id="${reelId}"]`);
        if (btn) btn.classList.toggle('is-active', data.liked);
        const countEl = document.getElementById(`reel-likes-${reelId}`);
        if (countEl) countEl.textContent = data.count;
      }
    })
    .catch(() => {});
  }

  document.querySelectorAll('[data-like]').forEach(btn => {
    btn.addEventListener('click', function() {
      const reelId = this.dataset.reelId;
      const slide = this.closest('.reel-slide');
      likeReel(reelId, slide);
    });
  });

  /* ── Save ── */
  document.querySelectorAll('[data-save]').forEach(btn => {
    btn.addEventListener('click', function() {
      const reelId = this.dataset.reelId;
      fetch(`/reels/api/reels/${reelId}/save`, { method: 'POST' })
      .then(r => r.json())
      .then(data => {
        if (data.success) this.classList.toggle('is-active', data.saved);
      })
      .catch(() => {});
    });
  });

  /* ── Comment Drawer ── */
  const commentDrawer = document.getElementById('reel-comment-drawer');
  const commentList = document.getElementById('reel-comment-list');
  const commentInput = document.getElementById('reel-comment-input');
  const commentSubmit = document.getElementById('reel-comment-submit');
  const commentClose = document.getElementById('reel-comment-close');
  let commentReelId = null;

  document.querySelectorAll('[data-comment]').forEach(btn => {
    btn.addEventListener('click', function() {
      const slide = this.closest('.reel-slide');
      if (!slide) return;
      commentReelId = slide.dataset.reelId;
      loadComments(commentReelId);
      commentDrawer.style.display = 'flex';
    });
  });

  if (commentClose) commentClose.addEventListener('click', function() { commentDrawer.style.display = 'none'; });

  function loadComments(reelId) {
    if (!commentList) return;
    commentList.innerHTML = '<p style="opacity:.6;text-align:center;padding:20px;">Loading...</p>';
    fetch(`/reels/api/reels/${reelId}/comments`)
    .then(r => r.json())
    .then(data => {
      const comments = data.comments || data || [];
      if (!comments.length) { commentList.innerHTML = '<p style="opacity:.6;text-align:center;padding:20px;">No comments yet.</p>'; return; }
      commentList.innerHTML = comments.map(c => `
        <div class="reel-comment-item">
          <div class="reel-comment-avatar">${c.avatar_url ? '<img src="'+c.avatar_url+'" alt="">' : '<i class="fas fa-user"></i>'}</div>
          <div class="reel-comment-body">
            <strong class="reel-comment-user">${c.username || 'User'}</strong> ${c.body || ''}
            <div class="reel-comment-time">${timeAgo(c.created_at)}</div>
          </div>
        </div>
      `).join('');
    })
    .catch(() => { commentList.innerHTML = '<p style="opacity:.6;text-align:center;padding:20px;">Could not load comments.</p>'; });
  }

  if (commentSubmit) commentSubmit.addEventListener('click', function() {
    if (!commentReelId || !commentInput) return;
    const body = commentInput.value.trim();
    if (!body) return;
    fetch(`/reels/api/reels/${commentReelId}/comment`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ body })
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        commentInput.value = '';
        const countEl = document.getElementById(`reel-comments-${commentReelId}`);
        if (countEl) countEl.textContent = data.count;
        loadComments(commentReelId);
      }
    })
    .catch(() => {});
  });

  if (commentInput) commentInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') commentSubmit.click();
  });

  /* ── Share Drawer ── */
  const shareDrawer = document.getElementById('reel-share-drawer');
  const shareClose = document.getElementById('reel-share-close');
  let shareReelId = null;

  document.querySelectorAll('[data-share]').forEach(btn => {
    btn.addEventListener('click', function() {
      const slide = this.closest('.reel-slide');
      if (!slide) return;
      shareReelId = slide.dataset.reelId;
      shareDrawer.style.display = 'flex';
      const url = window.location.origin + '/reels';
      const whatsappLink = shareDrawer.querySelector('[data-share-whatsapp]');
      const twitterLink = shareDrawer.querySelector('[data-share-twitter]');
      const text = encodeURIComponent('Check out this reel on NamVibe! ' + url);
      if (whatsappLink) whatsappLink.href = 'https://wa.me/?text=' + text;
      if (twitterLink) twitterLink.href = 'https://twitter.com/intent/tweet?text=' + text;
    });
  });

  if (shareClose) shareClose.addEventListener('click', function() { shareDrawer.style.display = 'none'; });

  shareDrawer.querySelector('[data-copy-link]')?.addEventListener('click', function() {
    navigator.clipboard.writeText(window.location.origin + '/reels').then(() => {
      this.innerHTML = '<i class="fas fa-check"></i> Copied!';
      setTimeout(() => { shareDrawer.style.display = 'none'; location.reload(); }, 500);
    }).catch(() => {});
  });

  /* ── Follow ── */
  document.querySelectorAll('[data-follow]').forEach(btn => {
    btn.addEventListener('click', function() {
      const creatorId = this.dataset.creatorId;
      if (!creatorId) return;
      fetch(`/api/home/follow/${creatorId}`, {
        method: 'POST'
      })
      .then(r => r.json())
      .then(data => {
        if (data.success || data.following) {
          this.style.display = 'none';
          const followingBtn = this.closest('.reel-creator-row')?.querySelector('[data-following]');
          if (followingBtn) followingBtn.style.display = 'block';
        }
      })
      .catch(() => {});
    });
  });

  document.querySelectorAll('[data-following]').forEach(btn => {
    btn.addEventListener('click', function() {
      const creatorId = this.dataset.creatorId;
      if (!creatorId) return;
      fetch(`/api/home/unfollow/${creatorId}`, {
        method: 'POST'
      })
      .then(r => r.json())
      .then(data => {
        if (data.success || !data.following) {
          this.style.display = 'none';
          const followBtn = this.closest('.reel-creator-row')?.querySelector('[data-follow]');
          if (followBtn) followBtn.style.display = 'block';
        }
      })
      .catch(() => {});
    });
  });

  /* ── Helpers ── */
  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const now = Date.now();
    const d = new Date(dateStr);
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff/60)+'m';
    if (diff < 86400) return Math.floor(diff/3600)+'h';
    return Math.floor(diff/86400)+'d';
  }

  /* ── Init ── */
  if (slides.length > 0) {
    trackView(slides[0]);
    setTimeout(() => playVideo(slides[0]), 200);
    watchStart = Date.now();
  }

  /* ── Watch-time on leave ── */
  window.addEventListener('beforeunload', function() {
    const slide = getCurrentSlide();
    if (!slide) return;
    const reelId = slide.dataset.reelId;
    const ms = Date.now() - watchStart;
    if (ms > 1000) {
      navigator.sendBeacon(`/reels/api/reels/${reelId}/event`,
        JSON.stringify({ event_type: 'watch_time', watch_ms: ms })
      );
    }
  });
})();
