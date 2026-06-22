/**
 * Phase 86 – Profile Systems
 * Posts/Reels/Followers/Following/Friends managers with cursor pagination.
 */
(function () {
  'use strict';

  /* ── Helpers ─────────────────────────────────────────────── */

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  const API = {
    async get(url) { const r = await fetch(url); return r.json(); },
    async post(url, body) {
      const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' };
      const r = await fetch(url, {
        method: 'POST',
        headers,
        credentials: 'same-origin',
        body: body ? JSON.stringify(body) : undefined,
      });
      return r.json();
    },
    async del(url) { const r = await fetch(url, { method: 'DELETE' }); return r.json(); },
  };

  function toast(msg, type) {
    const el = document.getElementById('sysToast');
    if (el) { el.textContent = msg; el.className = 'sys-toast ' + (type || 'info'); el.style.display = 'block'; setTimeout(() => { el.style.display = 'none'; }, 3000); }
    else { alert(msg); }
  }

  function confirmAction(msg) {
    return window.confirm(msg);
  }

  /* ── Cursor Pagination Loader ────────────────────────────── */

  const cursors = {};

  async function loadMore(endpoint, listId, config) {
    const list = document.getElementById(listId);
    const btn = list?.querySelector('.load-more-btn');
    if (!list || !btn) return;
    const cursor = cursors[listId];
    const url = endpoint + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : '') + `&limit=20`;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading…';
    try {
      const data = await API.get(url);
      const items = data.items || data.friends || data.followers || data.following || data.requests || data.posts || data.reels || [];
      const container = list.querySelector('.people-list') || list.querySelector('.manager-grid');
      if (!container) return;
      items.forEach(item => {
        const card = config.renderCard(item);
        if (card) container.appendChild(card);
      });
      if (data.next_cursor) {
        cursors[listId] = data.next_cursor;
        btn.style.display = 'inline-flex';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-chevron-down"></i> Load more';
      } else {
        btn.style.display = 'none';
      }
    } catch {
      toast('Failed to load', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-chevron-down"></i> Load more';
    }
  }

  /* ── Post Manager ────────────────────────────────────────── */

  window.Phase86 = window.Phase86 || {};

  Phase86.toggleComments = async (postId) => {
    const d = await API.post(`/profile/api/posts/${postId}/comments-toggle`);
    toast(d.comments_enabled ? 'Comments enabled' : 'Comments disabled');
  };

  Phase86.toggleSharing = async (postId) => {
    const d = await API.post(`/profile/api/posts/${postId}/share-toggle`);
    toast(d.sharing_enabled ? 'Sharing enabled' : 'Sharing disabled');
  };

  Phase86.togglePin = async (itemId, type) => {
    const ep = type === 'reel' ? `/profile/api/reels/${itemId}/pin` : `/profile/api/posts/${itemId}/pin`;
    const d = await API.post(ep);
    toast(d.pinned ? 'Pinned' : 'Unpinned');
    if (d.pinned !== undefined) location.reload();
  };

  Phase86.toggleArchive = async (itemId, type) => {
    const ep = type === 'reel' ? `/profile/api/reels/${itemId}/archive` : `/profile/api/posts/${itemId}/archive`;
    const d = await API.post(ep);
    toast(d.archived ? 'Archived' : 'Unarchived');
    if (d.status === 'ok') location.reload();
  };

  Phase86.deleteItem = async (itemId, type) => {
    if (!confirmAction(`Delete this ${type}?`)) return;
    const ep = type === 'reel' ? `/profile/api/reels/${itemId}` : `/profile/api/posts/${itemId}`;
    const d = await API.del(ep);
    if (d.status === 'ok') {
      const card = document.querySelector(`[data-item-id="${itemId}"]`);
      if (card) card.remove();
      toast(`${type} deleted`);
    } else toast('Failed to delete', 'error');
  };

  Phase86.showVisibilityModal = (itemId, type, currentVis) => {
    const overlay = document.createElement('div');
    overlay.className = 'vis-modal-overlay';
    overlay.innerHTML = `
      <div class="vis-modal">
        <h3>Change Visibility</h3>
        <select id="vis-select">
          <option value="public" ${currentVis === 'public' ? 'selected' : ''}>Public</option>
          <option value="followers" ${currentVis === 'followers' ? 'selected' : ''}>Followers</option>
          <option value="friends" ${currentVis === 'friends' ? 'selected' : ''}>Friends</option>
          <option value="private" ${currentVis === 'private' ? 'selected' : ''}>Private</option>
        </select>
        <div class="vis-modal-actions">
          <button class="btn-cancel" onclick="this.closest('.vis-modal-overlay').remove()">Cancel</button>
          <button class="btn-save" onclick="Phase86.saveVisibility('${itemId}', '${type}')">Save</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
  };

  Phase86.saveVisibility = async (itemId, type) => {
    const sel = document.getElementById('vis-select');
    if (!sel) return;
    const ep = type === 'reel' ? `/profile/api/reels/${itemId}/visibility` : `/profile/api/posts/${itemId}/visibility`;
    const d = await API.post(ep, { visibility: sel.value });
    if (d.status === 'ok') {
      toast('Visibility updated');
      const ov = document.querySelector('.vis-modal-overlay');
      if (ov) ov.remove();
      location.reload();
    } else toast('Failed to update visibility', 'error');
  };

  Phase86.showReelAnalytics = async (reelId) => {
    const d = await API.get(`/profile/api/reels/analytics/${reelId}`);
    toast(`Views: ${d.views || 0}  Likes: ${d.likes || 0}  Comments: ${d.comments || 0}`, 'info');
  };

  /* ── Follower / Following ────────────────────────────────── */

  Phase86.followUser = async (profileId, btn) => {
    const d = await API.post(`/social/follow/${profileId}`);
    if (d.status === 'ok') {
      if (btn) { 
        if (d.following) {
          btn.innerHTML = '<i class="fas fa-user-check"></i> Following'; 
          btn.dataset.following = 'true'; 
        } else {
          btn.innerHTML = '<i class="fas fa-user-plus"></i> Follow'; 
          btn.dataset.following = 'false';
        }
      }
      toast(d.following ? 'Following' : 'Unfollowed');
    } else toast(d.error || 'Failed', 'error');
  };

  Phase86.unfollowUser = async (profileId) => {
    if (!confirmAction('Unfollow?')) return;
    const d = await API.post(`/social/follow/${profileId}`);
    if (d.status === 'ok') { toast('Unfollowed'); location.reload(); }
    else toast('Failed to unfollow', 'error');
  };

  Phase86.removeFollower = async (profileId) => {
    if (!confirmAction('Remove this follower?')) return;
    const d = await API.post(`/social/followers/remove/${profileId}`);
    if (d.status === 'ok') { toast('Follower removed'); location.reload(); }
    else toast('Failed to remove', 'error');
  };

  Phase86.blockUser = async (profileId) => {
    if (!confirmAction('Block this user?')) return;
    const d = await API.post(`/social/block/${profileId}`);
    if (d.status === 'ok' || d.ok) { toast('Blocked'); location.reload(); }
    else toast('Failed to block', 'error');
  };

  Phase86.muteUser = async (profileId) => {
    const type = prompt('Mute: posts, reels, stories, or all', 'posts');
    if (!type) return;
    const d = await API.post('/profile/api/mute', { profile_id: profileId, mute_type: type });
    if (d.status === 'ok') toast('Muted');
    else toast('Failed to mute', 'error');
  };

  /* ── Friend System ───────────────────────────────────────── */

  Phase86.sendFriendRequest = async (profileId) => {
    const d = await API.post('/social/friends/request', { recipient_id: profileId });
    if (d.success || d.status === 'ok') { toast('Friend request sent!'); location.reload(); }
    else toast(d.error || 'Failed to send request', 'error');
  };

  Phase86.acceptFriendRequest = async (requestId) => {
    const d = await API.post(`/social/friends/accept`, { request_id: requestId });
    if (d.success || d.status === 'ok') { toast('Friend request accepted!'); location.reload(); }
    else toast('Failed to accept', 'error');
  };

  Phase86.declineFriendRequest = async (requestId) => {
    if (!confirmAction('Decline friend request?')) return;
    const d = await API.post(`/social/friends/decline`, { request_id: requestId });
    if (d.success || d.status === 'ok') { toast('Declined'); location.reload(); }
    else toast('Failed to decline', 'error');
  };

  Phase86.cancelFriendRequest = async (requestId) => {
    if (!confirmAction('Cancel friend request?')) return;
    const d = await API.post(`/social/friends/cancel`, { request_id: requestId });
    if (d.success || d.status === 'ok') { toast('Request cancelled'); location.reload(); }
    else toast('Failed to cancel', 'error');
  };

  Phase86.removeFriend = async (profileId) => {
    if (!confirmAction('Remove this friend?')) return;
    const d = await API.post(`/social/friends/remove`, { friend_id: profileId });
    if (d.success || d.status === 'ok') { toast('Friend removed'); location.reload(); }
    else toast('Failed to remove', 'error');
  };

  Phase86.toggleCloseFriend = async (friendId, enabled) => {
    const d = await API.post(`/social/friends/${friendId}/close`, { enabled });
    if (d.status === 'ok') toast(d.close_friend ? 'Marked as close friend' : 'Removed close friend');
    else toast('Failed', 'error');
  };

  Phase86.toggleBestFriend = async (friendId, enabled) => {
    const d = await API.post(`/social/friends/${friendId}/best`, { enabled });
    if (d.status === 'ok') toast(d.best_friend ? 'Marked as best friend' : 'Removed best friend');
    else toast('Failed', 'error');
  };

  /* ── Load More Helpers ───────────────────────────────────── */

  Phase86.loadMoreFollowers = (profileId, listId) => {
    return loadMore(`/social/api/followers?profile_id=${profileId}`, listId, {
      renderCard: (item) => {
        const div = document.createElement('div');
        div.className = 'people-card';
        div.innerHTML = `
          <div class="people-avatar">${item.avatar_url ? `<img src="${item.avatar_url}" alt="">` : `<span>${(item.display_name || item.username || 'U')[0].toUpperCase()}</span>`}</div>
          <div class="people-info"><strong>${item.display_name || item.username || 'User'}</strong><span>@${item.username || 'user'}</span></div>
          <div class="people-actions">
            <a href="/profile/${item.username}" class="action-btn" title="View"><i class="fas fa-user"></i></a>
            <button class="action-btn" title="Message" onclick="window.location='/messages/start/${item.follower_profile_id || item.profile_id}'"><i class="fas fa-comment"></i></button>
            <button class="action-btn" title="Follow" onclick="Phase86.followUser('${item.follower_profile_id || item.profile_id}', this)"><i class="fas fa-user-plus"></i></button>
          </div>`;
        return div;
      },
    });
  };

  Phase86.loadMoreFollowing = (profileId, listId, type) => {
    return loadMore(`/social/api/following?profile_id=${profileId}&type=${type || 'all'}`, listId, {
      renderCard: (item) => {
        const div = document.createElement('div');
        div.className = 'people-card';
        div.innerHTML = `
          <div class="people-avatar">${item.avatar_url ? `<img src="${item.avatar_url}" alt="">` : `<span>${(item.display_name || item.username || 'U')[0].toUpperCase()}</span>`}</div>
          <div class="people-info"><strong>${item.display_name || item.username || 'User'}</strong><span>@${item.username || 'user'}</span></div>
          <div class="people-actions">
            <a href="/profile/${item.username}" class="action-btn" title="View"><i class="fas fa-user"></i></a>
            <button class="action-btn" title="Message" onclick="window.location='/messages/start/${item.following_profile_id || item.profile_id}'"><i class="fas fa-comment"></i></button>
            <button class="action-btn danger" title="Unfollow" onclick="Phase86.unfollowUser('${item.following_profile_id || item.profile_id}')"><i class="fas fa-user-slash"></i></button>
          </div>`;
        return div;
      },
    });
  };

  /* ── Init ────────────────────────────────────────────────── */

  Phase86.init = function () {
    document.querySelectorAll('[data-action="toggle-comments"]').forEach(el => {
      el.addEventListener('click', () => Phase86.toggleComments(el.dataset.id));
    });
    document.querySelectorAll('[data-action="toggle-sharing"]').forEach(el => {
      el.addEventListener('click', () => Phase86.toggleSharing(el.dataset.id));
    });
    document.querySelectorAll('[data-action="toggle-pin"]').forEach(el => {
      el.addEventListener('click', () => Phase86.togglePin(el.dataset.id, el.dataset.type || 'post'));
    });
    document.querySelectorAll('[data-action="toggle-archive"]').forEach(el => {
      el.addEventListener('click', () => Phase86.toggleArchive(el.dataset.id, el.dataset.type || 'post'));
    });
    document.querySelectorAll('[data-action="delete-item"]').forEach(el => {
      el.addEventListener('click', () => Phase86.deleteItem(el.dataset.id, el.dataset.type || 'post'));
    });
    document.querySelectorAll('[data-action="show-visibility"]').forEach(el => {
      el.addEventListener('click', () => Phase86.showVisibilityModal(el.dataset.id, el.dataset.type || 'post', el.dataset.vis || 'public'));
    });
    document.querySelectorAll('[data-action="reel-analytics"]').forEach(el => {
      el.addEventListener('click', () => Phase86.showReelAnalytics(el.dataset.id));
    });
    document.querySelectorAll('[data-action="follow"]').forEach(el => {
      el.addEventListener('click', () => Phase86.followUser(el.dataset.id, el));
    });
    document.querySelectorAll('[data-action="unfollow"]').forEach(el => {
      el.addEventListener('click', () => Phase86.unfollowUser(el.dataset.id));
    });
    document.querySelectorAll('[data-action="remove-follower"]').forEach(el => {
      el.addEventListener('click', () => Phase86.removeFollower(el.dataset.id));
    });
    document.querySelectorAll('[data-action="block"]').forEach(el => {
      el.addEventListener('click', () => Phase86.blockUser(el.dataset.id));
    });
    document.querySelectorAll('[data-action="mute"]').forEach(el => {
      el.addEventListener('click', () => Phase86.muteUser(el.dataset.id));
    });
    document.querySelectorAll('[data-action="send-friend-request"]').forEach(el => {
      el.addEventListener('click', () => Phase86.sendFriendRequest(el.dataset.id));
    });
    document.querySelectorAll('[data-action="accept-friend"]').forEach(el => {
      el.addEventListener('click', () => Phase86.acceptFriendRequest(el.dataset.id));
    });
    document.querySelectorAll('[data-action="decline-friend"]').forEach(el => {
      el.addEventListener('click', () => Phase86.declineFriendRequest(el.dataset.id));
    });
    document.querySelectorAll('[data-action="cancel-friend-request"]').forEach(el => {
      el.addEventListener('click', () => Phase86.cancelFriendRequest(el.dataset.id));
    });
    document.querySelectorAll('[data-action="remove-friend"]').forEach(el => {
      el.addEventListener('click', () => Phase86.removeFriend(el.dataset.id));
    });
    document.querySelectorAll('[data-action="close-friend"]').forEach(el => {
      el.addEventListener('click', () => Phase86.toggleCloseFriend(el.dataset.id, el.dataset.enabled !== 'false'));
    });
    document.querySelectorAll('[data-action="best-friend"]').forEach(el => {
      el.addEventListener('click', () => Phase86.toggleBestFriend(el.dataset.id, el.dataset.enabled !== 'false'));
    });
    document.querySelectorAll('[data-load-more]').forEach(el => {
      const handler = window[el.dataset.loadMore];
      if (typeof handler === 'function') {
        el.addEventListener('click', () => handler());
      }
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', Phase86.init);
  } else {
    Phase86.init();
  }
})();
