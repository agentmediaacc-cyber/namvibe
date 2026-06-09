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
  async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      C.mediaRecorder = new MediaRecorder(stream);
      C.audioChunks = [];
      C.isRecording = true;

      C.mediaRecorder.ondataavailable = function (e) {
        C.audioChunks.push(e.data);
      };
      C.mediaRecorder.onstop = uploadVoiceNote;

      C.mediaRecorder.start();
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

  function stopAndSendVoice() {
    if (C.mediaRecorder && C.mediaRecorder.state === 'recording') {
      C.mediaRecorder.stop();
      C.mediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
      clearInterval(C.recordTimer);
      if (C.voiceOverlay) C.voiceOverlay.style.display = 'none';
      if (C.micBtn) C.micBtn.classList.remove('recording');
      if (C.form) C.form.style.display = '';
      C.isRecording = false;
    }
  }

  function cancelRecording() {
    if (C.mediaRecorder && C.mediaRecorder.state === 'recording') {
      C.mediaRecorder.stop();
      C.mediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
      clearInterval(C.recordTimer);
      C.audioChunks = [];
      if (C.voiceOverlay) C.voiceOverlay.style.display = 'none';
      if (C.micBtn) C.micBtn.classList.remove('recording');
      if (C.form) C.form.style.display = '';
      C.isRecording = false;
    }
  }

  function uploadVoiceNote() {
    if (C.audioChunks.length === 0) return;
    var audioBlob = new Blob(C.audioChunks, { type: 'audio/webm' });
    C.pendingVoiceFile = new File([audioBlob], 'voice-note.webm', { type: 'audio/webm' });
    if (C.voiceAudio) C.voiceAudio.src = URL.createObjectURL(audioBlob);
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
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
