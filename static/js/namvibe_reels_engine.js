// ===== NamVibe Reels Engine Premium JS =====
(function () {
  "use strict";

  // ── State ──
  const state = {
    reels: [],
    currentIndex: 0,
    isMuted: false,
    isLoading: false,
    hasMore: true,
    cursor: null,
    viewport: null,
    preloadQueue: [],
    watchTimers: {},
    lastWatchReport: {},
    doubleTapTimer: null,
  };

  const WATCH_REPORT_INTERVAL = 5000; // ms
  const COMPLETION_THRESHOLD = 0.9;
  const PRELOAD_COUNT = 2;

  function safeReelUrl(reelId) {
    const id = String(reelId || "").trim();
    if (!id || id === "None" || id === "null" || id === "undefined") return "/reels/";
    return `/reels/${encodeURIComponent(id)}`;
  }

  // ── Init ──
  function init() {
    state.viewport = document.getElementById("nv-reels-viewport");
    if (!state.viewport) return;
    loadReels().then(start);
  }

  async function loadReels() {
    if (state.isLoading || !state.hasMore) return;
    state.isLoading = true;
    showSkeleton();
    try {
      const params = new URLSearchParams({ limit: "10" });
      if (state.cursor) params.set("cursor", state.cursor);
      const res = await fetch("/reels/api/feed?" + params);
      const data = await res.json();
      const items = data.reels || data.items || [];
      if (items.length === 0) {
        state.hasMore = false;
        return;
      }
      state.reels.push(...items);
      state.cursor = data.next_cursor || null;
      state.hasMore = data.has_more !== false;
    } catch (e) {
      console.error("[NV Reels] load error", e);
      showError();
    } finally {
      state.isLoading = false;
      hideSkeleton();
    }
  }

  function start() {
    renderSlides();
    observeScroll();
    observeActiveSlide();
    bindKeyboard();
    bindMuteToggle();
    setTimeout(() => playCurrent(), 300);
  }

  // ── Render ──
  function renderSlides() {
    const frag = document.createDocumentFragment();
    state.reels.forEach((reel, i) => {
      const slide = createSlide(reel, i);
      frag.appendChild(slide);
    });
    state.viewport.innerHTML = "";
    state.viewport.appendChild(frag);
  }

  function createSlide(reel, index) {
    const div = document.createElement("div");
    div.className = "nv-reel-slide";
    div.dataset.index = index;

    div.innerHTML = `
      <div class="nv-reel-skeleton" id="skel-${index}">
        <div style="color:#555;font-size:14px">Loading...</div>
      </div>
      <video
        src="${escapeHtml(reel.video_url || '')}"
        poster="${escapeHtml(reel.thumbnail_url || '')}"
        playsinline loop muted
        preload="metadata"
        id="nv-video-${index}"
        style="display:none"
      ></video>
      <div class="nv-reel-overlay"></div>
      <div class="nv-reel-progress"><div class="nv-reel-progress-bar" id="nv-progress-${index}"></div></div>
      <div class="nv-reel-info">
        <div class="nv-reel-creator">
          <img class="nv-reel-avatar" src="${escapeHtml(reel.avatar_url || '')}" alt="" loading="lazy" onerror="this.src='/static/img/default-avatar.png'">
          <span class="nv-reel-username">${escapeHtml(reel.display_name || '')}</span>
        </div>
        <div class="nv-reel-caption">${escapeHtml(reel.caption || '')}</div>
        ${reel.music_title ? `<div class="nv-reel-music"><i class="fas fa-music"></i> ${escapeHtml(reel.music_title)} ${reel.music_artist ? '· ' + escapeHtml(reel.music_artist) : ''}</div>` : ''}
      </div>
      <div class="nv-reel-actions">
        <button class="nv-reel-action-btn" data-action="like" data-reel-id="${reel.id || ''}" ${reel.id ? '' : 'disabled'}>
          <i class="fas fa-heart${reel.viewer_has_liked ? ' liked' : ''}"></i>
        </button>
        <span class="nv-reel-action-label">${formatCount(reel.likes_count || 0)}</span>
        <button class="nv-reel-action-btn" data-action="comment" data-reel-id="${reel.id || ''}" ${reel.id ? '' : 'disabled'}>
          <i class="fas fa-comment"></i>
        </button>
        <span class="nv-reel-action-label">${formatCount(reel.comments_count || 0)}</span>
        <button class="nv-reel-action-btn ${reel.viewer_has_saved ? 'saved' : ''}" data-action="save" data-reel-id="${reel.id || ''}" ${reel.id ? '' : 'disabled'}>
          <i class="fas fa-bookmark"></i>
        </button>
        <span class="nv-reel-action-label">${formatCount(reel.saves_count || 0)}</span>
        <button class="nv-reel-action-btn" data-action="share" data-reel-id="${reel.id || ''}" ${reel.id ? '' : 'disabled'}>
          <i class="fas fa-share"></i>
        </button>
      </div>
      <button class="nv-reel-mute-btn" style="display:none"><i class="fas fa-volume-up"></i></button>
      <div class="nv-double-tap-heart" id="nv-heart-${index}"><i class="fas fa-heart"></i></div>
    `;

    // Video loadeddata -> hide skeleton, show video
    const video = div.querySelector("video");
    video.addEventListener("loadeddata", () => {
      const skel = div.querySelector(".nv-reel-skeleton");
      if (skel) skel.remove();
      video.style.display = "block";
    });
    video.addEventListener("error", () => {
      const skel = div.querySelector(".nv-reel-skeleton");
      if (skel) {
        skel.innerHTML = `<div class="nv-reel-error"><span>Failed to load</span><button onclick="location.reload()">Retry</button></div>`;
      }
    });

    // Double-tap for like
    let lastTap = 0;
    div.addEventListener("click", (e) => {
      if (e.target.closest(".nv-reel-action-btn, .nv-reel-mute-btn")) return;
      const now = Date.now();
      if (now - lastTap < 300) {
        handleDoubleTap(index, reel.id, e);
        lastTap = 0;
      } else {
        lastTap = now;
      }
    });

    // Touch swipe up/down signals
    let touchStartY = 0;
    div.addEventListener("touchstart", (e) => {
      touchStartY = e.touches[0].clientY;
    }, { passive: true });

    return div;
  }

  // ── Playback ──
  function playCurrent() {
    const slides = state.viewport.querySelectorAll(".nv-reel-slide");
    slides.forEach((s, i) => {
      const v = s.querySelector("video");
      if (!v) return;
      if (i === state.currentIndex) {
        v.muted = state.isMuted;
        v.play().catch(() => {});
        startWatchTimer(i);
        preloadNext(i);
        if (i === slides.length - 1 && state.hasMore && !state.isLoading) {
          loadReels().then(() => {
            // Re-render if new reels added
            if (state.reels.length > slides.length) {
              const currentScroll = state.viewport.scrollTop;
              const slideHeight = window.innerHeight;
              const newIndex = Math.round(currentScroll / slideHeight);
              renderSlides();
              state.currentIndex = newIndex;
              // restore scroll to maintain position
              setTimeout(() => {
                state.viewport.scrollTop = newIndex * slideHeight;
                playCurrent();
              }, 50);
            }
          });
        }
      } else {
        v.pause();
        v.currentTime = 0;
        stopWatchTimer(i);
      }
    });
  }

  function preloadNext(index) {
    const slides = state.viewport.querySelectorAll(".nv-reel-slide");
    for (let i = 1; i <= PRELOAD_COUNT; i++) {
      const nextIdx = index + i;
      if (nextIdx < slides.length) {
        const v = slides[nextIdx].querySelector("video");
        if (v && v.readyState < 2) v.preload = "auto";
      }
    }
  }

  // ── Watch Tracking ──
  function startWatchTimer(index) {
    const reel = state.reels[index];
    if (!reel) return;
    stopWatchTimer(index);

    const key = `watch_${index}`;
    state.lastWatchReport[key] = Date.now();
    state.lastWatchReport[`start_${index}`] = Date.now();

    state.watchTimers[key] = setInterval(() => {
      reportWatch(index);
    }, WATCH_REPORT_INTERVAL);
  }

  function stopWatchTimer(index) {
    const key = `watch_${index}`;
    if (state.watchTimers[key]) {
      clearInterval(state.watchTimers[key]);
      delete state.watchTimers[key];
      // Final report on stop
      reportWatch(index, true);
    }
  }

  function reportWatch(index, isFinal) {
    const reel = state.reels[index];
    if (!reel) return;
    const key = `watch_${index}`;
    const now = Date.now();
    const elapsed = now - (state.lastWatchReport[key] || now);
    state.lastWatchReport[key] = now;
    const duration = (reel.duration_seconds || 30) * 1000;
    const video = document.getElementById(`nv-video-${index}`);
    const currentTime = video ? video.currentTime * 1000 : 0;
    const completed = currentTime > 0 && duration > 0 && (currentTime / duration) >= COMPLETION_THRESHOLD;

    fetch(`/reels/api/reels/${reel.id}/watch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watch_seconds: currentTime / 1000,
        completion_percent: duration > 0 ? Math.min(currentTime / duration, 1) : 0,
        replay_count: 0,
        session_id: `web_${index}`,
      }),
    }).catch(() => {});
  }

  // ── Progress Bar ──
  function updateProgress(index) {
    const reel = state.reels[index];
    if (!reel) return;
    const video = document.getElementById(`nv-video-${index}`);
    const bar = document.getElementById(`nv-progress-${index}`);
    if (!video || !bar) return;
    const duration = reel.duration_seconds || video.duration || 30;
    const pct = duration > 0 ? (video.currentTime / duration) * 100 : 0;
    bar.style.width = Math.min(pct, 100) + "%";
  }

  // ── Scroll / Intersection ──
  function observeScroll() {
    state.viewport.addEventListener("scroll", () => {
      const slideHeight = window.innerHeight;
      const newIndex = Math.round(state.viewport.scrollTop / slideHeight);
      if (newIndex !== state.currentIndex && newIndex >= 0 && newIndex < state.reels.length) {
        // Stop old watch timer for current
        stopWatchTimer(state.currentIndex);
        state.currentIndex = newIndex;
        playCurrent();
      }
    }, { passive: true });
  }

  function observeActiveSlide() {
    setInterval(() => {
      const idx = state.currentIndex;
      updateProgress(idx);
    }, 200);
  }

  // ── Keyboard ──
  function bindKeyboard() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "ArrowUp") {
        e.preventDefault();
        scrollTo(state.currentIndex - 1);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        scrollTo(state.currentIndex + 1);
      } else if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      } else if (e.key === "m" || e.key === "M") {
        toggleMute();
      }
    });
  }

  function scrollTo(index) {
    if (index < 0 || index >= state.reels.length) return;
    state.currentIndex = index;
    state.viewport.scrollTo({ top: index * window.innerHeight, behavior: "smooth" });
  }

  function togglePlay() {
    const slide = state.viewport.querySelectorAll(".nv-reel-slide")[state.currentIndex];
    if (!slide) return;
    const v = slide.querySelector("video");
    if (!v) return;
    if (v.paused) {
      v.play().catch(() => {});
      startWatchTimer(state.currentIndex);
    } else {
      v.pause();
      stopWatchTimer(state.currentIndex);
    }
  }

  // ── Mute ──
  function bindMuteToggle() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".nv-reel-mute-btn");
      if (btn) toggleMute();
    });
  }

  function toggleMute() {
    state.isMuted = !state.isMuted;
    const slides = state.viewport.querySelectorAll(".nv-reel-slide");
    slides.forEach((s, i) => {
      const v = s.querySelector("video");
      if (v) v.muted = state.isMuted;
    });
    const btns = document.querySelectorAll(".nv-reel-mute-btn i");
    btns.forEach((b) => {
      b.className = state.isMuted ? "fas fa-volume-mute" : "fas fa-volume-up";
    });
  }

  // ── Action Handlers (delegated) ──
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    const reelId = btn.dataset.reelId;
    if (!reelId) return;

    e.stopPropagation();

    switch (action) {
      case "like":
        await handleLike(btn, reelId);
        break;
      case "save":
        await handleSave(btn, reelId);
        break;
      case "share":
        openShareDrawer(reelId);
        break;
      case "comment":
        openCommentDrawer(reelId);
        break;
    }
  });

  async function handleLike(btn, reelId) {
    try {
      const res = await fetch(`/reels/api/reels/${reelId}/like`, { method: "POST" });
      const data = await res.json();
      const icon = btn.querySelector("i");
      const liked = data.liked || data.new_state === "liked" || data.is_liked;
      if (liked) {
        icon.classList.add("liked");
      } else {
        icon.classList.remove("liked");
      }
      // Update count
      const label = btn.parentElement.querySelector(".nv-reel-action-label");
      if (label && data.likes_count != null) {
        label.textContent = formatCount(data.likes_count);
      }
      // Track
      if (liked) trackActivity(reelId, "reel_liked");
    } catch (e) {
      console.error("[NV Reels] like error", e);
    }
  }

  async function handleSave(btn, reelId) {
    try {
      const res = await fetch(`/reels/api/reels/${reelId}/save`, { method: "POST" });
      const data = await res.json();
      const icon = btn.querySelector("i");
      const saved = data.saved || data.new_state === "saved" || data.is_saved;
      if (saved) {
        btn.classList.add("saved");
      } else {
        btn.classList.remove("saved");
      }
      const label = btn.parentElement.querySelector(".nv-reel-action-label");
      if (label && data.saves_count != null) {
        label.textContent = formatCount(data.saves_count);
      }
      if (saved) trackActivity(reelId, "reel_saved");
    } catch (e) {
      console.error("[NV Reels] save error", e);
    }
  }

  // ── Double-tap Like ──
  function handleDoubleTap(index, reelId, e) {
    const heart = document.getElementById(`nv-heart-${index}`);
    if (heart) {
      heart.classList.remove("pop");
      void heart.offsetWidth;
      heart.style.left = e.clientX + "px";
      heart.style.top = e.clientY + "px";
      heart.style.transform = "translate(-50%, -50%) scale(0)";
      heart.classList.add("pop");
    }
    // Trigger like
    const btn = document.querySelector(`[data-action="like"][data-reel-id="${reelId}"]`);
    if (btn) handleLike(btn, reelId);
  }

  // ── Share Drawer ──
  function openShareDrawer(reelId) {
    const existing = document.getElementById("nv-share-drawer");
    if (existing) existing.remove();
    const backdrop = document.createElement("div");
    backdrop.className = "nv-comment-drawer-backdrop";
    backdrop.id = "nv-share-backdrop";
    backdrop.addEventListener("click", closeShareDrawer);
    document.body.appendChild(backdrop);

    const drawer = document.createElement("div");
    drawer.className = "nv-share-drawer";
    drawer.id = "nv-share-drawer";
    drawer.innerHTML = `
      <div class="nv-comment-drawer-header">
        <span>Share</span>
        <button class="nv-drawer-close" onclick="closeShareDrawer()">&times;</button>
      </div>
      <div class="nv-share-grid">
        <button class="nv-share-option" data-share="link" data-reel-id="${reelId}">
          <div class="nv-share-icon"><i class="fas fa-link"></i></div>
          <span>Copy Link</span>
        </button>
        <button class="nv-share-option" data-share="dm" data-reel-id="${reelId}">
          <div class="nv-share-icon"><i class="fas fa-paper-plane"></i></div>
          <span>Send</span>
        </button>
        <button class="nv-share-option" data-share="native" data-reel-id="${reelId}">
          <div class="nv-share-icon"><i class="fas fa-share-alt"></i></div>
          <span>Share</span>
        </button>
      </div>
    `;
    document.body.appendChild(drawer);
    setTimeout(() => {
      backdrop.classList.add("open");
      drawer.classList.add("open");
    }, 10);

    drawer.addEventListener("click", async (e) => {
      const opt = e.target.closest("[data-share]");
      if (!opt) return;
      const rId = opt.dataset.reelId;
      const type = opt.dataset.share;
      const url = `${window.location.origin}${safeReelUrl(rId)}`;
      if (type === "link") {
        try {
          await navigator.clipboard.writeText(url);
          showToast("Link copied!");
        } catch {
          showToast("Copy: " + url);
        }
        trackActivity(rId, "reel_shared", { target: "link" });
        closeShareDrawer();
      } else if (type === "native") {
        if (navigator.share) {
          try {
            await navigator.share({ url, title: "Check this reel" });
            trackActivity(rId, "reel_shared", { target: "native" });
          } catch {}
        } else {
          try {
            await navigator.clipboard.writeText(url);
            showToast("Link copied!");
            trackActivity(rId, "reel_shared", { target: "link" });
          } catch {}
        }
        closeShareDrawer();
      } else if (type === "dm") {
        // DM share redirects to messages
        window.location.href = `/messages?share=${rId}`;
        trackActivity(rId, "reel_shared", { target: "dm" });
      }
    });
  }

  window.closeShareDrawer = function () {
    const drawer = document.getElementById("nv-share-drawer");
    const backdrop = document.getElementById("nv-share-backdrop");
    if (drawer) { drawer.classList.remove("open"); setTimeout(() => drawer.remove(), 300); }
    if (backdrop) { backdrop.classList.remove("open"); setTimeout(() => backdrop.remove(), 300); }
  };

  // ── Comment Drawer ──
  async function openCommentDrawer(reelId) {
    const existing = document.getElementById("nv-comment-drawer");
    if (existing) existing.remove();
    const backdrop = document.createElement("div");
    backdrop.className = "nv-comment-drawer-backdrop";
    backdrop.id = "nv-comment-backdrop";
    backdrop.addEventListener("click", closeCommentDrawer);
    document.body.appendChild(backdrop);

    const drawer = document.createElement("div");
    drawer.className = "nv-comment-drawer";
    drawer.id = "nv-comment-drawer";
    drawer.innerHTML = `
      <div class="nv-comment-drawer-header">
        <span>Comments</span>
        <button class="nv-drawer-close" onclick="closeCommentDrawer()">&times;</button>
      </div>
      <div class="nv-comment-list" id="nv-comment-list"><div style="text-align:center;color:#999;padding:20px">Loading...</div></div>
      <form class="nv-comment-form" id="nv-comment-form">
        <input class="nv-comment-input" placeholder="Add a comment..." maxlength="500" required>
        <button class="nv-comment-submit" type="submit">Post</button>
      </form>
    `;
    document.body.appendChild(drawer);
    setTimeout(() => {
      backdrop.classList.add("open");
      drawer.classList.add("open");
    }, 10);

    // Load comments
    try {
      const res = await fetch(`/reels/api/reels/${reelId}/comments`);
      const data = await res.json();
      const list = document.getElementById("nv-comment-list");
      const comments = data.comments || [];
      if (comments.length === 0) {
        list.innerHTML = '<div style="text-align:center;color:#999;padding:20px">No comments yet</div>';
      } else {
        list.innerHTML = comments.map(c => `
          <div class="nv-comment-item">
            <img class="nv-comment-avatar" src="${escapeHtml(c.avatar_url || '')}" alt="" onerror="this.src='/static/img/default-avatar.png'">
            <div class="nv-comment-body">
              <div class="nv-comment-username">${escapeHtml(c.username || c.display_name || '')}</div>
              <div class="nv-comment-text">${escapeHtml(c.body || '')}</div>
              <div class="nv-comment-time">${timeAgo(c.created_at)}</div>
            </div>
          </div>
        `).join('');
      }
    } catch {
      document.getElementById("nv-comment-list").innerHTML = '<div style="text-align:center;color:#999;padding:20px">Failed to load comments</div>';
    }

    // Submit comment
    document.getElementById("nv-comment-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = e.target.querySelector(".nv-comment-input");
      const body = input.value.trim();
      if (!body) return;
      const btn = e.target.querySelector(".nv-comment-submit");
      btn.disabled = true;
      try {
        const res = await fetch(`/reels/api/reels/${reelId}/comment`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body }),
        });
        const result = await res.json();
        if (result.success || result.ok) {
          input.value = "";
          trackActivity(reelId, "reel_commented");
          // Reload comments
          openCommentDrawer(reelId);
        }
      } catch {}
      btn.disabled = false;
    });
  }

  window.closeCommentDrawer = function () {
    const drawer = document.getElementById("nv-comment-drawer");
    const backdrop = document.getElementById("nv-comment-backdrop");
    if (drawer) { drawer.classList.remove("open"); setTimeout(() => drawer.remove(), 300); }
    if (backdrop) { backdrop.classList.remove("open"); setTimeout(() => backdrop.remove(), 300); }
  };

  // ── Activity Tracking ──
  function trackActivity(reelId, verb, extra) {
    const payload = { verb, reel_id: reelId, ts: Date.now() };
    if (extra) Object.assign(payload, extra);
    navigator.sendBeacon && navigator.sendBeacon("/reels/api/track", JSON.stringify(payload));
  }

  // ── Toast ──
  function showToast(msg) {
    const t = document.createElement("div");
    t.style.cssText = "position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.8);color:#fff;padding:10px 24px;border-radius:20px;font-size:14px;z-index:200;white-space:nowrap";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2000);
  }

  // ── Skeleton ──
  function showSkeleton() {
    if (!state.viewport) return;
    for (let i = 0; i < 3; i++) {
      const skel = document.createElement("div");
      skel.className = "nv-reel-slide";
      skel.innerHTML = '<div class="nv-reel-skeleton" style="height:100dvh"><div style="color:#333;font-size:14px">Loading...</div></div>';
      skel.id = "nv-skel-" + i;
      state.viewport.appendChild(skel);
    }
  }

  function hideSkeleton() {
    document.querySelectorAll('[id^="nv-skel-"]').forEach(el => el.remove());
  }

  function showError() {
    if (!state.viewport) return;
    state.viewport.innerHTML = `
      <div class="nv-reel-slide">
        <div style="color:#fff;text-align:center;padding:40px">
          <div style="font-size:48px;margin-bottom:16px">&#9888;</div>
          <p>Something went wrong</p>
          <button onclick="location.reload()" style="margin-top:16px;padding:10px 32px;border:none;border-radius:20px;background:#fff;color:#000;font-weight:600;cursor:pointer">Retry</button>
        </div>
      </div>
    `;
  }

  // ── Utils ──
  function formatCount(n) {
    if (!n) return "0";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(n);
  }

  function timeAgo(dateStr) {
    if (!dateStr) return "";
    const now = Date.now();
    const d = new Date(dateStr);
    const diff = (now - d.getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + "m";
    if (diff < 86400) return Math.floor(diff / 3600) + "h";
    return Math.floor(diff / 86400) + "d";
  }

  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Export ──
  window.NamVibeReelsEngine = { init, loadReels, playCurrent, toggleMute, scrollTo };

  // Auto-init
  if (document.getElementById("nv-reels-viewport")) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }
})();
