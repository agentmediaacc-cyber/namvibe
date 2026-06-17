/* ================================================================
   Phase 71 — NamVibe TikTok-style Reel Feed JS
   ================================================================ */

(function () {
  'use strict';

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  var state = {
    reels: [],
    currentIndex: 0,
    isPlaying: false,
    isMuted: true,
    commentReelId: null,
    shareReelId: null,
    activeVideo: null,
    lastTap: 0,
    scrollTimeout: null,
  };

  function init() {
    if (!document.querySelector('.tiktok-reel-scroll')) return;
    initReelScroll();
    initActionButtons();
    initCommentDrawer();
    initShareDrawer();
    initKeyboardNav();
  }

  /* ================================================================
     Reel Scroll / Navigation
     ================================================================ */
  function initReelScroll() {
    var container = document.querySelector('.tiktok-reel-scroll');
    if (!container) return;
    var cards = container.querySelectorAll('.tiktok-reel-card');
    state.reels = Array.from(cards);

    // Autoplay first visible reel
    setTimeout(function () {
      playReel(0);
    }, 300);

    // Scroll-based navigation
    container.addEventListener('scroll', function () {
      clearTimeout(state.scrollTimeout);
      state.scrollTimeout = setTimeout(function () {
        var index = getCurrentReelIndex(container);
        if (index !== -1 && index !== state.currentIndex) {
          playReel(index);
        }
      }, 100);
    }, { passive: true });

    // Touch swipe support
    var touchStartY = 0;
    container.addEventListener('touchstart', function (e) {
      touchStartY = e.touches[0].clientY;
    }, { passive: true });

    container.addEventListener('touchend', function (e) {
      var diff = touchStartY - e.changedTouches[0].clientY;
      if (Math.abs(diff) > 30) {
        clearTimeout(state.scrollTimeout);
        state.scrollTimeout = setTimeout(function () {
          var index = getCurrentReelIndex(container);
          if (index !== -1 && index !== state.currentIndex) {
            playReel(index);
          }
        }, 50);
      }
    }, { passive: true });

    // Mouse wheel
    container.addEventListener('wheel', function (e) {
      clearTimeout(state.scrollTimeout);
      state.scrollTimeout = setTimeout(function () {
        var index = getCurrentReelIndex(container);
        if (index !== -1 && index !== state.currentIndex) {
          playReel(index);
        }
      }, 150);
    }, { passive: true });
  }

  function getCurrentReelIndex(container) {
    var cards = container.querySelectorAll('.tiktok-reel-card');
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

  /* ================================================================
     Video Playback
     ================================================================ */
  function playReel(index) {
    // Stop previous
    if (state.activeVideo) {
      state.activeVideo.pause();
      state.activeVideo.currentTime = 0;
    }

    var card = state.reels[index];
    if (!card) return;

    state.currentIndex = index;
    var video = card.querySelector('.tiktok-reel-video');
    var thumbnail = card.querySelector('.tiktok-reel-thumbnail');
    var loader = card.querySelector('.tiktok-reel-loader');

    if (!video) return;

    state.activeVideo = video;
    video.muted = state.isMuted;

    // Try autoplay
    var playPromise = video.play();
    if (playPromise) {
      playPromise.then(function () {
        state.isPlaying = true;
        if (loader) loader.style.display = 'none';
        if (thumbnail) thumbnail.classList.add('is-hidden');
        video.controls = false;
      }).catch(function () {
        // Autoplay blocked — show controls
        video.controls = true;
        if (loader) loader.style.display = 'none';
        if (thumbnail) thumbnail.classList.remove('is-hidden');
      });
    }

    // Record view
    var reelId = card.getAttribute('data-reel-id');
    if (reelId) {
      fetch('/reels/api/reels/' + reelId + '/view', { method: 'POST', headers: { 'Content-Type': 'application/json' } }).catch(function () {});
    }

    updateActionRail(index);
  }

  /* ================================================================
     Tap to Pause/Play
     ================================================================ */
  document.addEventListener('click', function (e) {
    var card = e.target.closest('.tiktok-reel-card');
    if (!card) return;
    var now = Date.now();
    // Double tap detection for like
    if (state.lastTap && (now - state.lastTap) < 300) {
      handleDoubleTap(card);
      state.lastTap = 0;
      return;
    }
    state.lastTap = now;
    // Defer single tap for pause/play
    clearTimeout(card._tapTimer);
    card._tapTimer = setTimeout(function () {
      togglePlay(card);
    }, 300);
  });

  function togglePlay(card) {
    var video = card.querySelector('.tiktok-reel-video');
    if (!video) return;
    if (video.paused) {
      video.play().catch(function () {});
    } else {
      video.pause();
    }
  }

  /* ================================================================
     Double Tap Like
     ================================================================ */
  function handleDoubleTap(card) {
    var reelId = card.getAttribute('data-reel-id');
    if (!reelId) return;
    // Show heart animation
    var heart = card.querySelector('.tt-like-heart');
    if (heart) {
      heart.classList.remove('is-active');
      void heart.offsetWidth; // reflow
      heart.classList.add('is-active');
    }
    // Send like
    likeReel(reelId);
  }

  function likeReel(reelId) {
    fetch('/reels/api/reels/' + reelId + '/like', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          var btn = document.querySelector('.tiktok-action-btn[data-action="like"][data-reel-id="' + reelId + '"]');
          if (btn) {
            btn.classList.toggle('is-liked');
            var span = btn.querySelector('span');
            if (span) {
              var count = parseInt(span.textContent) || 0;
              span.textContent = btn.classList.contains('is-liked') ? (count + 1) : Math.max(0, count - 1);
            }
          }
        }
      })
      .catch(function () {});
  }

  /* ================================================================
     Update Action Rail
     ================================================================ */
  function updateActionRail(index) {
    var cards = document.querySelectorAll('.tiktok-action-rail');
    cards.forEach(function (rail) { rail.style.display = 'none'; });
    var card = state.reels[index];
    if (card) {
      var rail = card.querySelector('.tiktok-action-rail');
      if (rail) rail.style.display = 'flex';
    }
  }

  /* ================================================================
     Action Buttons (like, comment, share, save, follow)
     ================================================================ */
  function initActionButtons() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.tiktok-action-btn');
      if (!btn) return;
      var action = btn.getAttribute('data-action');
      var reelId = btn.getAttribute('data-reel-id');
      if (!action || !reelId) return;

      switch (action) {
        case 'like':
          likeReel(reelId);
          break;
        case 'comment':
          openCommentDrawer(reelId);
          break;
        case 'share':
          openShareDrawer(reelId);
          break;
        case 'save':
          saveReel(reelId);
          break;
      }
    });

    // Follow button
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.tt-follow-btn');
      if (!btn) return;
      var profileId = btn.getAttribute('data-profile-id');
      if (!profileId) return;
      followCreator(btn, profileId);
    });
  }

  function saveReel(reelId) {
    fetch('/reels/api/reels/' + reelId + '/save', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          var btn = document.querySelector('.tiktok-action-btn[data-action="save"][data-reel-id="' + reelId + '"]');
          if (btn) {
            btn.classList.toggle('is-saved');
            showToast(data.is_saved ? 'Saved' : 'Removed');
          }
        }
      })
      .catch(function () {});
  }

  function followCreator(btn, profileId) {
    var isFollowing = btn.classList.contains('is-following');
    var method = isFollowing ? 'unfollow' : 'follow';
    fetch('/api/profile/' + profileId + '/' + method, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success || data.ok) {
          btn.classList.toggle('is-following');
          btn.textContent = isFollowing ? 'Follow' : 'Following';
          showToast(isFollowing ? 'Unfollowed' : 'Following');
        } else {
          showToast(data.error || 'Could not update follow');
        }
      })
      .catch(function () {
        showToast('Network error');
      });
  }

  /* ================================================================
     Comment Drawer
     ================================================================ */
  function initCommentDrawer() {
    var overlay = document.getElementById('tt-comment-overlay');
    if (!overlay) return;

    var closeBtn = overlay.querySelector('.tt-comment-close');
    var sendBtn = overlay.querySelector('.tt-comment-send');
    var input = overlay.querySelector('.tt-comment-input');

    closeBtn && closeBtn.addEventListener('click', function () { closeCommentDrawer(); });

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeCommentDrawer();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeCommentDrawer();
    });

    sendBtn && sendBtn.addEventListener('click', function () {
      sendComment();
    });

    input && input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendComment();
      }
    });
  }

  function openCommentDrawer(reelId) {
    state.commentReelId = reelId;
    var overlay = document.getElementById('tt-comment-overlay');
    if (!overlay) return;
    overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    loadComments(reelId);
  }

  function closeCommentDrawer() {
    var overlay = document.getElementById('tt-comment-overlay');
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    state.commentReelId = null;
  }

  function loadComments(reelId) {
    var body = document.querySelector('.tt-comment-body');
    if (!body) return;
    body.innerHTML = '<div class="tt-comment-empty"><i class="fas fa-spinner fa-spin"></i><span>Loading comments...</span></div>';

    fetch('/reels/api/reels/' + reelId + '/comments')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var comments = data.comments || [];
        if (!comments.length) {
          body.innerHTML = '<div class="tt-comment-empty"><i class="fas fa-comment"></i><span>No comments yet. Be the first!</span></div>';
          return;
        }
        var html = '';
        comments.forEach(function (c) {
          var initial = (c.username || '?')[0];
          var avatarHtml = c.avatar_url
            ? '<img src="' + escapeHtml(c.avatar_url) + '" alt="" onerror="this.style.display=\'none\';this.parentElement.innerHTML=\'<span class=\\\\\'avatar-fallback\\\\\'>' + initial + '</span>\'">'
            : '<span class="avatar-fallback">' + initial + '</span>';
          html += '<div class="tt-comment-item">' +
            '<div class="tt-comment-avatar">' + avatarHtml + '</div>' +
            '<div><div class="tt-comment-author">@' + escapeHtml(c.username || 'user') + '</div>' +
            '<div class="tt-comment-text">' + escapeHtml(c.body || '') + '</div>' +
            '<div class="tt-comment-time">' + escapeHtml(relativeTime(c.created_at)) + '</div></div></div>';
        });
        body.innerHTML = html;
      })
      .catch(function () {
        body.innerHTML = '<div class="tt-comment-empty"><i class="fas fa-exclamation-circle"></i><span>Could not load comments.</span></div>';
      });
  }

  function sendComment() {
    var input = document.querySelector('.tt-comment-input');
    var sendBtn = document.querySelector('.tt-comment-send');
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
          loadComments(state.commentReelId);
          // Update comment count
          var btn = document.querySelector('.tiktok-action-btn[data-action="comment"][data-reel-id="' + state.commentReelId + '"]');
          if (btn) {
            var span = btn.querySelector('span');
            if (span) span.textContent = (parseInt(span.textContent) || 0) + 1;
          }
        } else {
          showToast(data.error || 'Could not post comment');
        }
      })
      .catch(function () { showToast('Network error'); })
      .finally(function () { sendBtn.disabled = false; });
  }

  /* ================================================================
     Share Drawer
     ================================================================ */
  function initShareDrawer() {
    var overlay = document.getElementById('tt-share-overlay');
    if (!overlay) return;

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeShareDrawer();
    });

    var nativeBtn = document.getElementById('tt-share-native');
    if (nativeBtn && navigator.share) {
      nativeBtn.style.display = '';
    } else if (nativeBtn) {
      nativeBtn.style.display = 'none';
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeShareDrawer();
    });

    // Share option clicks
    overlay.addEventListener('click', function (e) {
      var opt = e.target.closest('.tt-share-opt');
      if (!opt) return;
      var action = opt.getAttribute('data-share-action');
      if (action === 'copy') {
        var urlInput = document.getElementById('tt-share-url');
        if (urlInput) {
          if (navigator.clipboard) {
            navigator.clipboard.writeText(urlInput.value).then(function () {
              showToast('Link copied!');
              closeShareDrawer();
            }).catch(function () { fallbackCopy(urlInput); });
          } else {
            fallbackCopy(urlInput);
          }
        }
      } else if (action === 'native' && navigator.share) {
        var urlInput = document.getElementById('tt-share-url');
        navigator.share({ url: urlInput ? urlInput.value : window.location.href }).catch(function () {});
        closeShareDrawer();
      }
    });
  }

  function openShareDrawer(reelId) {
    state.shareReelId = reelId;
    var overlay = document.getElementById('tt-share-overlay');
    if (!overlay) return;
    var urlInput = document.getElementById('tt-share-url');
    if (urlInput) {
      urlInput.value = window.location.origin + '/reels#reel-' + reelId;
    }
    overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';

    // Record share
    fetch('/reels/api/reels/' + reelId + '/share', { method: 'POST', headers: { 'Content-Type': 'application/json' } }).catch(function () {});

    // Update share count
    var btn = document.querySelector('.tiktok-action-btn[data-action="share"][data-reel-id="' + reelId + '"]');
    if (btn) {
      var span = btn.querySelector('span');
      if (span) span.textContent = (parseInt(span.textContent) || 0) + 1;
    }
  }

  function closeShareDrawer() {
    var overlay = document.getElementById('tt-share-overlay');
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    state.shareReelId = null;
  }

  function fallbackCopy(input) {
    input.select();
    try {
      document.execCommand('copy');
      showToast('Link copied!');
      closeShareDrawer();
    } catch (e) {
      showToast('Could not copy');
    }
  }

  /* ================================================================
     Keyboard Navigation (Desktop)
     ================================================================ */
  function initKeyboardNav() {
    document.addEventListener('keydown', function (e) {
      var tag = (e.target || {}).tagName || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        var container = document.querySelector('.tiktok-reel-scroll');
        if (!container) return;
        var delta = e.key === 'ArrowDown' ? container.clientHeight * 0.9 : -container.clientHeight * 0.9;
        container.scrollBy({ top: delta, behavior: 'smooth' });
        setTimeout(function () {
          var index = getCurrentReelIndex(container);
          if (index !== -1 && index !== state.currentIndex) {
            playReel(index);
          }
        }, 200);
      }
      // Mute toggle with 'm'
      if (e.key === 'm' || e.key === 'M') {
        toggleMute();
      }
    });
  }

  function toggleMute() {
    state.isMuted = !state.isMuted;
    if (state.activeVideo) {
      state.activeVideo.muted = state.isMuted;
    }
    showToast(state.isMuted ? 'Muted' : 'Unmuted');
  }

  /* ================================================================
     Toast
     ================================================================ */
  function showToast(msg) {
    var toast = document.getElementById('tt-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'tt-toast';
      toast.className = 'tt-toast';
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
     Utilities
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

  // Expose for external use
  window.ttState = state;
  window.ttPlayReel = playReel;
  window.ttShowToast = showToast;
  window.ttCloseComment = closeCommentDrawer;
  window.ttCloseShare = closeShareDrawer;
})();
