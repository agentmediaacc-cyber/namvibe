/* Phase 84: one-at-a-time reels autoplay with interest tracking. */
(function () {
  'use strict';

  var currentVideo = null;
  var unmuted = false;
  var watchStarts = new WeakMap();

  function postEvent(card, type, watchMs) {
    if (!card || !card.dataset.reelId) return;
    fetch('/api/video-events', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_type: 'reel',
        video_id: card.dataset.reelId,
        creator_profile_id: card.dataset.creatorId || null,
        event_type: type,
        watch_ms: Math.max(0, Math.round(watchMs || 0))
      })
    }).catch(function () {});
  }

  function progress(video) {
    var card = video && video.closest('.nv-reel-card');
    var bar = card && card.querySelector('.nv-video-progress span');
    if (!bar || !video.duration) return;
    bar.style.width = Math.min(100, (video.currentTime / video.duration) * 100) + '%';
  }

  function pause(video, eventType) {
    if (!video) return;
    var card = video.closest('.nv-reel-card');
    var started = watchStarts.get(video);
    if (started && eventType) postEvent(card, eventType, performance.now() - started);
    video.pause();
    if (currentVideo === video) currentVideo = null;
  }

  function play(video) {
    if (!video || !video.getAttribute('src')) return;
    if (currentVideo && currentVideo !== video) pause(currentVideo, 'skip');
    video.muted = !unmuted;
    currentVideo = video;
    watchStarts.set(video, performance.now());
    video.play().then(function () {
      postEvent(video.closest('.nv-reel-card'), 'impression', 0);
    }).catch(function () {});
  }

  function preloadNext(card) {
    var next = card && card.nextElementSibling;
    var video = next && next.querySelector && next.querySelector('video.nv-reel-video');
    if (video && video.preload !== 'auto') video.preload = 'auto';
  }

  function setupVideo(video) {
    video.muted = true;
    video.playsInline = true;
    video.addEventListener('timeupdate', function () {
      progress(video);
      if (video.currentTime >= 3 && !video.dataset.watch3) {
        video.dataset.watch3 = '1';
        postEvent(video.closest('.nv-reel-card'), 'watch_3s', 3000);
      }
      if (video.currentTime >= 10 && !video.dataset.watch10) {
        video.dataset.watch10 = '1';
        postEvent(video.closest('.nv-reel-card'), 'watch_10s', 10000);
      }
    });
    video.addEventListener('ended', function () {
      pause(video, 'complete');
      var card = video.closest('.nv-reel-card');
      var next = card && card.nextElementSibling;
      var nextVideo = next && next.querySelector && next.querySelector('video.nv-reel-video');
      if (nextVideo) nextVideo.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    video.addEventListener('click', function () {
      unmuted = !unmuted;
      video.muted = !unmuted;
      document.body.classList.toggle('nv-video-unmuted', unmuted);
    });
  }

  function setupDoubleTap(card) {
    var lastTap = 0;
    card.addEventListener('pointerup', function () {
      var now = Date.now();
      if (now - lastTap < 280) {
        var like = card.querySelector('[data-action="like"]');
        if (like) like.click();
        postEvent(card, 'like', 0);
      }
      lastTap = now;
    });
  }

  function init() {
    var cards = Array.prototype.slice.call(document.querySelectorAll('.nv-reel-card'));
    var videos = cards.map(function (card) {
      setupDoubleTap(card);
      return card.querySelector('video.nv-reel-video');
    }).filter(Boolean);
    videos.forEach(setupVideo);
    if (!('IntersectionObserver' in window)) {
      if (videos[0]) play(videos[0]);
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var video = entry.target;
        if (entry.isIntersecting && entry.intersectionRatio >= 0.72) {
          play(video);
          preloadNext(video.closest('.nv-reel-card'));
        } else if (!entry.isIntersecting || entry.intersectionRatio < 0.35) {
          pause(video, 'skip');
        }
      });
    }, { threshold: [0, 0.35, 0.72, 0.95] });
    videos.forEach(function (video) { observer.observe(video); });
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) pause(currentVideo, 'skip');
  });
  ['pagehide', 'beforeunload', 'popstate', 'hashchange'].forEach(function (eventName) {
    window.addEventListener(eventName, function () { pause(currentVideo, 'skip'); });
  });
  document.addEventListener('DOMContentLoaded', init);
})();
