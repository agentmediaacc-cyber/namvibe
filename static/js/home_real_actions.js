/* Phase 82: robust homepage action wiring for real feature APIs. */
(function () {
  'use strict';

  function toast(message) {
    var node = document.getElementById('nv-toast') || document.querySelector('.nv-toast');
    if (!node) {
      node = document.createElement('div');
      node.className = 'nv-toast';
      document.body.appendChild(node);
    }
    node.textContent = message || 'Done';
    node.classList.add('show', 'is-visible');
    clearTimeout(node._phase82Timer);
    node._phase82Timer = setTimeout(function () {
      node.classList.remove('show', 'is-visible');
    }, 2400);
  }

  function csrfHeaders(headers) {
    var finalHeaders = new Headers(headers || {});
    if (window.chainCsrfHeaders) return window.chainCsrfHeaders(finalHeaders);
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta && meta.getAttribute('content');
    if (token && !finalHeaders.has('X-CSRFToken')) finalHeaders.set('X-CSRFToken', token);
    return finalHeaders;
  }

  async function requestJson(url, options) {
    var finalOptions = Object.assign({ credentials: 'same-origin' }, options || {});
    finalOptions.headers = csrfHeaders(finalOptions.headers || { 'Content-Type': 'application/json' });
    var response = await fetch(url, finalOptions);
    if (response.redirected) {
      window.location.href = response.url;
      return null;
    }
    if (response.status === 401 || response.status === 403) {
      toast('Please log in to continue');
      return null;
    }
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  function setBusy(button, busy) {
    if (!button) return;
    button.disabled = !!busy;
    button.classList.toggle('is-loading', !!busy);
  }

  function updateCount(button, value, delta) {
    var span = button && button.querySelector('span');
    if (!span) return;
    if (Number.isFinite(Number(value))) {
      span.textContent = String(value);
      return;
    }
    var current = parseInt(span.textContent, 10) || 0;
    span.textContent = String(Math.max(0, current + (delta || 0)));
  }

  async function likeReel(button, reelId) {
    setBusy(button, true);
    try {
      var data = await requestJson('/reels/api/reels/' + encodeURIComponent(reelId) + '/like', { method: 'POST' });
      if (!data) return;
      var active = Boolean(data.liked || data.is_liked || data.success || data.ok);
      button.classList.toggle('is-liked', active);
      updateCount(button, data.likes_count != null ? data.likes_count : data.count, active ? 1 : -1);
      toast(active ? 'Liked' : 'Like removed');
    } catch (error) {
      toast(error.message || 'Could not like reel');
    } finally {
      setBusy(button, false);
    }
  }

  async function saveReel(button, reelId) {
    setBusy(button, true);
    try {
      var data = await requestJson('/reels/api/reels/' + encodeURIComponent(reelId) + '/save', { method: 'POST' });
      if (!data) return;
      var saved = Boolean(data.saved || data.is_saved || data.success || data.ok);
      button.classList.toggle('is-saved', saved);
      toast(saved ? 'Saved' : 'Removed from saved');
    } catch (error) {
      toast(error.message || 'Could not save reel');
    } finally {
      setBusy(button, false);
    }
  }

  async function shareReel(button, reelId) {
    setBusy(button, true);
    try {
      await requestJson('/reels/api/reels/' + encodeURIComponent(reelId) + '/share', { method: 'POST' });
      updateCount(button, null, 1);
      var url = window.location.origin + '/reels#reel-' + encodeURIComponent(reelId);
      if (navigator.share) {
        await navigator.share({ title: 'NamVibe reel', url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(url).catch(function () {});
      }
      toast('Share ready');
    } catch (error) {
      toast(error.message || 'Could not share reel');
    } finally {
      setBusy(button, false);
    }
  }

  function openComments(reelId) {
    var overlay = document.getElementById('nv-comment-overlay');
    if (!overlay) {
      window.location.href = '/reels#reel-' + encodeURIComponent(reelId);
      return;
    }
    overlay.classList.add('is-open');
    toast('Comments opened');
  }

  async function followProfile(button, profileId) {
    setBusy(button, true);
    try {
      var data = await requestJson('/social/follow/' + encodeURIComponent(profileId), { method: 'POST' });
      if (!data) return;
      var following = Boolean(data.following || data.is_following || data.follow_status === 'following' || data.success || data.ok);
      button.classList.toggle('is-following', following);
      var icon = button.querySelector('i');
      if (icon) icon.className = 'fas ' + (following ? 'fa-check' : 'fa-plus');
      if (!button.classList.contains('nv-follow-pill')) button.textContent = following ? 'Following' : 'Follow';
      toast(following ? 'Following' : 'Follow request updated');
    } catch (error) {
      toast(error.message || 'Could not update follow');
    } finally {
      setBusy(button, false);
    }
  }

  document.addEventListener('click', function (event) {
    var actionButton = event.target.closest('[data-action]');
    if (actionButton && actionButton.classList.contains('nv-action-btn')) {
      var action = actionButton.getAttribute('data-action');
      var reelId = actionButton.getAttribute('data-reel-id');
      if (!reelId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (action === 'like') likeReel(actionButton, reelId);
      else if (action === 'comment') openComments(reelId);
      else if (action === 'share') shareReel(actionButton, reelId);
      else if (action === 'save') saveReel(actionButton, reelId);
      return;
    }

    var followButton = event.target.closest('.nv-follow-pill, .nv-follow-btn, [data-profile-id]');
    if (followButton && (followButton.classList.contains('nv-follow-pill') || followButton.classList.contains('nv-follow-btn'))) {
      var profileId = followButton.getAttribute('data-profile-id');
      if (!profileId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      followProfile(followButton, profileId);
    }
  }, true);
})();
