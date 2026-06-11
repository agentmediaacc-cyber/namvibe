/* ============================================================
   CHAIN Message Composer
   Handles: auto-grow, drafts, typing emission, emoji, attach,
            voice recording, send coordination
   ============================================================ */

(function () {
  'use strict';

  var C = {};

  function init() {
    C.form = document.getElementById('chat-form');
    C.input = document.getElementById('msg-input');
    C.sendBtn = document.getElementById('send-btn');
    C.micBtn = document.getElementById('mic-btn');
    C.fileInput = document.getElementById('file-input');
    C.parentId = document.getElementById('parent_message_id');
    C.threadId = document.getElementById('thread_id');
    C.emojiPanel = document.getElementById('emoji-panel');
    C.attachPanel = document.getElementById('media-panel');
    C.stickerPanel = document.getElementById('sticker-panel');
    C.gifPanel = document.getElementById('gif-panel');
    C.voiceOverlay = document.getElementById('voice-overlay');
    C.voicePreview = document.getElementById('voice-note-preview');
    C.voiceAudio = document.getElementById('voice-note-audio');
    C.attachPreview = document.getElementById('attachment-preview');
    C.attachBody = document.getElementById('attachment-preview-body');
    C.attachRemove = document.getElementById('attachment-remove');
    C.recordingTimer = document.getElementById('recording-timer');
    C.draftIndicator = document.getElementById('draft-indicator');
    C.typingIndicator = document.getElementById('typing-indicator');
    C.typingText = document.getElementById('typing-text');

    if (!C.form || !C.input) return;

    C.DRAFT_KEY = 'chain_draft_' + (C.threadId ? C.threadId.value : '');
    C.TYPING_TIMEOUT_MS = 2000;
    C.typingTimeout = null;
    C.draftTimer = null;
    C.pendingAttachment = null;
    C.pendingVoiceFile = null;
    C.mediaRecorder = null;
    C.audioChunks = [];
    C.recordTimer = null;
    C.startTime = null;
    C.isRecording = false;

    C.emojiCategories = {
      Smileys: ['\u{1F600}','\u{1F603}','\u{1F604}','\u{1F601}','\u{1F606}','\u{1F602}','\u{1F923}','\u{1F60A}','\u{1F60D}','\u{1F970}','\u{1F618}','\u{1F60E}','\u{1F929}','\u{1F973}','\u{1F60B}','\u{1F97A}','\u{1F625}','\u{1F600}','\u{1F609}','\u{1F60C}','\u{1F914}','\u{1F634}','\u{1F92F}','\u{1F979}'],
      Hearts: ['\u2764\uFE0F','\u{1F9E1}','\u{1F49B}','\u{1F49A}','\u{1F499}','\u{1F49C}','\u{1F5A4}','\u{1F90D}','\u{1F90E}','\u{1F495}','\u{1F49E}','\u{1F493}','\u{1F497}','\u{1F496}','\u{1F498}','\u{1F49D}','\u{1F49F}','\u2763\uFE0F','\u2764\uFE0F\u200D\u{1F525}','\u2764\uFE0F\u200D\u{1FA79}'],
      Hands: ['\u{1F44B}','\u{1F91A}','\u270B','\u{1F44C}','\u{1F90C}','\u{1F90F}','\u270C\uFE0F','\u{1F91E}','\u{1F91F}','\u{1F918}','\u{1F919}','\u{1F448}','\u{1F449}','\u{1F446}','\u{1F447}','\u{1F44D}','\u{1F44E}','\u270A','\u{1F44A}','\u{1F44F}','\u{1F64C}','\u{1FAF6}','\u{1F64F}','\u{1F91D}'],
      Fire: ['\u{1F525}','\u{1F4A5}','\u26A1','\u2728','\u{1F31F}','\u{1F31F}','\u{1F4AB}','\u{1F680}','\u{1F3C6}','\u{1F4AF}','\u{1F389}','\u{1F38A}','\u{1F534}','\u{1F7E0}','\u{1F7E1}','\u{1F7E2}','\u{1F535}','\u{1F7E3}'],
      Food: ['\u{1F34E}','\u{1F34C}','\u{1F347}','\u{1F353}','\u{1F352}','\u{1F96D}','\u{1F34D}','\u{1F951}','\u{1F354}','\u{1F35F}','\u{1F355}','\u{1F32E}','\u{1F357}','\u{1F356}','\u{1F369}','\u{1F36A}','\u{1F370}','\u2615','\u{1F37A}','\u{1F942}'],
      Flags: ['\u{1F1F3}\u{1F1E6}','\u{1F1FF}\u{1F1E6}','\u{1F1E7}\u{1F1FC}','\u{1F1FF}\u{1F1F2}','\u{1F1FF}\u{1F1FC}','\u{1F1E6}\u{1F1F4}','\u{1F1FA}\u{1F1F8}','\u{1F1EC}\u{1F1E7}','\u{1F1EA}\u{1F1FA}','\u{1F1E8}\u{1F1E6}','\u{1F1E7}\u{1F1F7}','\u{1F1EE}\u{1F1F3}','\u{1F1E8}\u{1F1F3}','\u{1F1EF}\u{1F1F5}','\u{1F1E6}\u{1F1FA}','\u{1F3C1}','\u{1F6A9}','\u{1F3F4}']
    };
    C.activeEmojiCategory = 'Smileys';
    C._emojiListener = null;

    bindEvents();
    restoreDraft();
    updateSendButton();
    initSmartFeatures();
  }

  /* ---- Auto-grow ---- */
  function autoGrow() {
    C.input.style.height = 'auto';
    var scrollH = C.input.scrollHeight;
    var maxH = parseFloat(getComputedStyle(C.input).lineHeight || 20) * 5;
    C.input.style.height = Math.min(scrollH, maxH) + 'px';
    if (scrollH > maxH) {
      C.input.style.overflowY = 'auto';
    } else {
      C.input.style.overflowY = 'hidden';
    }
  }

  /* ---- Draft ---- */
  function saveDraft() {
    try {
      var text = C.input.value.trim();
      if (text) {
        localStorage.setItem(C.DRAFT_KEY, text);
        showDraftIndicator(true);
      } else {
        localStorage.removeItem(C.DRAFT_KEY);
        showDraftIndicator(false);
      }
    } catch (e) {}
  }

  function restoreDraft() {
    try {
      var saved = localStorage.getItem(C.DRAFT_KEY);
      if (saved) {
        C.input.value = saved;
        if (C.sendBtn) C.sendBtn.disabled = false;
        autoGrow();
        showDraftIndicator(true);
      }
    } catch (e) {}
  }

  function clearDraft() {
    try {
      localStorage.removeItem(C.DRAFT_KEY);
      showDraftIndicator(false);
    } catch (e) {}
  }

  function showDraftIndicator(show) {
    if (!C.draftIndicator) {
      C.draftIndicator = document.getElementById('draft-indicator');
      if (!C.draftIndicator) return;
    }
    C.draftIndicator.style.display = show ? 'inline' : 'none';
  }

  /* ---- Send button state ---- */
  function updateSendButton() {
    if (!C.sendBtn) return;
    var hasText = C.input.value.trim().length > 0;
    var hasFile = !!C.pendingAttachment;
    C.sendBtn.disabled = !hasText && !hasFile;
  }

  /* ---- Typing emission ---- */
  function emitTypingStart() {
    if (typeof debouncedTypingStart === 'function') {
      debouncedTypingStart(C.threadId ? C.threadId.value : '');
    } else {
      try {
        var s = window.socket || window.io();
        s.emit('typing:start', { thread_id: C.threadId ? C.threadId.value : '' });
      } catch (e) {}
    }
  }

  function emitTypingStop() {
    if (typeof debouncedTypingStop === 'function') {
      debouncedTypingStop(C.threadId ? C.threadId.value : '');
    } else {
      try {
        var s = window.socket || window.io();
        s.emit('typing:stop', { thread_id: C.threadId ? C.threadId.value : '' });
      } catch (e) {}
    }
  }

  /* ---- Emoji ---- */
  function toggleEmojiPanel() {
    if (!C.emojiPanel) return;
    var shown = C.emojiPanel.style.display === 'block';
    C.emojiPanel.style.display = shown ? 'none' : 'block';
    if (C.stickerPanel) C.stickerPanel.style.display = 'none';
    if (C.gifPanel) C.gifPanel.style.display = 'none';
    if (C.attachPanel) C.attachPanel.style.display = 'none';
    if (!shown) {
      renderEmojiGrid(C.activeEmojiCategory);
      if (!C._emojiListener) {
        C._emojiListener = function (e) {
          if (C.emojiPanel && !C.emojiPanel.contains(e.target) && !e.target.closest('[data-action="emoji"]') && !e.target.closest('.emoji-tabs') && !e.target.closest('.emoji-item') && !e.target.closest('.emoji-grid')) {
            C.emojiPanel.style.display = 'none';
          }
        };
        document.addEventListener('click', C._emojiListener);
      }
    }
  }

  function insertEmoji(emoji) {
    var start = C.input.selectionStart;
    var end = C.input.selectionEnd;
    C.input.value = C.input.value.substring(0, start) + emoji + C.input.value.substring(end);
    C.input.selectionStart = C.input.selectionEnd = start + emoji.length;
    C.input.focus();
    updateSendButton();
  }

  function renderEmojiGrid(category) {
    C.activeEmojiCategory = category || C.activeEmojiCategory;
    var grid = document.getElementById('emoji-grid');
    if (!grid) return;
    grid.innerHTML = (C.emojiCategories[C.activeEmojiCategory] || []).map(function (e) {
      return '<button type="button" class="emoji-item" data-emoji="' + e + '">' + e + '</button>';
    }).join('');
    document.querySelectorAll('[data-emoji-tab]').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.emojiTab === C.activeEmojiCategory);
    });
  }

  /* ---- Attach ---- */
  function uploadFile(file) {
    if (!file) return;
    C.pendingAttachment = file;
    var preview = C.attachPreview;
    var body = C.attachBody;
    if (!preview || !body) return;
    var url = URL.createObjectURL(file);
    body.innerHTML = renderMediaTag(url, file.type) + '<span class="attachment-name">' + escapeHtml(file.name) + '</span>';
    preview.hidden = false;
    updateSendButton();
  }

  function hideAttachmentPreview() {
    if (C.attachPreview) C.attachPreview.hidden = true;
    if (C.attachBody) C.attachBody.innerHTML = '';
  }

  /* ---- Voice Recording ---- */

  function detectAudioMime() {
    var types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/mpeg',
      'audio/ogg;codecs=opus',
      'audio/ogg',
    ];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) {
        return types[i];
      }
    }
    return '';
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      var mimeType = detectAudioMime();
      var options = {};
      if (mimeType) {
        options.mimeType = mimeType;
      }
      if (!MediaRecorder.isTypeSupported) {
        C.mediaRecorder = new MediaRecorder(stream);
      } else {
        C.mediaRecorder = new MediaRecorder(stream, options);
      }
      C.audioChunks = [];
      C.isRecording = true;

      C.mediaRecorder.ondataavailable = function (e) {
        if (e.data.size > 0) {
          C.audioChunks.push(e.data);
        }
      };
      C.mediaRecorder.onstop = handleVoiceStop;

      C.mediaRecorder.start(250);
      C.startTime = Date.now();
      if (C.voiceOverlay) C.voiceOverlay.style.display = 'flex';
      if (C.micBtn) C.micBtn.classList.add('recording');

      if (C.form) C.form.style.display = 'none';

      C.recordTimer = setInterval(function () {
        var elapsed = Math.floor((Date.now() - C.startTime) / 1000);
        var m = Math.floor(elapsed / 60);
        var s = elapsed % 60;
        if (C.recordingTimer) {
          C.recordingTimer.innerText = m.toString().padStart(2, '0') + ':' + s.toString().padStart(2, '0');
        }
      }, 1000);
    } catch (e) {
      C.isRecording = false;
    }
  }

  function handleVoiceStop() {
    var tracks = [];
    if (C.mediaRecorder) {
      try { tracks = C.mediaRecorder.stream ? C.mediaRecorder.stream.getTracks() : []; } catch (ex) {}
    }
    tracks.forEach(function (t) { try { t.stop(); } catch (ex) {} });
    clearInterval(C.recordTimer);
    if (C.voiceOverlay) C.voiceOverlay.style.display = 'none';
    if (C.micBtn) C.micBtn.classList.remove('recording');
    if (C.form) C.form.style.display = '';
    C.isRecording = false;
    uploadVoiceNote();
    C.mediaRecorder = null;
  }

  function stopAndSendVoice() {
    if (C.mediaRecorder && C.mediaRecorder.state === 'recording') {
      C.mediaRecorder.stop();
    }
  }

  function cancelRecording() {
    if (C.mediaRecorder && C.mediaRecorder.state === 'recording') {
      C.audioChunks = [];
      C.mediaRecorder.stop();
    } else {
      C.audioChunks = [];
      C.isRecording = false;
    }
  }

  function uploadVoiceNote() {
    if (!C.audioChunks || C.audioChunks.length === 0) return;
    var mime = detectAudioMime() || 'audio/webm';
    var ext = 'webm';
    if (mime.indexOf('mp4') !== -1) ext = 'mp4';
    else if (mime.indexOf('mpeg') !== -1) ext = 'mp3';
    else if (mime.indexOf('ogg') !== -1) ext = 'ogg';
    var audioBlob = new Blob(C.audioChunks, { type: mime });
    C.pendingVoiceFile = new File([audioBlob], 'voice-note.' + ext, { type: mime });
    if (C.voiceAudio) {
      C.voiceAudio.src = URL.createObjectURL(audioBlob);
      C.voiceAudio.load();
    }
    if (C.voicePreview) C.voicePreview.hidden = false;
  }

  /* ---- Events ---- */
  function bindEvents() {
    /* Input: auto-grow, typing, draft */
    C.input.addEventListener('input', function () {
      autoGrow();
      updateSendButton();
      clearTimeout(C.typingTimeout);
      clearTimeout(C.draftTimer);
      if (C.input.value.trim().length > 0) {
        emitTypingStart();
      } else {
        emitTypingStop();
      }
      C.typingTimeout = setTimeout(function () {
        emitTypingStop();
      }, C.TYPING_TIMEOUT_MS);
      C.draftTimer = setTimeout(saveDraft, 500);
    });

    /* Enter sends, Shift+Enter newline */
    C.input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        C.form.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });

    /* Form submit */
    C.form.addEventListener('submit', handleSubmit);

    /* File input */
    if (C.fileInput) {
      C.fileInput.addEventListener('change', function () {
        if (C.fileInput.files && C.fileInput.files[0]) uploadFile(C.fileInput.files[0]);
      });
    }

    /* Attachment remove */
    if (C.attachRemove) {
      C.attachRemove.addEventListener('click', function () {
        C.pendingAttachment = null;
        if (C.fileInput) C.fileInput.value = '';
        hideAttachmentPreview();
        updateSendButton();
      });
    }

    /* Action buttons via data attributes */
    document.querySelectorAll('[data-action="emoji"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toggleEmojiPanel();
      });
    });

    /* Emoji tab clicks */
    document.querySelectorAll('[data-emoji-tab]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        renderEmojiGrid(btn.dataset.emojiTab);
      });
    });

    /* Emoji grid click */
    var emojiGrid = document.getElementById('emoji-grid');
    if (emojiGrid) {
      emojiGrid.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-emoji]');
        if (btn) insertEmoji(btn.dataset.emoji);
      });
    }

    /* Mic button press-and-hold */
    if (C.micBtn) {
      C.micBtn.addEventListener('mousedown', startRecording);
      C.micBtn.addEventListener('mouseup', stopAndSendVoice);
      C.micBtn.addEventListener('mouseleave', function () {
        if (C.isRecording) stopAndSendVoice();
      });
      C.micBtn.addEventListener('touchstart', function (e) {
        e.preventDefault();
        startRecording();
      }, { passive: false });
      C.micBtn.addEventListener('touchend', function (e) {
        e.preventDefault();
        stopAndSendVoice();
      }, { passive: false });
    }

    /* Voice preview buttons */
    var voiceSend = document.getElementById('voice-preview-send');
    if (voiceSend) {
      voiceSend.addEventListener('click', async function () {
        if (!C.pendingVoiceFile) return;
        if (typeof sendMessage === 'function') {
          await sendMessage('', C.pendingVoiceFile);
        }
        C.pendingVoiceFile = null;
        if (C.voicePreview) C.voicePreview.hidden = true;
      });
    }

    var voiceDelete = document.getElementById('voice-preview-delete');
    if (voiceDelete) {
      voiceDelete.addEventListener('click', function () {
        C.pendingVoiceFile = null;
        C.audioChunks = [];
        if (C.voicePreview) C.voicePreview.hidden = true;
      });
    }

    var voiceRerecord = document.getElementById('voice-preview-rerecord');
    if (voiceRerecord) {
      voiceRerecord.addEventListener('click', function () {
        C.pendingVoiceFile = null;
        C.audioChunks = [];
        if (C.voicePreview) C.voicePreview.hidden = true;
        startRecording();
      });
    }

    /* Voice overlay controls */
    var voiceCancel = document.querySelector('#voice-overlay [data-voice-control="cancel"]');
    if (voiceCancel) {
      voiceCancel.addEventListener('click', cancelRecording);
    }
    var voiceLock = document.querySelector('[data-voice-control="lock"]');
    if (voiceLock) {
      voiceLock.addEventListener('click', function () {
        voiceLock.classList.toggle('locked');
      });
    }
    var voicePause = document.querySelector('[data-voice-control="pause"]');
    if (voicePause) {
      voicePause.addEventListener('click', function () {
        if (C.mediaRecorder && C.mediaRecorder.state === 'recording') {
          C.mediaRecorder.pause();
          voicePause.style.display = 'none';
          var voiceResume = document.querySelector('[data-voice-control="resume"]');
          if (voiceResume) voiceResume.style.display = '';
        }
      });
    }
    var voiceResume = document.querySelector('[data-voice-control="resume"]');
    if (voiceResume) {
      voiceResume.addEventListener('click', function () {
        if (C.mediaRecorder && C.mediaRecorder.state === 'paused') {
          C.mediaRecorder.resume();
          voiceResume.style.display = 'none';
          if (voicePause) voicePause.style.display = '';
        }
      });
    }
  }

  /* ---- Submit handler ---- */
  async function handleSubmit(e) {
    e.preventDefault();
    var body = C.input.value.trim();
    var file = C.pendingAttachment || C.pendingVoiceFile;
    if (!body && !file) return;

    var savedBody = body;
    C.input.value = '';
    C.input.style.height = 'auto';
    C.pendingAttachment = null;
    C.pendingVoiceFile = null;
    if (C.fileInput) C.fileInput.value = '';
    hideAttachmentPreview();
    if (C.voicePreview) C.voicePreview.hidden = true;
    updateSendButton();
    clearDraft();
    emitTypingStop();

    if (typeof sendMessage === 'function') {
      await sendMessage(body, file);
    } else {
      console.warn('[Composer] sendMessage not available');
    }

    cancelReply();
  }

  /* ============================================================
     Smart Composer Features: AI, Smart Replies, Location, Media,
     Voice Upgrades, Reply/Edit/Quote, Shortcuts, Themes, A11y
     ============================================================ */

  /* ---- AI Assistant ---- */
  C.aiTransforms = {
    friendly: { icon: 'fa-face-smile', label: 'Make Friendly', hint: 'Warm, casual tone' },
    professional: { icon: 'fa-briefcase', label: 'Make Professional', hint: 'Formal business tone' },
    shorter: { icon: 'fa-compress', label: 'Make Shorter', hint: 'Concise version' },
    grammar: { icon: 'fa-spell-check', label: 'Fix Grammar', hint: 'Correct spelling & grammar' },
    translate: { icon: 'fa-language', label: 'Translate', hint: 'Translate to English' },
    suggest: { icon: 'fa-wand-magic-sparkles', label: 'Suggest Reply', hint: 'AI suggests a response' },
    template: { icon: 'fa-rectangle-ad', label: 'Quick Reply Templates', hint: 'Common replies' },
  };

  function toggleAIPanel() {
    var panel = document.getElementById('ai-panel');
    if (!panel) return;
    var shown = panel.classList.contains('show');
    panel.classList.toggle('show', !shown);
    if (C.emojiPanel) C.emojiPanel.style.display = 'none';
    if (C.stickerPanel) C.stickerPanel.style.display = 'none';
    if (C.gifPanel) C.gifPanel.style.display = 'none';
    if (C.attachPanel) C.attachPanel.style.display = 'none';
    var themeMenu = document.getElementById('theme-menu');
    if (themeMenu) themeMenu.classList.remove('show');
  }

  function applyAITransform(mode) {
    var input = C.input;
    var text = input.value.trim();
    var panel = document.getElementById('ai-panel');
    if (panel) panel.classList.remove('show');

    if (mode === 'template') {
      showSmartReplies(['Okay, sounds good!', 'I will check and get back to you.', 'Thank you!', 'Please send details.', 'On it!', 'Got it, thanks!', 'Let me confirm.', 'Will do!']);
      return;
    }

    if (!text) {
      if (mode === 'suggest') {
        showSmartReplies(['Sure, what do you need?', 'Let me look into that.', 'I am here to help!', 'Can you clarify?']);
        return;
      }
      return;
    }

    var transformed = transformText(text, mode);
    if (transformed && transformed !== text) {
      input.value = transformed;
      autoGrow();
      updateSendButton();
      showSuggestionChip(transformed);
    }
  }

  function transformText(text, mode) {
    var transforms = {
      friendly: function (t) {
        var lower = t.toLowerCase();
        if (lower.startsWith('please') || lower.includes('thanks') || lower.includes('thank you')) return t;
        return 'Hey! ' + t.charAt(0).toUpperCase() + t.slice(1) + ' 😊';
      },
      professional: function (t) {
        if (t.length > 1) return 'Dear team, ' + t.charAt(0).toLowerCase() + t.slice(1).replace(/[.!]+$/, '') + '. Best regards.';
        return t;
      },
      shorter: function (t) {
        if (t.length > 50) return t.slice(0, 47) + '...';
        return t;
      },
      grammar: function (t) {
        return t.replace(/\bi\b/g, 'I').replace(/ u /g, ' you ').replace(/r u/g, 'are you').replace(/pls/g, 'please').replace(/thx/g, 'thanks').replace(/im /g, "I'm ").replace(/dont/g, "don't").replace(/cant/g, "can't").replace(/wont/g, "won't").replace(/didnt/g, "didn't");
      },
      translate: function (t) {
        return t;
      },
    };
    return (transforms[mode] || function (t) { return t; })(text);
  }

  function showSuggestionChip(transformed) {
    var existing = document.querySelector('.ai-suggestion-chip');
    if (existing) existing.remove();
    var chip = document.createElement('div');
    chip.className = 'ai-suggestion-chip';
    chip.innerHTML = '<span>Use suggestion</span>';
    chip.onclick = function () { chip.remove(); };
    var preview = document.getElementById('ai-panel');
    if (preview) {
      var body = preview.querySelector('.ai-body');
      if (body) body.appendChild(chip);
    }
  }

  /* ---- Smart Reply Chips ---- */
  function showSmartReplies(replies) {
    var bar = document.getElementById('smart-reply-bar');
    if (!bar) return;
    bar.innerHTML = '';
    (replies || ['Okay', 'Thank you', 'I will check', 'Please send details']).forEach(function (r) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'smart-reply-chip';
      chip.textContent = r;
      chip.onclick = function () { insertSmartReply(r); };
      bar.appendChild(chip);
    });
    bar.classList.add('show');
    C._smartReplyTimer = setTimeout(function () {
      bar.classList.remove('show');
    }, 15000);
    if (C._smartReplyTimer) clearTimeout(C._smartReplyTimer);
    C._smartReplyTimer = setTimeout(function () {
      bar.classList.remove('show');
    }, 15000);
  }

  function hideSmartReplies() {
    var bar = document.getElementById('smart-reply-bar');
    if (bar) bar.classList.remove('show');
    if (C._smartReplyTimer) { clearTimeout(C._smartReplyTimer); C._smartReplyTimer = null; }
  }

  function insertSmartReply(text) {
    C.input.value = text;
    autoGrow();
    updateSendButton();
    hideSmartReplies();
    C.input.focus();
  }

  /* ---- Location Sharing ---- */
  function shareLocation() {
    if (!navigator.geolocation) {
      C.input.value = '📍 My location: https://maps.google.com/?q=0,0 (Location unavailable)';
      autoGrow(); updateSendButton();
      return;
    }
    var preview = document.getElementById('location-preview');
    if (preview) preview.hidden = false;

    navigator.geolocation.getCurrentPosition(
      function (pos) {
        var lat = pos.coords.latitude;
        var lng = pos.coords.longitude;
        C._pendingLocation = { lat: lat, lng: lng };
        updateLocationPreview(lat, lng);
      },
      function () {
        C._pendingLocation = { lat: 0, lng: 0 };
        if (preview) preview.hidden = true;
        C.input.value = '📍 My location: https://maps.google.com/?q=0,0';
        autoGrow(); updateSendButton();
      }
    );
  }

  function updateLocationPreview(lat, lng) {
    var preview = document.getElementById('location-preview');
    if (!preview) return;
    preview.hidden = false;
    var coords = preview.querySelector('.lp-coords');
    if (coords) coords.textContent = lat.toFixed(4) + ', ' + lng.toFixed(4);
    var mapEl = preview.querySelector('.lp-map i');
    if (mapEl) mapEl.className = 'fas fa-map-marker-alt';
  }

  function sendLocation() {
    var loc = C._pendingLocation;
    if (!loc) return;
    var body = '📍 My location: https://maps.google.com/?q=' + loc.lat + ',' + loc.lng;
    C.input.value = body;
    autoGrow();
    updateSendButton();
    C._pendingLocation = null;
    var preview = document.getElementById('location-preview');
    if (preview) preview.hidden = true;
  }

  function cancelLocation() {
    C._pendingLocation = null;
    var preview = document.getElementById('location-preview');
    if (preview) preview.hidden = true;
  }

  /* ---- Media: File size warning, camera ---- */
  function uploadFileWithCheck(file) {
    if (!file) return;
    var maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      alert('File too large. Max 50 MB.');
      return;
    }
    uploadFile(file);
  }

  function captureCamera() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*;capture=camera';
    input.onchange = function () {
      if (input.files && input.files[0]) uploadFileWithCheck(input.files[0]);
    };
    input.click();
  }

  /* ---- Voice: Slide cancel zone detection ---- */
  C._voiceStartY = 0;
  C._voiceSlideCancel = false;

  function onVoiceTouchStart(e) {
    C._voiceStartY = e.touches ? e.touches[0].clientY : e.clientY;
    C._voiceSlideCancel = false;
    startRecording();
  }

  function onVoiceTouchMove(e) {
    if (!C.isRecording) return;
    var y = e.touches ? e.touches[0].clientY : e.clientY;
    var diff = y - C._voiceStartY;
    if (diff > 60) {
      C._voiceSlideCancel = true;
      var zone = document.querySelector('.vo-slide-cancel-zone');
      if (zone) zone.classList.add('active');
    }
  }

  function onVoiceTouchEnd(e) {
    var zone = document.querySelector('.vo-slide-cancel-zone');
    if (zone) zone.classList.remove('active');
    if (C._voiceSlideCancel) {
      cancelRecording();
      C._voiceSlideCancel = false;
    } else if (C.isRecording) {
      stopAndSendVoice();
    }
  }

  /* ---- Reply/Edit/Quote preview in composer ---- */
  function initReplyFromComposer(msgId, msgText, author) {
    var preview = document.getElementById('reply-preview');
    var textEl = document.getElementById('reply-text');
    var parentId = document.getElementById('parent_message_id');
    if (preview && textEl && parentId) {
      preview.style.display = 'flex';
      textEl.innerHTML = '<strong>' + (author || '') + '</strong> ' + (msgText || '');
      parentId.value = msgId;
      C._replyMode = msgId;
    }
    C.input.focus();
  }

  function cancelReplyFromComposer() {
    var preview = document.getElementById('reply-preview');
    var parentId = document.getElementById('parent_message_id');
    if (preview) preview.style.display = 'none';
    if (parentId) parentId.value = '';
    C._replyMode = null;
  }

  function initEditFromComposer(msgId, msgText) {
    C.input.value = msgText || '';
    autoGrow();
    updateSendButton();
    C._editMode = msgId;
    C._originalText = msgText || '';
    var editPreview = document.getElementById('edit-preview');
    if (editPreview) editPreview.classList.add('show');
    C.input.focus();
  }

  function cancelEditFromComposer() {
    C._editMode = null;
    C._originalText = null;
    var editPreview = document.getElementById('edit-preview');
    if (editPreview) editPreview.classList.remove('show');
    var currentText = C.input.value;
    if (currentText === '') {
      C.input.value = C._originalText || '';
      autoGrow();
    }
  }

  /* ---- Keyboard Shortcuts ---- */
  function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function (e) {
      var tag = (e.target || {}).tagName || '';
      var isInput = tag === 'INPUT' || tag === 'TEXTAREA';

      if (e.key === 'Escape') {
        var panel = document.getElementById('ai-panel');
        if (panel && panel.classList.contains('show')) {
          panel.classList.remove('show'); e.preventDefault(); return;
        }
        var themeMenu = document.getElementById('theme-menu');
        if (themeMenu && themeMenu.classList.contains('show')) {
          themeMenu.classList.remove('show'); e.preventDefault(); return;
        }
        if (C.emojiPanel && C.emojiPanel.style.display === 'block') {
          C.emojiPanel.style.display = 'none'; e.preventDefault(); return;
        }
        if (C._editMode) { cancelEditFromComposer(); e.preventDefault(); return; }
        if (C._replyMode) { cancelReplyFromComposer(); e.preventDefault(); return; }
        hideSmartReplies();
        return;
      }

      if (e.ctrlKey || e.metaKey) {
        if (e.shiftKey && (e.key === 'e' || e.key === 'E')) {
          e.preventDefault();
          toggleEmojiPanel();
          return;
        }
        if (e.shiftKey && (e.key === 'a' || e.key === 'A')) {
          e.preventDefault();
          var fileInput = document.getElementById('file-input');
          if (fileInput) fileInput.click();
          return;
        }
        if ((e.key === 'k' || e.key === 'K')) {
          if (!isInput) {
            e.preventDefault();
            C.input.focus();
            return;
          }
        }
      }
    });
  }

  /* ---- Theme Management ---- */
  function applyTheme(theme) {
    var themes = {
      light: { '--chat-bg': '#ffffff', '--chat-surface': '#f5f5f5', '--chat-panel': 'rgba(0,0,0,0.05)', '--chat-border': 'rgba(0,0,0,0.1)', '--chat-text': '#1a1a1a', '--chat-muted': '#666', '--chat-bubble-mine': 'linear-gradient(135deg,#2563eb,#7c3aed)', '--chat-bubble-theirs': 'rgba(0,0,0,0.06)' },
      dark: { '--chat-bg': '#070711', '--chat-surface': '#0d0d1d', '--chat-panel': 'rgba(255,255,255,0.06)', '--chat-border': 'rgba(255,255,255,0.10)', '--chat-text': '#fff', '--chat-muted': '#9ca3af', '--chat-bubble-mine': 'linear-gradient(135deg,#2563eb,#7c3aed)', '--chat-bubble-theirs': 'rgba(255,255,255,0.10)' },
      namibia: { '--chat-bg': '#0a0a0f', '--chat-surface': '#12121f', '--chat-panel': 'rgba(255,200,50,0.08)', '--chat-border': 'rgba(255,200,50,0.15)', '--chat-text': '#fff', '--chat-muted': '#b8943a', '--chat-bubble-mine': 'linear-gradient(135deg,#ffcc00,#ff8800)', '--chat-bubble-theirs': 'rgba(255,200,50,0.10)' },
      ocean: { '--chat-bg': '#0a1628', '--chat-surface': '#0f1f3a', '--chat-panel': 'rgba(100,200,255,0.08)', '--chat-border': 'rgba(100,200,255,0.15)', '--chat-text': '#fff', '--chat-muted': '#7eb8da', '--chat-bubble-mine': 'linear-gradient(135deg,#00b4d8,#0077b6)', '--chat-bubble-theirs': 'rgba(100,200,255,0.10)' },
      emerald: { '--chat-bg': '#0a1a0f', '--chat-surface': '#0f2415', '--chat-panel': 'rgba(50,255,150,0.08)', '--chat-border': 'rgba(50,255,150,0.15)', '--chat-text': '#fff', '--chat-muted': '#6ee7b7', '--chat-bubble-mine': 'linear-gradient(135deg,#059669,#10b981)', '--chat-bubble-theirs': 'rgba(50,255,150,0.10)' },
      purple: { '--chat-bg': '#0f0a1a', '--chat-surface': '#1a0f2e', '--chat-panel': 'rgba(200,100,255,0.08)', '--chat-border': 'rgba(200,100,255,0.15)', '--chat-text': '#fff', '--chat-muted': '#c084fc', '--chat-bubble-mine': 'linear-gradient(135deg,#7c3aed,#a855f7)', '--chat-bubble-theirs': 'rgba(200,100,255,0.10)' },
      minimal: { '--chat-bg': '#000', '--chat-surface': '#111', '--chat-panel': 'rgba(255,255,255,0.04)', '--chat-border': 'rgba(255,255,255,0.06)', '--chat-text': '#eee', '--chat-muted': '#555', '--chat-bubble-mine': '#333', '--chat-bubble-theirs': '#1a1a1a' },
    };
    var vars = themes[theme] || themes.dark;
    var root = document.documentElement;
    Object.keys(vars).forEach(function (key) {
      root.style.setProperty(key, vars[key]);
    });
    try { localStorage.setItem('chain_chat_theme', theme); } catch (e) {}
    document.querySelectorAll('#theme-menu .tm-item').forEach(function (item) {
      item.classList.toggle('active', item.dataset.theme === theme);
    });
  }

  function loadSavedTheme() {
    try {
      var saved = localStorage.getItem('chain_chat_theme');
      if (saved) applyTheme(saved);
    } catch (e) {}
  }

  function toggleThemeMenu() {
    var menu = document.getElementById('theme-menu');
    if (!menu) return;
    menu.classList.toggle('show');
    if (C.emojiPanel) C.emojiPanel.style.display = 'none';
    if (C.stickerPanel) C.stickerPanel.style.display = 'none';
    if (C.gifPanel) C.gifPanel.style.display = 'none';
    if (C.attachPanel) C.attachPanel.style.display = 'none';
    var aiPanel = document.getElementById('ai-panel');
    if (aiPanel) aiPanel.classList.remove('show');
  }

  /* ---- Accessibility: aria-labels & focus ---- */
  function applyAriaLabels() {
    document.querySelectorAll('.composer-btn, .composer-send, .composer-mic').forEach(function (btn) {
      if (!btn.getAttribute('aria-label')) {
        var title = btn.getAttribute('title') || btn.className;
        btn.setAttribute('aria-label', title || 'Button');
      }
    });
    if (C.input) C.input.setAttribute('aria-label', 'Message input');
    if (C.sendBtn) C.sendBtn.setAttribute('aria-label', 'Send message');
  }

  /* ---- Init new features ---- */
  function initSmartFeatures() {
    loadSavedTheme();
    setupKeyboardShortcuts();
    applyAriaLabels();

    /* AI panel toggle */
    document.querySelectorAll('[data-action="ai"]').forEach(function (btn) {
      btn.addEventListener('click', function (e) { e.stopPropagation(); toggleAIPanel(); });
    });

    /* AI transform buttons (delegated) */
    var aiBody = document.getElementById('ai-panel');
    if (aiBody) {
      aiBody.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-ai-mode]');
        if (btn) applyAITransform(btn.dataset.aiMode);
      });
    }

    /* Location buttons */
    var locSend = document.getElementById('location-send');
    if (locSend) locSend.addEventListener('click', sendLocation);
    var locCancel = document.getElementById('location-cancel');
    if (locCancel) locCancel.addEventListener('click', cancelLocation);

    /* File input change (with size check) */
    if (C.fileInput) {
      var origChange = C.fileInput._listeners;
      C.fileInput.addEventListener('change', function () {
        if (C.fileInput.files && C.fileInput.files[0]) uploadFileWithCheck(C.fileInput.files[0]);
      });
    }

    /* Mic with slide-to-cancel */
    if (C.micBtn) {
      C.micBtn.addEventListener('touchstart', onVoiceTouchStart, { passive: true });
      C.micBtn.addEventListener('touchmove', onVoiceTouchMove, { passive: true });
      C.micBtn.addEventListener('touchend', onVoiceTouchEnd, { passive: true });
      C.micBtn.addEventListener('mousedown', function () {
        C._voiceStartY = 0;
        C._voiceSlideCancel = false;
        startRecording();
      });
      C.micBtn.addEventListener('mousemove', function (e) {
        if (!C.isRecording) return;
        var diff = e.clientY - (C._voiceStartY || e.clientY);
        if (diff > 60 && !C._voiceSlideCancel) {
          C._voiceSlideCancel = true;
          var zone = document.querySelector('.vo-slide-cancel-zone');
          if (zone) zone.classList.add('active');
        }
      });
      C.micBtn.addEventListener('mouseup', function () {
        var zone = document.querySelector('.vo-slide-cancel-zone');
        if (zone) zone.classList.remove('active');
        if (C._voiceSlideCancel) { cancelRecording(); C._voiceSlideCancel = false; }
        else if (C.isRecording) stopAndSendVoice();
      });
      C.micBtn.addEventListener('mouseleave', function () {
        if (C.isRecording && !C._voiceSlideCancel) stopAndSendVoice();
        var zone = document.querySelector('.vo-slide-cancel-zone');
        if (zone) zone.classList.remove('active');
      });
    }

    /* Voice lock button — hold mode */
    var voiceLock = document.querySelector('#voice-overlay [data-voice-control="lock"]');
    if (voiceLock) {
      voiceLock.addEventListener('click', function () {
        voiceLock.classList.toggle('locked');
        if (voiceLock.classList.contains('locked')) {
          C._voiceLocked = true;
        } else {
          C._voiceLocked = false;
        }
      });
    }

    /* Waveform animation during recording */
    var waveformContainer = document.getElementById('recording-waveform');
    if (waveformContainer && !waveformContainer.querySelector('span')) {
      for (var i = 0; i < 16; i++) {
        var bar = document.createElement('span');
        waveformContainer.appendChild(bar);
      }
    }

    /* Theme menu items (delegated) */
    var themeMenu = document.getElementById('theme-menu');
    if (themeMenu) {
      themeMenu.addEventListener('click', function (e) {
        var item = e.target.closest('[data-theme]');
        if (item) {
          applyTheme(item.dataset.theme);
          themeMenu.classList.remove('show');
        }
      });
    }

    /* Click outside to close panels */
    document.addEventListener('click', function (e) {
      var aiPanel = document.getElementById('ai-panel');
      if (aiPanel && aiPanel.classList.contains('show') && !aiPanel.contains(e.target) && !e.target.closest('[data-action="ai"]')) {
        aiPanel.classList.remove('show');
      }
      var themeMenu = document.getElementById('theme-menu');
      if (themeMenu && themeMenu.classList.contains('show') && !themeMenu.contains(e.target) && !e.target.closest('[data-action="theme"]')) {
        themeMenu.classList.remove('show');
      }
    });

    /* Expose new globals */
    window.toggleAIPanel = toggleAIPanel;
    window.applyAITransform = applyAITransform;
    window.showSmartReplies = showSmartReplies;
    window.hideSmartReplies = hideSmartReplies;
    window.insertSmartReply = insertSmartReply;
    window.shareLocation = shareLocation;
    window.sendLocation = sendLocation;
    window.cancelLocation = cancelLocation;
    window.captureCamera = captureCamera;
    window.initReplyFromComposer = initReplyFromComposer;
    window.cancelReplyFromComposer = cancelReplyFromComposer;
    window.initEditFromComposer = initEditFromComposer;
    window.cancelEditFromComposer = cancelEditFromComposer;
    window.applyTheme = applyTheme;
    window.toggleThemeMenu = toggleThemeMenu;
  }

  /* ---- Exposed Globals ---- */
  window.uploadFile = uploadFile;
  window.hideAttachmentPreview = hideAttachmentPreview;
  window.toggleEmojiPanel = toggleEmojiPanel;
  window.insertEmoji = insertEmoji;
  window.renderEmojiGrid = renderEmojiGrid;
  window.startRecording = startRecording;
  window.stopAndSendVoice = stopAndSendVoice;
  window.cancelRecording = cancelRecording;

  window.__composerState = {
    get pendingAttachment() { return C.pendingAttachment; },
    set pendingAttachment(v) { C.pendingAttachment = v; },
    get pendingVoiceFile() { return C.pendingVoiceFile; },
    set pendingVoiceFile(v) { C.pendingVoiceFile = v; },
    clearDraft: clearDraft,
    updateSendButton: updateSendButton,
    emitTypingStop: emitTypingStop,
    hideSmartReplies: hideSmartReplies,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
