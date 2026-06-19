/* Phase 84: status/story viewer autoplay. */
(function () {
  'use strict';

  var viewer = null;
  var items = [];
  var index = 0;
  var timer = null;
  var paused = false;
  var muted = true;

  function clearTimer() {
    if (timer) clearTimeout(timer);
    timer = null;
  }

  function close() {
    clearTimer();
    if (viewer) viewer.classList.remove('is-open');
    var video = viewer && viewer.querySelector('video');
    if (video) video.pause();
  }

  function renderProgress() {
    var progress = viewer.querySelector('.status-progress');
    if (!progress) return;
    progress.innerHTML = items.map(function (_, i) {
      return '<span class="' + (i < index ? 'done' : i === index ? 'active' : '') + '"></span>';
    }).join('');
  }

  function next() {
    if (index < items.length - 1) {
      index += 1;
      show();
    } else {
      close();
    }
  }

  function prev() {
    index = Math.max(0, index - 1);
    show();
  }

  function show() {
    clearTimer();
    if (!viewer || !items[index]) return;
    renderProgress();
    var body = viewer.querySelector('.status-body');
    var item = items[index];
    body.innerHTML = '';
    if (item.video_url) {
      var video = document.createElement('video');
      video.src = item.video_url;
      video.poster = item.thumbnail_url || '';
      video.muted = muted;
      video.playsInline = true;
      video.autoplay = true;
      video.onended = next;
      body.appendChild(video);
      video.play().catch(function () { timer = setTimeout(next, 5000); });
    } else if (item.image_url || item.thumbnail_url) {
      var img = document.createElement('img');
      img.src = item.image_url || item.thumbnail_url;
      img.alt = item.caption || 'Status';
      body.appendChild(img);
      timer = setTimeout(next, 5000);
    } else {
      var text = document.createElement('p');
      text.textContent = item.caption || 'Status';
      body.appendChild(text);
      timer = setTimeout(next, 5000);
    }
  }

  function open(payload, startIndex) {
    items = (payload || []).filter(function (item) {
      var text = ((item.caption || '') + ' ' + (item.username || '')).toLowerCase();
      return text.indexOf('phase8') === -1 && text.indexOf('test reel') === -1 && text.indexOf('seed') === -1;
    });
    if (!items.length) return;
    index = Math.max(0, startIndex || 0);
    if (!viewer) buildViewer();
    viewer.classList.add('is-open');
    show();
  }

  function buildViewer() {
    viewer = document.createElement('div');
    viewer.className = 'status-viewer';
    viewer.innerHTML = '<div class="status-progress"></div><button class="status-close" type="button">×</button><div class="status-body"></div><div class="status-hit status-prev"></div><div class="status-hit status-next"></div><button class="status-mute" type="button">Mute</button><button class="status-reply" type="button">Reply</button>';
    document.body.appendChild(viewer);
    viewer.querySelector('.status-close').onclick = close;
    viewer.querySelector('.status-prev').onclick = prev;
    viewer.querySelector('.status-next').onclick = next;
    viewer.querySelector('.status-mute').onclick = function () {
      muted = !muted;
      var video = viewer.querySelector('video');
      if (video) video.muted = muted;
      this.textContent = muted ? 'Mute' : 'Unmute';
    };
    viewer.addEventListener('pointerdown', function () { paused = true; clearTimer(); });
    viewer.addEventListener('pointerup', function () { if (paused) { paused = false; show(); } });
    var startY = 0;
    viewer.addEventListener('touchstart', function (e) { startY = e.touches[0].clientY; }, { passive: true });
    viewer.addEventListener('touchend', function (e) {
      if (e.changedTouches[0].clientY - startY > 80) close();
    }, { passive: true });
  }

  window.NamVibeStatusAutoplay = { open: open, close: close, next: next, prev: prev };
  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-status-viewer]');
    if (!trigger) return;
    var data = [];
    try { data = JSON.parse(trigger.getAttribute('data-status-viewer') || '[]'); } catch (e) {}
    open(data, 0);
  });
})();
