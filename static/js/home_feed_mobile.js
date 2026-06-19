/* Phase 84: mobile feed interaction polish. */
(function () {
  'use strict';

  function init() {
    document.documentElement.classList.add('nv-feed-mobile-ready');
    document.querySelectorAll('.nv-reel-card').forEach(function (card) {
      if (!card.querySelector('.nv-reel-video') && !card.querySelector('.nv-video-fallback')) {
        var fallback = document.createElement('div');
        fallback.className = 'nv-video-fallback';
        fallback.textContent = 'Media unavailable';
        card.appendChild(fallback);
      }
    });
    window.addEventListener('resize', function () {
      document.documentElement.style.setProperty('--nv-vh', (window.innerHeight * 0.01) + 'px');
    }, { passive: true });
    window.dispatchEvent(new Event('resize'));
  }

  document.addEventListener('DOMContentLoaded', init);
})();
