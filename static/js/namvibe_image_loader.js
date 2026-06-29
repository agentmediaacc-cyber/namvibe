(function () {
  'use strict';

  function init(root) {
    root = root || document;
    var images = root.querySelectorAll('img[data-src]');
    for (var i = 0; i < images.length; i++) {
      setupImage(images[i]);
    }
  }

  function setupImage(img) {
    if (img.dataset.nvLoaded) return;
    img.dataset.nvLoaded = '1';

    var src = img.getAttribute('data-src') || img.getAttribute('src') || '';
    var fallback = img.getAttribute('data-fallback') || '';
    var initials = img.getAttribute('data-initials') || '';
    var alt = img.getAttribute('alt') || '';

    if (img.tagName === 'IMG') {
      if (!img.src || img.src === window.location.href) {
        img.src = '';
      }
    }

    img.style.position = 'relative';

    if (initials && !fallback) {
      fallback = 'initials';
    }

    if (window.IntersectionObserver) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            observer.unobserve(img);
            loadImage(img, src, fallback, initials, alt);
          }
        });
      }, { rootMargin: '200px' });
      observer.observe(img);
    } else {
      loadImage(img, src, fallback, initials, alt);
    }
  }

  function loadImage(img, src, fallback, initials, alt) {
    if (!src) {
      applyFallback(img, fallback, initials, alt);
      return;
    }

    img.classList.add('nv-image-loading');

    var temp = new Image();
    temp.onload = function () {
      img.classList.remove('nv-image-loading');
      img.classList.add('nv-image-loaded');
      img.src = src;
      img.removeAttribute('data-src');
      var ph = img.nextElementSibling;
      if (ph && ph.classList.contains('nv-image-placeholder')) {
        ph.style.opacity = '0';
        setTimeout(function () { if (ph.parentNode) ph.parentNode.removeChild(ph); }, 300);
      }
    };
    temp.onerror = function () {
      img.classList.remove('nv-image-loading');
      applyFallback(img, fallback, initials, alt);
    };
    temp.src = src;
  }

  function applyFallback(img, fallback, initials, alt) {
    if (fallback === 'initials' || initials) {
      showInitials(img, initials || alt);
    } else if (fallback) {
      img.src = fallback;
      img.classList.add('nv-image-loaded');
    } else {
      showInitials(img, initials || alt);
    }
  }

  function showInitials(img, text) {
    var initials = getInitials(text || '?');
    img.style.display = 'none';
    var existing = img.nextElementSibling;
    if (existing && existing.classList.contains('nv-image-placeholder')) return;
    var ph = document.createElement('div');
    ph.className = 'nv-image-placeholder';
    ph.textContent = initials;
    img.parentNode.insertBefore(ph, img.nextSibling);
  }

  function getInitials(text) {
    if (!text) return '?';
    var parts = text.trim().split(/\s+/);
    var initials = '';
    for (var i = 0; i < Math.min(parts.length, 2); i++) {
      if (parts[i].length > 0) {
        initials += parts[i][0].toUpperCase();
      }
    }
    return initials || '?';
  }

  function watchMutations() {
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var added = mutations[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          if (added[j].nodeType === 1) {
            var imgs = added[j].tagName === 'IMG'
              ? [added[j]]
              : added[j].querySelectorAll('img[data-src]');
            for (var k = 0; k < imgs.length; k++) {
              setupImage(imgs[k]);
            }
          }
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      init();
      watchMutations();
    });
  } else {
    init();
    watchMutations();
  }

  window.NamVibeImageLoader = {
    init: init,
    setupImage: setupImage,
  };
})();
