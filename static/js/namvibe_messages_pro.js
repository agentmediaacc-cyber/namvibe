(function () {
  if (window.NamVibeMessagesPro) return;

  const QUEUE_KEY = "namvibe_messages_offline_queue_v1";
  const emojis = ["😀", "😂", "😍", "🔥", "🙏", "👏", "❤️", "👍", "🎉", "😎"];
  const state = {
    threadId: window.threadId || window.currentThreadId || document.getElementById("thread_id")?.value || null,
    typingTimer: null,
    typingStopTimer: null,
    mediaRecorder: null,
    voiceChunks: [],
    recordingStartedAt: 0,
    attachment: null,
    replyToMessageId: null
  };

  function $(id) { return document.getElementById(id); }
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
  function csrfHeaders() {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || window.chainCsrfToken?.();
    return token ? { "X-CSRFToken": token } : {};
  }
  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return "ct_" + Date.now() + "_" + Math.random().toString(16).slice(2);
  }
  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch (_) { return []; }
  }
  function saveQueue(queue) { localStorage.setItem(QUEUE_KEY, JSON.stringify(queue)); }
  function escapeText(value) {
    const node = document.createElement("span");
    node.textContent = value == null ? "" : String(value);
    return node.innerHTML;
  }
  function insertAtCursor(input, text) {
    if (!input) return;
    const start = input.selectionStart || 0;
    const end = input.selectionEnd || 0;
    input.value = input.value.slice(0, start) + text + input.value.slice(end);
    input.selectionStart = input.selectionEnd = start + text.length;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  }

  async function sendPayload(payload, file) {
    const clientTempId = payload.client_temp_id || uuid();
    payload.client_temp_id = clientTempId;
    const form = new FormData();
    Object.entries(payload).forEach(([key, value]) => {
      if (value !== undefined && value !== null) form.append(key, value);
    });
    if (file) form.append("file", file, file.name || "attachment");
    const res = await fetch("/messages/api/messages/send", {
      method: "POST",
      body: form,
      credentials: "same-origin",
      headers: csrfHeaders()
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !(json.ok || json.success)) throw new Error(json.error || "send_failed");
    markLocalStatus(clientTempId, "sent");
    return json;
  }

  function queueMessage(payload) {
    const queue = loadQueue();
    queue.push({ payload, queued_at: new Date().toISOString() });
    saveQueue(queue);
    markLocalStatus(payload.client_temp_id, "pending");
  }

  async function flushOfflineQueue() {
    if (!navigator.onLine) return;
    const queue = loadQueue();
    if (!queue.length) return;
    const remaining = [];
    for (const item of queue) {
      try {
        await sendPayload(item.payload);
      } catch (_) {
        remaining.push(item);
      }
    }
    saveQueue(remaining);
  }

  function markLocalStatus(clientTempId, status) {
    if (!clientTempId) return;
    const bubble = document.querySelector(`[data-client-temp-id="${CSS.escape(clientTempId)}"]`) || document.querySelector(`[data-message-id="${CSS.escape(clientTempId)}"]`);
    if (bubble) {
      bubble.dataset.messageStatus = status;
      let marker = bubble.querySelector("[data-message-status]");
      if (!marker) {
        marker = document.createElement("span");
        marker.className = "message-status";
        bubble.appendChild(marker);
      }
      marker.dataset.messageStatus = status;
      marker.textContent = status === "seen" ? "✓✓" : status === "delivered" ? "✓✓" : status === "sent" ? "✓" : status;
    }
  }

  function showEmojiTray(input) {
    let tray = $("emoji-tray");
    if (!tray) {
      tray = document.createElement("div");
      tray.id = "emoji-tray";
      tray.className = "emoji-tray";
      tray.setAttribute("data-emoji-picker", "true");
      emojis.forEach((emoji) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = emoji;
        btn.addEventListener("click", () => insertAtCursor(input, emoji));
        tray.appendChild(btn);
      });
      qs(".chat-composer")?.before(tray);
    }
    tray.hidden = !tray.hidden;
  }

  function wireComposer() {
    const form = $("chat-form") || qs("form.chat-composer");
    const input = $("msg-input") || qs("textarea[data-message-composer]") || qs(".composer-textarea");
    const send = $("send-btn") || qs(".composer-send");
    const fileInput = $("file-input");
    if (input) {
      input.setAttribute("data-message-composer", "true");
      input.addEventListener("input", () => {
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 116) + "px";
        if (send) send.disabled = !(input.value.trim() || state.attachment);
        emitTyping(true);
      });
      input.addEventListener("keydown", (event) => {
        const isMobile = matchMedia("(max-width: 760px)").matches;
        if (!isMobile && event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          form?.requestSubmit();
        }
      });
    }
    qs('[data-action="emoji"]')?.addEventListener("click", () => showEmojiTray(input));
    form?.addEventListener("submit", async (event) => {
      if (form.dataset.nvProSubmit === "legacy") return;
      event.preventDefault();
      const body = input?.value.trim() || "";
      if (!state.threadId) state.threadId = $("thread_id")?.value || window.currentThreadId;
      if (!state.threadId || (!body && !state.attachment)) return;
      const payload = {
        thread_id: state.threadId,
        body,
        reply_to_message_id: state.replyToMessageId || "",
        client_temp_id: uuid()
      };
      try {
        if (!navigator.onLine) {
          queueMessage(payload);
        } else {
          await sendPayload(payload, state.attachment);
        }
        if (input) input.value = "";
        clearAttachmentPreview();
        clearReplyPreview();
      } catch (_) {
        queueMessage(payload);
        markLocalStatus(payload.client_temp_id, "failed");
      }
    }, { capture: true });
    fileInput?.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (file) showAttachmentPreview(file);
    });
  }

  function showAttachmentPreview(file) {
    state.attachment = file;
    const preview = $("attachment-preview") || $("inboxAttachmentPreview") || qs("[data-attachment-preview]");
    const body = $("attachment-preview-body") || $("inboxAttachmentPreviewBody") || preview;
    if (body) body.innerHTML = `<strong>${escapeText(file.name)}</strong><span>${escapeText(file.type || "file")}</span>`;
    if (preview) {
      preview.hidden = false;
      preview.setAttribute("data-attachment-preview", "true");
    }
    if ($("send-btn")) $("send-btn").disabled = false;
  }

  function clearAttachmentPreview() {
    state.attachment = null;
    qsa("#attachment-preview,#inboxAttachmentPreview,[data-attachment-preview]").forEach((el) => { el.hidden = true; });
  }

  function clearReplyPreview() {
    state.replyToMessageId = null;
    const preview = $("reply-preview") || qs("[data-reply-preview]");
    if (preview) preview.style.display = "none";
  }

  function emitTyping(isTyping) {
    if (!state.threadId || !window.socket?.emit) return;
    clearTimeout(state.typingTimer);
    clearTimeout(state.typingStopTimer);
    state.typingTimer = setTimeout(() => window.socket.emit("typing:start", { thread_id: state.threadId }), 120);
    if (isTyping) {
      state.typingStopTimer = setTimeout(() => window.socket.emit("typing:stop", { thread_id: state.threadId }), 3000);
    }
  }

  function wireSocket() {
    const socket = window.socket || window.io?.();
    if (!socket) return;
    window.socket = socket;
    var myProfileId = window.myProfileId || window.myId;
    if (myProfileId) socket.emit("join:user", { profile_id: myProfileId });
    if (state.threadId) socket.emit("join:thread", { thread_id: state.threadId });
    socket.on("message:ack", (data) => markLocalStatus(data.client_temp_id || data.client_event_id, "sent"));
    socket.on("message:delivered", (data) => markLocalStatus(data.client_temp_id || data.client_event_id || data.message_id, "delivered"));
    socket.on("message:seen", (data) => markLocalStatus(data.client_temp_id || data.client_event_id || data.message_id, "seen"));
    socket.on("typing:start", (data) => updateTyping(data, true));
    socket.on("typing:stop", (data) => updateTyping(data, false));
    window.addEventListener("online", flushOfflineQueue);
    window.addEventListener("offline", () => showToast("Offline. Messages will send when connection returns."));
  }

  function updateTyping(data, active) {
    if (data && data.thread_id && state.threadId && data.thread_id !== state.threadId) return;
    const el = $("typing-indicator") || qs("[data-typing-indicator]");
    const text = $("typing-text") || el;
    if (!el) return;
    if (active) {
      if (text) text.textContent = (data.display_name || data.username || "Someone") + " is typing...";
      el.style.display = "block";
      el.hidden = false;
    } else {
      el.style.display = "none";
      el.hidden = true;
    }
  }

  function showToast(message) {
    let toast = $("message-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "message-toast";
      toast.style.cssText = "position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:9999;padding:10px 14px;border-radius:999px;background:#111827;color:#fff;font-size:13px;box-shadow:0 12px 30px rgba(0,0,0,.28)";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { toast.hidden = true; }, 3200);
  }

  let _voiceStream = null;
  let _voicePreviewCleanup = null;

  function generateWaveformBars(count) {
    const bars = [];
    for (let i = 0; i < count; i++) {
      bars.push(Math.floor(Math.random() * 60) + 10);
    }
    return bars;
  }

  function renderWaveform(container, bars, active) {
    container.innerHTML = "";
    const maxBar = 40;
    bars.forEach((h) => {
      const span = document.createElement("span");
      const pct = Math.min((h / 100) * maxBar, maxBar);
      span.style.height = Math.max(pct, 4) + "px";
      if (active) span.classList.add("active");
      container.appendChild(span);
    });
  }

  function showVoiceOverlay(recording, duration) {
    const overlay = $("voice-overlay");
    if (!overlay) return;
    overlay.classList.remove("hidden");
    overlay.hidden = false;
    const timer = $("vo-timer") || $("recording-timer");
    const wave = $("vo-wave") || $("recording-waveform");
    const slideCancel = $("vo-slide-cancel") || qs(".vo-slide-cancel", overlay) || $("voice-cancel-zone");
    const bars = generateWaveformBars(32);

    if (wave) renderWaveform(wave, bars, true);

    let startX = 0;
    let cancelThreshold = 80;

    const updateTimer = () => {
      if (timer) {
        const sec = Math.floor((Date.now() - state.recordingStartedAt) / 1000);
        const m = String(Math.floor(sec / 60)).padStart(2, "0");
        const s = String(sec % 60).padStart(2, "0");
        timer.textContent = `${m}:${s}`;
      }
    };
    state._voiceTimer = setInterval(updateTimer, 200);
    updateTimer();

    const onMove = (e) => {
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const dx = startX - clientX;
      if (dx > cancelThreshold) {
        if (slideCancel) slideCancel.classList.add("active");
      } else {
        if (slideCancel) slideCancel.classList.remove("active");
      }
    };
    const onEnd = (e) => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onEnd);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onEnd);
      const clientX = e.changedTouches ? e.changedTouches[0].clientX : e.clientX;
      const dx = startX - clientX;
      if (dx > cancelThreshold) {
        cancelVoiceRecording();
      } else if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
        state.mediaRecorder.stop();
      }
      if (slideCancel) slideCancel.classList.remove("active");
      clearInterval(state._voiceTimer);
    };

    const captureStart = (e) => {
      startX = e.touches ? e.touches[0].clientX : e.clientX;
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onEnd);
      document.addEventListener("touchmove", onMove, { passive: false });
      document.addEventListener("touchend", onEnd);
    };
    captureStart({ clientX: 0 });
  }

  function hideVoiceOverlay() {
    const overlay = $("voice-overlay");
    if (overlay) { overlay.classList.add("hidden"); overlay.hidden = true; }
    clearInterval(state._voiceTimer);
    if (_voiceStream) {
      _voiceStream.getTracks().forEach((t) => t.stop());
      _voiceStream = null;
    }
  }

  function cancelVoiceRecording() {
    if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
      state.mediaRecorder.ondataavailable = null;
      state.mediaRecorder.onstop = null;
      state.mediaRecorder.stop();
    }
    state.voiceChunks = [];
    hideVoiceOverlay();
    const btn = $("mic-btn") || qs("[data-voice-record-button]");
    if (btn) btn.classList.remove("recording");
    showToast("Recording cancelled");
  }

  function wireVoice() {
    const button = $("mic-btn") || qs("[data-voice-record]") || qs("[data-voice-record-button]");
    if (!button || !navigator.mediaDevices) return;
    button.setAttribute("data-voice-record-button", "true");

    const start = async (event) => {
      event.preventDefault();
      if (state.mediaRecorder && state.mediaRecorder.state === "recording") return;
      try {
        _voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.voiceChunks = [];
        state.mediaRecorder = new MediaRecorder(_voiceStream);
        state.recordingStartedAt = Date.now();
        state.mediaRecorder.ondataavailable = (e) => e.data.size && state.voiceChunks.push(e.data);
        state.mediaRecorder.onstop = () => {
          if (state.voiceChunks.length === 0) { hideVoiceOverlay(); return; }
          const blob = new Blob(state.voiceChunks, { type: "audio/webm" });
          const dur = Math.round((Date.now() - state.recordingStartedAt) / 1000);
          hideVoiceOverlay();
          showVoicePreview(blob, Math.max(dur, 1));
        };
        state.mediaRecorder.start();
        button.classList.add("recording");
        showVoiceOverlay(true);
      } catch (_) {
        showToast("Microphone permission is blocked.");
      }
    };

    const stop = (event) => {
      event.preventDefault();
      if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
        state.mediaRecorder.stop();
      }
      button.classList.remove("recording");
    };

    button.addEventListener("mousedown", start);
    button.addEventListener("touchstart", start, { passive: false });
    button.addEventListener("mouseup", stop);
    button.addEventListener("mouseleave", stop);
    button.addEventListener("touchend", stop, { passive: false });
  }

  function showVoicePreview(blob, duration) {
    const preview = $("voice-note-preview");
    const audio = $("voice-note-audio");
    if (!preview) return;
    preview.hidden = false;

    if (audio) {
      audio.src = URL.createObjectURL(blob);
      audio.loop = false;
    }

    const playBtn = $("vp-play");
    const waveEl = $("vp-wave") || qs(".voice-wave", preview);
    const durEl = $("vp-duration");
    const speedBtn = $("vp-speed");
    const deleteBtn = $("vp-delete") || $("voice-preview-delete");
    const sendBtn = $("vp-send") || $("voice-preview-send");
    const progressBar = $("vp-progress");
    const progressText = $("vp-progress-text");
    const cancelBtn = $("vp-cancel");
    const retryBtn = $("vp-retry");

    let isPlaying = false;
    let playbackSpeed = 1;
    let uploadCancelled = false;

    if (durEl) durEl.textContent = `${String(Math.floor(duration / 60)).padStart(2, "0")}:${String(duration % 60).padStart(2, "0")}`;

    const bars = generateWaveformBars(24);
    if (waveEl) renderWaveform(waveEl, bars, false);

    if (playBtn) {
      playBtn.onclick = () => {
        if (!audio) return;
        if (isPlaying) {
          audio.pause();
          playBtn.textContent = "▶";
          isPlaying = false;
        } else {
          audio.playbackRate = playbackSpeed;
          audio.play();
          playBtn.textContent = "⏸";
          isPlaying = true;
          audio.onended = () => { playBtn.textContent = "▶"; isPlaying = false; };
        }
      };
    }

    if (speedBtn) {
      speedBtn.textContent = "1x";
      speedBtn.onclick = () => {
        const speeds = [1, 1.5, 2];
        const idx = speeds.indexOf(playbackSpeed);
        playbackSpeed = speeds[(idx + 1) % speeds.length];
        speedBtn.textContent = playbackSpeed + "x";
        if (audio) audio.playbackRate = playbackSpeed;
      };
    }

    let _uploadXHR = null;

    const doUpload = () => {
      uploadCancelled = false;
      const file = new File([blob], "voice-note.webm", { type: "audio/webm" });
      _uploadXHR = new XMLHttpRequest();
      _uploadXHR.upload.onprogress = (e) => {
        if (uploadCancelled || !progressBar) return;
        const pct = e.lengthComputable ? Math.round((e.loaded / e.total) * 100) : 0;
        progressBar.style.width = pct + "%";
        progressBar.textContent = pct + "%";
        if (progressText) progressText.textContent = `Uploading ${pct}%`;
      };
      _uploadXHR.onload = () => {
        if (progressText) progressText.textContent = "Upload complete!";
        if (progressBar) progressBar.style.width = "100%";
        setTimeout(() => {
          if (preview) preview.hidden = true;
          if (progressText) progressText.textContent = "";
        }, 800);
      };
      _uploadXHR.onerror = () => {
        if (progressText) progressText.textContent = "Upload failed";
        if (retryBtn) retryBtn.hidden = false;
      };

      const formData = new FormData();
      formData.append("file", file);
      formData.append("thread_id", state.threadId || "");
      formData.append("body", "");
      formData.append("media_type", "voice");
      formData.append("duration_seconds", String(duration));
      formData.append("client_temp_id", uuid());
      _uploadXHR.open("POST", "/messages/api/messages/send");
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || window.chainCsrfToken?.();
      if (csrfToken) _uploadXHR.setRequestHeader("X-CSRFToken", csrfToken);
      _uploadXHR.send(formData);
    };

    if (sendBtn) {
      sendBtn.onclick = () => {
        sendBtn.disabled = true;
        if (cancelBtn) cancelBtn.hidden = false;
        doUpload();
      };
    }

    if (cancelBtn) {
      cancelBtn.onclick = () => {
        uploadCancelled = true;
        if (_uploadXHR) _uploadXHR.abort();
        if (progressText) progressText.textContent = "Upload cancelled";
        if (progressBar) progressBar.style.width = "0%";
        if (cancelBtn) cancelBtn.hidden = true;
        if (retryBtn) retryBtn.hidden = false;
        sendBtn.disabled = false;
      };
    }

    if (retryBtn) {
      retryBtn.hidden = true;
      retryBtn.onclick = () => {
        retryBtn.hidden = true;
        sendBtn.disabled = true;
        if (cancelBtn) cancelBtn.hidden = false;
        if (progressText) progressText.textContent = "";
        doUpload();
      };
    }

    if (deleteBtn) {
      deleteBtn.onclick = () => {
        if (_voicePreviewCleanup) _voicePreviewCleanup();
        if (audio) { audio.pause(); audio.src = ""; }
        preview.hidden = true;
      };
    }
  }

  // ── Keyboard Support ──
  function wireKeyboardSupport() {
    if (window.visualViewport) {
      const composer = $("chat-composer") || qs(".chat-composer");
      if (!composer) return;
      window.visualViewport.addEventListener("resize", () => {
        const vh = window.visualViewport.height;
        const diff = window.innerHeight - vh;
        if (diff > 100) {
          composer.style.bottom = diff + "px";
          composer.style.paddingBottom = "env(safe-area-inset-bottom, 0px)";
        } else {
          composer.style.bottom = "0";
        }
      });
    }
  }

  // ── Draft Autosave ──
  function wireDraftAutosave() {
    const input = $("message-input") || $("msg-input") || qs("[data-message-input]") || qs("[data-message-composer]") || qs(".composer-textarea");
    if (!input || !state.threadId) return;
    const draftKey = "namvibe_draft_" + state.threadId;
    const saved = localStorage.getItem(draftKey);
    if (saved && !input.value) {
      input.value = saved;
      input.dispatchEvent(new Event("input"));
    }
    let _draftTimer = null;
    input.addEventListener("input", () => {
      clearTimeout(_draftTimer);
      _draftTimer = setTimeout(() => {
        if (input.value.trim()) {
          localStorage.setItem(draftKey, input.value);
        } else {
          localStorage.removeItem(draftKey);
        }
      }, 500);
    });
    const sendHandler = () => setTimeout(() => localStorage.removeItem(draftKey), 100);
    (qs("[data-send-btn]") || $("send-btn"))?.addEventListener("click", sendHandler);
  }

  // ── Scroll-to-Bottom Button ──
  function wireScrollToBottom() {
    const container = $("message-list") || $("message-container") || qs(".message-list, .messages-area, [data-message-container]");
    if (!container) return;
    let btn = $("nv-scroll-bottom") || $("scroll-to-bottom") || qs("[data-scroll-bottom]");
    if (!btn) {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "nv-scroll-bottom";
      btn.id = "nv-scroll-bottom";
      btn.setAttribute("data-scroll-bottom", "true");
      btn.setAttribute("aria-label", "Scroll to latest messages");
      btn.textContent = "↓";
      container.appendChild(btn);
    }
    btn.setAttribute("data-scroll-bottom", "true");

    const checkScroll = () => {
      const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
      btn.hidden = atBottom;
    };
    container.addEventListener("scroll", checkScroll, { passive: true });
    btn.addEventListener("click", () => {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
      btn.hidden = true;
    });
    const observer = new MutationObserver(checkScroll);
    observer.observe(container, { childList: true, subtree: true });
    window.addEventListener("resize", checkScroll);
    checkScroll();
  }

  // ── PiP Support ──
  function minimizeCall() {
    const overlay = $("call-overlay") || qs("[data-call-overlay]");
    if (overlay) overlay.classList.add("nv-call-minimized");
    document.body.classList.add("nv-call-minimized");
  }

  function restoreCall() {
    const overlay = $("call-overlay") || qs("[data-call-overlay]");
    if (overlay) overlay.classList.remove("nv-call-minimized");
    document.body.classList.remove("nv-call-minimized");
  }

  function wirePiP() {
    const videoEl = $("call-remote-video");
    const pipBtn = $("pip-btn") || qs("[data-pip-btn]") || qs("[data-minimize-call]");
    if (!videoEl || !pipBtn) return;
    pipBtn.hidden = false;
    pipBtn.addEventListener("click", async () => {
      try {
        if (document.pictureInPictureElement) {
          await document.exitPictureInPicture();
          pipBtn.textContent = "PiP";
          restoreCall();
        } else if (videoEl.requestPictureInPicture) {
          await videoEl.requestPictureInPicture();
          pipBtn.textContent = "Exit PiP";
        } else {
          minimizeCall();
        }
      } catch (_) {
        minimizeCall();
      }
    });
    videoEl.addEventListener("enterpictureinpicture", () => { pipBtn.textContent = "Exit PiP"; });
    videoEl.addEventListener("leavepictureinpicture", () => { pipBtn.textContent = "PiP"; restoreCall(); });
    qs("[data-restore-call]")?.addEventListener("click", restoreCall);
  }

  // ── Wallpaper Support ──
  function wireWallpaper() {
    const container = $("message-list") || $("messages-area") || $("message-container") || qs(".message-list, .messages-area, [data-message-container]");
    if (!container) return;
    const saved = localStorage.getItem("namvibe_chat_wallpaper");
    if (saved) {
      try {
        const wp = JSON.parse(saved);
        if (wp.image) container.style.backgroundImage = `url(${wp.image})`;
        if (wp.color) container.style.backgroundColor = wp.color;
        container.style.backgroundSize = "cover";
        container.style.backgroundPosition = "center";
        container.style.backgroundBlendMode = "overlay";
      } catch (_) {}
    }
  }

  function setWallpaper(imageUrl, color) {
    const data = {};
    if (imageUrl) data.image = imageUrl;
    if (color) data.color = color;
    localStorage.setItem("namvibe_chat_wallpaper", JSON.stringify(data));
    wireWallpaper();
  }

  function clearWallpaper() {
    localStorage.removeItem("namvibe_chat_wallpaper");
    const container = $("message-list") || $("messages-area") || $("message-container") || qs(".message-list, .messages-area, [data-message-container]");
    if (container) {
      container.style.backgroundImage = "";
      container.style.backgroundColor = "";
    }
  }

  // ── Conversation Actions (Pin / Mute / Archive) ──
  function wireConversationActions() {
    qsa(".thread-card .thread-context-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const card = this.closest(".thread-card");
        if (!card) return;
        let menu = $("thread-context-menu");
        if (!menu) {
          menu = document.createElement("div");
          menu.id = "thread-context-menu";
          menu.className = "thread-context-menu";
          menu.innerHTML = [
            '<button class="context-item" data-action="pin"><i class="fas fa-thumbtack"></i> <span>Pin</span></button>',
            '<button class="context-item" data-action="mute"><i class="fas fa-volume-off"></i> <span>Mute</span></button>',
            '<button class="context-item" data-action="archive"><i class="fas fa-archive"></i> <span>Archive</span></button>',
            '<button class="context-item danger" data-action="delete"><i class="fas fa-trash"></i> <span>Delete</span></button>',
          ].join("");
          document.body.appendChild(menu);
        }

        const rect = this.getBoundingClientRect();
        menu.style.top = rect.bottom + 4 + "px";
        menu.style.left = Math.max(8, rect.right - 180) + "px";
        menu.style.display = "block";
        menu.dataset.threadId = card.dataset.id;
        menu.dataset.threadName = card.dataset.name || "";
        menu.dataset.isPinned = card.dataset.pinned || "false";
        menu.dataset.isMuted = card.dataset.muted || "false";

        menu.querySelector('[data-action="pin"] span').textContent = card.dataset.pinned === "true" ? "Unpin" : "Pin";
        menu.querySelector('[data-action="mute"] span').textContent = card.dataset.muted === "true" ? "Unmute" : "Mute";
      });
    });

    qsa(".context-item[data-action]").forEach(function (item) {
      item.addEventListener("click", function () {
        const menu = this.closest(".thread-context-menu");
        if (!menu) return;
        const tid = menu.dataset.threadId;
        const action = this.dataset.action;
        if (!tid) return;
        menu.style.display = "none";

        if (action === "pin") {
          const pinned = menu.dataset.isPinned === "true";
          fetch("/messages/api/threads/" + encodeURIComponent(tid) + "/pin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pinned: !pinned }),
          }).then(function () { location.reload(); }).catch(function () {});
        } else if (action === "mute") {
          const muted = menu.dataset.isMuted === "true";
          fetch("/messages/api/threads/" + encodeURIComponent(tid) + "/mute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ muted: !muted }),
          }).then(function () { location.reload(); }).catch(function () {});
        } else if (action === "archive") {
          fetch("/messages/api/threads/" + encodeURIComponent(tid) + "/archive", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ archived: true }),
          }).then(function () { location.reload(); }).catch(function () {});
        } else if (action === "delete") {
          if (!confirm("Delete this conversation?")) return;
          fetch("/messages/api/threads/" + encodeURIComponent(tid) + "/move", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder: "trash" }),
          }).then(function () { location.reload(); }).catch(function () {});
        }
      });
    });

    document.addEventListener("click", function (e) {
      const menu = $("thread-context-menu");
      if (menu && !menu.contains(e.target) && !e.target.closest(".thread-context-btn")) {
        menu.style.display = "none";
      }
    });
  }

  // ── New Message Chip ──
  function wireNewMessageChip() {
    const container = $("messages-area") || $("message-list") || qs(".messages-area, .message-list, [data-message-container]");
    if (!container) return;
    let chip = $("new-message-chip");
    if (!chip) {
      chip = document.createElement("div");
      chip.id = "new-message-chip";
      chip.className = "new-message-chip";
      chip.innerHTML = '<i class="fas fa-arrow-down"></i> New messages';
      chip.setAttribute("hidden", "");
      container.parentElement?.appendChild(chip);
    }
    container.addEventListener("scroll", function () {
      const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
      if (atBottom) {
        chip.setAttribute("hidden", "");
      } else if (container.scrollHeight > container.clientHeight + 120) {
        chip.removeAttribute("hidden");
      }
    });
    chip.addEventListener("click", function () {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
      chip.setAttribute("hidden", "");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("chain-message-mode");
    $("reply-preview")?.setAttribute("data-reply-preview", "true");
    $("attachment-preview")?.setAttribute("data-attachment-preview", "true");
    $("typing-indicator")?.setAttribute("data-typing-indicator", "true");
    wireComposer();
    wireSocket();
    wireVoice();
    wireKeyboardSupport();
    wireDraftAutosave();
    wireScrollToBottom();
    wirePiP();
    wireWallpaper();
    wireConversationActions();
    wireNewMessageChip();
    flushOfflineQueue();
  });

  window.NamVibeMessagesPro = {
    flushOfflineQueue, queueMessage, sendPayload,
    minimizeCall, restoreCall,
    setWallpaper, clearWallpaper, wireWallpaper,
  };
})();
