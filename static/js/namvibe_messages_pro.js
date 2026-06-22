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
    const res = await fetch("/api/messages/send", {
      method: "POST",
      body: form,
      credentials: "same-origin",
      headers: csrfHeaders()
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.ok) throw new Error(json.error || "send_failed");
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

  function wireVoice() {
    const button = $("mic-btn") || qs("[data-voice-record]") || qs("[data-voice-record-button]");
    if (!button || !navigator.mediaDevices) return;
    button.setAttribute("data-voice-record-button", "true");
    const start = async (event) => {
      event.preventDefault();
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.voiceChunks = [];
        state.mediaRecorder = new MediaRecorder(stream);
        state.recordingStartedAt = Date.now();
        state.mediaRecorder.ondataavailable = (e) => e.data.size && state.voiceChunks.push(e.data);
        state.mediaRecorder.onstop = () => {
          stream.getTracks().forEach((track) => track.stop());
          const blob = new Blob(state.voiceChunks, { type: "audio/webm" });
          showVoicePreview(blob, Math.round((Date.now() - state.recordingStartedAt) / 1000));
        };
        state.mediaRecorder.start();
        button.classList.add("recording");
      } catch (_) {
        showToast("Microphone permission is blocked.");
      }
    };
    const stop = (event) => {
      event.preventDefault();
      if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") state.mediaRecorder.stop();
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
    if (audio) audio.src = URL.createObjectURL(blob);
    if (preview) preview.hidden = false;
    $("voice-preview-send")?.addEventListener("click", async () => {
      const file = new File([blob], "voice-note.webm", { type: "audio/webm" });
      await sendPayload({ thread_id: state.threadId, body: "", media_type: "voice", duration_seconds: duration, client_temp_id: uuid() }, file);
      if (preview) preview.hidden = true;
    }, { once: true });
    $("voice-preview-delete")?.addEventListener("click", () => { if (preview) preview.hidden = true; }, { once: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("chain-message-mode");
    $("reply-preview")?.setAttribute("data-reply-preview", "true");
    $("attachment-preview")?.setAttribute("data-attachment-preview", "true");
    $("typing-indicator")?.setAttribute("data-typing-indicator", "true");
    wireComposer();
    wireSocket();
    wireVoice();
    flushOfflineQueue();
  });

  window.NamVibeMessagesPro = { flushOfflineQueue, queueMessage, sendPayload };
})();
