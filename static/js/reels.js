(function () {
  'use strict';

  if (window.__NAMVIBE_REELS_INITIALIZED__) return;
  window.__NAMVIBE_REELS_INITIALIZED__ = true;

  const viewport = document.getElementById('reels-viewport');
  if (!viewport) return;

  const statusEl = document.getElementById('reels-feed-status');
  const slides = new Set();
  const seenIds = new Set();
  const controller = {
    activeSlide: null,
    activeVideo: null,
    currentIndex: 0,
    nextCursor: viewport.dataset.nextCursor || '',
    hasMore: viewport.dataset.hasMore === 'true',
    loadingMore: false,
    muted: sessionStorage.getItem('namvibe_reels_muted') !== 'false',
    progressRaf: 0,
    visibleSince: 0,
    qualifiedSent: new Set(),
    pendingAction: new Map(),
    openPanel: null,
    mountedLimit: 24,
    pageVisible: document.visibilityState !== 'hidden',
    networkOffline: !navigator.onLine,
    fetchPageOneGuard: true
  };

  function qs(sel, root = document) { return root.querySelector(sel); }
  function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }
  function escText(text) { return String(text == null ? '' : text); }
  function isTextInput(el) {
    if (!el) return false;
    return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable;
  }
  function safeUrl(value) {
    try {
      const url = new URL(value, window.location.origin);
      if (!/^https?:$/.test(url.protocol)) return '';
      return url.href;
    } catch (e) {
      return '';
    }
  }
  function toast(msg) {
    if (window.NamVibeToast && typeof window.NamVibeToast.show === 'function') {
      window.NamVibeToast.show(msg);
      return;
    }
    console.log(msg);
  }
  function setStatus(msg, show) {
    if (!statusEl) return;
    statusEl.hidden = !show;
    statusEl.textContent = msg || '';
  }

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function sendTelemetry(url, payload) {
    const body = JSON.stringify(payload || {});
    const headers = { 'X-CSRFToken': csrfToken() };
    if (navigator.sendBeacon) {
      try {
        const blob = new Blob([body], { type: 'application/json' });
        if (navigator.sendBeacon(url, blob)) return true;
      } catch (e) {}
    }
    return fetch(url, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body,
      credentials: 'same-origin',
      keepalive: true
    });
  }

  function currentSlide() {
    return controller.activeSlide || Array.from(slides)[0] || null;
  }

  function reelIdFor(slide) {
    return slide ? slide.dataset.reelId : '';
  }

  function videoFor(slide) {
    return slide ? qs('.reel-video', slide) : null;
  }

  function setMuted(muted) {
    controller.muted = !!muted;
    sessionStorage.setItem('namvibe_reels_muted', controller.muted ? 'true' : 'false');
    qsa('.reel-video', viewport).forEach(v => { v.muted = controller.muted; });
    updateMuteButtons();
  }

  function updateMuteButtons() {
    qsa('[data-reel-mute]').forEach(btn => {
      btn.setAttribute('aria-pressed', controller.muted ? 'true' : 'false');
      btn.dataset.state = controller.muted ? 'muted' : 'sound';
    });
  }

  function updateActiveState(slide) {
    if (!slide) return;
    controller.activeSlide = slide;
    const video = videoFor(slide);
    if (!video) return;
    qsa('.reel-video', viewport).forEach(v => {
      if (v !== video) {
        v.pause();
        if (!v.dataset.keepPosition) v.currentTime = 0;
        v.preload = controller.networkOffline || navigator.connection?.saveData ? 'metadata' : 'none';
      }
    });
    video.preload = 'auto';
    video.muted = controller.muted;
    attemptPlay(video, slide);
    controller.currentIndex = Array.from(slides).indexOf(slide);
    updatePreloadWindow();
    startProgressLoop();
  }

  function attemptPlay(video, slide) {
    if (!video) return;
    if (!controller.pageVisible) return;
    if (controller.openPanel) return;
    if (video.readyState < 2) video.preload = 'auto';
    const p = video.play();
    if (p && typeof p.catch === 'function') {
      p.catch(() => {
        slide.dataset.playBlocked = 'true';
        showTapToPlay(slide, true);
      });
    }
  }

  function showTapToPlay(slide, on) {
    if (!slide) return;
    slide.classList.toggle('is-play-blocked', !!on);
  }

  function updatePreloadWindow() {
    const all = Array.from(slides);
    const activeIndex = controller.currentIndex;
    const saveData = !!navigator.connection?.saveData;
    const effectiveType = navigator.connection?.effectiveType || '';
    const nextAuto = !saveData && ['4g', 'wifi', 'ethernet'].some(t => effectiveType.includes(t)) ? 'auto' : 'metadata';
    all.forEach((slide, idx) => {
      const video = videoFor(slide);
      if (!video) return;
      const delta = idx - activeIndex;
      if (delta === 0) video.preload = 'auto';
      else if (Math.abs(delta) === 1) video.preload = nextAuto;
      else video.preload = saveData ? 'none' : 'metadata';
    });
  }

  function startProgressLoop() {
    if (controller.progressRaf) return;
    const tick = () => {
      controller.progressRaf = 0;
      const slide = currentSlide();
      const video = videoFor(slide);
      if (slide && video && !video.paused && controller.pageVisible) {
        const dur = Number(video.duration) || 0;
        if (dur > 0) {
          const bar = qs('.reel-progress-bar', slide);
          if (bar) bar.style.width = Math.min(100, Math.max(0, (video.currentTime / dur) * 100)).toFixed(2) + '%';
        }
        maybeTrackMilestones(slide, video);
      }
      controller.progressRaf = window.requestAnimationFrame(tick);
    };
    controller.progressRaf = window.requestAnimationFrame(tick);
  }

  function stopProgressLoop() {
    if (controller.progressRaf) cancelAnimationFrame(controller.progressRaf);
    controller.progressRaf = 0;
  }

  function maybeTrackMilestones(slide, video) {
    const reelId = reelIdFor(slide);
    if (!reelId) return;
    const state = slide.__reelsWatchState || (slide.__reelsWatchState = { qualified: false, half: false, high: false, started: 0, accum: 0, lastTick: 0 });
    if (!controller.pageVisible || video.paused) {
      state.lastTick = 0;
      return;
    }
    const now = performance.now();
    if (!state.started) state.started = now;
    if (state.lastTick) state.accum += Math.max(0, now - state.lastTick);
    state.lastTick = now;
    const watched = state.accum / 1000;
    const ratio = video.duration ? video.currentTime / video.duration : 0;
    if (!state.qualified && watched >= 2 && slide.dataset.visibilityScore === '1') {
      state.qualified = true;
      sendTelemetry(`/reels/api/reels/${reelId}/event`, { event_type: 'qualified_view', watch_ms: Math.round(watched * 1000) });
    }
    if (!state.half && ratio >= 0.5) {
      state.half = true;
      sendTelemetry(`/reels/api/reels/${reelId}/event`, { event_type: 'watch_50', watch_ms: Math.round(watched * 1000) });
    }
    if (!state.high && ratio >= 0.95) {
      state.high = true;
      sendTelemetry(`/reels/api/reels/${reelId}/event`, { event_type: 'watch_95', watch_ms: Math.round(watched * 1000) });
    }
  }

  function registerSlide(slide) {
    if (!slide || slides.has(slide)) return;
    slides.add(slide);
    const reelId = reelIdFor(slide);
    if (reelId) seenIds.add(reelId);
    const video = videoFor(slide);
    if (video) {
      video.preload = 'metadata';
      video.muted = controller.muted;
      video.setAttribute('playsinline', '');
      video.setAttribute('webkit-playsinline', '');
      video.addEventListener('waiting', () => slide.classList.add('is-buffering'));
      video.addEventListener('playing', () => slide.classList.remove('is-buffering', 'is-play-blocked'));
      video.addEventListener('stalled', () => slide.classList.add('is-stalled'));
      video.addEventListener('error', () => slide.classList.add('has-error'));
      video.addEventListener('ended', () => {
        sendTelemetry(`/reels/api/reels/${reelId}/event`, { event_type: 'complete', watch_ms: Math.round((video.currentTime || 0) * 1000) });
      });
    }
    if (slide.classList.contains('is-active')) updateActiveState(slide);
  }

  function unregisterSlide(slide) {
    if (!slide || !slides.has(slide)) return;
    const video = videoFor(slide);
    if (video) video.pause();
    slides.delete(slide);
    if (controller.activeSlide === slide) controller.activeSlide = null;
    if (slide.__reelsObserveCleanup) {
      slide.__reelsObserveCleanup();
      delete slide.__reelsObserveCleanup;
    }
  }

  function mountInitialSlides() {
    qsa('.reel-slide', viewport).forEach(registerSlide);
    updatePreloadWindow();
  }

  function openComments(slide, button) {
    const reelId = reelIdFor(slide);
    if (!reelId) return;
    pauseActive('comments');
    controller.openPanel = 'comments';
    const drawer = qs('#reel-comment-drawer');
    if (!drawer) return;
    drawer.style.display = 'flex';
    drawer.dataset.reelId = reelId;
    drawer.dataset.triggerId = button ? button.id || '' : '';
    loadComments(drawer, reelId);
    const input = qs('#reel-comment-input');
    if (input) input.focus();
  }

  function closeComments() {
    const drawer = qs('#reel-comment-drawer');
    if (drawer) drawer.style.display = 'none';
    controller.openPanel = null;
    resumeIfActive();
  }

  function pauseActive(reason) {
    const video = videoFor(controller.activeSlide);
    if (video) video.pause();
    stopProgressLoop();
    if (reason) controller.openPanel = reason;
  }

  function resumeIfActive() {
    const slide = controller.activeSlide;
    const video = videoFor(slide);
    if (slide && video && controller.pageVisible && !controller.networkOffline) {
      controller.openPanel = null;
      attemptPlay(video, slide);
      startProgressLoop();
    }
  }

  function loadComments(drawer, reelId) {
    const list = qs('#reel-comment-list');
    if (!list) return;
    list.textContent = '';
    const loading = document.createElement('p');
    loading.style.opacity = '.6';
    loading.style.textAlign = 'center';
    loading.style.padding = '20px';
    loading.textContent = 'Loading...';
    list.appendChild(loading);
    fetch(`/reels/api/reels/${reelId}/comments`, { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        const comments = Array.isArray(data.comments) ? data.comments : [];
        list.textContent = '';
        if (!comments.length) {
          const empty = document.createElement('p');
          empty.style.opacity = '.6';
          empty.style.textAlign = 'center';
          empty.style.padding = '20px';
          empty.textContent = 'No comments yet.';
          list.appendChild(empty);
          return;
        }
        comments.forEach(c => {
          const item = document.createElement('div');
          item.className = 'reel-comment-item';
          const avatar = document.createElement('div');
          avatar.className = 'reel-comment-avatar';
          if (c.avatar_url) {
            const img = document.createElement('img');
            const safe = safeUrl(c.avatar_url);
            if (safe) img.src = safe;
            img.alt = '';
            avatar.appendChild(img);
          } else {
            const icon = document.createElement('i');
            icon.className = 'fas fa-user';
            avatar.appendChild(icon);
          }
          const body = document.createElement('div');
          body.className = 'reel-comment-body';
          const user = document.createElement('strong');
          user.className = 'reel-comment-user';
          user.textContent = c.username || 'User';
          const text = document.createElement('span');
          text.textContent = ' ' + (c.body || '');
          const time = document.createElement('div');
          time.className = 'reel-comment-time';
          time.textContent = timeAgo(c.created_at);
          body.append(user, text, time);
          item.append(avatar, body);
          list.appendChild(item);
        });
      })
      .catch(() => {
        list.textContent = '';
        const err = document.createElement('p');
        err.style.opacity = '.6';
        err.style.textAlign = 'center';
        err.style.padding = '20px';
        err.textContent = 'Could not load comments.';
        list.appendChild(err);
      });
  }

  function loadMore() {
    if (controller.loadingMore || !controller.hasMore || !controller.nextCursor || controller.networkOffline) return;
    controller.loadingMore = true;
    setStatus('Loading more reels...', true);
    const url = `/reels/api/reels/feed?limit=5&cursor=${encodeURIComponent(controller.nextCursor)}`;
    fetch(url, { credentials: 'same-origin' })
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(data => {
        const items = Array.isArray(data.items) ? data.items : Array.isArray(data.reels) ? data.reels : [];
        const filtered = items.filter(item => item && item.id && !seenIds.has(item.id));
        if (filtered.length) appendSlides(filtered);
        controller.nextCursor = data.next_cursor || null;
        controller.hasMore = !!data.has_more && !!controller.nextCursor;
        setStatus('', false);
      })
      .catch(() => {
        setStatus('Could not load more reels. Tap to retry.', true);
      })
      .finally(() => {
        controller.loadingMore = false;
      });
  }

  function appendSlides(items) {
    const anchor = qs('#reels-feed-end');
    items.forEach(item => {
      const slide = buildSlide(item);
      if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(slide, anchor);
      else viewport.appendChild(slide);
      registerSlide(slide);
    });
    trimMounted();
    observeSlides();
    observeLoadSentinel();
  }

  function trimMounted() {
    const all = qsa('.reel-slide', viewport);
    if (all.length <= controller.mountedLimit) return;
    const active = controller.activeSlide;
    const keep = new Set([active]);
    let before = 0;
    let after = 0;
    for (let i = 0; i < all.length; i++) {
      const slide = all[i];
      if (slide === active) continue;
      const idx = i - all.indexOf(active);
      if (idx < 0 && before < 8) { keep.add(slide); before++; }
      if (idx > 0 && after < 12) { keep.add(slide); after++; }
    }
    all.forEach(slide => {
      if (!keep.has(slide) && !controller.openPanel) unregisterSlide(slide), slide.remove();
    });
  }

  function buildSlide(item) {
    const slide = document.createElement('section');
    slide.className = 'reel-slide';
    slide.dataset.reelId = item.id;
    slide.dataset.creatorId = item.creator_id || item.profile_id || '';
    slide.dataset.visibilityScore = '1';
    const mediaWrap = document.createElement('div');
    mediaWrap.className = 'reel-media-wrap';
    if (item.video_url) {
      const video = document.createElement('video');
      video.className = 'reel-video';
      video.src = item.video_url;
      if (item.thumbnail_url) video.poster = item.thumbnail_url;
      video.preload = 'metadata';
      video.autoplay = true;
      video.loop = true;
      video.playsInline = true;
      video.muted = controller.muted;
      video.setAttribute('webkit-playsinline', '');
      video.setAttribute('controlslist', 'nodownload noplaybackrate');
      video.setAttribute('disablepictureinpicture', '');
      video.setAttribute('oncontextmenu', 'return false');
      mediaWrap.appendChild(video);
    } else {
      const noVideo = document.createElement('div');
      noVideo.className = 'reel-no-video';
      const icon = document.createElement('i');
      icon.className = 'fas fa-film';
      const p = document.createElement('p');
      p.textContent = 'Video unavailable';
      noVideo.append(icon, p);
      mediaWrap.appendChild(noVideo);
    }
    const gradient = document.createElement('div');
    gradient.className = 'reel-gradient-bottom';
    const heart = document.createElement('div');
    heart.className = 'double-tap-heart';
    const heartIcon = document.createElement('i');
    heartIcon.className = 'fas fa-heart';
    heart.appendChild(heartIcon);
    mediaWrap.append(gradient, heart);
    slide.appendChild(mediaWrap);

    const sidebar = document.createElement('div');
    sidebar.className = 'reel-sidebar';
    sidebar.append(
      buildActionButton('like', item.id, 'Like', 'fa-heart', item.likes_count || 0),
      buildActionButton('comment', item.id, 'Comment', 'fa-comment', item.comments_count || 0),
      buildActionButton('save', item.id, 'Save', 'fa-bookmark', 'Save'),
      buildActionButton('share', item.id, 'Share', 'fa-share', 'Share')
    );
    slide.appendChild(sidebar);

    const footer = document.createElement('div');
    footer.className = 'reel-footer';
    const creatorRow = document.createElement('div');
    creatorRow.className = 'reel-creator-row';

    const avatarLink = document.createElement('a');
    avatarLink.className = 'reel-creator-avatar';
    avatarLink.href = item.creator_url || '/profile/';
    if (item.creator_avatar_url) {
      const avatar = document.createElement('img');
      avatar.alt = '';
      const safe = safeUrl(item.creator_avatar_url);
      if (safe) avatar.src = safe;
      avatarLink.appendChild(avatar);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'reel-avatar-placeholder';
      placeholder.textContent = (item.creator_username || item.username || 'C').charAt(0).toUpperCase();
      avatarLink.appendChild(placeholder);
    }
    creatorRow.appendChild(avatarLink);

    const creatorInfo = document.createElement('div');
    creatorInfo.className = 'reel-creator-info';
    const creatorName = document.createElement('a');
    creatorName.className = 'reel-creator-name';
    creatorName.href = item.creator_url || '/profile/';
    creatorName.textContent = `@${item.creator_username || item.username || ''}`;
    if (item.creator_is_verified) {
      const badge = document.createElement('i');
      badge.className = 'fas fa-circle-check verified-badge';
      creatorName.appendChild(document.createTextNode(' '));
      creatorName.appendChild(badge);
    }
    const music = document.createElement('span');
    music.className = 'reel-music';
    music.textContent = (item.music && item.music.title) || item.music_title || 'Original Audio';
    creatorInfo.append(creatorName, music);
    creatorRow.appendChild(creatorInfo);
    if (window.__NAMVIBE_CURRENT_PROFILE_ID) {
      const followBtn = document.createElement('button');
      followBtn.className = 'reel-follow-btn';
      followBtn.type = 'button';
      followBtn.dataset.follow = '';
      followBtn.dataset.creatorId = item.creator_id || item.profile_id || '';
      followBtn.textContent = 'Follow';
      creatorRow.appendChild(followBtn);
    }
    footer.appendChild(creatorRow);

    const caption = document.createElement('div');
    caption.className = 'reel-caption';
    const captionUser = document.createElement('a');
    captionUser.className = 'reel-caption-user';
    captionUser.href = item.creator_url || '/profile/';
    captionUser.textContent = `@${item.creator_username || item.username || ''}`;
    const captionText = document.createElement('span');
    captionText.textContent = item.caption || '';
    caption.append(captionUser, document.createTextNode(' '), captionText);
    footer.appendChild(caption);
    slide.appendChild(footer);
    return slide;
  }

  function buildActionButton(action, reelId, label, iconClass, count) {
    const btn = document.createElement('button');
    btn.className = 'reel-action-btn';
    btn.type = 'button';
    btn.setAttribute(`data-${action}`, '');
    btn.dataset.reelId = reelId || '';
    btn.setAttribute('aria-label', label);
    const icon = document.createElement('i');
    icon.className = `fas ${iconClass}`;
    const countEl = document.createElement('span');
    countEl.className = 'reel-count';
    countEl.id = `reel-${action}s-${reelId}`;
    countEl.textContent = String(count);
    btn.append(icon, countEl);
    return btn;
  }

  function observeSlides() {
    if (controller.slideObserver) return;
    controller.slideObserver = new IntersectionObserver(entries => {
      let best = null;
      entries.forEach(entry => {
        const slide = entry.target;
        slide.dataset.visibilityScore = String(entry.intersectionRatio >= 0.6 ? 1 : 0);
        if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
          if (!best || entry.intersectionRatio > best.ratio) best = { slide, ratio: entry.intersectionRatio };
        }
      });
      if (best && best.slide !== controller.activeSlide) updateActiveState(best.slide);
    }, { threshold: [0, 0.25, 0.6, 0.75, 1] });
    qsa('.reel-slide', viewport).forEach(slide => {
      if (!slide.__reelsObserved) {
        slide.__reelsObserved = true;
        controller.slideObserver.observe(slide);
      }
    });
  }

  function observeLoadSentinel() {
    const sentinel = qs('#reels-feed-end');
    if (!sentinel) return;
    if (!controller.loadObserver) {
      controller.loadObserver = new IntersectionObserver(entries => {
        if (entries.some(e => e.isIntersecting)) loadMore();
      }, { rootMargin: '800px 0px' });
    }
    if (!sentinel.__observed) {
      sentinel.__observed = true;
      controller.loadObserver.observe(sentinel);
    }
  }

  function handleActionClick(btn) {
    const slide = btn.closest('.reel-slide');
    if (!slide) return;
    const reelId = reelIdFor(slide);
    if (!reelId) return;
    if (btn.hasAttribute('data-like')) return toggleLike(btn, slide, reelId);
    if (btn.hasAttribute('data-save')) return toggleSave(btn, slide, reelId);
    if (btn.hasAttribute('data-comment')) return openComments(slide, btn);
    if (btn.hasAttribute('data-share')) return openShare(slide, btn, reelId);
    if (btn.hasAttribute('data-follow')) return toggleFollow(btn, slide, reelId);
  }

  function lock(key) {
    if (controller.pendingAction.get(key)) return false;
    controller.pendingAction.set(key, true);
    return true;
  }
  function unlock(key) { controller.pendingAction.delete(key); }

  function toggleLike(btn, slide, reelId) {
    const key = `like:${reelId}`;
    if (!lock(key)) return;
    const countEl = qs(`#reel-likes-${reelId}`);
    const was = btn.classList.contains('is-active');
    btn.classList.toggle('is-active', !was);
    if (countEl) countEl.textContent = Math.max(0, parseInt(countEl.textContent || '0', 10) + (was ? -1 : 1));
    fetch(`/reels/api/reels/${reelId}/like`, { method: 'POST', headers: { 'X-CSRFToken': csrfToken() }, credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        if (!data.success) throw new Error(data.error || 'like_failed');
        btn.classList.toggle('is-active', !!data.liked);
        if (countEl && typeof data.count === 'number') countEl.textContent = data.count;
        syncVisibleCount(reelId, 'like', data.count, !!data.liked);
      })
      .catch(() => {
        btn.classList.toggle('is-active', was);
        if (countEl) countEl.textContent = parseInt(countEl.textContent || '0', 10) + (was ? 1 : -1);
        toast('Could not like reel.');
      })
      .finally(() => unlock(key));
  }

  function toggleSave(btn, slide, reelId) {
    const key = `save:${reelId}`;
    if (!lock(key)) return;
    const was = btn.classList.contains('is-active');
    btn.classList.toggle('is-active', !was);
    fetch(`/reels/api/reels/${reelId}/save`, { method: 'POST', headers: { 'X-CSRFToken': csrfToken() }, credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        if (!data.success) throw new Error(data.error || 'save_failed');
        btn.classList.toggle('is-active', !!data.saved);
        syncVisibleCount(reelId, 'save', data.count, !!data.saved);
      })
      .catch(() => {
        btn.classList.toggle('is-active', was);
        toast('Could not save reel.');
      })
      .finally(() => unlock(key));
  }

  function toggleFollow(btn, slide, creatorId) {
    const key = `follow:${creatorId}`;
    if (!lock(key)) return;
    fetch(`/api/home/follow/${creatorId}`, { method: 'POST', headers: { 'X-CSRFToken': csrfToken() }, credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        if (!data.success && !data.following) throw new Error('follow_failed');
        btn.textContent = 'Following';
        toast('Following creator');
      })
      .catch(() => toast('Could not follow creator.'))
      .finally(() => unlock(key));
  }

  function openShare(slide, btn, reelId) {
    pauseActive('share');
    const url = `${window.location.origin}/reels/${reelId}`;
    if (navigator.share) {
      navigator.share({ title: 'NamVibe Reel', url }).catch(() => {});
      return;
    }
    navigator.clipboard?.writeText(url).then(() => toast('Link copied')).catch(() => toast('Could not copy link'));
    resumeIfActive();
  }

  function syncVisibleCount(reelId, type, count) {
    const el = document.getElementById(`reel-${type}s-${reelId}`);
    if (el && typeof count === 'number') el.textContent = count;
  }

  function handleCommentSubmit() {
    const drawer = qs('#reel-comment-drawer');
    if (!drawer) return;
    const reelId = drawer.dataset.reelId;
    const input = qs('#reel-comment-input');
    const btn = qs('#reel-comment-submit');
    if (!reelId || !input || !btn) return;
    const body = input.value.trim();
    if (!body) return;
    const key = `comment:${reelId}`;
    if (!lock(key)) return;
    btn.disabled = true;
    pauseActive('comments');
    fetch(`/reels/api/reels/${reelId}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify({ body })
    })
      .then(r => r.json())
      .then(data => {
        if (!data.success || !data.comment) throw new Error('comment_failed');
        input.value = '';
        renderComment(data.comment, reelId);
        const countEl = qs(`#reel-comments-${reelId}`);
        if (countEl && typeof data.count === 'number') countEl.textContent = data.count;
        toast('Comment posted');
      })
      .catch(() => {
        input.value = body;
        toast('Could not post comment');
      })
      .finally(() => {
        btn.disabled = false;
        unlock(key);
        resumeIfActive();
      });
  }

  function renderComment(comment, reelId) {
    const list = qs('#reel-comment-list');
    if (!list) return;
    const empty = list.querySelector('p');
    if (empty && empty.textContent.includes('No comments')) empty.remove();
    const item = document.createElement('div');
    item.className = 'reel-comment-item';
    const avatar = document.createElement('div');
    avatar.className = 'reel-comment-avatar';
    if (comment.avatar_url) {
      const img = document.createElement('img');
      const safe = safeUrl(comment.avatar_url);
      if (safe) img.src = safe;
      avatar.appendChild(img);
    } else {
      const icon = document.createElement('i');
      icon.className = 'fas fa-user';
      avatar.appendChild(icon);
    }
    const body = document.createElement('div');
    body.className = 'reel-comment-body';
    const user = document.createElement('strong');
    user.className = 'reel-comment-user';
    user.textContent = comment.username || 'User';
    const text = document.createElement('span');
    text.textContent = ' ' + (comment.body || '');
    const time = document.createElement('div');
    time.className = 'reel-comment-time';
    time.textContent = timeAgo(comment.created_at);
    body.append(user, text, time);
    item.append(avatar, body);
    list.prepend(item);
  }

  function openOrCloseComments(btn) {
    const drawer = qs('#reel-comment-drawer');
    if (!drawer) return;
    if (drawer.style.display === 'flex') {
      closeComments();
    } else {
      openComments(btn.closest('.reel-slide'), btn);
    }
  }

  function setupDrawerControls() {
    const close = qs('#reel-comment-close');
    if (close) close.addEventListener('click', closeComments);
    const submit = qs('#reel-comment-submit');
    if (submit) submit.addEventListener('click', handleCommentSubmit);
    const input = qs('#reel-comment-input');
    if (input) {
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleCommentSubmit();
        }
      });
    }
  }

  function setupShareDrawer() {
    const close = qs('#reel-share-close');
    if (close) close.addEventListener('click', () => { const d = qs('#reel-share-drawer'); if (d) d.style.display = 'none'; resumeIfActive(); });
    const copy = qs('[data-copy-link]');
    if (copy) copy.addEventListener('click', function () {
      const reelId = this.closest('.reel-drawer')?.dataset?.reelId;
      const url = `${window.location.origin}/reels/${reelId}`;
      navigator.clipboard?.writeText(url).then(() => {
        this.textContent = 'Copied!';
        toast('Link copied');
      }).catch(() => toast('Could not copy link'));
    });
  }

  function setupDelegatedActions() {
    viewport.addEventListener('click', e => {
      const btn = e.target.closest('[data-like], [data-save], [data-comment], [data-share], [data-follow]');
      if (!btn) {
        const video = e.target.closest('.reel-video');
        if (video && e.detail === 1) {
          video.paused ? video.play().catch(() => {}) : video.pause();
        }
        return;
      }
      e.preventDefault();
      handleActionClick(btn);
    });
  }

  function setupKeyboard() {
    document.addEventListener('keydown', e => {
      if (isTextInput(e.target)) return;
      if (e.key === 'Escape') {
        closeComments();
        const share = qs('#reel-share-drawer');
        if (share) share.style.display = 'none';
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'PageDown') { e.preventDefault(); scrollByOne(1); }
      if (e.key === 'ArrowUp' || e.key === 'PageUp') { e.preventDefault(); scrollByOne(-1); }
      if (e.key === ' ') {
        e.preventDefault();
        const video = videoFor(controller.activeSlide);
        if (video) video.paused ? video.play().catch(() => {}) : video.pause();
      }
      if (e.key === 'm' || e.key === 'M') setMuted(!controller.muted);
    });
  }

  function scrollByOne(delta) {
    const all = Array.from(slides);
    const next = all[Math.max(0, Math.min(all.length - 1, controller.currentIndex + delta))];
    if (next) next.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function setupVisibility() {
    document.addEventListener('visibilitychange', () => {
      controller.pageVisible = document.visibilityState !== 'hidden';
      if (!controller.pageVisible) pauseActive('visibility');
      else resumeIfActive();
    });
    window.addEventListener('offline', () => { controller.networkOffline = true; setStatus('Offline', true); pauseActive('offline'); });
    window.addEventListener('online', () => { controller.networkOffline = false; setStatus('', false); resumeIfActive(); });
    window.addEventListener('beforeunload', () => {
      const slide = controller.activeSlide;
      const video = videoFor(slide);
      if (slide && video) sendTelemetry(`/reels/api/reels/${reelIdFor(slide)}/event`, { event_type: 'leave', watch_ms: Math.round((video.currentTime || 0) * 1000) });
    });
  }

  function timeAgo(value) {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    const diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h';
    return Math.floor(diff / 86400) + 'd';
  }

  function init() {
    mountInitialSlides();
    setupDelegatedActions();
    setupKeyboard();
    setupVisibility();
    setupDrawerControls();
    setupShareDrawer();
    updateMuteButtons();
    observeSlides();
    observeLoadSentinel();
    startProgressLoop();
    const first = Array.from(slides)[0];
    if (first) {
      first.scrollIntoView({ behavior: 'auto', block: 'start' });
      updateActiveState(first);
    }
  }

  init();

  window.NamVibeReels = {
    debug: () => ({
      mounted: slides.size,
      seen: seenIds.size,
      active: reelIdFor(controller.activeSlide),
      hasMore: controller.hasMore,
      nextCursor: controller.nextCursor
    })
  };
})();
