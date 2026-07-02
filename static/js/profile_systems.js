/* ─── Profile 2026 JS ─── */
(function () {
  "use strict";

  const root = document.querySelector("[data-profile-pro]");
  if (!root) return;

  const PROFILE_ID = root.dataset.profileId;
  const USERNAME = root.dataset.username;
  const IS_SELF = root.dataset.self === "true";
  const BASE = "/profile/api";

  let currentTab = "posts";
  const loadedTabs = new Set();

  function $(sel) { return root.querySelector(sel); }
  function $$(sel) { return root.querySelectorAll(sel); }

  function showToast(msg, type) {
    var t = document.createElement("div");
    t.className = "nv-toast nv-toast-" + (type || "info");
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3000);
  }

  async function apiFetch(path, opts) {
    try {
      var res = await fetch(BASE + path, {
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "same-origin",
        ...opts,
      });
      return await res.json();
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function escapeHtml(text) {
    var d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
  }

  // ─── Tab Switching ───

  function initTabs() {
    $$("[data-tabs] .nv-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tab = this.dataset.tab;
        $$("[data-tabs] .nv-tab").forEach(function (b) { b.classList.remove("active"); });
        this.classList.add("active");
        $$("[data-panel]").forEach(function (p) { p.classList.remove("active"); });
        var panel = document.querySelector('[data-panel="' + tab + '"]');
        if (panel) {
          panel.classList.add("active");
          currentTab = tab;
          loadTab(tab);
        }
      });
    });
    // Load initial tab
    loadTab("posts");
  }

  function loadTab(tab) {
    if (loadedTabs.has(tab)) return;
    if (tab === "about" || tab === "highlights") {
      // Already rendered server-side, mark as loaded
      if (tab === "highlights") {
        var p = document.querySelector('[data-panel="highlights"]');
        if (p) {
          var items = p.querySelectorAll(".nv-highlight");
          if (items.length > 0) loadedTabs.add("highlights");
        }
      }
      loadedTabs.add(tab);
      return;
    }

    var panel = document.querySelector('[data-panel="' + tab + '"]');
    if (!panel) return;

    switch (tab) {
      case "posts": loadPosts(panel); break;
      case "reels": loadReels(panel); break;
      case "stories": loadStories(panel); break;
      case "gallery": loadGallery(panel); break;
      case "live": loadLive(panel); break;
      case "friends": loadFriends(panel); break;
      case "activity": loadActivity(panel); break;
    }
  }

  function renderGrid(items, type) {
    if (!items || items.length === 0) {
      return '<div class="nv-empty-inline"><h3>No ' + type + ' yet</h3><p>' +
        (IS_SELF ? "Create your first " + type + " to get started." : "No public " + type + " available.") +
        "</p></div>";
    }
    var html = '<div class="nv-grid nv-grid-3">';
    items.forEach(function (item) {
      var mediaUrl = item.thumbnail || item.media_url || "";
      var caption = escapeHtml((item.caption || "").slice(0, 80));
      var detailUrl = item.detail_url || (type === "posts" ? (item.id ? "/post/" + encodeURIComponent(item.id) : "/profile/") : type === "reels" ? (item.id ? "/reels/" + encodeURIComponent(item.id) : "/reels/") : type === "gallery" ? (item.media_url || "/profile/") : "/profile/");
      html += '<a class="nv-tile' + (item.media_type === "video" ? " nv-tile-video" : "") + '" href="' + escapeHtml(detailUrl) + '" data-id="' + escapeHtml(item.id) + '">';
      if (mediaUrl) html += '<img src="' + escapeHtml(mediaUrl) + '" alt="' + caption + '" loading="lazy">';
      html += '<div class="nv-tile-overlay"><i class="fas fa-heart"></i> ' + (item.likes || 0) + ' <i class="fas fa-eye"></i> ' + (item.views || 0) + "</div>";
      html += "</a>";
    });
    html += "</div>";
    return html;
  }

  async function loadPosts(panel) {
    loadedTabs.add("posts");
    panel.innerHTML = '<div class="nv-grid nv-grid-3"><div class="nv-skeleton"></div><div class="nv-skeleton"></div><div class="nv-skeleton"></div></div>';
    var data = await apiFetch("/" + USERNAME + "/content?section=posts");
    if (data.ok && data.items && data.items.length) {
      panel.innerHTML = renderGrid(data.items, "posts");
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No posts yet</h3><p>' +
        (IS_SELF ? "Share your first post to get started." : "No public posts available.") + "</p></div>";
    }
  }

  async function loadReels(panel) {
    loadedTabs.add("reels");
    panel.innerHTML = '<div class="nv-grid nv-grid-3"><div class="nv-skeleton"></div><div class="nv-skeleton"></div><div class="nv-skeleton"></div></div>';
    var data = await apiFetch("/" + USERNAME + "/reels");
    if (data.ok && data.items) {
      panel.innerHTML = renderGrid(data.items, "reels");
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No reels yet</h3><p>' +
        (IS_SELF ? "Upload a reel to share with your audience." : "No public reels available.") + "</p></div>";
    }
  }

  async function loadStories(panel) {
    loadedTabs.add("stories");
    panel.innerHTML = '<div class="nv-grid nv-grid-3"><div class="nv-skeleton"></div><div class="nv-skeleton"></div><div class="nv-skeleton"></div></div>';
    var data = await apiFetch("/" + USERNAME + "/stories");
    if (data.ok && data.items && data.items.length) {
      var html = '<div class="nv-grid nv-grid-3">';
      data.items.forEach(function (s) {
        html += '<button type="button" class="nv-tile" data-story-id="' + escapeHtml(s.id) + '">';
        if (s.media_url) html += '<img src="' + escapeHtml(s.media_url) + '" alt="Story" loading="lazy">';
        if (s.viewed) html += '<div class="nv-viewed-badge">Viewed</div>';
        html += "</button>";
      });
      html += "</div>";
      panel.innerHTML = html;
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No stories</h3><p>No recent stories available.</p></div>';
    }
  }

  async function loadGallery(panel) {
    loadedTabs.add("gallery");
    panel.innerHTML = '<div class="nv-grid nv-grid-3"><div class="nv-skeleton"></div><div class="nv-skeleton"></div><div class="nv-skeleton"></div></div>';
    var data = await apiFetch("/" + USERNAME + "/gallery");
    if (data.ok && data.items && data.items.length) {
      panel.innerHTML = renderGrid(data.items, "gallery");
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No gallery items</h3><p>' +
        (IS_SELF ? "Add photos to your gallery." : "No public gallery available.") + "</p></div>";
    }
  }

  async function loadLive(panel) {
    loadedTabs.add("live");
    panel.innerHTML = '<div class="nv-grid nv-grid-2"><div class="nv-skeleton"></div><div class="nv-skeleton"></div></div>';
    var data = await apiFetch("/" + USERNAME + "/live");
    if (data.ok && data.items && data.items.length) {
      var html = '<div class="nv-grid nv-grid-2">';
      data.items.forEach(function (r) {
        var isLive = r.status === "live";
        html += '<a class="nv-tile" href="' + escapeHtml(r.room_url || "/live/") + '" style="aspect-ratio:16/9">';
        if (r.thumbnail) html += '<img src="' + escapeHtml(r.thumbnail) + '" alt="' + escapeHtml(r.title) + '" loading="lazy">';
        html += '<div class="nv-tile-overlay">';
        if (isLive) html += '<span class="nv-live-badge">LIVE</span>';
        html += '<span>' + escapeHtml(r.title) + "</span>";
        html += "</div></a>";
      });
      html += "</div>";
      panel.innerHTML = html;
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No live sessions</h3><p>' +
        (IS_SELF ? "Go live when you're ready to connect." : "No live sessions available.") + "</p></div>";
    }
  }

  async function loadFriends(panel) {
    loadedTabs.add("friends");
    loadedTabs.add("friends");
    panel.innerHTML = '<div class="nv-grid nv-grid-3"><div class="nv-skeleton"></div><div class="nv-skeleton"></div><div class="nv-skeleton"></div></div>';
    var data = await apiFetch("/" + USERNAME + "/content?section=friends");
    if (data.ok && data.items && data.items.length) {
      var html = '<div class="nv-grid nv-grid-3">';
      data.items.forEach(function (f) {
        html += '<a href="/profile/@' + escapeHtml(f.username) + '" class="nv-tile" style="display:flex;flex-direction:column;align-items:center;justify-content:center;aspect-ratio:auto;padding:16px;background:var(--p-surface);border:1px solid var(--p-border);border-radius:var(--p-radius-sm);text-decoration:none;color:var(--p-text)">';
        if (f.avatar_url) {
          html += '<img src="' + escapeHtml(f.avatar_url) + '" alt="' + escapeHtml(f.display_name) + '" style="width:48px;height:48px;border-radius:50%;object-fit:cover;margin-bottom:6px">';
        } else {
          html += '<div style="width:48px;height:48px;border-radius:50%;background:var(--p-surface-2);display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;margin-bottom:6px">' + (f.display_name ? f.display_name[0] : "?") + "</div>";
        }
        html += "<span style='font-size:12px;font-weight:600;text-align:center'>" + escapeHtml(f.display_name || f.username) + "</span>";
        html += "</a>";
      });
      html += "</div>";
      panel.innerHTML = html;
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No friends to show</h3></div>';
    }
  }

  async function loadActivity(panel) {
    loadedTabs.add("activity");
    panel.innerHTML = '<div class="nv-empty-inline"><div class="nv-spinner" style="margin-bottom:12px"></div><p>Loading activity...</p></div>';
    var data = await apiFetch("/" + USERNAME + "/activity");
    if (data.ok && data.items && data.items.length) {
      var html = '<div style="display:flex;flex-direction:column;gap:6px">';
      data.items.forEach(function (a) {
        html += '<div class="nv-activity-item" style="padding:10px 12px;background:var(--p-surface);border-radius:var(--p-radius-sm);border:1px solid var(--p-border);font-size:13px">';
        html += "<strong>" + escapeHtml(a.event_type.replace(/_/g, " ")) + "</strong>";
        if (a.created_at) html += " <span style='color:var(--p-secondary);font-size:11px'>" + new Date(a.created_at).toLocaleDateString() + "</span>";
        html += "</div>";
      });
      html += "</div>";
      panel.innerHTML = html;
    } else {
      panel.innerHTML = '<div class="nv-empty-inline"><h3>No recent activity</h3><p>Activity will appear here as you engage with the platform.</p></div>';
    }
  }

  // ─── Actions (Follow / Friend / Message) ───

  function initActions() {
    // Follow button
    var followBtn = root.querySelector('[data-action="follow"]');
    var friendBtn = root.querySelector('[data-action="friend"]');
    if (followBtn) {
      followBtn.addEventListener("click", function () {
        var state = this.dataset.state;
        if (state === "following" || state === "friends") {
          // Unfollow
          apiFetch("/profile/@" + USERNAME + "/follow", { method: "POST" }).then(function (d) {
            if (d.ok) {
              followBtn.dataset.state = "none";
              followBtn.innerHTML = '<i class="fas fa-user-plus"></i> Follow';
              showToast("Unfollowed", "info");
            }
          });
        } else {
          apiFetch("/profile/@" + USERNAME + "/follow", { method: "POST" }).then(function (d) {
            if (d.ok) {
              followBtn.dataset.state = "following";
              followBtn.innerHTML = '<i class="fas fa-user-check"></i> Following';
              showToast("Followed", "success");
            }
          });
        }
      });
    }
    if (friendBtn) {
      friendBtn.addEventListener("click", function () {
        if (!window.confirm("Remove @" + USERNAME + " from friends?")) return;
        fetch("/api/social/unfriend/" + PROFILE_ID, {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json" }
        }).then(function (r) { return r.json(); }).then(function (d) {
          if (d && d.ok) {
            showToast("Friend removed", "info");
            window.location.reload();
          } else {
            showToast((d && (d.error || d.message)) || "Could not update friendship.", "error");
          }
        }).catch(function () {
          showToast("Could not update friendship.", "error");
        });
      });
    }

    // Message button
    var msgBtn = root.querySelector('[data-action="message"]');
    if (msgBtn && !msgBtn.disabled) {
      msgBtn.addEventListener("click", function () {
        window.location.href = "/messages/start/" + PROFILE_ID;
      });
    }

    // Call buttons
    var callBtn = root.querySelector('[data-action="call"]');
    if (callBtn) {
      callBtn.addEventListener("click", function () {
        window.location.href = "/calls/start/" + PROFILE_ID + "/audio";
      });
    }
    var videoBtn = root.querySelector('[data-action="video-call"]');
    if (videoBtn) {
      videoBtn.addEventListener("click", function () {
        window.location.href = "/calls/start/" + PROFILE_ID + "/video";
      });
    }

    // Share
    var shareBtn = root.querySelector('[data-action="share"]');
    if (shareBtn) {
      shareBtn.addEventListener("click", function () {
        var url = window.location.origin + "/profile/@" + USERNAME;
        if (navigator.share) {
          navigator.share({ title: document.title, url: url }).catch(function () {});
        } else {
          navigator.clipboard.writeText(url).then(function () {
            showToast("Profile link copied!", "success");
          });
        }
      });
    }

    // More menu
    var moreBtn = root.querySelector('[data-action="more"]');
    var moreMenu = root.querySelector("[data-more-menu]");
    if (moreBtn && moreMenu) {
      var dropdown = moreMenu.querySelector(".nv-more-dropdown");
      moreBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        var hidden = dropdown.hasAttribute("hidden");
        document.querySelectorAll(".nv-more-dropdown").forEach(function (d) { d.hidden = true; });
        dropdown.hidden = !hidden;
      });
      document.addEventListener("click", function () {
        if (dropdown) dropdown.hidden = true;
      });
      // Report
      var reportBtn = dropdown.querySelector('[data-action="report"]');
      if (reportBtn) {
        reportBtn.addEventListener("click", function () {
          apiFetch("/profile/@" + USERNAME + "/report", { method: "POST" }).then(function (d) {
            showToast(d.ok ? "Reported" : "Error reporting", d.ok ? "info" : "error");
          });
          dropdown.hidden = true;
        });
      }
      // Block
      var blockBtn = dropdown.querySelector('[data-action="block"]');
      if (blockBtn) {
        blockBtn.addEventListener("click", function () {
          if (confirm("Block @" + USERNAME + "?")) {
            apiFetch("/profile/@" + USERNAME + "/block", { method: "POST" }).then(function (d) {
              showToast(d.ok ? "Blocked" : "Error", d.ok ? "info" : "error");
            });
          }
          dropdown.hidden = true;
        });
      }
      var restrictBtn = dropdown.querySelector('[data-action="restrict"]');
      if (restrictBtn) {
        restrictBtn.addEventListener("click", function () {
          fetch("/api/restrict/" + PROFILE_ID, {
            method: "POST",
            credentials: "same-origin",
            headers: { Accept: "application/json" }
          }).then(function (r) { return r.json(); }).then(function (d) {
            showToast(d && d.success ? "Restricted" : ((d && d.error) || "Could not restrict profile."), d && d.success ? "info" : "error");
          }).catch(function () {
            showToast("Could not restrict profile.", "error");
          });
          dropdown.hidden = true;
        });
      }
    }

    // Cover/avatar change
    var coverBtn = root.querySelector('[data-action="change-cover"]');
    if (coverBtn) {
      coverBtn.addEventListener("click", function () {
        var input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.onchange = function () {
          if (input.files && input.files[0]) {
            var form = new FormData();
            form.append("cover", input.files[0]);
            form.append("csrf_token", document.querySelector('[name="csrf_token"]')?.value || "");
            fetch("/profile/cover", { method: "POST", body: form }).then(function (r) {
              if (r.ok) showToast("Cover updated", "success");
              else showToast("Upload failed", "error");
            });
          }
        };
        input.click();
      });
    }

    var avatarBtn = root.querySelector('[data-action="change-avatar"]');
    if (avatarBtn) {
      avatarBtn.addEventListener("click", function () {
        var input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.onchange = function () {
          if (input.files && input.files[0]) {
            var form = new FormData();
            form.append("avatar", input.files[0]);
            form.append("csrf_token", document.querySelector('[name="csrf_token"]')?.value || "");
            fetch("/profile/avatar", { method: "POST", body: form }).then(function (r) {
              if (r.ok) { showToast("Avatar updated", "success"); location.reload(); }
              else showToast("Upload failed", "error");
            });
          }
        };
        input.click();
      });
    }

    // Stats click (navigate to followers/following list)
    var followersStat = root.querySelector('[data-action="followers"]');
    if (followersStat) {
      followersStat.style.cursor = "pointer";
      followersStat.addEventListener("click", function () {
        window.location.href = "/profile/@" + USERNAME + "/followers";
      });
    }
    var followingStat = root.querySelector('[data-action="following"]');
    if (followingStat) {
      followingStat.style.cursor = "pointer";
      followingStat.addEventListener("click", function () {
        window.location.href = "/profile/@" + USERNAME + "/following";
      });
    }
    var friendsStat = root.querySelector('[data-action="friends"]');
    if (friendsStat) {
      friendsStat.style.cursor = "pointer";
      friendsStat.addEventListener("click", function () {
        window.location.href = "/profile/@" + USERNAME + "/friends";
      });
    }
    root.querySelectorAll("[data-highlight-id]").forEach(function (button) {
      button.addEventListener("click", function () {
        var highlightId = this.dataset.highlightId;
        if (window.NamVibeStories && typeof window.NamVibeStories.openHighlight === "function" && highlightId) {
          window.NamVibeStories.openHighlight(highlightId);
          return;
        }
        window.location.href = "/stories/";
      });
    });
    root.addEventListener("click", function (event) {
      var storyTile = event.target.closest("[data-story-id]");
      if (!storyTile) return;
      event.preventDefault();
      window.location.href = "/stories/";
    });
  }

  // ─── Realtime Presence ───
  function initPresence() {
    // Listen for presence updates via socket
    if (typeof socket !== "undefined" && socket) {
      socket.on("presence:update", function (data) {
        if (data && data.profile_id === PROFILE_ID) {
          var dot = root.querySelector(".nv-online-dot");
          var label = root.querySelector(".nv-meta-line .is-online, .nv-meta-line .is-offline");
          if (data.state === "online") {
            if (!dot) {
              var wrap = root.querySelector(".nv-avatar-wrap");
              if (wrap) {
                var d = document.createElement("span");
                d.className = "nv-online-dot";
                wrap.appendChild(d);
              }
            }
            if (label) {
              label.className = "is-online";
              label.innerHTML = '<i class="fas fa-circle"></i> active now';
            }
          } else {
            if (dot) dot.remove();
            if (label) {
              label.className = "is-offline";
              label.innerHTML = '<i class="fas fa-circle"></i> offline';
            }
          }
        }
      });
    }
  }

  // ─── Init ───
  document.addEventListener("DOMContentLoaded", function () {
    initTabs();
    initActions();
    initPresence();
  });
})();
