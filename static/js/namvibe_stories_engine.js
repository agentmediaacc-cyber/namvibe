// ===== NamVibe Stories 2.0 Premium Engine JS =====
(function () {
  "use strict";

  const STATE = {
    groupIndex: 0,
    storyIndex: 0,
    groups: [],
    stories: [],
    viewerOpen: false,
    activeTimer: null,
    progressInterval: null,
    holdTimeout: null,
    isPaused: false,
    touchStartY: 0,
    touchStartX: 0,
    reactingStoryId: null,
  };

  const STORY_DURATION = 5000; // ms per story
  const SWIPE_THRESHOLD = 80;

  // ── Init ──
  function init() {
    loadFeed();
  }

  async function loadFeed() {
    try {
      const res = await fetch("/stories/api/stories/feed-v2");
      const data = await res.json();
      STATE.groups = data.groups || data.stories || [];
      renderTray();
    } catch (e) {
      console.error("[NV Stories] feed error", e);
    }
  }

  // ── Tray Rendering ──
  function renderTray() {
    const tray = document.getElementById("nv-story-tray");
    if (!tray) return;

    if (STATE.groups.length === 0) {
      tray.innerHTML = '<div class="nv-story-tray-empty" style="padding:20px;text-align:center;color:#999">No stories yet</div>';
      return;
    }

    let html = "";
    STATE.groups.forEach((group, gi) => {
      const firstStory = group.stories && group.stories[0];
      if (!firstStory) return;

      const isOwn = window.__NV_PROFILE_ID && String(group.profile_id) === String(window.__NV_PROFILE_ID);
      const statusClass = group.all_viewed ? "viewed" : "unviewed";
      const avatarUrl = group.avatar_url || "";
      const displayName = group.display_name || group.username || "User";

      html += `
        <div class="nv-story-tray-item" data-group-index="${gi}" onclick="NamVibeStories.openViewer(${gi})">
          <div class="nv-story-avatar-wrap ${statusClass}">
            <img class="nv-story-avatar" src="${escapeHtml(avatarUrl)}" alt="" loading="lazy" onerror="this.src='/static/img/default-avatar.png'">
            ${isOwn ? '<div class="nv-story-add-badge">+</div>' : ''}
          </div>
          <span class="nv-story-username">${isOwn ? 'Your Story' : escapeHtml(displayName)}</span>
        </div>
      `;
    });

    // Highlights section
    const highlightsSection = document.getElementById("nv-highlights-section");
    if (highlightsSection) {
      loadHighlights(highlightsSection);
    }

    tray.innerHTML = html;
  }

  async function loadHighlights(container) {
    try {
      const res = await fetch("/stories/api/highlights");
      const data = await res.json();
      const highlights = data.highlights || [];
      if (highlights.length === 0) {
        container.style.display = "none";
        return;
      }
      container.style.display = "block";
      let html = '<div class="nv-highlights-tray">';
      highlights.forEach((hl) => {
        html += `
          <div class="nv-highlight-item" onclick="NamVibeStories.openHighlight('${hl.id}')">
            <div class="nv-story-avatar-wrap viewed">
              <img class="nv-story-avatar" src="${escapeHtml(hl.cover_url || '')}" alt="" onerror="this.src='/static/img/default-avatar.png'">
            </div>
            <span class="nv-story-username">${escapeHtml(hl.title)}</span>
          </div>
        `;
      });
      html += "</div>";
      container.innerHTML = html;
    } catch (e) {
      container.style.display = "none";
    }
  }

  // ── Viewer ──
  function openViewer(groupIndex) {
    const group = STATE.groups[groupIndex];
    if (!group || !group.stories || group.stories.length === 0) return;

    STATE.groupIndex = groupIndex;
    STATE.storyIndex = 0;
    STATE.stories = group.stories;
    STATE.viewerOpen = true;

    renderViewer();
    document.getElementById("nv-story-viewer").classList.add("open");
    startStory();
  }

  function openHighlight(highlightId) {
    fetch(`/stories/api/highlights/${highlightId}`)
      .then(r => r.json())
      .then(data => {
        if (data.stories && data.stories.length > 0) {
          STATE.groupIndex = -1;
          STATE.storyIndex = 0;
          STATE.stories = data.stories;
          STATE.viewerOpen = true;
          renderViewer();
          document.getElementById("nv-story-viewer").classList.add("open");
          startStory();
        }
      })
      .catch(() => {});
  }

  function renderViewer() {
    const viewer = document.getElementById("nv-story-viewer");
    if (!viewer) return;

    const story = STATE.stories[STATE.storyIndex];
    if (!story) return;

    document.body.style.overflow = "hidden";

    // Progress bar
    let progressHtml = '<div class="nv-story-progress-bar">';
    STATE.stories.forEach((s, i) => {
      const isActive = i === STATE.storyIndex;
      const isPast = i < STATE.storyIndex;
      progressHtml += `<div class="nv-story-progress-seg">
        <div class="nv-story-progress-fill ${isActive ? 'active' : ''}" style="width:${isPast ? '100' : (isActive ? '0' : '0')}%"></div>
      </div>`;
    });
    progressHtml += "</div>";

    // Media
    let mediaHtml = "";
    if (story.text_content && !story.media_url) {
      mediaHtml = `<div class="nv-story-text-overlay" style="background:${story.background_color || '#1a1a2e'}">${escapeHtml(story.text_content)}</div>`;
    } else if (story.media_type === "video" || (story.media_url && (story.media_url.endsWith(".mp4") || story.media_url.endsWith(".mov") || story.media_url.endsWith(".webm")))) {
      mediaHtml = `<video class="nv-story-media" src="${escapeHtml(story.media_url)}" playsinline autoplay muted loop></video>`;
    } else {
      mediaHtml = `<img class="nv-story-media" src="${escapeHtml(story.media_url || story.thumbnail_url || '')}" alt="" loading="eager">`;
    }

    // Caption with mentions/hashtags
    let captionHtml = "";
    if (story.caption) {
      captionHtml = `<div style="color:#fff;font-size:13px;text-align:center;padding:8px;text-shadow:0 1px 4px rgba(0,0,0,.5);position:absolute;bottom:70px;left:0;right:0;z-index:6">${escapeHtml(story.caption)}</div>`;
    }

    // Header info
    const profileId = story.profile_id;
    const isOwn = window.__NV_PROFILE_ID && String(profileId) === String(window.__NV_PROFILE_ID);

    viewer.innerHTML = `
      ${progressHtml}
      <div class="nv-story-header">
        <button class="nv-story-header-close" onclick="NamVibeStories.closeViewer()">&times;</button>
        <img class="nv-story-header-avatar" src="${escapeHtml(story.avatar_url || '')}" alt="" onerror="this.src='/static/img/default-avatar.png'">
        <div class="nv-story-header-info">
          <div class="nv-story-header-name">${escapeHtml(story.display_name || story.username || '')}</div>
          <div class="nv-story-header-time">${timeAgo(story.created_at)}${story.location_name ? ' · ' + escapeHtml(story.location_name) : ''}</div>
        </div>
        <div class="nv-story-privacy-badge"><i class="fas fa-${story.visibility === 'close_friends' ? 'lock' : story.visibility === 'followers' ? 'users' : 'globe'}"></i> ${story.visibility}</div>
        ${isOwn ? `<button class="nv-story-delete-btn" onclick="NamVibeStories.deleteCurrent()" title="Delete"><i class="fas fa-trash"></i></button>` : ''}
      </div>
      <div class="nv-story-viewer-content" id="nv-story-content">
        ${mediaHtml}
        ${captionHtml}
        <div class="nv-story-tap-left" onclick="NamVibeStories.prevStory()"></div>
        <div class="nv-story-tap-center" onmousedown="NamVibeStories.holdStart()" onmouseup="NamVibeStories.holdEnd()" ontouchstart="NamVibeStories.holdStart()" ontouchend="NamVibeStories.holdEnd()"></div>
        <div class="nv-story-tap-right" onclick="NamVibeStories.nextStory()"></div>
        <div class="nv-story-emoji-picker" id="nv-story-emoji-picker">
          <button class="nv-story-emoji-option" onclick="NamVibeStories.sendReaction('❤️')">❤️</button>
          <button class="nv-story-emoji-option" onclick="NamVibeStories.sendReaction('😂')">😂</button>
          <button class="nv-story-emoji-option" onclick="NamVibeStories.sendReaction('😮')">😮</button>
          <button class="nv-story-emoji-option" onclick="NamVibeStories.sendReaction('😢')">😢</button>
          <button class="nv-story-emoji-option" onclick="NamVibeStories.sendReaction('🔥')">🔥</button>
        </div>
      </div>
      <div class="nv-story-footer">
        <button class="nv-story-react-btn" onclick="NamVibeStories.toggleEmojiPicker()"><i class="far fa-smile"></i></button>
        <input class="nv-story-reply-input" id="nv-story-reply-input" placeholder="Send message..." maxlength="200">
        <button class="nv-story-send-btn" id="nv-story-send-btn" disabled onclick="NamVibeStories.sendReply()"><i class="fas fa-paper-plane"></i></button>
      </div>
    `;

    // Reply input handler
    const replyInput = document.getElementById("nv-story-reply-input");
    const sendBtn = document.getElementById("nv-story-send-btn");
    if (replyInput && sendBtn) {
      replyInput.addEventListener("input", () => {
        sendBtn.disabled = !replyInput.value.trim();
      });
      replyInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && replyInput.value.trim()) {
          sendReply();
        }
      });
    }

    // Video auto-play handler
    const video = viewer.querySelector("video");
    if (video) {
      video.addEventListener("ended", () => nextStory());
      video.addEventListener("loadedmetadata", () => {
        video.play().catch(() => {});
      });
    }
  }

  // ── Story Navigation ──
  function startStory() {
    clearTimers();
    const story = STATE.stories[STATE.storyIndex];
    if (!story) { closeViewer(); return; }

    // Record view
    recordView(story.id);

    // Start progress
    updateProgress();
    STATE.progressInterval = setInterval(updateProgress, 100);

    // Auto-advance
    STATE.activeTimer = setTimeout(() => {
      nextStory();
    }, STORY_DURATION);
  }

  function nextStory() {
    if (STATE.isPaused) return;
    recordAnalytics("forward");
    if (STATE.storyIndex < STATE.stories.length - 1) {
      STATE.storyIndex++;
      renderViewer();
      startStory();
    } else if (STATE.groupIndex >= 0 && STATE.groupIndex < STATE.groups.length - 1) {
      // Next group
      STATE.groupIndex++;
      const group = STATE.groups[STATE.groupIndex];
      if (group && group.stories && group.stories.length > 0) {
        STATE.stories = group.stories;
        STATE.storyIndex = 0;
        renderViewer();
        startStory();
      } else {
        closeViewer();
      }
    } else {
      closeViewer();
    }
  }

  function prevStory() {
    if (STATE.isPaused) return;
    recordAnalytics("back");
    if (STATE.storyIndex > 0) {
      STATE.storyIndex--;
      renderViewer();
      startStory();
    } else if (STATE.groupIndex > 0) {
      STATE.groupIndex--;
      const group = STATE.groups[STATE.groupIndex];
      if (group && group.stories && group.stories.length > 0) {
        STATE.stories = group.stories;
        STATE.storyIndex = group.stories.length - 1;
        renderViewer();
        startStory();
      }
    }
  }

  function closeViewer() {
    STATE.viewerOpen = false;
    clearTimers();
    const viewer = document.getElementById("nv-story-viewer");
    if (viewer) viewer.classList.remove("open");
    document.body.style.overflow = "";
    loadFeed(); // refresh tray
  }

  // ── Progress ──
  function updateProgress() {
    const fills = document.querySelectorAll(".nv-story-progress-fill.active");
    fills.forEach((fill) => {
      const elapsed = Date.now() - (STATE._storyStart || Date.now());
      const pct = Math.min((elapsed / STORY_DURATION) * 100, 100);
      fill.style.width = pct + "%";
      if (pct >= 100) {
        fill.style.width = "100%";
      }
    });
  }

  // ── View Tracking ──
  function recordView(storyId) {
    STATE._storyStart = Date.now();
    fetch(`/stories/api/stories/${storyId}/view-v2`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }).catch(() => {});
  }

  function recordAnalytics(eventType) {
    const story = STATE.stories[STATE.storyIndex];
    if (!story) return;
    fetch(`/stories/api/stories/${story.id}/analytics-event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_type: eventType }),
    }).catch(() => {});
  }

  // ── Reactions ──
  function toggleEmojiPicker() {
    const picker = document.getElementById("nv-story-emoji-picker");
    if (picker) picker.classList.toggle("open");
  }

  function sendReaction(reaction) {
    const story = STATE.stories[STATE.storyIndex];
    if (!story) return;
    const picker = document.getElementById("nv-story-emoji-picker");
    if (picker) picker.classList.remove("open");

    fetch(`/stories/api/stories/${story.id}/react-v2`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reaction }),
    }).catch(() => {});
  }

  // ── Reply ──
  function sendReply() {
    const story = STATE.stories[STATE.storyIndex];
    if (!story) return;
    const input = document.getElementById("nv-story-reply-input");
    if (!input || !input.value.trim()) return;

    const replyText = input.value.trim();
    input.value = "";
    document.getElementById("nv-story-send-btn").disabled = true;

    fetch(`/stories/api/stories/${story.id}/reply-v2`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reply_text: replyText }),
    }).catch(() => {});
  }

  // ── Delete ──
  function deleteCurrent() {
    const story = STATE.stories[STATE.storyIndex];
    if (!story) return;
    if (!confirm("Delete this story?")) return;

    fetch(`/stories/api/stories/${story.id}/delete-v2`, {
      method: "POST",
    }).then(r => r.json()).then(data => {
      if (data.ok) {
        STATE.stories.splice(STATE.storyIndex, 1);
        if (STATE.stories.length === 0) {
          closeViewer();
        } else {
          if (STATE.storyIndex >= STATE.stories.length) STATE.storyIndex = STATE.stories.length - 1;
          renderViewer();
          startStory();
        }
      }
    }).catch(() => {});
  }

  // ── Hold to Pause ──
  function holdStart() {
    STATE.isPaused = true;
    clearTimers();
  }

  function holdEnd() {
    STATE.isPaused = false;
    STATE._storyStart = Date.now() - (STATE._heldElapsed || 0);
    STATE.activeTimer = setTimeout(() => nextStory(), STORY_DURATION);
    STATE.progressInterval = setInterval(updateProgress, 100);
  }

  function clearTimers() {
    if (STATE.activeTimer) { clearTimeout(STATE.activeTimer); STATE.activeTimer = null; }
    if (STATE.progressInterval) { clearInterval(STATE.progressInterval); STATE.progressInterval = null; }
    if (STATE.holdTimeout) { clearTimeout(STATE.holdTimeout); STATE.holdTimeout = null; }
  }

  // ── Swipe to Close ──
  document.addEventListener("touchstart", (e) => {
    if (!STATE.viewerOpen) return;
    const target = e.target.closest(".nv-story-viewer-content, .nv-story-header, .nv-story-footer");
    if (target) {
      STATE.touchStartY = e.touches[0].clientY;
      STATE.touchStartX = e.touches[0].clientX;
    }
  }, { passive: true });

  document.addEventListener("touchmove", (e) => {
    if (!STATE.viewerOpen || STATE.touchStartY === 0) return;
    const dy = e.touches[0].clientY - STATE.touchStartY;
    if (dy > SWIPE_THRESHOLD) {
      STATE.touchStartY = 0;
      closeViewer();
    }
  }, { passive: true });

  document.addEventListener("touchend", () => {
    STATE.touchStartY = 0;
    STATE.touchStartX = 0;
  }, { passive: true });

  // ── Keyboard ──
  document.addEventListener("keydown", (e) => {
    if (!STATE.viewerOpen) return;
    switch (e.key) {
      case "ArrowRight":
      case " ": e.preventDefault(); nextStory(); break;
      case "ArrowLeft": e.preventDefault(); prevStory(); break;
      case "Escape": closeViewer(); break;
    }
  });

  // ── Utils ──
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
  const NV = {
    init, loadFeed, renderTray,
    openViewer, openHighlight, closeViewer,
    nextStory, prevStory, startStory,
    toggleEmojiPicker, sendReaction, sendReply,
    deleteCurrent,
    holdStart, holdEnd,
  };
  window.NamVibeStories = NV;

  // Auto-init
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
