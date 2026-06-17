(function () {
  window.Phase85 = window.Phase85 || {};

  const API = {
    async post(url, body) {
      const r = await fetch(url, {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      return r.json();
    },

    async del(url) {
      const r = await fetch(url, { method: 'DELETE' });
      return r.json();
    },

    async get(url) {
      const r = await fetch(url);
      return r.json();
    },
  };

  /* ── Post / Reel Management ─────────────────────────────── */

  Phase85.toggleComments = async function (postId) {
    try {
      const d = await API.post(`/profile/api/posts/${postId}/comments-toggle`);
      if (d.status === 'ok') alert(d.comments_enabled ? 'Comments enabled' : 'Comments disabled');
      else alert('Failed to toggle comments');
    } catch { alert('Request failed'); }
  };

  Phase85.toggleSharing = async function (postId) {
    try {
      const d = await API.post(`/profile/api/posts/${postId}/share-toggle`);
      if (d.status === 'ok') alert(d.sharing_enabled ? 'Sharing enabled' : 'Sharing disabled');
      else alert('Failed to toggle sharing');
    } catch { alert('Request failed'); }
  };

  Phase85.togglePin = async function (itemId, type) {
    try {
      const endpoint = type === 'reel'
        ? `/profile/api/reels/${itemId}/pin`
        : `/profile/api/posts/${itemId}/pin`;
      const d = await API.post(endpoint);
      if (d.status === 'ok') alert(d.pinned ? 'Pinned' : 'Unpinned');
      else alert('Failed to toggle pin');
    } catch { alert('Request failed'); }
  };

  Phase85.toggleArchive = async function (itemId, type) {
    try {
      const endpoint = type === 'reel'
        ? `/profile/api/reels/${itemId}/archive`
        : `/profile/api/posts/${itemId}/archive`;
      const d = await API.post(endpoint);
      if (d.status === 'ok') alert(d.archived ? 'Archived' : 'Unarchived');
      else alert('Failed to toggle archive');
    } catch { alert('Request failed'); }
  };

  Phase85.deleteItem = async function (itemId, type) {
    if (!confirm(`Delete this ${type}?`)) return;
    try {
      const endpoint = type === 'reel'
        ? `/profile/api/reels/${itemId}`
        : `/profile/api/posts/${itemId}`;
      const d = await API.del(endpoint);
      if (d.status === 'ok') {
        const card = document.querySelector(`[data-${type}-id="${itemId}"]`);
        if (card) card.remove();
        alert(`${type} deleted`);
      } else alert('Failed to delete');
    } catch { alert('Request failed'); }
  };

  /* ── Visibility ─────────────────────────────────────────── */

  Phase85.showVisibilityModal = function (itemId, type, currentVis) {
    const overlay = document.createElement('div');
    overlay.className = 'visibility-modal-overlay';
    overlay.innerHTML = `
      <div class="visibility-modal">
        <h3>Change Visibility</h3>
        <select id="vis-select">
          <option value="public" ${currentVis === 'public' ? 'selected' : ''}>Public</option>
          <option value="followers" ${currentVis === 'followers' ? 'selected' : ''}>Followers</option>
          <option value="friends" ${currentVis === 'friends' ? 'selected' : ''}>Friends</option>
          <option value="private" ${currentVis === 'private' ? 'selected' : ''}>Private</option>
        </select>
        <div class="modal-actions">
          <button class="btn-cancel" onclick="this.closest('.visibility-modal-overlay').remove()">Cancel</button>
          <button class="btn-save" onclick="Phase85.saveVisibility('${itemId}', '${type}')">Save</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
  };

  Phase85.saveVisibility = async function (itemId, type) {
    const select = document.getElementById('vis-select');
    if (!select) return;
    const visibility = select.value;
    const endpoint = type === 'reel'
      ? `/profile/api/reels/${itemId}/visibility`
      : `/profile/api/posts/${itemId}/visibility`;
    try {
      const d = await API.post(endpoint, { visibility });
      if (d.status === 'ok') {
        alert('Visibility updated');
        const overlay = document.querySelector('.visibility-modal-overlay');
        if (overlay) overlay.remove();
        location.reload();
      } else alert('Failed to update visibility');
    } catch { alert('Request failed'); }
  };

  /* ── Reel Analytics ─────────────────────────────────────── */

  Phase85.showReelAnalytics = async function (reelId) {
    try {
      const d = await API.get(`/profile/api/reels/analytics/${reelId}`);
      alert(`Views: ${d.views || 0}\nLikes: ${d.likes || 0}\nComments: ${d.comments || 0}`);
    } catch { alert('Failed to load analytics'); }
  };

  /* ── Friend / Follow / Block / Mute ─────────────────────── */

  Phase85.sendFriendRequest = async function (profileId) {
    try {
      const d = await API.post('/social/friends/request', { receiver_profile_id: profileId });
      if (d.status === 'ok' || d.success) alert('Friend request sent');
      else alert(d.error || 'Failed to send request');
    } catch { alert('Request failed'); }
  };

  Phase85.acceptFriendRequest = async function (requestId) {
    try {
      const d = await API.post('/social/friends/accept', { request_id: requestId });
      if (d.status === 'ok' || d.success) { alert('Friend request accepted'); location.reload(); }
      else alert('Failed to accept');
    } catch { alert('Request failed'); }
  };

  Phase85.declineFriendRequest = async function (requestId) {
    if (!confirm('Decline friend request?')) return;
    try {
      const r = await fetch('/social/friends/decline', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request_id: requestId }) });
      if (r.ok) { alert('Declined'); location.reload(); }
      else alert('Failed to decline');
    } catch { alert('Request failed'); }
  };

  Phase85.removeFriend = async function (profileId) {
    if (!confirm('Remove this friend?')) return;
    try {
      const d = await API.post('/social/friends/remove', { friend_id: profileId });
      if (d.status === 'ok' || d.success) { alert('Friend removed'); location.reload(); }
      else alert('Failed to remove');
    } catch { alert('Request failed'); }
  };

  Phase85.followUser = async function (profileId, btn) {
    try {
      const r = await fetch(`/social/follow/${profileId}`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
      });
      const d = await r.json();
      if (d.status === 'ok') {
        if (btn) {
          btn.innerHTML = '<i class="fas fa-user-check"></i><span>Following</span>';
          btn.dataset.following = 'true';
        }
        alert('Following');
      }
    } catch { alert('Request failed'); }
  };

  Phase85.unfollowUser = async function (profileId) {
    if (!confirm('Unfollow?')) return;
    try {
      const d = await API.post(`/social/following/remove/${profileId}`);
      if (d.status === 'ok') { alert('Unfollowed'); location.reload(); }
      else alert('Failed to unfollow');
    } catch { alert('Request failed'); }
  };

  Phase85.removeFollower = async function (profileId) {
    if (!confirm('Remove this follower?')) return;
    try {
      const d = await API.post(`/social/followers/remove/${profileId}`);
      if (d.status === 'ok') { alert('Follower removed'); location.reload(); }
      else alert('Failed to remove follower');
    } catch { alert('Request failed'); }
  };

  Phase85.blockUser = async function (profileId) {
    if (!confirm('Block this user?')) return;
    try {
      const r = await fetch(`/social/block/${profileId}`, { method: 'POST' });
      const d = await r.json();
      if (d.status === 'ok' || d.ok) { alert('Blocked'); location.reload(); }
      else alert('Failed to block');
    } catch { alert('Request failed'); }
  };

  Phase85.muteUser = async function (profileId) {
    const type = prompt('Mute type: posts, reels, stories, or all', 'posts');
    if (!type) return;
    try {
      const d = await API.post('/profile/api/mute', { profile_id: profileId, mute_type: type });
      if (d.status === 'ok') alert('Muted');
      else alert('Failed to mute');
    } catch { alert('Request failed'); }
  };

  /* ── Lazy Tab Loading ───────────────────────────────────── */

  Phase85.loadTab = async function (tabName) {
    const container = document.getElementById(`${tabName}-content`);
    if (!container || container.dataset.loaded) return;
    container.dataset.loaded = 'true';
    container.innerHTML = '<div class="tab-lazy-placeholder">Loading…</div>';
    try {
      const r = await fetch(`/profile/tab/${tabName}`);
      if (!r.ok) throw new Error('Tab load failed');
      const html = await r.text();
      container.innerHTML = html;
    } catch {
      container.innerHTML = '<div class="manager-empty"><i class="fas fa-exclamation-triangle"></i><p>Failed to load</p></div>';
    }
  };

  /* ── Init ────────────────────────────────────────────────── */

  Phase85.init = function () {
    document.querySelectorAll('[data-toggle-comments]').forEach((el) => {
      el.addEventListener('click', () => Phase85.toggleComments(el.dataset.toggleComments));
    });

    document.querySelectorAll('[data-toggle-sharing]').forEach((el) => {
      el.addEventListener('click', () => Phase85.toggleSharing(el.dataset.toggleSharing));
    });

    document.querySelectorAll('[data-toggle-pin]').forEach((el) => {
      el.addEventListener('click', () => Phase85.togglePin(el.dataset.togglePin, el.dataset.type || 'post'));
    });

    document.querySelectorAll('[data-toggle-archive]').forEach((el) => {
      el.addEventListener('click', () => Phase85.toggleArchive(el.dataset.toggleArchive, el.dataset.type || 'post'));
    });

    document.querySelectorAll('[data-delete-item]').forEach((el) => {
      el.addEventListener('click', () => Phase85.deleteItem(el.dataset.deleteItem, el.dataset.type || 'post'));
    });

    document.querySelectorAll('[data-visibility]').forEach((el) => {
      el.addEventListener('click', () => Phase85.showVisibilityModal(el.dataset.visibility, el.dataset.type || 'post', el.dataset.currentVis || 'public'));
    });

    document.querySelectorAll('[data-reel-analytics]').forEach((el) => {
      el.addEventListener('click', () => Phase85.showReelAnalytics(el.dataset.reelAnalytics));
    });

    document.querySelectorAll('[data-send-friend-request]').forEach((el) => {
      el.addEventListener('click', () => Phase85.sendFriendRequest(el.dataset.sendFriendRequest));
    });

    document.querySelectorAll('[data-accept-friend]').forEach((el) => {
      el.addEventListener('click', () => Phase85.acceptFriendRequest(el.dataset.acceptFriend));
    });

    document.querySelectorAll('[data-decline-friend]').forEach((el) => {
      el.addEventListener('click', () => Phase85.declineFriendRequest(el.dataset.declineFriend));
    });

    document.querySelectorAll('[data-remove-friend]').forEach((el) => {
      el.addEventListener('click', () => Phase85.removeFriend(el.dataset.removeFriend));
    });

    document.querySelectorAll('[data-follow-user]').forEach((el) => {
      el.addEventListener('click', () => Phase85.followUser(el.dataset.followUser, el));
    });

    document.querySelectorAll('[data-unfollow-user]').forEach((el) => {
      el.addEventListener('click', () => Phase85.unfollowUser(el.dataset.unfollowUser));
    });

    document.querySelectorAll('[data-remove-follower]').forEach((el) => {
      el.addEventListener('click', () => Phase85.removeFollower(el.dataset.removeFollower));
    });

    document.querySelectorAll('[data-block-user]').forEach((el) => {
      el.addEventListener('click', () => Phase85.blockUser(el.dataset.blockUser));
    });

    document.querySelectorAll('[data-mute-user]').forEach((el) => {
      el.addEventListener('click', () => Phase85.muteUser(el.dataset.muteUser));
    });

    document.querySelectorAll('[data-lazy-tab]').forEach((el) => {
      el.addEventListener('click', () => Phase85.loadTab(el.dataset.lazyTab));
    });

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const tab = entry.target.dataset.lazyTabObserve;
          if (tab) Phase85.loadTab(tab);
          observer.unobserve(entry.target);
        });
      }, { rootMargin: '200px' });

      document.querySelectorAll('[data-lazy-tab-observe]').forEach((el) => observer.observe(el));
    }

    document.querySelectorAll('.command-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.command-tab').forEach((t) => t.classList.remove('is-active'));
        tab.classList.add('is-active');
        const target = tab.dataset.tabTarget;
        if (target) Phase85.loadTab(target);
      });
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', Phase85.init);
  } else {
    Phase85.init();
  }
})();
