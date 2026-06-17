document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  body.classList.add("has-premium-profile");

  document.querySelectorAll("[data-file-trigger]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.fileTrigger);
      if (input) input.click();
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.files && input.files.length && input.form) input.form.submit();
    });
  });

  const activateTab = (tabId, shouldScroll = false) => {
    if (!tabId || !document.getElementById(`${tabId}-content`)) return;
    document.querySelectorAll("[data-tab-target]").forEach((tab) => {
      const active = tab.dataset.tabTarget === tabId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".tab-content").forEach((panel) => {
      panel.hidden = panel.id !== `${tabId}-content`;
    });
    window.history.replaceState(null, "", `#${tabId}`);
    if (shouldScroll) {
      document.querySelector("[data-profile-tabs]")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  document.querySelectorAll("[data-tab-target]").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tabTarget, true));
  });
  activateTab(window.location.hash.replace("#", "") || "posts", false);

  const miniProfile = document.querySelector("[data-mini-profile]");
  if (miniProfile) {
    const updateMiniHeader = () => miniProfile.classList.toggle("is-visible", window.scrollY > 420);
    updateMiniHeader();
    window.addEventListener("scroll", updateMiniHeader, { passive: true });
  }

  document.querySelectorAll("[data-copy-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = `${window.location.origin}${button.dataset.copyProfile || window.location.pathname}`;
      try {
        await navigator.clipboard.writeText(url);
        const original = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i>Copied';
        window.setTimeout(() => {
          button.innerHTML = original;
        }, 1400);
      } catch (error) {
        window.prompt("Copy profile link", url);
      }
    });
  });

  document.querySelectorAll("[data-share-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = window.location.href;
      if (navigator.share) {
        try {
          await navigator.share({ title: document.title, url });
          return;
        } catch (error) {
          if (error.name === "AbortError") return;
        }
      }
      try {
        await navigator.clipboard.writeText(url);
      } catch (error) {
        window.prompt("Share profile link", url);
      }
    });
  });

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      [...body.classList].forEach((className) => {
        if (className.startsWith("profile-theme-")) body.classList.remove(className);
      });
      body.classList.add(`profile-theme-${button.dataset.themeChoice}`);
      document.querySelector(".premium-profile-shell")?.setAttribute("data-theme", button.dataset.themeChoice);
      localStorage.setItem("chain_profile_theme_preview", button.dataset.themeChoice);
    });
  });

  const savedTheme = localStorage.getItem("chain_profile_theme_preview");
  if (savedTheme && document.querySelector(".premium-profile-shell")) {
    body.classList.add(`profile-theme-${savedTheme}`);
    document.querySelector(".premium-profile-shell")?.setAttribute("data-theme", savedTheme);
  }

  const animateNumber = (element) => {
    const target = Number(element.dataset.countUp || "0");
    if (!Number.isFinite(target) || target <= 0) {
      element.textContent = "0";
      return;
    }
    const duration = 900;
    const start = performance.now();
    const formatter = new Intl.NumberFormat();
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = formatter.format(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  const countObserver = "IntersectionObserver" in window
    ? new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          animateNumber(entry.target);
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.4 })
    : null;

  document.querySelectorAll("[data-count-up]").forEach((counter) => {
    if (countObserver) countObserver.observe(counter);
    else animateNumber(counter);
  });

  const qrPopover = document.querySelector("[data-profile-qr-popover]");
  const qrCode = document.querySelector("[data-profile-qr-code]");
  const buildQr = (value) => {
    if (!qrCode) return;
    qrCode.innerHTML = "";
    const seed = [...String(value || window.location.href)].reduce((sum, char) => sum + char.charCodeAt(0), 0);
    for (let index = 0; index < 169; index += 1) {
      const cell = document.createElement("span");
      const row = Math.floor(index / 13);
      const col = index % 13;
      const finder =
        (row < 4 && col < 4) ||
        (row < 4 && col > 8) ||
        (row > 8 && col < 4);
      const dark = finder || ((index * 17 + seed + row * col) % 5 < 2);
      cell.classList.toggle("is-dark", dark);
      qrCode.appendChild(cell);
    }
  };

  document.querySelectorAll("[data-profile-qr]").forEach((button) => {
    button.addEventListener("click", () => {
      const path = button.dataset.profileUrl || window.location.pathname;
      buildQr(`${window.location.origin}${path}`);
      if (qrPopover) qrPopover.hidden = false;
    });
  });

  document.querySelectorAll("[data-profile-qr-close]").forEach((button) => {
    button.addEventListener("click", () => {
      if (qrPopover) qrPopover.hidden = true;
    });
  });

  qrPopover?.addEventListener("click", (event) => {
    if (event.target === qrPopover) qrPopover.hidden = true;
  });

  document.querySelectorAll("[data-profile-follow]").forEach((button) => {
    button.addEventListener("click", async () => {
      const profileId = button.dataset.profileId;
      if (!profileId || button.disabled) return;
      button.disabled = true;
      try {
        const response = await fetch(`/social/follow/${profileId}`, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("Follow request failed");
        const following = button.dataset.following !== "true";
        document.querySelectorAll(`[data-profile-follow][data-profile-id="${profileId}"]`).forEach((followButton) => {
          followButton.dataset.following = following ? "true" : "false";
          followButton.innerHTML = following
            ? '<i class="fas fa-user-check"></i><span>Following</span>'
            : '<i class="fas fa-user-plus"></i><span>Follow</span>';
        });
      } catch (error) {
        console.error("Follow action failed", error);
      } finally {
        button.disabled = false;
      }
    });
  });
});

