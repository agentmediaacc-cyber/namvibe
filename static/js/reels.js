(function () {
  'use strict';

  if (window.__NAMVIBE_REELS_INITIALIZED__) return;
  window.__NAMVIBE_REELS_INITIALIZED__ = true;

  const viewport = document.getElementById('reels-viewport');
  if (!viewport) return;

  const statusEl = document.getElementById('reels-feed-status');
  const emptyStateEl = qs('.reels-empty', viewport);
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
    fetchPageOneGuard: true,
    lastPlayError: null,
    initialServerItemCount: qsa('.reel-slide', viewport).length,
    firstPageRequested: false,
    firstPageStatus: 0,
    firstPageItemCount: 0,
    emptyStateVisible: !!emptyStateEl
  };
  let scrollUpdateRaf = 0;

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
  function safeReelUrl(reelId) {
    const id = String(reelId || '').trim();
    if (!id) return '';
    return `${window.location.origin}/reels/${encodeURIComponent(id)}`;
  }
  function scheduleActiveSlideUpdate() {
    if (scrollUpdateRaf) return;
    scrollUpdateRaf = window.requestAnimationFrame(() => {
      scrollUpdateRaf = 0;
      updateActiveSlideFromViewport();
    });
  }
  function updateActiveSlideFromViewport() {
    if (!slides.size) return;
    const viewportRect = viewport.getBoundingClientRect();
    const centerY = viewportRect.top + viewportRect.height * 0.5;
    let bestSlide = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    slides.forEach(slide => {
      if (!slide || !document.contains(slide)) return;
      const rect = slide.getBoundingClientRect();
      if (rect.bottom < viewportRect.top || rect.top > viewportRect.bottom) return;
      const slideCenter = rect.top + rect.height * 0.5;
      const distance = Math.abs(slideCenter - centerY);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestSlide = slide;
      }
    });
    if (bestSlide && bestSlide !== controller.activeSlide) updateActiveState(bestSlide);
  }
  function toast(msg) {
    if (window.NamVibeToast && typeof window.NamVibeToast.show === 'function') {
      window.NamVibeToast.show(msg);
      return;
    }
    console.log(msg);
  }
  function ensureAuthPrompt() {
    let modal = document.getElementById('reel-auth-prompt');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'reel-auth-prompt';
    modal.className = 'reel-auth-prompt';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="reel-auth-prompt__backdrop" data-auth-close></div>
      <div class="reel-auth-prompt__card" role="dialog" aria-modal="true" aria-labelledby="reel-auth-title">
        <h2 id="reel-auth-title">Join NamVibe to connect</h2>
        <p>Watch public reels freely. Sign in or create an account to like, comment, save, follow, or message.</p>
        <div class="reel-auth-prompt__actions">
          <a class="px-btn px-btn--gold" data-auth-login href="/auth/login">Log in</a>
          <a class="px-btn px-btn--outline" data-auth-register href="/auth/register">Create account</a>
          <button type="button" class="px-btn px-btn--ghost" data-auth-close>Not now</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', (event) => {
      if (event.target.closest('[data-auth-close]')) {
        modal.hidden = true;
      }
    });
    return modal;
  }
  function showAuthPrompt(loginUrl, registerUrl) {
    const modal = ensureAuthPrompt();
    const current = window.location.pathname + window.location.search + window.location.hash;
    const login = modal.querySelector('[data-auth-login]');
    const register = modal.querySelector('[data-auth-register]');
    if (login) login.href = loginUrl || `/auth/login?next=${encodeURIComponent(current)}`;
    if (register) register.href = registerUrl || `/auth/register?next=${encodeURIComponent(current)}`;
    modal.hidden = false;
    const focusable = modal.querySelector('a,button');
    if (focusable) focusable.focus();
  }
  function handleAuthResponse(data) {
    const error = data && (data.error || data.message || '');
    const isAuth = String(error).toLowerCase().includes('auth') || error === 'authentication_required';
    if (isAuth) {
      showAuthPrompt(data.login_url, data.register_url);
      return true;
    }
    return false;
  }
  function setStatus(msg, show) {
    if (!statusEl) return;
    statusEl.hidden = !show;
    statusEl.textContent = msg || '';
  }

  function getFeedItems(payload) {
    if (Array.isArray(payload && payload.items)) return payload.items;
    if (Array.isArray(payload && payload.reels)) return payload.reels;
    return [];
  }

  function setLoadingShell(message) {
    if (emptyStateEl) {
      emptyStateEl.hidden = false;
      emptyStateEl.style.display = 'grid';
      emptyStateEl.setAttribute('aria-hidden', 'false');
      const title = qs('h2', emptyStateEl);
      const body = qs('p', emptyStateEl);
      const action = qs('a', emptyStateEl);
      if (title) title.textContent = message || 'Loading Reels…';
      if (body) body.textContent = 'Fetching public Reels.';
      if (action) {
        action.textContent = 'Upload Reel';
        action.href = '/reels/upload';
        action.onclick = null;
      }
    }
    setStatus(message || 'Loading Reels…', true);
    controller.emptyStateVisible = true;
  }

  function showGenuineEmptyState() {
    if (emptyStateEl) {
      emptyStateEl.hidden = false;
      emptyStateEl.style.display = 'grid';
      emptyStateEl.setAttribute('aria-hidden', 'false');
      const title = qs('h2', emptyStateEl);
      const body = qs('p', emptyStateEl);
      const action = qs('a', emptyStateEl);
      if (title) title.textContent = 'No reels yet';
      if (body) body.textContent = 'Be the first to share a short video on NamVibe.';
      if (action) {
        action.textContent = 'Upload Reel';
        action.href = '/reels/upload';
        action.onclick = null;
      }
    }
    setStatus('', false);
    controller.emptyStateVisible = true;
  }

  function showLoadErrorState(message) {
    if (emptyStateEl) {
      emptyStateEl.hidden = false;
      emptyStateEl.style.display = 'grid';
      emptyStateEl.setAttribute('aria-hidden', 'false');
      const title = qs('h2', emptyStateEl);
      const body = qs('p', emptyStateEl);
      const action = qs('a', emptyStateEl);
      if (title) title.textContent = 'Reels could not load.';
      if (body) body.textContent = message || 'Tap retry to try again.';
      if (action) {
        action.textContent = 'Retry';
        action.href = '#';
        action.onclick = (event) => {
          event.preventDefault();
          loadFirstPage({ force: true });
        };
      }
    }
    setStatus(message || 'Reels could not load. Tap to retry.', true);
    controller.emptyStateVisible = true;
  }

  function hideEmptyState() {
    if (emptyStateEl) {
      emptyStateEl.hidden = true;
      emptyStateEl.style.display = 'none';
      emptyStateEl.setAttribute('aria-hidden', 'true');
    }
    setStatus('', false);
    controller.emptyStateVisible = false;
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

  function mediaShellFor(slide) {
    return slide ? qs('.reel-media-shell', slide) : null;
  }

  function posterFor(slide) {
    return slide ? qs('.reel-poster', slide) : null;
  }

  function loadingFor(slide) {
    return slide ? qs('.reel-loading', slide) : null;
  }

  function retryFor(slide) {
    return slide ? qs('.reel-play-retry', slide) : null;
  }

  function setMuted(muted) {
    controller.muted = !!muted;
    sessionStorage.setItem('namvibe_reels_muted', controller.muted ? 'true' : 'false');
    qsa('.reel-video', viewport).forEach(v => { v.muted = controller.muted; });
    updateMuteButtons();
    updateDebugState();
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
    controller.activeVideo = video;
    qsa('.reel-video', viewport).forEach(v => {
      if (v !== video) {
        v.pause();
        if (!v.dataset.keepPosition) v.currentTime = 0;
        v.preload = controller.networkOffline || navigator.connection?.saveData ? 'metadata' : 'none';
      }
    });
    if (video.readyState === 0) video.load();
    video.preload = 'auto';
    video.muted = controller.muted;
    video.defaultMuted = controller.muted;
    video.playsInline = true;
    video.setAttribute('muted', '');
    slide.classList.add('is-loading');
    slide.classList.remove('has-error', 'is-play-blocked');
    attemptPlay(video, slide);
    controller.currentIndex = Array.from(slides).indexOf(slide);
    updatePreloadWindow();
    startProgressLoop();
    updateDebugState();
  }

  async function attemptPlay(video, slide) {
    if (!video) return;
    if (!controller.pageVisible) return;
    if (controller.openPanel) return;
    if (video.readyState === 0) video.load();
    controller.lastPlayError = null;
    showTapToPlay(slide, false);
    if (controller.muted !== true && sessionStorage.getItem('namvibe_reels_muted') !== 'false') {
      setMuted(true);
    }
    video.muted = controller.muted;
    video.defaultMuted = controller.muted;
    try {
      await video.play();
      slide.classList.add('is-playing');
      slide.classList.remove('is-buffering', 'is-stalled', 'is-play-blocked', 'has-error', 'is-loading');
      await waitForRenderedFrame(video, slide);
      markRenderedFrame(slide);
      showTapToPlay(slide, false);
    } catch (error) {
      controller.lastPlayError = String(error && error.message ? error.message : error || 'play_failed');
      if (!controller.muted) {
        setMuted(true);
        try {
          await video.play();
          slide.classList.add('is-playing');
          slide.classList.remove('is-buffering', 'is-stalled', 'is-play-blocked', 'has-error', 'is-loading');
          await waitForRenderedFrame(video, slide);
          markRenderedFrame(slide);
          showTapToPlay(slide, false);
          updateDebugState();
          return;
        } catch (secondError) {
          controller.lastPlayError = String(secondError && secondError.message ? secondError.message : secondError || 'play_failed');
        }
      }
      slide.dataset.playBlocked = 'true';
      slide.classList.add('is-play-blocked');
      showTapToPlay(slide, true);
    }
    updateDebugState();
  }

  function showTapToPlay(slide, on) {
    if (!slide) return;
    slide.classList.toggle('is-play-blocked', !!on);
    const retry = retryFor(slide);
    if (retry) retry.hidden = !on;
    const loading = loadingFor(slide);
    if (loading) loading.hidden = !!on;
    const shell = mediaShellFor(slide);
    if (shell && on) shell.classList.remove('has-rendered-frame');
  }

  function markRenderedFrame(slide) {
    if (!slide) return;
    const video = videoFor(slide);
    const shell = mediaShellFor(slide);
    if (!video || !shell) return;
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0 && video.videoHeight > 0) {
      shell.classList.add('has-rendered-frame');
      slide.classList.remove('is-loading');
      showTapToPlay(slide, false);
    }
  }

  function waitForRenderedFrame(video, slide, timeoutMs = 5000) {
    if (!video || !slide) return Promise.resolve(null);
    if (video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      markRenderedFrame(slide);
      return Promise.resolve({ width: video.videoWidth, height: video.videoHeight, currentTime: video.currentTime });
    }
    return new Promise((resolve, reject) => {
      let settled = false;
      const timer = window.setTimeout(() => {
        if (settled) return;
        settled = true;
        reject(new Error('No rendered video frame'));
      }, timeoutMs);
      const finish = (metadata) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(metadata);
      };
      const onReady = () => {
        if (video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          markRenderedFrame(slide);
          finish({ width: video.videoWidth, height: video.videoHeight, currentTime: video.currentTime });
        }
      };
      if (typeof video.requestVideoFrameCallback === 'function') {
        video.requestVideoFrameCallback((_now, metadata) => {
          markRenderedFrame(slide);
          finish(metadata);
        });
        return;
      }
      video.addEventListener('timeupdate', onReady);
      video.addEventListener('loadeddata', onReady, { once: true });
      video.addEventListener('playing', onReady, { once: true });
    });
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

  viewport.addEventListener('scroll', scheduleActiveSlideUpdate, { passive: true });
  window.addEventListener('resize', scheduleActiveSlideUpdate, { passive: true });

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
    const retry = retryFor(slide);
    if (video) {
      video.preload = 'metadata';
      video.muted = controller.muted;
      video.defaultMuted = controller.muted;
      video.setAttribute('playsinline', '');
      video.setAttribute('webkit-playsinline', '');
      video.setAttribute('muted', '');
      video.setAttribute('disablepictureinpicture', '');
      video.setAttribute('controlslist', 'nodownload noplaybackrate');
      video.addEventListener('loadedmetadata', () => slide.classList.remove('is-loading'));
      video.addEventListener('loadeddata', () => {
        if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) slide.classList.remove('is-loading');
      });
      video.addEventListener('canplay', () => {
        if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) slide.classList.remove('is-loading');
      });
      video.addEventListener('waiting', () => { slide.classList.add('is-buffering'); slide.classList.remove('is-playing'); });
      video.addEventListener('playing', () => { slide.classList.add('is-playing'); slide.classList.remove('is-buffering', 'is-stalled', 'is-play-blocked', 'has-error', 'is-loading'); markRenderedFrame(slide); });
      video.addEventListener('stalled', () => { slide.classList.add('is-stalled'); slide.classList.remove('is-playing'); showTapToPlay(slide, true); });
      video.addEventListener('error', () => { slide.classList.add('has-error'); slide.classList.remove('is-playing', 'is-loading'); showTapToPlay(slide, true); controller.lastPlayError = 'media_error'; updateDebugState(); });
      video.addEventListener('emptied', () => { slide.classList.remove('is-playing'); slide.classList.add('is-loading'); });
      video.addEventListener('ended', () => {
        sendTelemetry(`/reels/api/reels/${reelId}/event`, { event_type: 'complete', watch_ms: Math.round((video.currentTime || 0) * 1000) });
      });
    }
    if (retry) {
      retry.hidden = true;
      retry.addEventListener('click', () => {
        showTapToPlay(slide, false);
        if (video) {
          if (video.readyState === 0) video.load();
          video.muted = true;
          setMuted(true);
          attemptPlay(video, slide);
        }
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
    fetchFeedPage(controller.nextCursor)
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(data => {
        const items = getFeedItems(data);
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

  function fetchFeedPage(cursor) {
    const url = cursor
      ? `/reels/api/reels/feed?limit=5&cursor=${encodeURIComponent(cursor)}`
      : '/reels/api/reels/feed?limit=5';
    return fetch(url, { credentials: 'same-origin' });
  }

  async function loadFirstPage(opts = {}) {
    const force = !!opts.force;
    if (controller.loadingMore) return null;
    if (controller.firstPageRequested && !force) return null;
    controller.firstPageRequested = true;
    controller.fetchPageOneGuard = false;
    controller.firstPageStatus = 0;
    controller.firstPageItemCount = 0;
    controller.loadingMore = true;
    setLoadingShell('Loading Reels…');
    try {
      const response = await fetchFeedPage(null);
      controller.firstPageStatus = response.status;
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const items = getFeedItems(payload).filter(item => item && item.id && !seenIds.has(item.id));
      controller.firstPageItemCount = items.length;
      controller.nextCursor = payload.next_cursor || null;
      controller.hasMore = !!payload.has_more && !!controller.nextCursor;
      if (items.length) {
        hideEmptyState();
        appendSlides(items);
        requestAnimationFrame(() => {
          const first = Array.from(slides)[0];
          if (first) updateActiveState(first);
        });
      } else {
        if (controller.hasMore) {
          hideEmptyState();
        } else {
          showGenuineEmptyState();
        }
      }
      updateDebugState();
      return payload;
    } catch (error) {
      controller.lastPlayError = String(error && error.message ? error.message : error || 'feed_failed');
      showLoadErrorState('Reels could not load. Tap to retry.');
      updateDebugState();
      return null;
    } finally {
      controller.loadingMore = false;
    }
  }

  function appendSlides(items) {
    const anchor = qs('#reels-feed-end');
    if (items.length) hideEmptyState();
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
    mediaWrap.className = 'reel-media-shell';
    const poster = document.createElement(item.thumbnail_url ? 'img' : 'div');
    if (item.thumbnail_url) {
      poster.className = 'reel-poster';
      poster.alt = '';
      poster.setAttribute('aria-hidden', 'true');
      poster.src = item.thumbnail_url;
    } else {
      poster.className = 'reel-poster reel-poster-fallback';
      poster.setAttribute('aria-hidden', 'true');
      poster.dataset.reelFallback = (item.creator_username || item.username || item.id || 'R').charAt(0).toUpperCase();
      const fallback = document.createElement('span');
      fallback.textContent = escText((item.creator_username || item.username || item.id || 'R').charAt(0).toUpperCase());
      poster.appendChild(fallback);
    }
    mediaWrap.appendChild(poster);
    if (item.video_url) {
      const video = document.createElement('video');
      video.className = 'reel-video';
      video.src = item.video_url;
      if (item.thumbnail_url) video.poster = item.thumbnail_url;
      video.preload = 'metadata';
      video.loop = true;
      video.playsInline = true;
      video.autoplay = true;
      video.muted = controller.muted;
      video.defaultMuted = controller.muted;
      video.setAttribute('webkit-playsinline', '');
      video.setAttribute('controlslist', 'nodownload noplaybackrate');
      video.setAttribute('disablepictureinpicture', '');
      video.setAttribute('oncontextmenu', 'return false');
      mediaWrap.appendChild(video);
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'reel-play-retry';
      retry.hidden = true;
      retry.textContent = 'Tap to play';
      retry.setAttribute('aria-label', 'Tap to play reel');
      mediaWrap.appendChild(retry);
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
    const loading = document.createElement('div');
    loading.className = 'reel-loading';
    loading.setAttribute('aria-hidden', 'true');
    const heart = document.createElement('div');
    heart.className = 'double-tap-heart';
    const heartIcon = document.createElement('i');
    heartIcon.className = 'fas fa-heart';
    heart.appendChild(heartIcon);
    mediaWrap.append(loading, gradient, heart);
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
    }, { threshold: [0.6, 0.75, 0.9] });
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
        if (data && handleAuthResponse(data)) {
          throw new Error('authentication_required');
        }
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
        if (data && handleAuthResponse(data)) {
          throw new Error('authentication_required');
        }
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
        if (data && handleAuthResponse(data)) {
          throw new Error('authentication_required');
        }
        if (!data.success && !data.following) throw new Error('follow_failed');
        btn.textContent = 'Following';
        toast('Following creator');
      })
      .catch(() => toast('Could not follow creator.'))
      .finally(() => unlock(key));
  }

  function openShare(slide, btn, reelId) {
    pauseActive('share');
    const url = safeReelUrl(reelId);
    if (!url) return;
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
        if (data && handleAuthResponse(data)) {
          throw new Error('authentication_required');
        }
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
      const url = safeReelUrl(reelId);
      if (!url) return;
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
    } else {
      loadFirstPage();
    }
    updateDebugState();
  }

  init();

  window.NamVibeReels = {
    debug: () => ({
      mounted: slides.size,
      seen: seenIds.size,
      active: reelIdFor(controller.activeSlide),
      hasMore: controller.hasMore,
      nextCursor: controller.nextCursor,
      initialServerItemCount: controller.initialServerItemCount,
      firstPageRequested: controller.firstPageRequested,
      firstPageStatus: controller.firstPageStatus,
      firstPageItemCount: controller.firstPageItemCount,
      emptyStateVisible: controller.emptyStateVisible
    })
  };

  function updateDebugState() {
    if (!window.__NAMVIBE_REELS_BROWSER_DEBUG__ && !window.__NAMVIBE_REELS_DEBUG__) return;
    const slide = controller.activeSlide;
    const video = videoFor(slide);
    window.__NAMVIBE_REELS_DEBUG__ = {
      activeReelId: reelIdFor(slide),
      mountedSlides: slides.size,
      playingVideos: qsa('.reel-video', viewport).filter(v => !v.paused && !v.ended && v.readyState > 2).length,
      lastPlayError: controller.lastPlayError,
      activeReadyState: video ? video.readyState : 0,
      activeNetworkState: video ? video.networkState : 0,
      activeMuted: video ? !!video.muted : controller.muted,
      activeVideoSrc: video ? video.currentSrc || video.src || '' : '',
      initialServerItemCount: controller.initialServerItemCount,
      firstPageRequested: controller.firstPageRequested,
      firstPageStatus: controller.firstPageStatus,
      firstPageItemCount: controller.firstPageItemCount,
      emptyStateVisible: controller.emptyStateVisible
    };
  }
})();
