/* Phase 60: Explore — minimal interactivity */
(function() {
  'use strict';
  // Smooth tab transitions
  document.querySelectorAll('.explore-tab').forEach(tab => {
    tab.addEventListener('click', function(e) {
      const parent = this.closest('.explore-tabs');
      if (parent) {
        parent.querySelectorAll('.explore-tab').forEach(t => t.classList.remove('is-active'));
        this.classList.add('is-active');
      }
    });
  });
})();