/* Phase 84 — Profile Manager Interactive Functions */
async function toggleComments(postId) {
  try {
    const r = await fetch(`/profile/api/posts/${postId}/comments-toggle`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') alert(d.comments_enabled ? 'Comments enabled' : 'Comments disabled');
    else alert('Failed to toggle comments');
  } catch (e) { alert('Request failed'); }
}

async function toggleSharing(postId) {
  try {
    const r = await fetch(`/profile/api/posts/${postId}/share-toggle`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') alert(d.sharing_enabled ? 'Sharing enabled' : 'Sharing disabled');
    else alert('Failed to toggle sharing');
  } catch (e) { alert('Request failed'); }
}

async function togglePin(itemId, type) {
  try {
    const endpoint = type === 'reel' ? `/profile/api/reels/${itemId}/pin` : `/profile/api/posts/${itemId}/pin`;
    const r = await fetch(endpoint, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') alert(d.pinned ? 'Pinned' : 'Unpinned');
    else alert('Failed to toggle pin');
  } catch (e) { alert('Request failed'); }
}

async function deleteItem(itemId, type) {
  if (!confirm(`Delete this ${type}?`)) return;
  try {
    const endpoint = type === 'reel' ? `/profile/api/reels/${itemId}` : `/profile/api/posts/${itemId}`;
    const r = await fetch(endpoint, { method: 'DELETE' });
    const d = await r.json();
    if (d.status === 'ok') {
      document.querySelector(`[data-${type}-id="${itemId}"]`)?.remove();
      alert(`${type} deleted`);
    } else alert('Failed to delete');
  } catch (e) { alert('Request failed'); }
}

async function toggleReelComments(reelId) {
  try {
    const r = await fetch(`/profile/api/reels/${reelId}/comments-toggle`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') alert(d.comments_enabled ? 'Comments enabled' : 'Comments disabled');
    else alert('Failed to toggle comments');
  } catch (e) { alert('Request failed'); }
}

async function showReelAnalytics(reelId) {
  try {
    const r = await fetch(`/profile/api/reels/analytics/${reelId}`);
    const d = await r.json();
    alert(`Views: ${d.views || 0}\nLikes: ${d.likes || 0}\nComments: ${d.comments || 0}`);
  } catch (e) { alert('Failed to load analytics'); }
}

function showVisibilityModal(itemId, type, currentVisibility) {
  const overlay = document.createElement('div');
  overlay.className = 'visibility-modal-overlay';
  overlay.innerHTML = `
    <div class="visibility-modal">
      <h3>Change Visibility</h3>
      <select id="vis-select">
        <option value="public" ${currentVisibility === 'public' ? 'selected' : ''}>Public</option>
        <option value="followers" ${currentVisibility === 'followers' ? 'selected' : ''}>Followers</option>
        <option value="friends" ${currentVisibility === 'friends' ? 'selected' : ''}>Friends</option>
        <option value="private" ${currentVisibility === 'private' ? 'selected' : ''}>Private</option>
      </select>
      <div class="modal-actions">
        <button class="btn-cancel" onclick="this.closest('.visibility-modal-overlay').remove()">Cancel</button>
        <button class="btn-save" onclick="saveVisibility('${itemId}', '${type}')">Save</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
}

async function saveVisibility(itemId, type) {
  const select = document.getElementById('vis-select');
  const visibility = select.value;
  const endpoint = type === 'reel' ? `/profile/api/reels/${itemId}/visibility` : `/profile/api/posts/${itemId}/visibility`;
  try {
    const r = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visibility }) });
    const d = await r.json();
    if (d.status === 'ok') { alert('Visibility updated'); document.querySelector('.visibility-modal-overlay')?.remove(); location.reload(); }
    else alert('Failed to update visibility');
  } catch (e) { alert('Request failed'); }
}

async function followUser(profileId, btn) {
  try {
    const r = await fetch(`/social/follow/${profileId}`, { method: 'POST', headers: { Accept: 'application/json' } });
    const d = await r.json();
    if (d.status === 'ok') {
      if (btn) { btn.innerHTML = '<i class="fas fa-user-check"></i>'; btn.onclick = null; }
      alert('Following');
    }
  } catch (e) { alert('Request failed'); }
}

async function unfollowUser(profileId) {
  if (!confirm('Unfollow?')) return;
  try {
    const r = await fetch(`/social/following/remove/${profileId}`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') { alert('Unfollowed'); location.reload(); }
    else alert('Failed to unfollow');
  } catch (e) { alert('Request failed'); }
}

async function removeFollower(profileId) {
  if (!confirm('Remove this follower?')) return;
  try {
    const r = await fetch(`/social/followers/remove/${profileId}`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') { alert('Follower removed'); location.reload(); }
    else alert('Failed to remove follower');
  } catch (e) { alert('Request failed'); }
}

async function blockUser(profileId) {
  if (!confirm('Block this user?')) return;
  try {
    const r = await fetch(`/social/block/${profileId}`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok' || d.ok) { alert('Blocked'); location.reload(); }
    else alert('Failed to block');
  } catch (e) { alert('Request failed'); }
}

async function sendFriendRequest(profileId) {
  try {
    const r = await fetch('/social/friends/request', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ receiver_profile_id: profileId }) });
    const d = await r.json();
    if (d.status === 'ok' || d.success) alert('Friend request sent');
    else alert(d.error || 'Failed to send request');
  } catch (e) { alert('Request failed'); }
}

async function acceptFriendRequest(requestId) {
  try {
    const r = await fetch('/social/friends/accept', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request_id: requestId }) });
    const d = await r.json();
    if (d.status === 'ok' || d.success) { alert('Friend request accepted'); location.reload(); }
    else alert('Failed to accept');
  } catch (e) { alert('Request failed'); }
}

async function declineFriendRequest(requestId) {
  if (!confirm('Decline friend request?')) return;
  try {
    const r = await fetch('/social/friends/decline', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request_id: requestId }) });
    if (r.ok) { alert('Declined'); location.reload(); }
    else alert('Failed to decline');
  } catch (e) { alert('Request failed'); }
}

async function removeFriend(profileId) {
  if (!confirm('Remove this friend?')) return;
  try {
    const r = await fetch('/social/friends/remove', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ friend_id: profileId }) });
    const d = await r.json();
    if (d.status === 'ok' || d.success) { alert('Friend removed'); location.reload(); }
    else alert('Failed to remove');
  } catch (e) { alert('Request failed'); }
}

async function muteUser(profileId) {
  const type = prompt('Mute type: posts, reels, stories, or all', 'posts');
  if (!type) return;
  try {
    const r = await fetch('/profile/api/mute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile_id: profileId, mute_type: type }) });
    const d = await r.json();
    if (d.status === 'ok') alert('Muted');
    else alert('Failed to mute');
  } catch (e) { alert('Request failed'); }
}
