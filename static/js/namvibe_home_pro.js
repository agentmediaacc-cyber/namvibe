/* ── Phase 120 — Premium Homepage ── */

(function () {
  "use strict";

  // ── State ──
  var activeTab = "for_you";
  var csrfToken = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };
  var toastEl = document.getElementById("nvpro-toast");

  // ── Toast ──
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-visible");
    setTimeout(function () { toastEl.classList.remove("is-visible"); }, 2500);
  }

  // ── CSRF fetch helper ──
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

  // ── Tab switching ──
  var tabs = document.querySelectorAll(".nvpro-tab");
  var feedEl = document.getElementById("nvpro-feed");

  function switchTab(tab) {
    if (tab === activeTab) return;
    activeTab = tab;
    tabs.forEach(function (t) { t.classList.toggle("is-active", t.dataset.tab === tab); });
    showSkeleton();
    fetchFeed(tab);
  }

  tabs.forEach(function (t) {
    t.addEventListener("click", function () { switchTab(t.dataset.tab); });
  });

  // ── Skeleton ──
  function showSkeleton() {
    if (!feedEl) return;
    var html = "";
    for (var i = 0; i < 3; i++) {
      html += '<div class="nvpro-skeleton nvpro-skeleton-card"></div>';
    }
    feedEl.innerHTML = html;
  }

  // ── Fetch feed ──
  function fetchFeed(tab) {
    apiFetch("/api/homepage/feed?tab=" + encodeURIComponent(tab) + "&limit=20")
      .then(function (data) {
        if (data.ok && data.payload && data.payload.feed_items) {
          renderFeed(data.payload.feed_items);
        } else {
          renderEmpty();
        }
      })
      .catch(function () {
        renderEmpty();
      });
  }

  function renderFeed(items) {
    if (!feedEl) return;
    if (!items || items.length === 0) { renderEmpty(); return; }
    var html = "";
    items.forEach(function (item) {
      var text = item.text || "";
      var mediaUrl = item.media_url || "";
      var videoUrl = item.video_url || "";
      var avatar = item.avatar_url || "";
      var displayName = item.display_name || item.username || "Creator";
      var username = item.username || "";
      var initial = displayName.charAt(0).toUpperCase();
      var verified = item.verified ? '<i class="fas fa-circle-check nvpro-verified"></i>' : "";
      var vAttr = item.type || "post";

      html += '<article class="nvpro-post-card" data-item-id="' + (item.id || "") + '" data-type="' + vAttr + '">';
      html += '<div class="nvpro-post-head">';
      html += '<a href="/profile/@" + username + '" class="nvpro-post-avatar">';
      if (avatar) {
        html += '<img src="' + avatar + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">';
        html += '<span class="nvpro-avatar-initials" style="display:none">' + initial + '</span>';
      } else {
        html += '<span class="nvpro-avatar-initials">' + initial + '</span>';
      }
      html += '</a>';
      html += '<div class="nvpro-post-meta">';
      html += '<a href="/profile/@" + username + '" class="nvpro-post-author">' + displayName + verified + '</a>';
      html += '<span class="nvpro-post-time">' + (item.created_label || "Just now") + '</span>';
      html += '</div>';
      if (item.profile_id) {
        html += '<button type="button" class="nvpro-follow-pill" data-follow-id="' + item.profile_id + '">Follow</button>';
      }
      html += '</div>';
      if (text) html += '<div class="nvpro-post-body">' + escapeHtml(text) + '</div>';
      if (mediaUrl) html += '<div class="nvpro-post-media"><img src="' + mediaUrl + '" alt="" loading="lazy"></div>';
      if (videoUrl) html += '<div class="nvpro-post-media"><video src="' + videoUrl + '" muted playsinline preload="metadata" class="nvpro-video-preview"></video></div>';
      html += '<div class="nvpro-post-actions">';
      html += '<button type="button" class="nvpro-action-btn" data-action="like" data-id="' + (item.id || "") + '" data-type="' + vAttr + '"><i class="far fa-heart"></i> <span>' + (item.likes_count || 0) + '</span></button>';
      html += '<button type="button" class="nvpro-action-btn" data-action="comment" data-id="' + (item.id || "") + '"><i class="far fa-comment"></i> <span>' + (item.comments_count || 0) + '</span></button>';
      html += '<button type="button" class="nvpro-action-btn" data-action="share" data-id="' + (item.id || "") + '"><i class="far fa-share-square"></i> <span>Share</span></button>';
      html += '<button type="button" class="nvpro-action-btn" data-action="save" data-id="' + (item.id || "") + '" data-type="' + vAttr + '"><i class="far fa-bookmark"></i></button>';
      html += '</div>';
      html += '</article>';
    });
    feedEl.innerHTML = html;
  }

  function renderEmpty() {
    if (!feedEl) return;
    feedEl.innerHTML =
      '<div class="nvpro-empty">' +
      '<div class="nvpro-empty-icon"><i class="fas fa-newspaper"></i></div>' +
      '<h3>Your NamVibe feed is ready</h3>' +
      '<p>Follow creators, watch reels, join live rooms, or share your first post.</p>' +
      '<div class="nvpro-empty-actions">' +
      '<a href="/discover/" class="nvpro-btn nvpro-btn-primary">Discover Creators</a>' +
      '<a href="/posts/create" class="nvpro-btn nvpro-btn-outline">Create Post</a>' +
      '<a href="/reels/" class="nvpro-btn nvpro-btn-outline">Watch Reels</a>' +
      '</div></div>';
  }

  function escapeHtml(str) {
    if (!str) return "";
    var d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // ── Video autoplay ──
  var videoObserver = null;
  function setupVideoObserver() {
    if (!window.IntersectionObserver) return;
    videoObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var vid = entry.target;
        if (entry.isIntersecting) {
          vid.play().catch(function () {});
        } else {
          vid.pause();
        }
      });
    }, { threshold: 0.5 });
    document.querySelectorAll(".nvpro-video-preview").forEach(function (v) { videoObserver.observe(v); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupVideoObserver();
  });

  // Watch for new videos added via JS
  var mutationObserver = new MutationObserver(function () {
    if (videoObserver) {
      document.querySelectorAll(".nvpro-video-preview:not([data-video-obs])").forEach(function (v) {
        v.setAttribute("data-video-obs", "1");
        videoObserver.observe(v);
      });
    }
  });
  if (document.body) mutationObserver.observe(document.body, { childList: true, subtree: true });

  // ── Like action ──
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=like]");
    if (!btn) return;
    var id = btn.dataset.id;
    var type = btn.dataset.type || "post";
    if (!id) return;
    var url = type === "reel" ? "/api/reels/" + id + "/like" : "/api/home/post/" + id + "/like";
    apiFetch(url, { method: "POST" })
      .then(function (data) {
        if (data.ok) {
          btn.classList.toggle("is-liked");
          var span = btn.querySelector("span");
          if (span) {
            var c = parseInt(span.textContent, 10) || 0;
            span.textContent = btn.classList.contains("is-liked") ? c + 1 : Math.max(c - 1, 0);
          }
          showToast(btn.classList.contains("is-liked") ? "Liked" : "Unliked");
        }
      })
      .catch(function () {
        showToast("Could not like. Try again.");
      });
  });

  // ── Save action ──
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=save]");
    if (!btn) return;
    var id = btn.dataset.id;
    var type = btn.dataset.type || "post";
    if (!id) return;
    var url = type === "reel" ? "/api/reels/" + id + "/save" : "/api/home/post/" + id + "/save";
    apiFetch(url, { method: "POST" })
      .then(function (data) {
        if (data.ok) {
          btn.classList.toggle("is-saved");
          showToast(btn.classList.contains("is-saved") ? "Saved" : "Unsaved");
        }
      })
      .catch(function () {
        showToast("Could not save. Try again.");
      });
  });

  // ── Share action ──
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=share]");
    if (!btn) return;
    var id = btn.dataset.id;
    var url = window.location.origin + "/posts/" + (id || "");
    if (navigator.share) {
      navigator.share({ title: "NamVibe", url: url }).catch(function () {});
    } else {
      navigator.clipboard.writeText(url).then(function () {
        showToast("Link copied!");
      }).catch(function () {
        showToast("Could not share. Try again.");
      });
    }
  });

  // ── Comment action ──
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action=comment]");
    if (!btn) return;
    var id = btn.dataset.id;
    if (id) window.location.href = "/posts/" + id;
  });

  // ── Follow action ──
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
      .catch(function () {
        showToast("Could not follow. Try again.");
      });
  });

})();
