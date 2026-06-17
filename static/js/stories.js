/* Phase 60: Stories V2 JS — full-screen viewer with progress, reactions, replies */
(function() {
  'use strict';

  const stories = window.__STORIES_DATA || [];
  if (!stories.length) return;

  const viewer = document.getElementById('story-viewer');
  const closeBtn = document.getElementById('story-close');
  const mediaWrap = document.getElementById('story-media-wrap');
  const storyImg = document.getElementById('story-image');
  const storyVideo = document.getElementById('story-video');
  const storyText = document.getElementById('story-text');
  const usernameLabel = document.getElementById('story-username-label');
  const userAvatar = document.getElementById('story-user-avatar');
  const timeLabel = document.getElementById('story-time-label');
  const progressSegments = document.querySelectorAll('.story-progress-segment');
  const tapLeft = document.getElementById('story-tap-left');
  const tapRight = document.getElementById('story-tap-right');
  const replyInput = document.getElementById('story-reply-input');
  const replySend = document.getElementById('story-reply-send');
  const likeBtn = document.getElementById('story-react-like');
  const laughBtn = document.getElementById('story-react-laugh');
  const wowBtn = document.getElementById('story-react-wow');
  const sadBtn = document.getElementById('story-react-sad');

  let currentIndex = 0;
  let progressTimer = null;
  let progressStart = 0;
  const STORY_DURATION = 5000;

  function showStory(index) {
    if (index < 0 || index >= stories.length) { hideViewer(); return; }
    currentIndex = index;
    const story = stories[index];
    if (!story) return;

    usernameLabel.textContent = story.username || 'User';
    timeLabel.textContent = timeAgo(story.created_at);
    userAvatar.src = story.avatar_url || '';
    storyText.textContent = story.caption || '';

    if (story.media_type === 'video' && story.media_url) {
      storyImg.style.display = 'none';
      storyVideo.style.display = 'block';
      storyVideo.src = story.media_url;
      storyVideo.play().catch(() => {});
    } else if (story.media_url) {
      storyVideo.style.display = 'none';
      storyImg.style.display = 'block';
      storyImg.src = story.media_url;
    } else {
      storyImg.style.display = 'none';
      storyVideo.style.display = 'none';
    }

    viewer.style.display = 'flex';
    startProgress();
  }

  function hideViewer() {
    clearInterval(progressTimer);
    storyVideo.pause();
    viewer.style.display = 'none';
  }

  function startProgress() {
    clearInterval(progressTimer);
    progressSegments.forEach((seg, i) => {
      seg.classList.toggle('active', i === 0);
      const span = seg.querySelector('span');
      if (span) span.style.width = i === 0 ? '0%' : '0%';
    });
    progressStart = Date.now();
    progressTimer = setInterval(() => {
      const elapsed = Date.now() - progressStart;
      const pct = Math.min(100, (elapsed / STORY_DURATION) * 100);
      const activeSeg = progressSegments[0];
      const span = activeSeg ? activeSeg.querySelector('span') : null;
      if (span) span.style.width = pct + '%';
      if (elapsed >= STORY_DURATION) nextStory();
    }, 50);
  }

  function nextStory() { showStory(currentIndex + 1); }
  function prevStory() { showStory(currentIndex - 1); }

  if (closeBtn) closeBtn.addEventListener('click', hideViewer);
  if (tapRight) tapRight.addEventListener('click', nextStory);
  if (tapLeft) tapLeft.addEventListener('click', prevStory);

  document.addEventListener('keydown', function(e) {
    if (viewer.style.display !== 'flex') return;
    if (e.key === 'ArrowRight') nextStory();
    else if (e.key === 'ArrowLeft') prevStory();
    else if (e.key === 'Escape') hideViewer();
  });

  /* ── Reactions ── */
  function sendReaction(storyId, reaction) {
    if (!storyId) return;
    fetch(`/api/stories/${storyId}/react`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ reaction })
    }).catch(() => {});
  }

  const reactBtns = [
    { btn: likeBtn, type: 'like' },
    { btn: laughBtn, type: 'laugh' },
    { btn: wowBtn, type: 'wow' },
    { btn: sadBtn, type: 'sad' },
  ];
  reactBtns.forEach(({btn, type}) => {
    if (!btn) return;
    btn.addEventListener('click', function() {
      const story = stories[currentIndex];
      if (!story) return;
      sendReaction(story.id, type);
      this.style.opacity = '1';
      setTimeout(() => this.style.opacity = '.7', 500);
    });
  });

  /* ── Replies ── */
  function sendReply(storyId, text) {
    if (!storyId || !text.trim()) return;
    fetch(`/api/stories/${storyId}/reply`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ reply_text: text })
    }).catch(() => {});
  }

  if (replySend) replySend.addEventListener('click', function() {
    const story = stories[currentIndex];
    if (!story || !replyInput) return;
    sendReply(story.id, replyInput.value);
    replyInput.value = '';
  });

  if (replyInput) replyInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') replySend.click();
  });

  /* ── Link story avatars ── */
  document.querySelectorAll('[data-story-id]').forEach(el => {
    el.addEventListener('click', function(e) {
      e.preventDefault();
      const id = this.dataset.storyId;
      const idx = stories.findIndex(s => s.id === id);
      if (idx >= 0) showStory(idx);
    });
  });

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const diff = Math.floor((Date.now() - d) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff/60)+'m';
    if (diff < 86400) return Math.floor(diff/3600)+'h';
    return Math.floor(diff/86400)+'d';
  }
})();
