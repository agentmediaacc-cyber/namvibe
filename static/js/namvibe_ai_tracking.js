(function () {
  var state = {
    enabled: false,
    queue: [],
    pendingStatus: false,
    seen: {},
    maxQueue: 50,
    reelSessions: {}
  };

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function enqueue(item) {
    if (!state.enabled || !item || !item.target_type || !item.target_id || !item.action_type) {
      return;
    }
    var dedupeKey = [item.target_type, item.target_id, item.action_type, item.source_surface || ''].join(':');
    if (item.action_type === 'impression' && state.seen[dedupeKey]) {
      return;
    }
    if (item.action_type === 'impression') {
      state.seen[dedupeKey] = true;
    }
    if (state.queue.length >= state.maxQueue) {
      state.queue.shift();
    }
    state.queue.push({
      target_type: item.target_type,
      target_id: String(item.target_id).slice(0, 200),
      action_type: item.action_type,
      source_surface: item.source_surface ? String(item.source_surface).slice(0, 80) : undefined,
      dwell_time_ms: typeof item.dwell_time_ms === 'number' ? item.dwell_time_ms : undefined,
      metadata: sanitizeMetadata(item.metadata)
    });
  }

  function sanitizeMetadata(metadata) {
    var allowed = {};
    if (!metadata || typeof metadata !== 'object') {
      return allowed;
    }
    [
      'playback_percent',
      'completion_percent',
      'media_type',
      'recommendation_request_id',
      'feed_position',
      'relationship_type'
    ].forEach(function (key) {
      if (metadata[key] === undefined || metadata[key] === null) {
        return;
      }
      if (typeof metadata[key] === 'number') {
        allowed[key] = metadata[key];
      } else {
        allowed[key] = String(metadata[key]).slice(0, 120);
      }
    });
    return allowed;
  }

  function flush() {
    if (!state.enabled || !state.queue.length) {
      return;
    }
    var payload = JSON.stringify({ interactions: state.queue.splice(0, state.queue.length) });
    if (navigator.sendBeacon) {
      var blob = new Blob([payload], { type: 'application/json' });
      navigator.sendBeacon('/api/ai/interactions/batch', blob);
      return;
    }
    fetch('/api/ai/interactions/batch', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      body: payload
    }).catch(function () {});
  }

  function fetchStatus() {
    if (state.pendingStatus) {
      return;
    }
    state.pendingStatus = true;
    fetch('/api/ai/status', {
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken() }
    }).then(function (res) {
      if (!res.ok) {
        return null;
      }
      return res.json();
    }).then(function (data) {
      state.enabled = !!(data && data.interaction_tracking_enabled);
    }).catch(function () {
      state.enabled = false;
    }).finally(function () {
      state.pendingStatus = false;
    });
  }

  function observeImpressions(selector, buildItem, threshold) {
    if (!window.IntersectionObserver) {
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) {
          return;
        }
        var item = buildItem(entry.target);
        if (item) {
          enqueue(item);
        }
      });
    }, { threshold: threshold || 0.6 });

    document.querySelectorAll(selector).forEach(function (element) {
      observer.observe(element);
    });
  }

  function bindClickTracking(selector, buildItem) {
    document.addEventListener('click', function (event) {
      var element = event.target.closest(selector);
      if (!element) {
        return;
      }
      var item = buildItem(element);
      if (item) {
        enqueue(item);
      }
    });
  }

  function bindReelPlaybackTracking() {
    document.querySelectorAll('video.rd-video, .nvpro-mobile-reel-slide video, video.tiktok-reel-video, .nv-reel-card video, .nvpro-post-card video').forEach(function (video) {
      if (video.dataset.aiTrackingBound === '1') {
        return;
      }
      video.dataset.aiTrackingBound = '1';
      video.addEventListener('play', function () {
        var node = video.closest('[data-reel-id], [data-video-id], [data-post-id], [data-item-id]');
        var reelId = node && (node.dataset.reelId || node.dataset.videoId || node.dataset.postId || node.dataset.itemId);
        if (reelId) {
          state.reelSessions[reelId] = Date.now();
        }
      });
      video.addEventListener('ended', function () {
        var node = video.closest('[data-reel-id], [data-video-id], [data-post-id], [data-item-id]');
        var reelId = node && (node.dataset.reelId || node.dataset.videoId || node.dataset.postId || node.dataset.itemId);
        if (!reelId) {
          return;
        }
        enqueue({
          target_type: 'reel',
          target_id: reelId,
          action_type: 'complete',
          source_surface: 'reels',
          metadata: {
            completion_percent: 100,
            media_type: 'video'
          },
          dwell_time_ms: state.reelSessions[reelId] ? Date.now() - state.reelSessions[reelId] : undefined
        });
      });
      video.addEventListener('timeupdate', function () {
        if (!video.duration || video.duration <= 0 || video.dataset.aiCompletionQueued === '1') {
          return;
        }
        var node = video.closest('[data-reel-id], [data-video-id], [data-post-id], [data-item-id]');
        var reelId = node && (node.dataset.reelId || node.dataset.videoId || node.dataset.postId || node.dataset.itemId);
        if (!reelId) {
          return;
        }
        var completionPercent = Math.round((video.currentTime / video.duration) * 100);
        if (completionPercent >= 90) {
          video.dataset.aiCompletionQueued = '1';
          enqueue({
            target_type: 'reel',
            target_id: reelId,
            action_type: 'complete',
            source_surface: 'reels',
            metadata: {
              completion_percent: completionPercent,
              playback_percent: completionPercent,
              media_type: 'video'
            },
            dwell_time_ms: state.reelSessions[reelId] ? Date.now() - state.reelSessions[reelId] : undefined
          });
        }
      });
    });
  }

  function setupDefaultHooks() {
    observeImpressions('[data-post-id]', function (element) {
      return {
        target_type: 'post',
        target_id: element.dataset.postId,
        action_type: 'impression',
        source_surface: 'homepage'
      };
    }, 0.5);

    observeImpressions('[data-reel-id]', function (element) {
      return {
        target_type: 'reel',
        target_id: element.dataset.reelId,
        action_type: 'impression',
        source_surface: element.closest('.nvpro-home') ? 'homepage' : 'reels'
      };
    }, 0.6);

    bindClickTracking('[data-story-id]', function (element) {
      return {
        target_type: 'story',
        target_id: element.dataset.storyId,
        action_type: 'open',
        source_surface: 'story'
      };
    });

    bindClickTracking('a[href^="/live/"], [data-room-id]', function (element) {
      var roomId = element.dataset.roomId;
      if (!roomId) {
        var href = element.getAttribute('href') || '';
        var match = href.match(/\/live\/([^/?#]+)/);
        roomId = match ? match[1] : '';
      }
      if (!roomId || roomId === 'studio') {
        return null;
      }
      return {
        target_type: 'live',
        target_id: roomId,
        action_type: 'open',
        source_surface: 'live'
      };
    });

    if (document.body && document.body.classList.contains('nv-profile-premium')) {
      var profileRoot = document.querySelector('[data-profile-id]');
      if (profileRoot && profileRoot.dataset.profileId) {
        enqueue({
          target_type: 'profile',
          target_id: profileRoot.dataset.profileId,
          action_type: 'open',
          source_surface: 'profile'
        });
      }
    }

    bindReelPlaybackTracking();
  }

  window.NamVibeAITracking = {
    init: fetchStatus,
    track: enqueue,
    flush: flush
  };

  fetchStatus();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupDefaultHooks);
  } else {
    setupDefaultHooks();
  }

  window.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      flush();
    }
  });
  window.addEventListener('beforeunload', flush);
})();
