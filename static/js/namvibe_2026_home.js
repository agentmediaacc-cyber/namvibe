/* ================================================================
   NamVibe 2026 — Phase 72 Homepage Rebuild JS
   Uses nv-* CSS classes matching namvibe_2026_home.css
   ================================================================ */

(function () {
  'use strict';

  var state = {
    currentIndex: 0,
    isPlaying: false,
    isMuted: true,
    activeVideo: null,
    lastTap: 0,
    scrollTimeout: null,
    commentReelId: null,
    shareReelId: null,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    var container = document.querySelector('.nv-feed-scroll');
    if (container && container.querySelector('.nv-reel-card')) {
      initTikTokFeed(container);
    }
    initActionButtons();
    initFollowButtons();
    initCommentDrawer();
    initShareDrawer();
    initStoryModal();
    initDrawer();
    initAvatarFallback();
    initReconnectBanner();
    initSearchSubmit();
    initTownChips();
    initHashTags();
    initNavActive();
  }

  function safeReelUrl(reelId) {
    var id = String(reelId || '').trim();
    if (!id) return '';
    return window.location.origin + '/reels/' + encodeURIComponent(id);
  }

  /* ================================================================
     TIKTOK FEED — scroll-based reel navigation with snap
     ================================================================ */

  function initTikTokFeed(container) {
    setTimeout(function () { playReel(0); }, 300);

    container.addEventListener('scroll', function () {
      clearTimeout(state.scrollTimeout);
      state.scrollTimeout = setTimeout(function () {
        var index = getCurrentReelIndex(container);
        if (index !== -1 && index !== state.currentIndex) playReel(index);
      }, 100);
    }, { passive: true });

    var touchStartY = 0;
    container.addEventListener('touchstart', function (e) {
      touchStartY = e.changedTouches[0].clientY;
    }, { passive: true });

    container.addEventListener('touchend', function (e) {
      var diff = touchStartY - e.changedTouches[0].clientY;
      if (Math.abs(diff) > 30) {
        clearTimeout(state.scrollTimeout);
        state.scrollTimeout = setTimeout(function () {
          var index = getCurrentReelIndex(container);
          if (index !== -1 && index !== state.currentIndex) playReel(index);
        }, 50);
      }
    }, { passive: true });

    container.addEventListener('wheel', function () {
      clearTimeout(state.scrollTimeout);
      state.scrollTimeout = setTimeout(function () {
        var index = getCurrentReelIndex(container);
        if (index !== -1 && index !== state.currentIndex) playReel(index);
      }, 150);
    }, { passive: true });

    container.addEventListener('click', function (e) {
      var card = e.target.closest('.nv-reel-card');
      if (!card) return;
      var now = Date.now();
      if (state.lastTap && (now - state.lastTap) < 300) {
        handleDoubleTap(card);
        state.lastTap = 0;
        return;
      }
      state.lastTap = now;
      clearTimeout(card._tapTimer);
      card._tapTimer = setTimeout(function () { togglePlay(card); }, 300);
    });

    initKeyboardNav(container);
  }

  function getCurrentReelIndex(container) {
    var cards = container.querySelectorAll('.nv-reel-card');
    var scrollTop = container.scrollTop;
    var viewHeight = container.clientHeight;
    for (var i = 0; i < cards.length; i++) {
      var offset = cards[i].offsetTop;
      if (offset >= scrollTop - viewHeight * 0.3 && offset < scrollTop + viewHeight * 0.7) {
        return i;
      }
    }
    return 0;
  }

  function playReel(index) {
    if (state.activeVideo) {
      state.activeVideo.pause();
      state.activeVideo.currentTime = 0;
    }

    var cards = document.querySelectorAll('.nv-reel-card');
    var card = cards[index];
    if (!card) return;

    state.currentIndex = index;
    var video = card.querySelector('.nv-reel-video');
    var thumbnail = card.querySelector('.nv-reel-thumbnail');
    var loader = card.querySelector('.nv-reel-loader');

    if (!video) {
      if (loader) loader.style.display = 'none';
      updateActionRail(index);
      return;
    }

    state.activeVideo = video;
    video.muted = state.isMuted;

    var promise = video.play();
    if (promise && typeof promise.then === 'function') {
      promise.then(function () {
        state.isPlaying = true;
        if (loader) loader.style.display = 'none';
        if (thumbnail) thumbnail.classList.add('is-hidden');
        video.controls = false;
      }).catch(function () {
        video.controls = true;
        if (loader) loader.style.display = 'none';
        if (thumbnail) thumbnail.classList.remove('is-hidden');
      });
    } else {
      if (loader) loader.style.display = 'none';
      if (thumbnail) thumbnail.classList.add('is-hidden');
    }

    var reelId = card.getAttribute('data-reel-id');
    if (reelId) {
      fetch('/reels/api/reels/' + reelId + '/view', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }).catch(function () {});
    }

    updateActionRail(index);
  }

  function togglePlay(card) {
    var video = card.querySelector('.nv-reel-video');
    if (!video) return;
    if (video.paused) {
      video.play().catch(function () {});
    } else {
      video.pause();
    }
  }

  function handleDoubleTap(card) {
    var reelId = card.getAttribute('data-reel-id');
    if (!reelId) return;
    var heart = card.querySelector('.nv-like-heart');
    if (heart) {
      heart.classList.remove('is-active');
      void heart.offsetWidth;
      heart.classList.add('is-active');
    }
    likeReel(reelId);
  }

  /* ================================================================
     KEYBOARD NAVIGATION
     ================================================================ */

  function initKeyboardNav(container) {
    document.addEventListener('keydown', function (e) {
      var tag = (e.target || {}).tagName || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (e.key === 'Escape') {
        closeAllModals();
        return;
      }

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!container || !document.contains(container)) {
          container = document.querySelector('.nv-tiktok-scroll');
        }
        if (!container) return;
        var delta = e.key === 'ArrowDown' ? container.clientHeight * 0.9 : -container.clientHeight * 0.9;
        container.scrollBy({ top: delta, behavior: 'smooth' });
        setTimeout(function () {
          var index = getCurrentReelIndex(container);
          if (index !== -1 && index !== state.currentIndex) playReel(index);
        }, 200);
      }

      if (e.key === 'm' || e.key === 'M') {
        state.isMuted = !state.isMuted;
        if (state.activeVideo) state.activeVideo.muted = state.isMuted;
        showToast(state.isMuted ? 'Muted' : 'Unmuted');
      }
    });
  }

  function closeAllModals() {
    closeCommentDrawer();
    closeShareDrawer();
    closeStoryModal();
    closeDrawer();
  }

  /* ================================================================
     ACTION RAIL — show only current reel's buttons
     ================================================================ */

  function updateActionRail(index) {
    var rails = document.querySelectorAll('.nv-action-rail');
    for (var i = 0; i < rails.length; i++) {
      rails[i].style.display = 'none';
    }
    var cards = document.querySelectorAll('.nv-reel-card');
    var card = cards[index];
    if (card) {
      var rail = card.querySelector('.nv-action-rail');
      if (rail) rail.style.display = 'flex';
    }
  }

  /* ================================================================
     ACTION BUTTONS
     ================================================================ */

  function initActionButtons() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.nv-action-btn');
      if (!btn) return;
      var action = btn.getAttribute('data-action');
      var reelId = btn.getAttribute('data-reel-id');
      if (!action || !reelId) return;
      e.preventDefault();
      e.stopPropagation();

      switch (action) {
        case 'like': likeReel(reelId, btn); break;
        case 'comment': openCommentDrawer(reelId); break;
        case 'share': openShareDrawer(reelId); break;
        case 'save': saveReel(reelId); break;
      }
    });
  }

  function likeReel(reelId, btn) {
    fetch('/reels/api/reels/' + reelId + '/like', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          if (!btn) {
            btn = document.querySelector('.nv-action-btn[data-action="like"][data-reel-id="' + reelId + '"]');
          }
          if (btn) {
            btn.classList.toggle('is-liked');
            var span = btn.querySelector('span');
            if (span) {
              var count = parseInt(span.textContent, 10) || 0;
              span.textContent = btn.classList.contains('is-liked') ? (count + 1) : Math.max(0, count - 1);
            }
          }
        }
      })
      .catch(function () {});
  }

  function saveReel(reelId) {
    fetch('/reels/api/reels/' + reelId + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          var btn = document.querySelector('.nv-action-btn[data-action="save"][data-reel-id="' + reelId + '"]');
          if (btn) {
            btn.classList.toggle('is-saved');
            showToast(data.is_saved ? 'Saved' : 'Removed');
          }
        }
      })
      .catch(function () {});
  }

  /* ================================================================
     FOLLOW BUTTONS
     ================================================================ */

  function initFollowButtons() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.nv-follow-pill, .nv-follow-btn');
      if (!btn) return;
      var profileId = btn.getAttribute('data-profile-id');
      if (!profileId) return;
      e.preventDefault();
      e.stopPropagation();
      toggleFollow(btn, profileId);
    });
  }

  function toggleFollow(btn, profileId) {
    var isFollowing = btn.classList.contains('is-following');
    if (btn.disabled) return;
    btn.disabled = true;

    var method = isFollowing ? 'DELETE' : 'POST';
    fetch('/api/profile/' + profileId + '/follow', {
      method: method,
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false;
        if (data.success || data.ok) {
          btn.classList.toggle('is-following');
          var isNowFollowing = btn.classList.contains('is-following');
          if (btn.classList.contains('nv-follow-pill')) {
            btn.textContent = isNowFollowing ? 'Following' : 'Follow';
          } else {
            var icon = btn.querySelector('i');
            if (icon) {
              icon.className = 'fas ' + (isNowFollowing ? 'fa-check' : 'fa-plus');
            }
            var spanText = btn.querySelector('span');
            if (spanText) {
              spanText.textContent = isNowFollowing ? 'Following' : 'Follow';
            } else if (!icon) {
              btn.textContent = isNowFollowing ? 'Following' : 'Follow';
            }
          }
          showToast(isNowFollowing ? 'Following' : 'Unfollowed');
        } else {
          showToast(data.error || 'Could not update');
        }
      })
      .catch(function () {
        btn.disabled = false;
        showToast('Network error');
      });
  }

  /* ================================================================
     COMMENT DRAWER
     ================================================================ */

  function initCommentDrawer() {
    var overlay = document.getElementById('nv-comment-overlay');
    if (!overlay) return;

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeCommentDrawer();
    });

    var closeBtn = overlay.querySelector('.nv-comment-close');
    if (closeBtn) closeBtn.addEventListener('click', closeCommentDrawer);

    var sendBtn = overlay.querySelector('.nv-comment-send');
    var input = overlay.querySelector('.nv-comment-input');

    if (input) {
      input.addEventListener('input', function () {
        if (sendBtn) sendBtn.disabled = !input.value.trim();
      });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendComment();
        }
      });
    }

    if (sendBtn) sendBtn.addEventListener('click', sendComment);
  }

  function openCommentDrawer(reelId) {
    state.commentReelId = reelId;
    var overlay = document.getElementById('nv-comment-overlay');
    if (!overlay) return;
    overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    loadComments(reelId);

    var input = overlay.querySelector('.nv-comment-input');
    if (input) { input.value = ''; input.focus(); }
    var sendBtn = overlay.querySelector('.nv-comment-send');
    if (sendBtn) sendBtn.disabled = true;
  }

  function closeCommentDrawer() {
    var overlay = document.getElementById('nv-comment-overlay');
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    state.commentReelId = null;
  }

  function loadComments(reelId) {
    var body = document.querySelector('.nv-comment-body');
    if (!body) return;
    body.innerHTML = '<div class="nv-comment-empty"><i class="fas fa-spinner fa-spin"></i><span>Loading comments...</span></div>';

    fetch('/reels/api/reels/' + reelId + '/comments')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var comments = data.comments || [];
        if (!comments.length) {
          body.innerHTML = '<div class="nv-comment-empty"><i class="fas fa-comment"></i><span>No comments yet. Be the first!</span></div>';
          return;
        }
        var html = '';
        for (var i = 0; i < comments.length; i++) {
          var c = comments[i];
          var initial = (c.username || '?')[0].toUpperCase();
          var avatarHtml = c.avatar_url
            ? '<img src="' + escapeHtml(c.avatar_url) + '" alt="" onerror="this.style.display=\'none\';this.parentElement.innerHTML=\'<span class=\\"nv-avatar-initials\\">' + initial + '</span>\'">'
            : '<span class="nv-avatar-initials">' + initial + '</span>';
          html += '<div class="nv-comment-item">' +
            '<div class="nv-comment-avatar">' + avatarHtml + '</div>' +
            '<div>' +
            '<div class="nv-comment-author">@' + escapeHtml(c.username || 'user') + '</div>' +
            '<div class="nv-comment-text">' + escapeHtml(c.body || '') + '</div>' +
            '<div class="nv-comment-time">' + relativeTime(c.created_at) + '</div>' +
            '</div></div>';
        }
        body.innerHTML = html;
      })
      .catch(function () {
        body.innerHTML = '<div class="nv-comment-empty"><i class="fas fa-exclamation-circle"></i><span>Could not load comments.</span></div>';
      });
  }

  function sendComment() {
    var input = document.querySelector('.nv-comment-input');
    var sendBtn = document.querySelector('.nv-comment-send');
    if (!input || !sendBtn) return;
    var text = input.value.trim();
    if (!text || !state.commentReelId) return;

    sendBtn.disabled = true;
    fetch('/reels/api/reels/' + state.commentReelId + '/comment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'body=' + encodeURIComponent(text),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          input.value = '';
          sendBtn.disabled = true;
          loadComments(state.commentReelId);
          var btn = document.querySelector('.nv-action-btn[data-action="comment"][data-reel-id="' + state.commentReelId + '"]');
          if (btn) {
            var span = btn.querySelector('span');
            if (span) span.textContent = (parseInt(span.textContent, 10) || 0) + 1;
          }
        } else {
          showToast(data.error || 'Could not post comment');
          sendBtn.disabled = false;
        }
      })
      .catch(function () { showToast('Network error'); sendBtn.disabled = false; });
  }

  /* ================================================================
     SHARE DRAWER
     ================================================================ */

  function initShareDrawer() {
    var overlay = document.getElementById('nv-share-overlay');
    if (!overlay) return;

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeShareDrawer();
    });

    var nativeBtn = document.getElementById('nv-share-native');
    if (nativeBtn) {
      nativeBtn.style.display = navigator.share ? '' : 'none';
    }

    overlay.addEventListener('click', function (e) {
      var opt = e.target.closest('.nv-share-opt');
      if (!opt) return;
      var action = opt.getAttribute('data-share-action');
      if (action === 'copy') {
        var urlInput = document.getElementById('nv-share-url');
        if (urlInput) copyLink(urlInput);
      } else if (action === 'native' && navigator.share) {
        var urlInput = document.getElementById('nv-share-url');
        navigator.share({ url: urlInput ? urlInput.value : window.location.href }).catch(function () {});
        closeShareDrawer();
      }
    });
  }

  function copyLink(input) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(input.value).then(function () {
        showToast('Link copied!');
        closeShareDrawer();
      }).catch(function () { fallbackCopy(input); });
    } else {
      fallbackCopy(input);
    }
  }

  function fallbackCopy(input) {
    input.select();
    try {
      document.execCommand('copy');
      showToast('Link copied!');
      closeShareDrawer();
    } catch (e) { showToast('Could not copy'); }
  }

  function openShareDrawer(reelId) {
    state.shareReelId = reelId;
    var overlay = document.getElementById('nv-share-overlay');
    if (!overlay) return;
    var urlInput = document.getElementById('nv-share-url');
    if (urlInput) {
      urlInput.value = safeReelUrl(reelId);
    }
    overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';

    fetch('/reels/api/reels/' + reelId + '/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }).catch(function () {});

    var btn = document.querySelector('.nv-action-btn[data-action="share"][data-reel-id="' + reelId + '"]');
    if (btn) {
      var span = btn.querySelector('span');
      if (span) span.textContent = (parseInt(span.textContent, 10) || 0) + 1;
    }
  }

  function closeShareDrawer() {
    var overlay = document.getElementById('nv-share-overlay');
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    state.shareReelId = null;
  }

  /* ================================================================
     STORY MODAL
     ================================================================ */

  function initStoryModal() {
    var overlay = document.getElementById('nv-story-overlay');
    var openTriggers = document.querySelectorAll('[data-open-story-modal]');
    if (!overlay) return;

    var closeBtn = overlay.querySelector('.nv-story-modal-close');
    var cancelBtn = overlay.querySelector('.nv-story-btn-cancel');
    var uploadZone = overlay.querySelector('.nv-story-upload-zone');
    var fileInput = document.getElementById('nv-story-file-input');
    var preview = overlay.querySelector('.nv-story-preview');
    var captionInput = overlay.querySelector('.nv-story-caption');
    var postBtn = overlay.querySelector('.nv-story-btn-post');
    var errorEl = overlay.querySelector('.nv-story-error');
    var loadingEl = overlay.querySelector('.nv-story-loading');

    var selectedFile = null;

    function openModal() {
      overlay.classList.add('is-open');
      document.body.style.overflow = 'hidden';
      resetModal();
    }

    function closeModal() {
      overlay.classList.remove('is-open');
      document.body.style.overflow = '';
      selectedFile = null;
    }

    function resetModal() {
      selectedFile = null;
      if (preview) {
        preview.classList.remove('is-visible');
        preview.innerHTML = '<button type="button" class="nv-story-remove-media" aria-label="Remove media">&times;</button>';
      }
      if (fileInput) fileInput.value = '';
      if (uploadZone) uploadZone.style.display = '';
      if (captionInput) captionInput.value = '';
      if (errorEl) { errorEl.classList.remove('is-visible'); errorEl.textContent = ''; }
      if (loadingEl) loadingEl.classList.remove('is-visible');
      if (postBtn) postBtn.disabled = true;
    }

    function showError(msg) {
      if (errorEl) { errorEl.textContent = msg; errorEl.classList.add('is-visible'); }
      if (loadingEl) loadingEl.classList.remove('is-visible');
      if (postBtn) postBtn.disabled = false;
    }

    openTriggers.forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        openModal();
      });
    });

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });

    if (uploadZone) {
      uploadZone.addEventListener('click', function () {
        if (fileInput) fileInput.click();
      });
    }

    if (fileInput) {
      fileInput.addEventListener('change', function () {
        var file = fileInput.files && fileInput.files[0];
        if (file) handleFile(file);
      });
    }

    if (uploadZone) {
      uploadZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadZone.classList.add('is-dragover');
      });
      uploadZone.addEventListener('dragleave', function () {
        uploadZone.classList.remove('is-dragover');
      });
      uploadZone.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadZone.classList.remove('is-dragover');
        var file = e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) handleFile(file);
      });
    }

    function handleFile(file) {
      if (!file.type.match(/^(image|video)\//)) {
        showError('Please select an image or video file.');
        return;
      }
      if (file.size > 100 * 1024 * 1024) {
        showError('File too large. Max 100MB.');
        return;
      }
      selectedFile = file;
      var reader = new FileReader();
      reader.onload = function (e) {
        if (uploadZone) uploadZone.style.display = 'none';
        if (preview) {
          preview.classList.add('is-visible');
          var media;
          if (file.type.startsWith('video/')) {
            media = document.createElement('video');
            media.src = e.target.result;
            media.muted = true;
            media.controls = true;
          } else {
            media = document.createElement('img');
            media.src = e.target.result;
          }
          media.style.width = '100%';
          media.style.maxHeight = '320px';
          media.style.objectFit = 'cover';
          preview.insertBefore(media, preview.firstChild);
          if (postBtn) postBtn.disabled = false;
        }
        if (errorEl) errorEl.classList.remove('is-visible');
      };
      reader.readAsDataURL(file);
    }

    preview.addEventListener('click', function (e) {
      var removeBtn = e.target.closest('.nv-story-remove-media');
      if (!removeBtn) return;
      selectedFile = null;
      if (fileInput) fileInput.value = '';
      resetModal();
    });

    if (postBtn) {
      postBtn.addEventListener('click', function () {
        if (!selectedFile) return;
        postBtn.disabled = true;
        if (loadingEl) loadingEl.classList.add('is-visible');
        if (errorEl) errorEl.classList.remove('is-visible');

        var formData = new FormData();
        formData.append('media', selectedFile);
        formData.append('caption', captionInput ? captionInput.value : '');

        fetch('/api/stories/create', {
          method: 'POST',
          body: formData,
        })
          .then(function (r) {
            if (r.redirected) { window.location.href = r.url; return null; }
            return r.json().catch(function () { return {}; });
          })
          .then(function (data) {
            if (!data) return;
            if (data.ok || data.success) { window.location.reload(); return; }
            if (data.redirect) { window.location.href = data.redirect; return; }
            window.location.reload();
          })
          .catch(function () {
            showError('Upload failed. Please try again.');
          });
      });
    }
  }

  function closeStoryModal() {
    var overlay = document.getElementById('nv-story-overlay');
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  /* ================================================================
     DRAWER (MOBILE HAMBURGER)
     ================================================================ */

  function initDrawer() {
    var openBtn = document.querySelector('[data-drawer-toggle]');
    var drawer = document.querySelector('.nv-mobile-drawer');
    var backdrop = document.querySelector('.nv-drawer-backdrop');

    if (!drawer) return;

    function setOpen(open) {
      drawer.classList.toggle('is-open', open);
      if (backdrop) {
        backdrop.classList.toggle('is-open', open);
      }
      document.body.style.overflow = open ? 'hidden' : '';
      if (openBtn) openBtn.setAttribute('aria-expanded', String(open));
    }

    window._nvCloseDrawer = function () { setOpen(false); };

    if (openBtn) {
      openBtn.addEventListener('click', function () { setOpen(true); });
    }

    var closeBtns = document.querySelectorAll('[data-drawer-close]');
    for (var i = 0; i < closeBtns.length; i++) {
      closeBtns[i].addEventListener('click', function () { setOpen(false); });
    }

    if (backdrop) {
      backdrop.addEventListener('click', function () { setOpen(false); });
    }
  }

  function closeDrawer() {
    var drawer = document.querySelector('.nv-mobile-drawer');
    var backdrop = document.querySelector('.nv-drawer-backdrop');
    var openBtn = document.querySelector('[data-drawer-toggle]');
    if (drawer) drawer.classList.remove('is-open');
    if (backdrop) backdrop.classList.remove('is-open');
    document.body.style.overflow = '';
    if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
  }

  /* ================================================================
     AVATAR FALLBACK
     ================================================================ */

  function initAvatarFallback() {
    document.addEventListener('error', function (e) {
      var target = e.target;
      if (target.tagName !== 'IMG') return;
      var container = target.closest('.nv-avatar');
      if (!container) return;
      target.style.display = 'none';
      var initials = container.querySelector('.nv-avatar-initials');
      if (initials) initials.style.display = '';
    }, true);
  }

  /* ================================================================
     RECONNECT BANNER
     ================================================================ */

  function initReconnectBanner() {
    var banner = document.querySelector('.nv-reconnect');
    if (!banner) return;
    var timer = null;

    if (!navigator.onLine) banner.classList.add('show');

    window.addEventListener('offline', function () {
      clearTimeout(timer);
      banner.classList.add('show');
      banner.style.background = '';
      banner.textContent = 'No internet connection';
    });

    window.addEventListener('online', function () {
      banner.classList.add('show');
      banner.style.background = '#16a34a';
      banner.textContent = 'Connected';
      clearTimeout(timer);
      timer = setTimeout(function () {
        banner.classList.remove('show');
        banner.style.background = '';
        banner.textContent = '';
      }, 3000);
    });
  }

  /* ================================================================
     SEARCH SUBMIT
     ================================================================ */

  function initSearchSubmit() {
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      var target = e.target;
      if (!target) return;
      var input = target.closest('[data-search-input]');
      if (!input) return;
      var q = input.value.trim();
      if (!q) {
        e.preventDefault();
        return;
      }
      e.preventDefault();
      window.location.href = '/search?q=' + encodeURIComponent(q);
    });
  }

  /* ================================================================
     TOWN CHIPS
     ================================================================ */

  function initTownChips() {
    document.addEventListener('click', function (e) {
      var chip = e.target.closest('[data-town-chip]');
      if (chip) {
        e.preventDefault();
        var town = chip.getAttribute('data-town-chip');
        if (town) {
          window.location.href = '/?town=' + encodeURIComponent(town);
        }
        return;
      }
      var clearBtn = e.target.closest('[data-clear-town]');
      if (clearBtn) {
        e.preventDefault();
        window.location.href = '/';
      }
    });
  }

  /* ================================================================
     HASHTAG CLICKS
     ================================================================ */

  function initHashTags() {
    document.addEventListener('click', function (e) {
      var tag = e.target.closest('.nv-reel-hashtag, .nv-rail-tag');
      if (!tag) return;
      e.preventDefault();
      var text = tag.textContent.replace(/^#/, '').trim();
      if (text) {
        window.location.href = '/search?q=%23' + encodeURIComponent(text);
      }
    });
  }

  /* ================================================================
     NAV ACTIVE STATE
     ================================================================ */

  function initNavActive() {
    var path = window.location.pathname;
    document.querySelectorAll('.nv-left-nav-item, .nv-bottom-nav-item, .nv-drawer-item').forEach(function (link) {
      var href = link.getAttribute('href');
      if (href && href !== '#' && path.indexOf(href) === 0) {
        link.classList.add('is-active');
      }
    });
  }

  /* ================================================================
     TOAST
     ================================================================ */

  function showToast(msg) {
    var toast = document.getElementById('nv-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'nv-toast';
      toast.className = 'nv-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('is-visible');
    clearTimeout(toast._hide);
    toast._hide = setTimeout(function () {
      toast.classList.remove('is-visible');
    }, 2000);
  }

  /* ================================================================
     UTILITIES
     ================================================================ */

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  }

  function relativeTime(dateStr) {
    if (!dateStr) return '';
    var now = new Date();
    var date = new Date(dateStr);
    var diff = (now - date) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h';
    if (diff < 2592000) return Math.floor(diff / 86400) + 'd';
    return Math.floor(diff / 2592000) + 'mo';
  }

  window.nvState = state;
  window.nvShowToast = showToast;
  window.nvCloseComment = closeCommentDrawer;
  window.nvCloseShare = closeShareDrawer;
  window.nvCloseStory = closeStoryModal;
})();
