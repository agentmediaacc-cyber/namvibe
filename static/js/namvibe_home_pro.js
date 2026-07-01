(function () {
  "use strict";

  function logRuntimeGuard(scope, error) {
    var message = error && error.message ? error.message : String(error);
    console.error("[nvpro-homepage:" + scope + "]", message);
    if (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost") {
      console.error(error);
    }
  }

  if (!document.getElementById("nvpro-feed") && !document.querySelector(".nvpro-tab, .nvpro-post-card, .nvpro-header")) {
    return;
  }

  var csrfToken = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };
  var toastEl = document.getElementById("nvpro-toast");

  // Offline support
  var isOnline = navigator.onLine;
  var offlineBanner = document.getElementById("nvpro-offline-banner");
  function updateOfflineBanner(online) {
    isOnline = online;
    if (offlineBanner) {
      offlineBanner.classList.toggle("is-offline", !online);
      offlineBanner.querySelector(".nvpro-offline-text").textContent =
        online ? "Back online — refreshing…" : "You are offline — showing cached content";
    }
    document.querySelectorAll("[data-open-upload], [data-open-camera]").forEach(function (b) {
      b.disabled = !online;
      b.title = online ? "" : "Upload unavailable while offline";
    });
    if (online && offlineBanner && offlineBanner.classList.contains("is-offline")) {
      setTimeout(function () {
        offlineBanner.classList.remove("is-offline");
        window.location.reload();
      }, 1500);
    }
  }
  window.addEventListener("offline", function () { updateOfflineBanner(false); });
  window.addEventListener("online", function () {
    updateOfflineBanner(true);
  });

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-visible");
    setTimeout(function () { toastEl.classList.remove("is-visible"); }, 2500);
  }

  var likeErrorLogged = false;

  /* ── Phase 168: Real-time badge updates via Socket.IO ── */
  function initRealtimeHooks() {
    if (window.NamVibeRealtime && window.NamVibeRealtime.isConnected()) {
      window.NamVibeRealtime.on("notification:new", function (data) {
        var badge = document.getElementById("nvpro-notif-badge");
        if (badge) {
          var c = parseInt(badge.textContent, 10) || 0;
          badge.textContent = c + 1;
          badge.classList.add("nvpro-badge-pulse");
          setTimeout(function () { badge.classList.remove("nvpro-badge-pulse"); }, 600);
        }
      });
      window.NamVibeRealtime.on("chat:message", function (data) {
        var badge = document.getElementById("nvpro-msg-badge");
        if (badge) {
          var c = parseInt(badge.textContent, 10) || 0;
          badge.textContent = c + 1;
          badge.classList.add("nvpro-badge-pulse");
          setTimeout(function () { badge.classList.remove("nvpro-badge-pulse"); }, 600);
        }
      });
      return true;
    }
    return false;
  }

  /* ── Phase 168: Polling with exponential backoff for feed refresh ── */
  var pollDelay = 30000;
  var pollMaxDelay = 120000;
  var pollTimer = null;
  var pollFailCount = 0;

  function startFeedPolling() {
    if (pollTimer) return;
    function poll() {
      fetch("/api/feed/check?t=" + Date.now(), {
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrfToken() }
      })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          pollFailCount = 0;
          if (data && data.has_new) {
            if (window.NamVibeToast) {
              window.NamVibeToast.info("New posts available — scroll to refresh");
            }
          }
          pollDelay = Math.min(pollDelay, pollMaxDelay);
          pollTimer = setTimeout(poll, pollDelay);
        })
        .catch(function () {
          pollFailCount++;
          pollDelay = Math.min(pollDelay * 1.5, pollMaxDelay);
          pollTimer = setTimeout(poll, pollDelay);
        });
    }
    pollTimer = setTimeout(poll, pollDelay);
  }

  function stopFeedPolling() {
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
  }

  /* ── Phase 168: Pull-to-refresh for mobile ── */
  function setupPullToRefresh() {
    var feedEl = document.getElementById("nvpro-feed");
    if (!feedEl) return;
    var startY = 0;
    var pulling = false;
    var ptrEl = document.createElement("div");
    ptrEl.className = "nvpro-ptr";
    ptrEl.innerHTML = '<div class="nvpro-ptr-indicator"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg><span>Pull to refresh</span></div>';
    feedEl.parentNode.insertBefore(ptrEl, feedEl);
    feedEl.addEventListener("touchstart", function (e) {
      if (feedEl.scrollTop <= 0) {
        startY = e.touches[0].clientY;
        pulling = true;
      }
    }, { passive: true });
    feedEl.addEventListener("touchmove", function (e) {
      if (!pulling) return;
      var dy = e.touches[0].clientY - startY;
      if (dy > 0) {
        ptrEl.style.transform = "translateY(" + Math.min(dy * 0.4, 80) + "px)";
        ptrEl.classList.toggle("nvpro-ptr-ready", dy > 60);
      }
    }, { passive: true });
    feedEl.addEventListener("touchend", function () {
      if (!pulling) return;
      pulling = false;
      if (ptrEl.classList.contains("nvpro-ptr-ready")) {
        ptrEl.classList.add("nvpro-ptr-refreshing");
        ptrEl.querySelector("span").textContent = "Refreshing…";
        window.location.reload();
      } else {
        ptrEl.style.transform = "";
      }
    }, { passive: true });
  }

  /* ── Phase 168: Escape key closes modals ── */
  function setupEscapeKey() {
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      document.querySelectorAll(".nvpro-modal-overlay.is-open, .nvpro-upload-modal.is-open").forEach(function (m) {
        m.classList.remove("is-open");
        m.classList.remove("show");
        m.style.display = "none";
      });
      document.body.classList.remove("nvpro-modal-open");
    });
  }

  /* ── Phase 168: Basic focus trap for upload modal ── */
  function setupFocusTrap() {
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Tab") return;
      var modal = document.querySelector(".nvpro-upload-modal.is-open, .nvpro-modal-overlay.is-open");
      if (!modal) return;
      var focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  /* ── Phase 168: Upload progress animation integration ── */
  function patchUploadProgress() {
    var origXhr = window.XMLHttpRequest;
    if (!origXhr) return;
    var open = origXhr.prototype.open;
    origXhr.prototype.open = function () {
      this._uploadUrl = arguments[1] || "";
      return open.apply(this, arguments);
    };
  }

  function apiFetch(url, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    headers["X-CSRFToken"] = csrfToken();
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    opts.headers = headers;
    opts.credentials = "same-origin";
    return fetch(url, opts).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    var d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function profileHref(username) {
    return username ? "/profile/@" + encodeURIComponent(username) : "/profile/";
  }

  /* ── SVG ICONS ── */
  var ICONS = {
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>',
    discover: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><path d="M12 2v4m0 12v4m10-10h-4M6 12H2"/></svg>',
    live: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>',
    reels: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
    stories: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><path d="M12 6v6l4 2"/></svg>',
    inbox: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/></svg>',
    contacts: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87m-8-12a4 4 0 010 7.75"/></svg>',
    calls: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>',
    dating: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>',
    wallet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/><circle cx="18" cy="14" r="1"/></svg>',
    profile: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    signout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
    signin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>',
    like: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14zM7 22H4a2 2 0 01-2-2v-7a2 2 0 012-2h3"/></svg>',
    comment: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
    share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>',
    save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>',
    more: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>',
    follow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>',
    camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>',
    video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>',
    envelope: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
    heart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    feedback: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
    film: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    newpost: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14m-7-7h14"/></svg>',
  };

  function icon(name) { return ICONS[name] || ""; }

  function setIcon(el, name) {
    if (!el) return;
    el.innerHTML = icon(name);
  }

  /* ── Replace all FontAwesome with SVG icons ── */
  function replaceFaIcons() {
    var map = {
      "fa-home": "home", "fa-compass": "discover", "fa-video": "live", "fa-film": "film",
      "fa-circle-notch": "stories", "fa-inbox": "inbox", "fa-address-book": "contacts",
      "fa-phone": "calls", "fa-heart": "heart", "fa-wallet": "wallet", "fa-user-circle": "profile",
      "fa-user": "profile", "fa-sign-out-alt": "signout", "fa-sign-in-alt": "signin",
      "fa-search": "search", "fa-bell": "bell", "fa-envelope": "envelope",
      "fa-plus": "plus", "fa-newspaper": "newpost", "fa-shield-alt": "shield",
      "fa-comment-dots": "feedback", "fa-play": "play", "fa-pause": "pause",
      "fa-heart": "like", "fa-comment": "comment", "fa-share-square": "share",
      "fa-bookmark": "save", "fa-ellipsis-h": "more", "fa-times": "close",
      "fa-check": "check", "fa-exclamation-circle": "alert",
    };
    document.querySelectorAll("i[class]").forEach(function (el) {
      var cls = Array.from(el.classList).find(function (c) { return map[c]; });
      if (cls) {
        var name = map[cls];
        el.outerHTML = '<span class="nv-icon-wrap">' + icon(name) + "</span>";
      }
    });
  }

  /* ── Skeleton ── */
  function showSkeleton(feedEl) {
    if (!feedEl) return;
    var html = "";
    for (var i = 0; i < 3; i++) {
      html += '<div class="nvpro-skeleton nvpro-skeleton-card"></div>';
    }
    feedEl.innerHTML = html;
  }

  function renderEmpty(feedEl) {
    if (!feedEl) return;
    feedEl.innerHTML =
      '<div class="nvpro-empty-card">' +
      icon("newpost") +
      '<h3>Fresh posts will land here</h3>' +
      '<p>Follow creators, watch reels, join live rooms, or share your first post.</p>' +
      '<div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">' +
      '<a href="/discover/" class="nvpro-btn nvpro-btn-primary">' + icon("discover") + ' Discover Creators</a>' +
      '<a href="/reels/" class="nvpro-btn nvpro-btn-outline">' + icon("film") + ' Watch Reels</a>' +
      "</div></div>";
  }

  function renderFeedItems(feedEl, items) {
    if (!feedEl) return;
    if (!items || items.length === 0) { renderEmpty(feedEl); return; }
    feedEl.innerHTML = "";
    var html = "";
    items.forEach(function (item, index) {
      var text = item.text || item.caption || "";
      var mediaUrl = item.media_url || item.public_url || item.image_url || item.thumbnail_url || "";
      var videoUrl = item.video_url || "";
      var thumbnail = item.thumbnail_url || mediaUrl || videoUrl || "";
      var avatar = item.avatar_url || "";
      var displayName = item.display_name || item.username || "Creator";
      var username = item.username || "";
      var initial = displayName.charAt(0).toUpperCase();
      var verified = item.verified ? '<svg class="nv-icon-sm nvpro-verified" viewBox="0 0 24 24" fill="currentColor"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' : "";
      var vAttr = item.type || "post";
      var isVideo = videoUrl || item.is_video || item.media_type === "video" || item.media_type === "reel" || (item.mime_type && item.mime_type.indexOf("video/") === 0) || (item.post_type === "video");
      var vidHtml = "";
      if (isVideo && videoUrl) {
        vidHtml = '<div class="nvpro-post-media" data-nv-video="' + escapeHtml(videoUrl) + '" data-nv-thumb="' + escapeHtml(thumbnail) + '">' +
          '<div class="nvpro-loading-skeleton"></div>' +
          '<div class="nvpro-video-overlay"><div class="nvpro-video-play-icon">' + icon("play") + "</div></div></div>";
      } else if (mediaUrl) {
        var loadMode = index < 3 ? "eager" : "lazy";
        vidHtml = '<div class="nvpro-post-media"><img src="' + escapeHtml(mediaUrl) + '" alt="' + escapeHtml(text) + '" loading="' + loadMode + '" class="nvpro-post-media"></div>';
      }
      html += '<article class="nvpro-post-card" data-item-id="' + (item.id || "") + '" data-type="' + vAttr + '" data-href="/post/' + (item.id || "") + '" style="cursor:pointer">';
      html += '<div class="nvpro-post-head">';
      html += '<a href="' + profileHref(username) + '" class="nvpro-post-avatar">';
      if (avatar) {
        html += '<img src="' + escapeHtml(avatar) + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">';
        html += '<span class="nvpro-avatar-initials" style="display:none">' + initial + "</span>";
      } else {
        html += '<span class="nvpro-avatar-initials">' + initial + "</span>";
      }
      html += "</a>";
      html += '<div class="nvpro-post-meta">';
      html += '<a href="' + profileHref(username) + '" class="nvpro-post-author">' + escapeHtml(displayName) + verified + "</a>";
      html += '<span class="nvpro-post-time">' + (item.created_label || "Just now") + "</span>";
      html += "</div>";
      if (item.profile_id) {
        html += '<button type="button" class="nvpro-follow-pill" data-follow-id="' + item.profile_id + '">Follow</button>';
      }
      html += "</div>";
      if (text) html += '<div class="nvpro-post-body">' + escapeHtml(text) + "</div>";
      html += vidHtml;
      html += '<div class="nvpro-post-actions">';
      html += '<button type="button" class="nvpro-action-btn" data-action="like" data-id="' + (item.id || "") + '" data-type="' + vAttr + '">' + icon("heart") + " <span>" + (item.likes_count || 0) + "</span></button>";
      html += '<button type="button" class="nvpro-action-btn" data-action="comment" data-id="' + (item.id || "") + '">' + icon("comment") + " <span>" + (item.comments_count || 0) + "</span></button>";
      html += '<button type="button" class="nvpro-action-btn" data-action="share" data-id="' + (item.id || "") + '">' + icon("share") + " <span>Share</span></button>";
      html += '<button type="button" class="nvpro-action-btn" data-action="save" data-id="' + (item.id || "") + '" data-type="' + vAttr + '">' + icon("save") + "</button>";
      html += "</div>";
      html += "</article>";
    });
    feedEl.innerHTML = html;
    // Lazy-load videos after rendering
    lazyLoadVideos();
  }

  /* ── Tab switching ── */
  var tabs = document.querySelectorAll(".nvpro-tab");
  var activeTab = "for_you";

  function switchTab(tab) {
    if (tab === activeTab) return;
    activeTab = tab;
    tabs.forEach(function (t) { t.classList.toggle("is-active", t.dataset.tab === tab); });
    showSkeleton(feedEl);
    fetchFeed(tab);
  }

  tabs.forEach(function (t) {
    t.addEventListener("click", function () { switchTab(t.dataset.tab); });
  });

  function fetchFeed(tab) {
    var url = tab === "for_you" ? "/api/feed?limit=20" : "/api/homepage/feed?tab=" + encodeURIComponent(tab) + "&limit=20";
    apiFetch(url)
      .then(function (data) {
        if (data.ok && data.payload) {
          var items = tab === "for_you" ? (data.payload.feed_items || []).concat(data.payload.reels || []) : (data.payload.feed_items || []);
          nextCursor = data.payload.next_cursor || null;
          hasMoreFeed = typeof data.payload.has_more === "boolean" ? data.payload.has_more : true;
          if (window.NamVibeCache) { window.NamVibeCache.saveFeed(data.payload); } else { try { localStorage.setItem("namvibe_feed_cache", JSON.stringify(data.payload)); } catch(e) {} }
          if (items.length) {
            renderFeedItems(feedEl, items);
            return;
          }
        }
        if (data.ok && data.payload && data.payload.feed_items) {
          renderFeedItems(feedEl, data.payload.feed_items);
        } else {
          renderEmpty(feedEl);
        }
      })
      .catch(function () {
        function tryCachedData(cached) {
          if (cached) {
            var citems = tab === "for_you" ? (cached.feed_items || []).concat(cached.reels || []) : (cached.feed_items || []);
            if (citems.length) { renderFeedItems(feedEl, citems); return true; }
          }
          return false;
        }
        if (window.NamVibeCache) {
          window.NamVibeCache.loadFeed().then(function (cached) { if (!tryCachedData(cached)) renderEmpty(feedEl); });
        } else {
          try { var cached = localStorage.getItem("namvibe_feed_cache"); if (cached) { var cp = JSON.parse(cached); if (tryCachedData(cp)) return; } } catch(e) {}
          renderEmpty(feedEl);
        }
      });
  }

  /* ── VIEW TRACKING ── */
  var viewedReels = {};
  var viewTimers = {};
  var viewBatchQueue = [];
  var viewBatchTimer = null;

  function trackReelView(reelId) {
    if (!reelId) return;
    if (viewedReels[reelId]) return;
    viewedReels[reelId] = true;
    viewBatchQueue.push(reelId);
    scheduleViewFlush();
  }

  function scheduleViewFlush() {
    if (viewBatchTimer) return;
    viewBatchTimer = setTimeout(function () {
      viewBatchTimer = null;
      flushViewBatch();
    }, 5000);
  }

  function flushViewBatch() {
    var batch = viewBatchQueue.slice();
    viewBatchQueue = [];
    if (batch.length === 0) return;
    var payload = JSON.stringify({ reel_ids: batch });
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/reels/api/reels/view/batch", payload);
    } else {
      fetch("/reels/api/reels/view/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      }).catch(function () {});
    }
  }

  function startViewTimer(reelId) {
    if (!reelId) return;
    if (viewTimers[reelId]) return;
    viewTimers[reelId] = setTimeout(function () {
      trackReelView(reelId);
    }, 2000);
  }

  function cancelViewTimer(reelId) {
    if (viewTimers[reelId]) {
      clearTimeout(viewTimers[reelId]);
      delete viewTimers[reelId];
    }
  }

  /* ── INTERSECTION OBSERVER — REELS / VIDEO AUTOPLAY ── */
  var videoObserver = null;

  function setupVideoObserver() {
    if (!window.IntersectionObserver) return;
    videoObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var el = entry.target;
        var vid = el.tagName === "VIDEO" ? el : el.querySelector("video");
        if (!vid) return;
        var reelId = el.dataset.reelId || el.closest("[data-item-id]") && el.closest("[data-item-id]").dataset.itemId;
        if (entry.intersectionRatio >= 0.65) {
          // Pause all other videos
          document.querySelectorAll("video[data-nv-video-active]").forEach(function (v) {
            if (v !== vid) {
              v.pause();
              v.removeAttribute("data-nv-video-active");
              var parent = v.closest("[data-nv-video]") || v.parentElement;
              if (parent) {
                var overlay = parent.querySelector(".nvpro-video-overlay");
                if (overlay) overlay.classList.remove("is-hidden");
              }
            }
          });
          vid.muted = true;
          vid.playsInline = true;
          vid.setAttribute("data-nv-video-active", "1");
          vid.play().catch(function () {});
          var overlay = el.querySelector(".nvpro-video-overlay");
          if (overlay) overlay.classList.add("is-hidden");
          // Preload next 3 videos
          preloadNearbyVideos(el, 3);
          // Start 2s view timer when video becomes visible
          startViewTimer(reelId);
        } else {
          vid.pause();
          vid.removeAttribute("data-nv-video-active");
          var overlay = el.querySelector(".nvpro-video-overlay");
          if (overlay && !vid.played.length) overlay.classList.remove("is-hidden");
          // Cancel view timer when video leaves viewport
          cancelViewTimer(reelId);
        }
      });
    }, { threshold: [0.65] });

    // Observe all video containers
    document.querySelectorAll("[data-nv-video]").forEach(function (el) {
      videoObserver.observe(el);
      el.setAttribute("data-nv-obs", "1");
    });
  }

  // Watch for new video elements added dynamically
  var mutationObserver = new MutationObserver(function () {
    if (videoObserver) {
      document.querySelectorAll("[data-nv-video]:not([data-nv-obs])").forEach(function (el) {
        el.setAttribute("data-nv-obs", "1");
        videoObserver.observe(el);
      });
    }
  });
  if (document.body) mutationObserver.observe(document.body, { childList: true, subtree: true });

  /* ── Preload nearby videos — start loading next N without autoplay ── */
  function preloadNearbyVideos(currentEl, count) {
    var all = document.querySelectorAll("[data-nv-video]");
    var idx = -1;
    all.forEach(function (el, i) { if (el === currentEl) idx = i; });
    if (idx < 0) return;
    for (var i = idx + 1; i <= idx + count && i < all.length; i++) {
      var next = all[i];
      if (next.getAttribute("data-nv-preload") === "1") continue;
      next.setAttribute("data-nv-preload", "1");
      var src = next.dataset.nvVideo;
      if (!src) continue;
      var link = document.createElement("link");
      link.rel = "preload";
      link.as = "video";
      link.href = src;
      document.head.appendChild(link);
    }
  }

  /* ── Lazy-load videos — replace skeleton with actual video ── */
  function lazyLoadVideos() {
    document.querySelectorAll("[data-nv-video]:not([data-nv-loaded])").forEach(function (el) {
      var src = el.dataset.nvVideo;
      var thumb = el.dataset.nvThumb || "";
      if (!src) return;
      el.setAttribute("data-nv-loaded", "1");
      var skeleton = el.querySelector(".nvpro-loading-skeleton");
      var video = document.createElement("video");
      video.src = src;
      video.muted = true;
      video.playsInline = true;
      video.preload = "metadata";
      video.className = "nvpro-video-preview";
      video.setAttribute("data-nv-video-active", "");
      video.style.width = "100%";
      video.style.display = "block";
      if (thumb) video.poster = thumb;
      video.addEventListener("loadedmetadata", function () {
        if (skeleton) skeleton.remove();
      });
      video.addEventListener("error", function () {
        if (skeleton) {
          skeleton.outerHTML = '<div class="nvpro-post-media" style="padding:20px;text-align:center;color:var(--nvpro-muted)">Video unavailable</div>';
        }
      });
      el.insertBefore(video, skeleton);
      // Show play overlay initially
      var overlay = el.querySelector(".nvpro-video-overlay");
      if (overlay) overlay.classList.remove("is-hidden");
    });
  }

  /* ── Video tap to toggle play/pause ── */
  document.addEventListener("click", function (e) {
    var media = e.target.closest("[data-nv-video]");
    if (!media) return;
    var vid = media.querySelector("video");
    if (!vid) return;
    if (vid.paused) {
      vid.play().catch(function () {});
      var overlay = media.querySelector(".nvpro-video-overlay");
      if (overlay) overlay.classList.add("is-hidden");
    } else {
      vid.pause();
      var overlay = media.querySelector(".nvpro-video-overlay");
      if (overlay) overlay.classList.remove("is-hidden");
    }
  });

  /* ── Double-tap like on videos ── */
  var lastVideoTap = 0;
  document.addEventListener("click", function (e) {
    var media = e.target.closest("[data-nv-video]");
    if (!media) return;
    var now = Date.now();
    if (now - lastVideoTap < 400) {
      // Double tap
      var heart = document.createElement("span");
      heart.className = "nvpro-double-tap-heart";
      heart.innerHTML = icon("heart");
      media.appendChild(heart);
      setTimeout(function () { heart.remove(); }, 700);
    }
    lastVideoTap = now;
  });

  /* ── Upload Modal ── */
  function initUploadModal() {
    var overlay = document.getElementById("nvpro-upload-modal");
    var openBtns = document.querySelectorAll("[data-open-upload]");
    var closeBtn = overlay ? overlay.querySelector(".nvpro-modal-close") : null;
    if (!overlay) return;

    openBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        overlay.classList.add("is-open");
        var tab = btn.dataset.openUpload || "post";
        switchUploadTab(tab);
      });
    });

    if (closeBtn) {
      closeBtn.addEventListener("click", function () { overlay.classList.remove("is-open"); });
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.classList.remove("is-open");
    });

    // Tab switching
    var tabBtns = overlay.querySelectorAll(".nvpro-modal-tab");
    var tabPanes = {
      post: document.getElementById("nvpro-upload-post"),
      reel: document.getElementById("nvpro-upload-reel"),
      story: document.getElementById("nvpro-upload-story"),
    };

    function switchUploadTab(tab) {
      tabBtns.forEach(function (t) { t.classList.toggle("is-active", t.dataset.uploadTab === tab); });
      Object.keys(tabPanes).forEach(function (k) {
        if (tabPanes[k]) tabPanes[k].style.display = k === tab ? "flex" : "none";
      });
      // Reset file previews
      window.resetPreview(tab);
    }

    window.switchUploadTab = switchUploadTab;

    tabBtns.forEach(function (t) {
      t.addEventListener("click", function () { switchUploadTab(t.dataset.uploadTab); });
    });

    // File drop zones
    window.__resetPreviewFns = {};
    ["post", "reel", "story"].forEach(function (type) {
      initDropZone(type);
    });
    window.resetPreview = function (t) {
      if (window.__resetPreviewFns[t]) window.__resetPreviewFns[t]();
    };

    // Cancel buttons
    overlay.querySelectorAll("[data-cancel-upload]").forEach(function (btn) {
      btn.addEventListener("click", function () { overlay.classList.remove("is-open"); });
    });
  }

  var UPLOAD_RULES = {
    post: { maxDuration: 600, maxSize: 700, accept: "video/mp4,video/webm,video/mov,image/jpeg,image/jpg,image/png,image/webp", label: "Post", types: ["video", "image"] },
    reel: { maxDuration: 90, maxSize: 250, accept: "video/mp4,video/webm,video/mov", label: "Reel", types: ["video"] },
    story: { maxDuration: 120, maxSize: 100, accept: "video/mp4,video/webm,video/mov,image/jpeg,image/jpg,image/png,image/webp", label: "Story", types: ["video", "image"] },
  };

  function initDropZone(type) {
    var rules = UPLOAD_RULES[type];
    if (!rules) return;
    var zone = document.getElementById("nvpro-drop-" + type);
    var input = document.getElementById("nvpro-file-" + type);
    var preview = document.getElementById("nvpro-preview-" + type);
    var result = document.getElementById("nvpro-result-" + type);
    var progress = document.getElementById("nvpro-progress-" + type);
    var submitBtn = document.getElementById("nvpro-submit-" + type);
    if (!zone || !input) return;

    function resetPreview() {
      if (preview) { preview.innerHTML = ""; preview.style.display = "none"; }
      if (result) { result.classList.remove("is-visible", "is-success", "is-error"); result.style.display = "none"; }
      if (progress) { progress.classList.remove("is-active"); var fill = progress.querySelector(".nvpro-progress-fill"); if (fill) fill.style.width = "0%"; }
      if (submitBtn) submitBtn.disabled = false;
      zone.style.display = "block";
    }

    window.__resetPreviewFns[type] = resetPreview;

    function showError(msg) {
      if (result) {
        result.className = "nvpro-upload-result is-visible is-error";
        result.style.display = "flex";
        result.innerHTML =
          icon("alert") +
          '<h3>Upload failed</h3>' +
          "<p>" + escapeHtml(msg) + "</p>" +
          '<button type="button" class="nvpro-btn nvpro-btn-outline nvpro-btn-sm" onclick="resetPreview(\'' + type + '\')">Try again</button>';
      }
    }

    function showSuccess(url) {
      if (result) {
        result.className = "nvpro-upload-result is-visible is-success";
        result.style.display = "flex";
        result.innerHTML =
          icon("check") +
          '<h3>' + rules.label + ' uploaded!</h3>' +
          '<p>Your ' + rules.label.toLowerCase() + ' is now live.</p>' +
          '<a href="' + escapeHtml(url || "/") + '" class="nvpro-btn nvpro-btn-primary">View</a>';
      }
    }

    function validateFile(file) {
      var ext = file.name.split(".").pop().toLowerCase();
      var validExts = ["mp4", "webm", "mov", "jpg", "jpeg", "png", "webp"];
      if (!validExts.includes(ext)) {
        showError("Unsupported file format. Use mp4, webm, mov, jpg, png, or webp.");
        return false;
      }
      var isVideo = file.type.startsWith("video/");
      var maxSize = rules.maxSize * 1024 * 1024;
      if (file.size > maxSize) {
        showError(rules.label + " must be under " + rules.maxSize + "MB.");
        return false;
      }
      if (isVideo && rules.maxDuration < 600) {
        // Validate video duration via metadata
        var videoEl = document.createElement("video");
        videoEl.preload = "metadata";
        var url = URL.createObjectURL(file);
        videoEl.src = url;
        return new Promise(function (resolve) {
          videoEl.onloadedmetadata = function () {
            URL.revokeObjectURL(url);
            var dur = videoEl.duration;
            if (dur > rules.maxDuration) {
              var msg = rules.label + "s must be " + rules.maxDuration + " seconds or less.";
              showError(msg);
              resolve(false);
            } else {
              resolve(true);
            }
          };
          videoEl.onerror = function () { URL.revokeObjectURL(url); resolve(true); };
          setTimeout(function () { resolve(true); }, 3000);
        });
      }
      return true;
    }

    function previewFile(file) {
      var reader = new FileReader();
      reader.onload = function (e) {
        if (!preview) return;
        preview.style.display = "block";
        preview.innerHTML = "";
        var isVideo = file.type.startsWith("video/");
        var el = isVideo
          ? '<video src="' + e.target.result + '" muted playsinline preload="metadata" style="width:100%;max-height:200px;border-radius:8px"></video>'
          : '<img src="' + e.target.result + '" alt="" style="width:100%;max-height:200px;border-radius:8px;object-fit:contain">';
        preview.innerHTML = el +
          '<button type="button" class="nvpro-preview-remove" onclick="var z=document.getElementById(\'nvpro-drop-' + type + '\');var inp=document.getElementById(\'nvpro-file-' + type + '\');inp.value=\'\';z.style.display=\'block\';this.parentElement.style.display=\'none\'">' +
          icon("close") + "</button>";
        zone.style.display = "none";
      };
      reader.readAsDataURL(file);
    }

    // Click to open file picker
    zone.addEventListener("click", function () { input.click(); });
    zone.addEventListener("dragover", function (e) { e.preventDefault(); zone.classList.add("is-dragover"); });
    zone.addEventListener("dragleave", function () { zone.classList.remove("is-dragover"); });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      zone.classList.remove("is-dragover");
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        handleFile(e.dataTransfer.files[0]);
      }
    });

    input.addEventListener("change", function () {
      if (input.files.length) handleFile(input.files[0]);
    });

    function handleFile(file) {
      if (!file) return;
      var validation = validateFile(file);
      if (validation && validation.then) {
        validation.then(function (ok) {
          if (ok) previewFile(file);
        });
      } else if (validation) {
        previewFile(file);
      }
    }

    // Submit form
    if (submitBtn) {
      submitBtn.addEventListener("click", function () {
        if (!input.files.length) { showError("Please select a file to upload."); return; }
        submitBtn.disabled = true;
        if (progress) progress.classList.add("is-active");

        var fd = new FormData();
        fd.append("media", input.files[0]);
        fd.append("caption", (document.getElementById("nvpro-caption-" + type) || {}).value || "");
        var fileType = input.files[0].type.startsWith("video/") ? "video" : "image";
        fd.append("media_type", fileType);
        var visibility = (document.getElementById("nvpro-visibility-" + type) || {}).value || (type === "story" ? "followers" : "public");
        fd.append("visibility", visibility);
        if (fileType === "video") fd.append("video", input.files[0]);

        // Use new API endpoints
        var uploadUrl = type === "post" ? "/posts/api/posts/create" : type === "reel" ? "/reels/api/reels/create" : "/status/api/status/create";
        var xhr = new XMLHttpRequest();
        xhr.open("POST", uploadUrl, true);
        xhr.setRequestHeader("X-CSRFToken", csrfToken());

        xhr.upload.onprogress = function (e) {
          if (e.lengthComputable && progress) {
            var pct = Math.round((e.loaded / e.total) * 100);
            var fill = progress.querySelector(".nvpro-progress-fill");
            var text = progress.querySelector(".nvpro-progress-text");
            if (fill) fill.style.width = pct + "%";
            if (text) text.textContent = pct + "%";
          }
        };

        xhr.onload = function () {
          if (progress) progress.classList.remove("is-active");
          submitBtn.disabled = false;
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              var resp = JSON.parse(xhr.responseText);
              if (resp.ok) {
                // Show success with the created item's URL
                var mediaPreviewUrl = (resp.story && (resp.story.media_url || resp.story.public_url || resp.story.image_url || resp.story.video_url)) ||
                  (resp.post && (resp.post.media_url || resp.post.public_url || resp.post.image_url || resp.post.video_url)) ||
                  resp.media_url || resp.video_url || "";
                if (mediaPreviewUrl && preview) {
                  preview.style.display = "block";
                  if ((resp.story && resp.story.video_url) || (resp.post && resp.post.video_url) || resp.video_url) {
                    preview.innerHTML = '<video src="' + escapeHtml(mediaPreviewUrl) + '" muted playsinline controls style="width:100%;max-height:200px;border-radius:8px"></video>';
                  } else {
                    preview.innerHTML = '<img src="' + escapeHtml(mediaPreviewUrl) + '" alt="" style="width:100%;max-height:200px;border-radius:8px;object-fit:contain">';
                  }
                }
                var itemUrl = resp.story && resp.story.id ? "/status/" + resp.story.id :
                              resp.post && resp.post.id ? "/post/" + resp.post.id :
                              resp.reel_id ? "/reels/" + resp.reel_id : "/";
                showSuccess(itemUrl);
                // Refresh feed after successful upload
                setTimeout(function() {
                  var feedEl = document.getElementById("nvpro-feed");
                  if (feedEl) {
                    fetchFeed(activeTab);
                  }
                }, 500);
                return;
              }
            } catch (e) {}
            showSuccess("/");
          } else {
            try {
              var err = JSON.parse(xhr.responseText);
              showError(err.error || err.message || "Upload failed. Try again.");
            } catch (e) {
              showError("Upload failed. Try again.");
            }
          }
        };

        xhr.onerror = function () {
          if (progress) progress.classList.remove("is-active");
          submitBtn.disabled = false;
          showError("Network error. Check your connection.");
        };

        xhr.send(fd);
      });
    }
  }

  /* ── Like action (optimistic) ── */
  function _handleLikeResult(btn, data) {
    if (!data || data.success !== true || typeof data.liked !== "boolean") {
      return false;
    }
    btn.classList.toggle("is-liked", data.liked);
    var span = btn.querySelector("span");
    if (span && typeof data.count === "number") span.textContent = data.count;
    showToast(data.liked ? "Liked" : "Unliked");
    return true;
  }

  function _logLikeErrorOnce(error) {
    if (likeErrorLogged) return;
    likeErrorLogged = true;
    console.error("NamVibe like failed", error);
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=like]");
    if (!btn) return;
    var id = btn.dataset.id;
    var type = btn.dataset.type || "post";
    if (!id) return;
    var wasLiked = btn.classList.contains("is-liked");
    var span = btn.querySelector("span");
    var oldCount = span ? parseInt(span.textContent, 10) : 0;
    btn.classList.toggle("is-liked");
    if (span) span.textContent = wasLiked ? Math.max(oldCount - 1, 0) : oldCount + 1;
    var url = "/api/social/" + encodeURIComponent(type) + "/" + encodeURIComponent(id) + "/like";
    apiFetch(url, { method: "POST" })
      .then(function (data) {
        if (!_handleLikeResult(btn, data)) {
          btn.classList.toggle("is-liked", wasLiked);
          if (span) span.textContent = oldCount;
          showToast("Could not like. Try again.");
          _logLikeErrorOnce(data);
        }
      })
      .catch(function () {
        btn.classList.toggle("is-liked", wasLiked);
        if (span) span.textContent = oldCount;
        showToast("Could not like. Try again.");
        _logLikeErrorOnce({ type: type, id: id });
      });
  });

  /* ── Save action ── */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=save]");
    if (!btn) return;
    var id = btn.dataset.id;
    var type = btn.dataset.type || "post";
    if (!id) return;
    var url = type === "reel" ? "/reels/api/reels/" + id + "/save" : "/api/home/post/" + id + "/save";
    apiFetch(url, { method: "POST" })
      .then(function (data) {
        if (data.ok) {
          btn.classList.toggle("is-saved");
          showToast(btn.classList.contains("is-saved") ? "Saved" : "Unsaved");
        }
      })
      .catch(function () { showToast("Could not save. Try again."); });
  });

  /* ── Share action ── */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=share]");
    if (!btn) return;
    var id = btn.dataset.id;
    if (!id) return;
    apiFetch("/api/home/post/" + encodeURIComponent(id) + "/share", { method: "POST" }).catch(function () {});
    var url = window.location.origin + "/post/" + (id || "");
    if (navigator.share) {
      navigator.share({ title: "NamVibe", url: url }).catch(function () {});
    } else {
      navigator.clipboard.writeText(url).then(function () { showToast("Link copied!"); }).catch(function () { showToast("Could not share."); });
    }
  });

  /* ── Comment action ── */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=comment]");
    if (!btn) return;
    var id = btn.dataset.id;
    if (id) window.location.href = "/post/" + id;
  });

  /* ── Follow action ── */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-follow-id]");
    if (!btn) return;
    var profileId = btn.dataset.followId;
    if (!profileId) return;
    var wasFollowing = btn.classList.contains("is-following");
    apiFetch("/api/home/follow/" + profileId, { method: "POST" })
      .then(function (data) {
        if (data.ok) {
          btn.classList.toggle("is-following");
          btn.textContent = btn.classList.contains("is-following") ? "Following" : "Follow";
          showToast(btn.classList.contains("is-following") ? "Followed" : "Unfollowed");
        }
      })
      .catch(function () { showToast("Could not follow. Try again."); });
  });

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    replaceFaIcons();
    initUploadModal();
    setupVideoObserver();
    setupScrollHeader();
    setupHamburgerMenu();
    setupEscapeKey();
    setupFocusTrap();
    patchUploadProgress();
    // Lazy-load initial videos
    setTimeout(lazyLoadVideos, 100);
    // Handle tab-based upload opening
    if (window.location.hash === "#upload") {
      var modal = document.getElementById("nvpro-upload-modal");
      if (modal) modal.classList.add("is-open");
    }
    // Always hydrate from API to ensure freshest content
    hydrateHomepage();
    // Phase 168: Real-time hooks (delayed to let socket connect)
    setTimeout(function () {
      if (!initRealtimeHooks()) {
        var retries = 0;
        var retryInterval = setInterval(function () {
          retries++;
          if (initRealtimeHooks() || retries > 10) clearInterval(retryInterval);
        }, 2000);
      }
      startFeedPolling();
    }, 500);
    // Phase 168: Pull-to-refresh on mobile
    if ("ontouchstart" in window) {
      setTimeout(setupPullToRefresh, 1000);
    }
  });

  /* ── Phase 156: Scroll header show/hide + infinite scroll ── */
  var pageNum = 1;
  var loadingMore = false;
  var hasMoreFeed = true;
  var nextCursor = null;
  var feedEl = document.getElementById("nvpro-feed");

  function fetchNextPage() {
    if (loadingMore || !hasMoreFeed) return;
    loadingMore = true;
    var url = activeTab === "for_you"
      ? "/api/feed?limit=20" + (nextCursor ? "&cursor=" + encodeURIComponent(nextCursor) : "")
      : "/api/home/feed?tab=" + encodeURIComponent(activeTab) + "&page=" + (pageNum + 1) + "&limit=20";
    apiFetch(url)
      .then(function (data) {
        loadingMore = false;
        if (activeTab === "for_you" && data.ok && data.payload) {
          var items = (data.payload.feed_items || []).concat(data.payload.reels || []);
          if (items.length > 0) {
            nextCursor = data.payload.next_cursor || null;
            hasMoreFeed = !!data.payload.has_more;
            appendFeedItems(feedEl, items);
          } else {
            hasMoreFeed = false;
          }
        } else if (data.ok && data.items && data.items.length > 0) {
          pageNum++;
          hasMoreFeed = data.has_more;
          appendFeedItems(feedEl, data.items);
        } else {
          hasMoreFeed = false;
        }
      })
      .catch(function () { loadingMore = false; });
  }

  function appendFeedItems(feedEl, items) {
    if (!feedEl || !items || items.length === 0) return;
    var html = "";
    items.forEach(function (item, index) {
      var text = item.text || item.caption || "";
      var mediaUrl = item.media_url || item.public_url || item.image_url || item.thumbnail_url || "";
      var videoUrl = item.video_url || "";
      var thumbnail = item.thumbnail_url || mediaUrl || videoUrl || "";
      var avatar = item.avatar_url || "";
      var displayName = item.display_name || item.username || "Creator";
      var username = item.username || "";
      var initial = displayName.charAt(0).toUpperCase();
      var verified = item.verified ? '<svg class="nv-icon-sm nvpro-verified" viewBox="0 0 24 24" fill="currentColor"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' : "";
      var vAttr = item.type || "post";
      var isVideo = videoUrl || item.is_video || item.media_type === "video" || item.media_type === "reel" || (item.mime_type && item.mime_type.indexOf("video/") === 0) || (item.post_type === "video");
      var vidHtml = "";
      if (isVideo && videoUrl) {
        vidHtml = '<div class="nvpro-post-media" data-nv-video="' + escapeHtml(videoUrl) + '" data-nv-thumb="' + escapeHtml(thumbnail) + '">' +
          '<div class="nvpro-loading-skeleton"></div>' +
          '<div class="nvpro-video-overlay"><div class="nvpro-video-play-icon">' + icon("play") + "</div></div></div>";
      } else if (mediaUrl) {
        var loadMode = "lazy";
        vidHtml = '<div class="nvpro-post-media"><img src="' + escapeHtml(mediaUrl) + '" alt="' + escapeHtml(text) + '" loading="' + loadMode + '" class="nvpro-post-media"></div>';
      }
      html += '<article class="nvpro-post-card" data-item-id="' + (item.id || "") + '" data-type="' + vAttr + '" data-href="/post/' + (item.id || "") + '" style="cursor:pointer">';
      html += '<div class="nvpro-post-head">';
      html += '<a href="' + profileHref(username) + '" class="nvpro-post-avatar">';
      if (avatar) {
        html += '<img src="' + escapeHtml(avatar) + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">';
        html += '<span class="nvpro-avatar-initials" style="display:none">' + initial + "</span>";
      } else {
        html += '<span class="nvpro-avatar-initials">' + initial + "</span>";
      }
      html += "</a>";
      html += '<div class="nvpro-post-meta">';
      html += '<a href="' + profileHref(username) + '" class="nvpro-post-author">' + escapeHtml(displayName) + verified + "</a>";
      html += '<span class="nvpro-post-time">' + (item.created_label || "Just now") + "</span>";
      html += "</div>";
      if (item.profile_id) {
        html += '<button type="button" class="nvpro-follow-pill" data-follow-id="' + item.profile_id + '">Follow</button>';
      }
      html += "</div>";
      if (text) html += '<div class="nvpro-post-body">' + escapeHtml(text) + "</div>";
      html += vidHtml;
      html += '<div class="nvpro-post-actions">';
      html += '<button type="button" class="nvpro-action-btn" data-action="like" data-id="' + (item.id || "") + '" data-type="' + vAttr + '">' + icon("heart") + " <span>" + (item.likes_count || 0) + "</span></button>";
      html += '<button type="button" class="nvpro-action-btn" data-action="comment" data-id="' + (item.id || "") + '">' + icon("comment") + " <span>" + (item.comments_count || 0) + "</span></button>";
      html += '<button type="button" class="nvpro-action-btn" data-action="share" data-id="' + (item.id || "") + '">' + icon("share") + " <span>Share</span></button>";
      html += '<button type="button" class="nvpro-action-btn" data-action="save" data-id="' + (item.id || "") + '" data-type="' + vAttr + '">' + icon("save") + "</button>";
      html += "</div>";
      html += "</article>";
    });
    feedEl.insertAdjacentHTML("beforeend", html);
    lazyLoadVideos();
  }

  function setupScrollHeader() {
    var header = document.querySelector(".nvpro-header");
    var lastY = 0;
    var ticking = false;
    if (!header) return;
    window.addEventListener("scroll", function () {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(function () {
          var y = window.scrollY;
          if (y > 120 && y > lastY) {
            header.classList.add("nvpro-header-hidden");
          } else if (y < lastY || y < 120) {
            header.classList.remove("nvpro-header-hidden");
          }
          lastY = y;
          // Infinite scroll: fetch next page when near bottom
          var docHeight = document.documentElement.scrollHeight;
          var winHeight = window.innerHeight;
          if (y + winHeight >= docHeight - 600 && hasMoreFeed && !loadingMore) {
            fetchNextPage();
          }
          ticking = false;
        });
      }
    }, { passive: true });
  }

  /* ── Phase 156: Hamburger menu toggle ── */
  function setupHamburgerMenu() {
    var btn = document.getElementById("nvpro-hamburger");
    var drawer = document.getElementById("nvpro-drawer");
    var overlay = document.getElementById("nvpro-drawer-overlay");
    if (!btn || !drawer) return;
    btn.addEventListener("click", function () {
      drawer.classList.toggle("is-open");
      if (overlay) overlay.classList.toggle("is-open");
      document.body.classList.toggle("nvpro-drawer-open");
    });
    if (overlay) {
      overlay.addEventListener("click", function () {
        drawer.classList.remove("is-open");
        overlay.classList.remove("is-open");
        document.body.classList.remove("nvpro-drawer-open");
      });
    }
  }

  /* ── Phase 158a: Hydrate homepage from API or server data ── */
  function hydrateHomepage() {
    console.log("NAMVIBE HYDRATE START");
    console.log("window.NAMVIBE_HOME:", window.NAMVIBE_HOME);

    // Helper: get data from payload with fallback shapes
    function getFeedItems(p) { return p.feed_items || p.feed_for_you || []; }
    function getStories(p)   { return p.stories || []; }
    function getReels(p)     { return p.reels || []; }

    function doHydrate(p) {
      var storiesList = getStories(p);
      var feedList    = getFeedItems(p);
      var reelsList   = getReels(p);

      console.log("stories:", storiesList.length);
      console.log("feed_items:", feedList.length);
      console.log("reels:", reelsList.length);

      // ── Stories ──
      var storiesEl = document.getElementById("nvpro-stories");
      if (!storiesEl) storiesEl = document.querySelector(".nvpro-stories-scroll");
      if (storiesEl) {
        if (storiesList.length > 0) {
          // Remove all empty/placeholder cards
          storiesEl.querySelectorAll(".nvpro-story-empty-card").forEach(function (e) { e.remove(); });
          var createBtn = storiesEl.querySelector(".nvpro-story-create");
          // Remove all story-items except the create button
          storiesEl.querySelectorAll(".nvpro-story-item").forEach(function (e) { e.remove(); });
          // Render fresh stories
          var itemsHtml = "";
          storiesList.forEach(function (s) {
            var name = (s.display_name || s.username || "?");
            var initial = name.charAt(0).toUpperCase();
            var avatar = s.avatar_url || "";
            var ringCls = s.viewed ? "" : " is-unseen";
            itemsHtml += '<a href="/stories/' + (s.id || "") + '" class="nvpro-story-item" data-story-id="' + (s.id || "") + '">' +
              '<div class="nvpro-story-ring' + ringCls + '">';
            if (avatar) {
              itemsHtml += '<img src="' + avatar + '" alt="" class="nvpro-story-avatar" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' +
                '<span class="nvpro-avatar-initials" style="display:none">' + initial + '</span>';
            } else {
              itemsHtml += '<span class="nvpro-avatar-initials">' + initial + '</span>';
            }
            itemsHtml += '</div><span class="nvpro-story-label">' + name.substring(0, 10) + '</span></a>';
          });
          if (createBtn) {
            createBtn.insertAdjacentHTML("afterend", itemsHtml);
          }
        }
      }

      // ── Feed ──
      var feedEl = document.getElementById("nvpro-feed");
      if (feedEl) {
        if (feedList.length > 0) {
          renderFeedItems(feedEl, feedList);
        }
      }

      // ── Reels ──
      var reelsGrid = document.getElementById("nvpro-reels");
      if (!reelsGrid) reelsGrid = document.querySelector(".nvpro-reels-grid");
      if (reelsGrid) {
        if (reelsList.length > 0) {
          // Remove any empty cards
          var reelsSection = reelsGrid.closest(".nvpro-reels-section");
          if (reelsSection) {
            reelsSection.querySelectorAll(".nvpro-empty-card").forEach(function (e) { e.remove(); });
          }
          reelsGrid.innerHTML = "";
          var rh = "";
          reelsList.slice(0, 6).forEach(function (r) {
            var thumb = r.thumbnail_url || r.media_url || r.public_url || r.image_url || r.video_url || "";
            var name = r.display_name || r.username || "Creator";
            var caption = (r.caption || "").substring(0, 60);
            rh += '<a href="/reels/' + (r.id || "") + '" class="nvpro-reel-card" data-reel-id="' + (r.id || "") + '">' +
              '<div class="nvpro-reel-thumb">';
            if (thumb) {
              rh += '<img src="' + thumb + '" alt="" loading="lazy" onerror="this.parentElement.innerHTML=\'<svg viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' width=\\\'36\\\' height=\\\'36\\\'><polygon points=\\\'23 7 16 12 23 17 23 7\\\'/><rect x=\\\'1\\\' y=\\\'5\\\' width=\\\'15\\\' height=\\\'14\\\' rx=\\\'2\\\' ry=\\\'2\\\'/></svg>\'">';
            } else {
              rh += '<div class="nvpro-reel-thumb-fallback"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="36" height="36"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg></div>';
            }
            rh += '</div><div class="nvpro-reel-info"><span class="nvpro-reel-creator">' + name + '</span>';
            if (caption) rh += '<span class="nvpro-reel-caption">' + caption + '</span>';
            rh += '</div></a>';
          });
          reelsGrid.innerHTML = rh;
        }
      }
    }

    // Hydrate from window.NAMVIBE_HOME (server data) immediately
    if (window.NAMVIBE_HOME) {
      doHydrate(window.NAMVIBE_HOME);
    }

    // Then fetch fresh data from API and re-hydrate
    var controller = new AbortController();
    var timeoutId = setTimeout(function () {
      controller.abort();
    }, 15000);

    fetch("/api/feed?limit=20", {
      method: "GET",
      headers: { "X-CSRFToken": csrfToken() },
      signal: controller.signal,
      credentials: "same-origin"
    })
      .then(function (r) {
        clearTimeout(timeoutId);
        if (!r.ok) {
          throw new Error("HTTP " + r.status);
        }
        return r.json();
      })
      .then(function (data) {
        if (data && data.ok && data.payload) {
          nextCursor = data.payload.next_cursor || null;
          hasMoreFeed = typeof data.payload.has_more === "boolean" ? data.payload.has_more : true;
          doHydrate(data.payload);
          if (window.NamVibeCache) {
            window.NamVibeCache.saveFeed(data.payload);
          } else {
            try { localStorage.setItem("namvibe_feed_cache", JSON.stringify(data.payload)); } catch(e) {}
          }
          console.log("NAMVIBE HYDRATE COMPLETE (API)");
        }
      })
      .catch(function (err) {
        clearTimeout(timeoutId);
        console.log("NAMVIBE HYDRATE API FAILED, using server data", err);
        if (window.NAMVIBE_HOME && (!window.NAMVIBE_HOME.feed_items || !window.NAMVIBE_HOME.feed_items.length)) {
          if (window.NamVibeCache) {
            window.NamVibeCache.loadFeed().then(function (cached) {
              if (cached) doHydrate(cached);
            });
          } else {
            try { var cached = localStorage.getItem("namvibe_feed_cache"); if (cached) doHydrate(JSON.parse(cached)); } catch(e) {}
          }
        }
      });
  }

  /* ── Media Preloading with IntersectionObserver ── */
  function getMediaUrlFromCard(card) {
    var img = card.querySelector("img");
    if (img && img.src && !img.src.includes("data:")) return { url: img.src, type: "image" };
    var video = card.querySelector("video");
    if (video && video.src) return { url: video.src, type: "video" };
    var srcAttr = card.querySelector("[src]");
    if (srcAttr) return { url: srcAttr.getAttribute("src"), type: "image" };
    var bg = card.style.backgroundImage;
    if (bg) {
      var m = bg.match(/url\(["']?([^"')]+)["']?\)/);
      if (m) return { url: m[1], type: "image" };
    }
    return null;
  }

  function preloadNextMedia() {
    var cards = document.querySelectorAll(".nvpro-post-card:not(.nvpro-preload-attached)");
    var preloadCount = 0;
    for (var i = 0; i < cards.length && preloadCount < 8; i++) {
      var card = cards[i];
      card.classList.add("nvpro-preload-attached");
      var info = getMediaUrlFromCard(card);
      if (info && info.url && preloadCount < 5) {
        var link = document.createElement("link");
        link.rel = "preload";
        link.as = info.type;
        link.href = info.url;
        document.head.appendChild(link);
        preloadCount++;
      }
    }
  }

  var mediaObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var card = entry.target;
      if (entry.isIntersecting) {
        card.classList.add("nvpro-card-visible");
        var v = card.querySelector("video");
        if (v) {
          v.preload = "auto";
          v.load();
        }
        preloadNextMedia();
      } else {
        var v = card.querySelector("video");
        if (v && !v.paused) v.pause();
      }
    });
  }, { rootMargin: "200px" });

  function observeCards() {
    document.querySelectorAll(".nvpro-post-card").forEach(function (card) {
      if (!card.dataset.observerAttached) {
        card.dataset.observerAttached = "1";
        mediaObserver.observe(card);
      }
    });
  }

  var origRender = window.renderFeedItems;
  var origAppend = window.appendFeedItems;
  function wrapRender(fn) {
    return function (container, items) {
      fn(container, items);
      setTimeout(observeCards, 100);
      setTimeout(preloadNextMedia, 200);
    };
  }
  if (typeof renderFeedItems === "function") { window.renderFeedItems = wrapRender(renderFeedItems); }
  if (typeof appendFeedItems === "function") { window.appendFeedItems = wrapRender(appendFeedItems); }
  setTimeout(observeCards, 500);
  setTimeout(preloadNextMedia, 1000);

  /* ── Clickable post cards (delegated) ── */
  document.addEventListener("click", function (e) {
    var card = e.target.closest(".nvpro-post-card");
    if (!card) return;
    if (e.target.closest("button, a, input, textarea, select, video, [data-action], [data-follow-id], [data-open-upload], [data-open-camera]")) return;
    var href = card.dataset.href;
    if (href) window.location.href = href;
  });
})();
