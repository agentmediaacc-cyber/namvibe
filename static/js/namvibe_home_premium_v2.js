(function () {
  "use strict";

  /* ── CSRF ── */
  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  /* ── API helpers ── */
  function apiPost(url, body, cb) {
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
      body: body ? JSON.stringify(body) : undefined,
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { if (cb) cb(d); })
      .catch(function () {
        if (window.NamVibeToast && window.NamVibeToast.show)
          window.NamVibeToast.show('Something went wrong. Try again.');
      });
  }

  function apiGet(url, cb) {
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (d) { if (cb) cb(d); })
      .catch(function () {});
  }

  /* ── Toast helper ── */
  function toast(msg) {
    if (window.NamVibeToast && window.NamVibeToast.show)
      window.NamVibeToast.show(msg);
  }

  /* ── Likes ── */
  function toggleLike(btn, id, silent) {
    var countEl = btn.querySelector('span');
    var wasLiked = btn.classList.contains('liked');
    btn.classList.toggle('liked');
    if (countEl) {
      var cur = parseInt(countEl.textContent, 10) || 0;
      countEl.textContent = wasLiked ? Math.max(0, cur - 1) : cur + 1;
    }
    if (!silent) {
      apiPost('/api/home/post/' + id + '/like', {}, function (d) {
        if (!d || d.ok === false) {
          btn.classList.toggle('liked');
          if (countEl) {
            var cur2 = parseInt(countEl.textContent, 10) || 0;
            countEl.textContent = wasLiked ? cur2 + 1 : Math.max(0, cur2 - 1);
          }
        }
      });
    }
  }

  /* ── Save ── */
  function toggleSave(btn, id) {
    btn.classList.toggle('saved');
    apiPost('/api/home/post/' + id + '/save', {});
  }

  /* ── Share ── */
  function sharePost(id) {
    if (navigator.share) {
      navigator.share({ title: 'NamVibe', text: 'Check this on NamVibe', url: window.location.href });
    }
    apiPost('/api/home/post/' + id + '/share', {});
  }

  function buildPostUrl(id) {
    return window.location.origin + '/posts/' + encodeURIComponent(id || '');
  }

  function openPostMenu(id) {
    var sheet = document.getElementById('bottomSheetOverlay');
    if (!sheet) return;
    sheet.dataset.postId = id || '';
    if (window.openBottomSheet) window.openBottomSheet();
  }

  function closePostMenu() {
    var sheet = document.getElementById('bottomSheetOverlay');
    if (!sheet) return;
    sheet.dataset.postId = '';
    if (window.closeBottomSheet) window.closeBottomSheet();
  }

  /* ── Comment ── */
  function sendComment(id, inputEl) {
    var text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    apiPost('/api/home/post/' + id + '/comment', { body: text });
  }

  /* ── Follow ── */
  function followUser(btn, id) {
    btn.classList.toggle('following');
    if (btn.classList.contains('following')) btn.textContent = 'Following';
    else btn.textContent = 'Follow';
    apiPost('/api/profile/' + id + '/follow', {});
  }

  /* ── Modals ── */
  function openCreate() {
    var modal = document.getElementById('nv-create-modal') || document.getElementById('createModal');
    if (!modal) return;
    modal.hidden = false;
    document.body.classList.add('nv-overlay-open');
  }
  function closeCreate() {
    var modal = document.getElementById('nv-create-modal') || document.getElementById('createModal');
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('nv-overlay-open');
  }

  function openMenu() {
    var menu = document.getElementById('nvMobileMenu');
    var overlay = document.getElementById('nvMobileMenuOverlay');
    if (!menu || !overlay) return;
    menu.hidden = false;
    overlay.hidden = false;
    menu.setAttribute('aria-hidden', 'false');
    document.body.classList.add('nv-overlay-open');
  }

  function closeMenu() {
    var menu = document.getElementById('nvMobileMenu');
    var overlay = document.getElementById('nvMobileMenuOverlay');
    if (!menu || !overlay) return;
    menu.hidden = true;
    overlay.hidden = true;
    menu.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('nv-overlay-open');
  }

  function openComments(id) {
    var drawer = document.getElementById('commentsDrawer');
    drawer.hidden = false;
    drawer.dataset.postId = id;
    document.body.classList.add('nv-overlay-open');
    apiGet('/api/home/post/' + id + '/comments?limit=20', function (d) {
      var list = document.getElementById('commentsList');
      if (d && d.comments) {
        list.innerHTML = d.comments.map(function (c) {
          return '<div class="nv-cmt"><strong>' + (c.display_name || c.username || 'User') + '</strong> ' + (c.body || c.text || '') + '</div>';
        }).join('');
      } else {
        list.innerHTML = '<div style="color:var(--muted);padding:12px;">No comments yet</div>';
      }
    });
  }
  function closeComments() {
    document.getElementById('commentsDrawer').hidden = true;
    document.body.classList.remove('nv-overlay-open');
  }

  /* ── Multi-reactions (Emoji Picker) ── */
  function showReactions(btn) {
    if (window.NamVibeEmojiPicker) {
      window.NamVibeEmojiPicker.show(btn, function (emoji, input) {
        var postId = btn.dataset.id;
        apiPost('/api/home/post/' + postId + '/react', { reaction: emoji }, function () {});
        toast(emoji + ' reacted!');
        window.NamVibeEmojiPicker.hide();
      });
    } else {
      var reactionPicker = document.querySelector('.nv-reactions');
      if (!reactionPicker) {
        reactionPicker = document.createElement('div');
        reactionPicker.className = 'nv-reactions';
        reactionPicker.innerHTML = ['❤️', '👍', '😂', '😮', '😢', '😡', '🔥', '👏', '💯', '😍']
          .map(function (r) { return '<button data-reaction="' + r + '">' + r + '</button>'; }).join('');
        document.body.appendChild(reactionPicker);
        reactionPicker.addEventListener('click', function (e) {
          var rb = e.target.closest('[data-reaction]');
          if (!rb) return;
          var postId = reactionPicker.dataset.postId;
          var emoji = rb.dataset.reaction;
          apiPost('/api/home/post/' + postId + '/react', { reaction: emoji }, function () {});
          reactionPicker.classList.remove('active');
          toast(emoji + ' reacted!');
        });
        document.addEventListener('click', function (e) {
          if (reactionPicker && !e.target.closest('.nv-reactions') && !e.target.closest('[data-action="like"]')) {
            reactionPicker.classList.remove('active');
          }
        });
      }
      var rect = btn.getBoundingClientRect();
      reactionPicker.dataset.postId = btn.dataset.id;
      reactionPicker.style.bottom = (window.innerHeight - rect.top + 10) + 'px';
      reactionPicker.style.left = Math.max(10, rect.left + rect.width / 2 - 140) + 'px';
      reactionPicker.classList.toggle('active');
    }
  }

  /* ── Profile Preview ── */
  var previewTimer = null;
  function showProfilePreview(username, el) {
    if (!username) return;
    var existing = document.querySelector('.nv-preview-popup');
    if (existing) existing.remove();
    previewTimer = setTimeout(function () {
      var popup = document.createElement('div');
      popup.className = 'nv-preview-popup';
      popup.innerHTML = '<div class="nv-preview-loading">Loading...</div>';
      document.body.appendChild(popup);
      var rect = el.getBoundingClientRect();
      popup.style.top = (rect.bottom + 8) + 'px';
      popup.style.left = Math.max(10, rect.left) + 'px';
      apiGet('/api/profile/' + username + '/summary', function (d) {
        if (d && !d.error) {
          popup.innerHTML =
            '<div class="nv-preview-card">' +
            '<img src="' + (d.avatar_url || '/static/img/default-avatar.png') + '" class="nv-preview-avatar">' +
            '<div class="nv-preview-info">' +
            '<strong>' + (d.display_name || d.username || username) + '</strong>' +
            '<small>@' + (d.username || username) + '</small>' +
            '<div class="nv-preview-stats">' +
            '<span><strong>' + ((d.stats && d.stats.posts) || 0) + '</strong> Posts</span>' +
            '<span><strong>' + ((d.stats && d.stats.followers) || 0) + '</strong> Followers</span>' +
            '<span><strong>' + ((d.stats && d.stats.following) || 0) + '</strong> Following</span>' +
            '</div>' +
            (d.bio ? '<p class="nv-preview-bio">' + d.bio + '</p>' : '') +
            '<a href="/profile/' + username + '" class="nv-preview-link">View Profile</a>' +
            '</div></div>';
        } else {
          popup.innerHTML = '<div class="nv-preview-card">Profile not found</div>';
        }
      });
    }, 500);
  }
  function hideProfilePreview() {
    if (previewTimer) clearTimeout(previewTimer);
    var existing = document.querySelector('.nv-preview-popup');
    if (existing) existing.remove();
  }

  /* ── Infinite Scroll ── */
  var loadingMore = false;
  var page = 1;
  var hasMore = true;
  var currentTab = 'for-you';

  function loadMoreFeed() {
    if (loadingMore || !hasMore) return;
    loadingMore = true;
    var sentinel = document.getElementById('scroll-sentinel');
    if (sentinel) sentinel.textContent = 'Loading...';
    page++;
    apiGet('/api/homepage/feed?tab=' + currentTab + '&limit=10&page=' + page, function (d) {
      loadingMore = false;
      if (sentinel) sentinel.textContent = '';
      var items = d && d.payload && d.payload.feed_items;
      if (!items || items.length === 0) {
        hasMore = false;
        if (sentinel) sentinel.textContent = '';
        return;
      }
      var feed = document.querySelector('.nv-feed');
      items.forEach(function (item) {
        var html = renderPost(item);
        if (feed) feed.insertBefore(html, sentinel || null);
      });
    });
  }

  function renderPost(item) {
    var article = document.createElement('article');
    article.className = 'nv-post';
    article.dataset.postId = item.id;
    article.dataset.type = item.type || 'post';

    var likedClass = (item.is_liked || item.user_liked) ? ' liked' : '';
    var followClass = item.viewer_is_following ? ' following' : '';
    var followText = item.viewer_is_following ? 'Following' : 'Follow';
    var likeIcon = (item.is_liked || item.user_liked) ? '❤️' : '🤍';

    var mediaHtml = '';
    if (item.type === 'reel' || item.type === 'reels') {
      mediaHtml = '<div class="nv-reel-card">' +
        '<video src="' + (item.video_url || '') + '" poster="' + (item.thumbnail_url || '') + '" controls playsinline></video>' +
        '<div class="nv-reel-actions">' +
        '<button data-action="like" data-id="' + item.id + '">❤️<span>' + (item.likes_count || 0) + '</span></button>' +
        '<button data-action="comment" data-id="' + item.id + '">💬<span>' + (item.comments_count || 0) + '</span></button>' +
        '<button data-action="share" data-id="' + item.id + '">↗️<span>' + (item.shares_count || 0) + '</span></button>' +
        '<button data-action="save" data-id="' + item.id + '">🔖</button>' +
        '</div></div>';
    } else if (item.image_url || item.media_url) {
      mediaHtml = '<div class="nv-media"><img src="' + (item.image_url || item.media_url) + '" loading="lazy"></div>';
    } else if (item.video_url) {
      mediaHtml = '<div class="nv-media"><video src="' + item.video_url + '" poster="' + (item.thumbnail_url || '') + '" controls playsinline></video></div>';
    }

    article.innerHTML =
      '<div class="nv-post-head">' +
      '<a class="nv-user" href="/profile/' + (item.username || item.id) + '" data-profile-preview="' + (item.username || '') + '">' +
      '<img src="' + (item.avatar_url || '/static/img/default-avatar.png') + '" loading="lazy">' +
      '<div><strong>' + (item.display_name || item.username || 'User') +
      (item.verified || item.is_verified ? '<span class="nv-badge">✓</span>' : '') +
      '</strong><small>@' + (item.username || 'user') + ' · ' + (item.time_ago || item.created_label || 'now') + '</small></div></a>' +
      (item.username ? '<button class="nv-follow-btn' + followClass + '" data-action="follow" data-id="' + (item.profile_id || item.id) + '">' + followText + '</button>' : '') +
      '<button class="nv-more" data-action="post-more" data-id="' + item.id + '">⋯</button></div>' +
      ((item.caption || item.text) ? '<p class="nv-caption">' + (item.caption || item.text) + '</p>' : '') +
      mediaHtml +
      '<div class="nv-actions">' +
      '<button data-action="like" data-id="' + item.id + '" class="' + likedClass + '">' + likeIcon + ' <span>' + (item.likes_count || 0) + '</span></button>' +
      '<button data-action="comment" data-id="' + item.id + '">💬 ' + (item.comments_count || 0) + '</button>' +
      '<button data-action="share" data-id="' + item.id + '">↗️ Share</button>' +
      '<button data-action="send" data-id="' + item.id + '">📩 Send</button>' +
      '<button data-action="save" data-id="' + item.id + '">🔖</button></div>' +
      '<div class="nv-comment-box"><input type="text" placeholder="Write a comment..." data-comment-input="' + item.id + '">' +
      '<button data-action="send-comment" data-id="' + item.id + '">Send</button></div>';
    return article;
  }

  /* ── Tab switching ── */
  function switchTab(tab) {
    currentTab = tab;
    page = 1;
    hasMore = true;
    var feed = document.querySelector('.nv-feed');
    if (feed) {
      var sentinel = document.getElementById('scroll-sentinel');
      feed.innerHTML = '';
      if (sentinel) feed.appendChild(sentinel);
    }
    showSkeleton();
    apiGet('/api/homepage/feed?tab=' + tab + '&limit=10', function (d) {
      hideSkeleton();
      var items = d && d.payload && d.payload.feed_items;
      if (!items || items.length === 0) {
        if (feed) feed.innerHTML = '<div class="nv-empty"><h2>No posts yet</h2><p>Follow people to see their posts here.</p></div>';
        return;
      }
      if (feed) {
        items.forEach(function (item) {
          feed.appendChild(renderPost(item));
        });
        if (sentinel) feed.appendChild(sentinel);
      }
    });
  }

  /* ── Skeleton loading ── */
  function showSkeleton() {
    var feed = document.querySelector('.nv-feed');
    if (!feed) return;
    var count = 3;
    for (var i = 0; i < count; i++) {
      var sk = document.createElement('div');
      sk.className = 'nv-skeleton';
      sk.innerHTML =
        '<div class="nv-sk-head"><div class="nv-sk-avatar"></div><div><div class="nv-sk-line w-60"></div><div class="nv-sk-line w-40"></div></div></div>' +
        '<div class="nv-sk-media"></div>' +
        '<div class="nv-sk-actions"><div class="nv-sk-btn"></div><div class="nv-sk-btn"></div><div class="nv-sk-btn"></div></div>';
      feed.appendChild(sk);
    }
  }
  function hideSkeleton() {
    var skeletons = document.querySelectorAll('.nv-skeleton');
    skeletons.forEach(function (s) { s.remove(); });
  }

  /* ── Scroll hide/show top bar + bottom nav ── */
  var lastScrollY = 0;
  var scrollThreshold = 10;
  var topbar = document.querySelector('.nv-topbar');
  var bottomNav = document.querySelector('.nv-bottom-nav');

  function handleScroll() {
    var currentY = window.scrollY || window.pageYOffset;
    var delta = currentY - lastScrollY;

    if (Math.abs(delta) > scrollThreshold) {
      if (delta > 0 && currentY > 60) {
        if (topbar) topbar.classList.add('hidden');
        if (bottomNav) bottomNav.classList.add('hidden');
      } else {
        if (topbar) topbar.classList.remove('hidden');
        if (bottomNav) bottomNav.classList.remove('hidden');
      }
      lastScrollY = currentY;
    }
  }

  var ticking = false;
  window.addEventListener('scroll', function () {
    if (!ticking) {
      window.requestAnimationFrame(function () {
        handleScroll();
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });

  /* ── Video IntersectionObserver: autoplay when visible ── */
  function setupVideoAutoplay() {
    if (!('IntersectionObserver' in window)) return;
    var videoObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var video = entry.target;
        if (entry.isIntersecting) {
          video.play().catch(function () {});
        } else {
          video.pause();
        }
      });
    }, { threshold: [0.5] });
    document.querySelectorAll('.nv-media video, .nv-reel-card video').forEach(function (v) {
      videoObserver.observe(v);
    });
  }
  document.addEventListener('DOMContentLoaded', setupVideoAutoplay);

  /* ── MOBILE VIDEO FULLSCREEN OVERLAY (TikTok-style) ── */
  var videoOverlay = null;
  var overlayVideo = null;
  var overlayPostId = null;
  var overlayData = null;
  var voCloseTimer = null;

  function getOverlay() {
    if (!videoOverlay) {
      videoOverlay = document.createElement('div');
      videoOverlay.className = 'nv-video-overlay';
      videoOverlay.innerHTML =
        '<button class="nv-vo-close" id="voCloseBtn" aria-label="Close video">✕</button>' +
        '<video id="voVideo" muted playsinline></video>' +
        '<div class="nv-vo-like-heart" id="voLikeHeart">❤️</div>' +
        '<a class="nv-vo-user" id="voUserLink" href="#">' +
        '<img id="voUserAvatar" src="" alt="">' +
        '<span id="voUserName"></span>' +
        '</a>' +
        '<div class="nv-vo-caption" id="voCaption"></div>' +
        '<div class="nv-vo-actions">' +
        '<button id="voLikeBtn" data-action="like"><span id="voLikeIcon">🤍</span><span id="voLikeCount">0</span></button>' +
        '<button id="voCommentBtn" data-action="comment">💬<span id="voCommentCount">0</span></button>' +
        '<button id="voShareBtn" data-action="share">↗️<span id="voShareCount">0</span></button>' +
        '<button id="voSaveBtn" data-action="save">🔖</button>' +
        '</div>';
      document.body.appendChild(videoOverlay);

      overlayVideo = videoOverlay.querySelector('#voVideo');

      var closeBtn = videoOverlay.querySelector('#voCloseBtn');
      closeBtn.addEventListener('click', function () { closeVideoOverlay(); });

      overlayVideo.addEventListener('click', function () {
        if (overlayVideo.paused) overlayVideo.play();
        else overlayVideo.pause();
      });

      var lastTap = 0;
      overlayVideo.addEventListener('click', function (e) {
        var now = Date.now();
        if (now - lastTap < 300) {
          var heart = videoOverlay.querySelector('#voLikeHeart');
          heart.classList.remove('pop');
          void heart.offsetWidth;
          heart.classList.add('pop');
          var likeBtn = videoOverlay.querySelector('#voLikeBtn');
          if (likeBtn) toggleLike(likeBtn, overlayPostId, true);
          if (navigator.vibrate) navigator.vibrate(20);
        }
        lastTap = now;
      });

      overlayVideo.addEventListener('loadedmetadata', function () {
        overlayVideo.play().catch(function () {});
      });

      var touchStartY = 0;
      var swiping = false;
      videoOverlay.addEventListener('touchstart', function (e) {
        touchStartY = e.touches[0].clientY;
        swiping = false;
      }, { passive: true });
      videoOverlay.addEventListener('touchmove', function (e) {
        var dy = e.touches[0].clientY - touchStartY;
        if (Math.abs(dy) > 20) {
          swiping = true;
          var pct = Math.min(1, dy / window.innerHeight);
          videoOverlay.style.transform = 'translateY(' + (dy * 0.4) + 'px)';
          videoOverlay.style.opacity = 1 - pct * 0.5;
        }
      }, { passive: true });
      videoOverlay.addEventListener('touchend', function (e) {
        var dy = e.changedTouches[0].clientY - touchStartY;
        if (dy > 80) {
          videoOverlay.classList.add('dismissing');
          setTimeout(function () { closeVideoOverlay(); }, 300);
        } else {
          videoOverlay.style.transform = '';
          videoOverlay.style.opacity = '';
        }
      }, { passive: true });

      videoOverlay.querySelector('#voLikeBtn').addEventListener('click', function () {
        toggleLike(this, overlayPostId);
      });
      videoOverlay.querySelector('#voCommentBtn').addEventListener('click', function () {
        closeVideoOverlay();
        openComments(overlayPostId);
      });
      videoOverlay.querySelector('#voShareBtn').addEventListener('click', function () {
        sharePost(overlayPostId);
        toast('Shared!');
      });
      videoOverlay.querySelector('#voSaveBtn').addEventListener('click', function () {
        toggleSave(this, overlayPostId);
        toast('Saved!');
      });
    }
    return videoOverlay;
  }

  function openVideoOverlay(videoEl, postData) {
    var ov = getOverlay();
    ov.style.transform = '';
    ov.style.opacity = '';
    ov.classList.remove('dismissing');
    overlayPostId = postData.id;
    overlayData = postData;

    var src = videoEl.getAttribute('src') || videoEl.querySelector('source')?.getAttribute('src') || '';
    var poster = videoEl.getAttribute('poster') || '';

    overlayVideo.setAttribute('src', src);
    if (poster) overlayVideo.setAttribute('poster', poster);
    overlayVideo.muted = false;
    overlayVideo.controls = false;
    overlayVideo.load();

    var userLink = ov.querySelector('#voUserLink');
    userLink.href = '/profile/' + (postData.username || '');
    ov.querySelector('#voUserAvatar').src = postData.avatar_url || '/static/img/default-avatar.png';
    ov.querySelector('#voUserName').textContent = postData.display_name || postData.username || 'User';
    ov.querySelector('#voCaption').textContent = postData.caption || postData.text || '';
    ov.querySelector('#voCaption').style.display = (postData.caption || postData.text) ? 'block' : 'none';
    ov.querySelector('#voLikeCount').textContent = postData.likes_count || 0;
    ov.querySelector('#voCommentCount').textContent = postData.comments_count || 0;
    ov.querySelector('#voShareCount').textContent = postData.shares_count || 0;
    var likeBtn = ov.querySelector('#voLikeBtn');
    likeBtn.classList.toggle('liked', !!(postData.is_liked || postData.user_liked));
    likeBtn.querySelector('#voLikeIcon').textContent = (postData.is_liked || postData.user_liked) ? '❤️' : '🤍';

    ov.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeVideoOverlay() {
    if (!videoOverlay) return;
    videoOverlay.classList.remove('active', 'dismissing');
    videoOverlay.style.transform = '';
    videoOverlay.style.opacity = '';
    overlayVideo.pause();
    overlayVideo.removeAttribute('src');
    overlayVideo.load();
    document.body.style.overflow = '';
  }

  /* ── Tap video to open fullscreen overlay (mobile) ── */
  function isMobile() {
    return window.innerWidth < 768;
  }

  document.addEventListener('click', function (e) {
    var dynamicLink = e.target.closest('[data-nav-url]');
    if (dynamicLink) {
      var navUrl = dynamicLink.getAttribute('data-nav-url');
      if (navUrl) {
        e.preventDefault();
        window.location.href = navUrl;
        return;
      }
    }

    var video = e.target.closest('.nv-media video, .nv-reel-card video');
    if (!video || !isMobile()) return;
    var post = video.closest('.nv-post');
    if (!post) return;
    var postId = post.dataset.postId;
    var postEl = post;
    var data = {
      id: postId,
      username: postEl.querySelector('.nv-user')?.getAttribute('href')?.replace('/profile/', '') || '',
      display_name: postEl.querySelector('.nv-user strong')?.textContent || 'User',
      avatar_url: postEl.querySelector('.nv-user img')?.src || '',
      caption: postEl.querySelector('.nv-caption')?.textContent || '',
      likes_count: parseInt(postEl.querySelector('[data-action="like"] span')?.textContent || '0', 10),
      comments_count: parseInt(postEl.querySelector('[data-action="comment"]')?.textContent?.replace(/[^0-9]/g, '') || '0', 10),
      shares_count: parseInt(postEl.querySelector('[data-action="share"]')?.textContent?.replace(/[^0-9]/g, '') || '0', 10),
      is_liked: postEl.querySelector('[data-action="like"]')?.classList.contains('liked') || false,
    };
    openVideoOverlay(video, data);
  });

  /* ── Notification strip dismiss ── */
  document.addEventListener('click', function (e) {
    var dismissBtn = e.target.closest('.nv-notif-dismiss');
    if (!dismissBtn) return;
    var strip = dismissBtn.closest('.nv-notif-strip');
    if (strip) strip.classList.add('dismissed');
  });

  /* ── DOM Events ── */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    var action = btn.dataset.action;
    var id = btn.dataset.id;

    switch (action) {
      case 'open-create': openCreate(); break;
      case 'close-create': closeCreate(); break;
      case 'like': toggleLike(btn, id); break;
      case 'save': toggleSave(btn, id); break;
      case 'share': sharePost(id); break;
      case 'comment': openComments(id); break;
      case 'close-comments': closeComments(); break;
      case 'send-comment':
        sendComment(id, btn.previousElementSibling || document.querySelector('[data-comment-input="' + id + '"]'));
        break;
      case 'post-more': openPostMenu(id); break;
      case 'open-live': window.location.href = '/live/'; break;
      case 'open-chat': window.location.href = '/messages/'; break;
      case 'open-notifications': window.location.href = '/notifications/'; break;
      case 'open-menu': openMenu(); break;
      case 'close-menu': closeMenu(); break;
      case 'create-story': window.location.href = '/status/create'; break;
      case 'follow': followUser(btn, id); break;
      case 'open-studio':
        if (window.NamVibeCreativeStudio) window.NamVibeCreativeStudio.open();
        break;
      case 'dismiss-notif':
        var strip = btn.closest('.nv-notif-strip');
        if (strip) strip.classList.add('dismissed');
        break;
    }
  });

  document.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'nvMobileMenuOverlay') closeMenu();
    if (e.target && e.target.id === 'nv-create-modal') closeCreate();
    if (e.target && e.target.id === 'commentsDrawer') closeComments();
    if (e.target && e.target.id === 'bottomSheetOverlay') closePostMenu();
  });

  document.addEventListener('click', function (e) {
    var closeBtn = e.target.closest('.nv-bottom-sheet-close');
    if (closeBtn) {
      closePostMenu();
      return;
    }

    var actionBtn = e.target.closest('[data-sheet-action]');
    if (!actionBtn) return;
    var sheet = document.getElementById('bottomSheetOverlay');
    var postId = sheet ? sheet.dataset.postId : '';
    var action = actionBtn.dataset.sheetAction;
    if (!postId) {
      closePostMenu();
      return;
    }

    if (action === 'share') {
      sharePost(postId);
      toast('Shared!');
    } else if (action === 'copy') {
      var url = buildPostUrl(postId);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () {
          toast('Link copied');
        }).catch(function () {
          toast('Could not copy link');
        });
      } else {
        toast('Copy not supported here');
      }
    } else if (action === 'report') {
      window.location.href = '/support?report_post=' + encodeURIComponent(postId);
      return;
    }

    closePostMenu();
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-create]');
    if (!btn) return;
    var type = btn.dataset.create;
    switch (type) {
      case 'post': window.location.href = '/posts/create'; break;
      case 'reel': window.location.href = '/reels/upload'; break;
      case 'story': window.location.href = '/status/create'; break;
      case 'live': window.location.href = '/live/studio'; break;
      case 'photo': window.location.href = '/posts/create?type=photo'; break;
      case 'voice': window.location.href = '/messages/'; break;
    }
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.nv-story[data-story-id]');
    if (btn && btn.dataset.storyId) window.location.href = '/stories/' + btn.dataset.storyId;
  });

  var tabs = document.querySelectorAll('.nv-tabs button');
  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      tabs.forEach(function (b) { b.classList.remove('active'); });
      t.classList.add('active');
      var tab = t.dataset.feed || 'for-you';
      switchTab(tab);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var input = e.target.closest('.nv-search input');
      if (input) {
        var q = input.value.trim();
        if (q) window.location.href = '/discover/?q=' + encodeURIComponent(q);
      }
    } else if (e.key === 'Escape') {
      closeCreate();
      closeComments();
      closeMenu();
      closePostMenu();
    }
  });

  var scrollSentinel = document.getElementById('scroll-sentinel');
  if (scrollSentinel && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) loadMoreFeed();
      });
    }, { rootMargin: '400px' });
    observer.observe(scrollSentinel);
  }

  document.addEventListener('mouseover', function (e) {
    var link = e.target.closest('[data-profile-preview]');
    if (link) showProfilePreview(link.dataset.profilePreview, link);
  });
  document.addEventListener('mouseout', function (e) {
    var link = e.target.closest('[data-profile-preview]');
    if (link) hideProfilePreview();
  });

  var longPressTimer = null;
  document.addEventListener('mousedown', function (e) {
    var btn = e.target.closest('[data-action="like"]');
    if (!btn) return;
    longPressTimer = setTimeout(function () { showReactions(btn); }, 500);
  });
  document.addEventListener('mouseup', function () {
    if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
  });
  document.addEventListener('mouseleave', function () {
    if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
  });

  var touchTimer = null;
  document.addEventListener('touchstart', function (e) {
    var btn = e.target.closest('[data-action="like"]');
    if (!btn) return;
    touchTimer = setTimeout(function () { showReactions(btn); }, 500);
  }, { passive: true });
  document.addEventListener('touchend', function () {
    if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; }
  });
  document.addEventListener('touchmove', function () {
    if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; }
  }, { passive: true });

})();
