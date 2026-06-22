(function() {
  'use strict';

  var stories = [];
  var currentIdx = 0;
  var progressInterval = null;
  var viewer = null;
  var isPaused = false;

  function escapeHtml(t) {
    if (!t) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(t));
    return d.innerHTML;
  }

  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function csrfHeaders() {
    var h = { 'Content-Type': 'application/json' };
    var t = getCSRF();
    if (t) h['X-CSRFToken'] = t;
    return h;
  }

  function loadTray() {
    fetch('/api/stories/tray', { headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        stories = data.stories || data.tray || data.data || [];
        renderTray();
      })
      .catch(function() {});
  }

  function renderTray() {
    var container = document.getElementById('story-tray');
    if (!container) return;
    if (!stories.length) {
      container.innerHTML = '<div class="story-tray-empty">No stories available</div>';
      return;
    }

    var grouped = {};
    stories.forEach(function(s) {
      var pid = s.profile_id;
      if (!grouped[pid]) grouped[pid] = [];
      grouped[pid].push(s);
    });

    container.innerHTML = Object.keys(grouped).map(function(pid) {
      var group = grouped[pid];
      var first = group[0];
      var avatarHtml = first.creator_avatar
        ? '<img class="story-avatar" src="' + escapeHtml(first.creator_avatar) + '" alt="" loading="lazy" onerror="this.onerror=null;this.style.display=\'none\'">'
        : '<div class="story-avatar story-avatar-fallback">' + escapeHtml((first.creator_name || '?')[0].toUpperCase()) + '</div>';
      var hasUnviewed = group.some(function(s) { return !s.viewed; });
      return '<div class="story-ring' + (hasUnviewed ? ' unviewed' : '') + '" data-profile="' + escapeHtml(pid) + '">' +
        avatarHtml +
        '<div class="story-username">' + escapeHtml(first.creator_name || 'User') + '</div>' +
      '</div>';
    }).join('');

    container.querySelectorAll('.story-ring').forEach(function(el) {
      el.addEventListener('click', function() {
        var pid = el.dataset.profile;
        var idx = stories.findIndex(function(s) { return s.profile_id === pid; });
        if (idx >= 0) openViewer(idx);
      });
    });
  }

  function openViewer(idx) {
    if (idx < 0 || idx >= stories.length) return;
    currentIdx = idx;
    viewer = document.getElementById('story-viewer');
    if (!viewer) return;
    viewer.classList.add('open');
    showStory(idx);
  }

  function showStory(idx) {
    var story = stories[idx];
    if (!story) return;
    recordView(story.id);

    var media = viewer.querySelector('.story-viewer-media');
    if (!media) return;

    if (story.media_type === 'video') {
      media.innerHTML = '<video class="story-video" src="' + escapeHtml(story.media_url) + '" autoplay playsinline></video>';
    } else {
      media.innerHTML = '<img class="story-image" src="' + escapeHtml(story.media_url) + '" alt="">';
    }

    viewer.querySelector('.story-viewer-name').textContent = story.creator_name || 'User';
    viewer.querySelector('.story-viewer-time').textContent = story.created_at ? new Date(story.created_at).toLocaleString() : '';

    startProgress();
  }

  function recordView(storyId) {
    fetch('/api/stories/' + storyId + '/view', { method: 'POST', headers: csrfHeaders() }).catch(function(){});
  }

  function startProgress() {
    stopProgress();
    var bar = viewer ? viewer.querySelector('.story-progress-bar') : null;
    if (bar) bar.style.width = '0%';
    var start = Date.now();
    var duration = 5000;
    isPaused = false;

    progressInterval = setInterval(function() {
      if (isPaused) return;
      var elapsed = Date.now() - start;
      var pct = Math.min(100, (elapsed / duration) * 100);
      if (bar) bar.style.width = pct + '%';
      if (pct >= 100) {
        stopProgress();
        navigateStory(1);
      }
    }, 100);
  }

  function stopProgress() {
    if (progressInterval) { clearInterval(progressInterval); progressInterval = null; }
  }

  function navigateStory(dir) {
    var next = currentIdx + dir;
    if (next < 0 || next >= stories.length) {
      closeViewer();
      return;
    }
    showStory(next);
    currentIdx = next;
  }

  function closeViewer() {
    stopProgress();
    if (viewer) viewer.classList.remove('open');
  }

  function sendReaction(storyId, reaction) {
    fetch('/api/stories/' + storyId + '/reaction', {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ reaction: reaction }),
    }).catch(function(){});
  }

  function sendReply(storyId) {
    var input = viewer ? viewer.querySelector('.story-reply-input') : null;
    if (!input || !input.value.trim()) return;
    var body = input.value.trim();
    input.value = '';
    fetch('/api/stories/' + storyId + '/reply', {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ body: body }),
    }).then(function(r) { return r.json(); }).then(function(d) {
      if (d.ok) alert('Reply sent!');
    }).catch(function(){});
  }

  function deleteStory(storyId) {
    if (!confirm('Delete this story?')) return;
    fetch('/api/stories/' + storyId, { method: 'DELETE', headers: csrfHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok) { closeViewer(); loadTray(); }
      });
  }

  document.addEventListener('click', function(e) {
    var reactionBtn = e.target.closest('[data-reaction]');
    if (reactionBtn && viewer && stories[currentIdx]) {
      sendReaction(stories[currentIdx].id, reactionBtn.dataset.reaction);
      return;
    }

    if (viewer && viewer.classList.contains('open')) {
      if (e.target.closest('.story-viewer-left')) navigateStory(-1);
      else if (e.target.closest('.story-viewer-right')) navigateStory(1);
      else if (e.target.closest('.story-close-btn')) closeViewer();
      else if (e.target.closest('.story-delete-btn') && stories[currentIdx]) deleteStory(stories[currentIdx].id);
    }
  });

  document.addEventListener('keydown', function(e) {
    if (!viewer || !viewer.classList.contains('open')) return;
    if (e.key === 'ArrowLeft') navigateStory(-1);
    else if (e.key === 'ArrowRight') navigateStory(1);
    else if (e.key === 'Escape') closeViewer();
  });

  var touchStartX = 0;
  document.addEventListener('touchstart', function(e) {
    if (viewer && viewer.classList.contains('open')) touchStartX = e.touches[0].clientX;
  }, { passive: true });
  document.addEventListener('touchend', function(e) {
    if (!viewer || !viewer.classList.contains('open')) return;
    var dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 50) navigateStory(dx > 0 ? -1 : 1);
  }, { passive: true });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadTray);
  else loadTray();
})();
