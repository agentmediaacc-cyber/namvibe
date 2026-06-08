(function () {
  const jsonHeaders = { "Content-Type": "application/json" };

  async function post(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: jsonHeaders,
      credentials: "same-origin",
      body: JSON.stringify(payload || {})
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      throw new Error(data.error || data.message || "Request failed");
    }
    return data;
  }

  function selectedMessages() {
    return Array.from(document.querySelectorAll("[data-message-select]:checked")).map((el) => el.value);
  }

  function bindMessageControls() {
    document.addEventListener("click", async (event) => {
      const target = event.target.closest("[data-phase30-action]");
      if (!target) return;
      const action = target.dataset.phase30Action;
      const messageId = target.dataset.messageId;
      const threadId = target.dataset.threadId;
      try {
        if (action === "pin-message" && messageId) {
          await post(`/messages/api/messages/${messageId}/pin`, { pinned: target.dataset.pinned !== "false" });
        } else if (action === "star-message" && messageId) {
          await post(`/messages/api/messages/${messageId}/star`, { starred: target.dataset.starred !== "false" });
        } else if (action === "forward-selected") {
          const toThreadId = target.dataset.toThreadId || prompt("Forward to thread ID");
          if (toThreadId) await post("/messages/api/messages/forward", { message_ids: selectedMessages(), to_thread_ids: [toThreadId] });
        } else if (action === "delete-selected") {
          await post("/messages/api/messages/multi-select", { action: "delete_for_me", message_ids: selectedMessages() });
        } else if (action === "save-draft" && threadId) {
          const input = document.querySelector(`[data-draft-input="${threadId}"]`);
          await post(`/messages/api/threads/${threadId}/draft`, { body: input ? input.value : "" });
        } else if (action === "save-wallpaper" && threadId) {
          await post(`/messages/api/threads/${threadId}/wallpaper`, { wallpaper_key: target.dataset.wallpaperKey || "neon-night" });
        }
        target.dispatchEvent(new CustomEvent("chain:phase30-ok", { bubbles: true }));
      } catch (err) {
        target.dispatchEvent(new CustomEvent("chain:phase30-error", { bubbles: true, detail: { error: err.message } }));
      }
    });
  }

  function bindVoiceControls() {
    let recorder = null;
    let chunks = [];
    let startTime = 0;
    const state = { locked: false, paused: false };

    async function start(button) {
      if (!navigator.mediaDevices || !window.MediaRecorder) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { noiseSuppression: true, echoCancellation: true } });
      recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "" });
      chunks = [];
      startTime = Date.now();
      recorder.ondataavailable = (event) => { if (event.data && event.data.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        const duration = (Date.now() - startTime) / 1000;
        const waveform = Array.from({ length: 24 }, (_, i) => Number((Math.abs(Math.sin(i)) * 0.85).toFixed(2)));
        const threadId = button.dataset.threadId;
        if (threadId) {
          await post(`/messages/api/threads/${threadId}/voice-draft`, {
            duration_seconds: duration,
            waveform,
            mime_type: blob.type,
            file_size: blob.size,
            draft_state: state.locked ? "locked" : "preview"
          });
        }
        button.dispatchEvent(new CustomEvent("chain:voice-preview", { bubbles: true, detail: { blob, duration, waveform } }));
      };
      recorder.start();
    }

    document.addEventListener("pointerdown", (event) => {
      const button = event.target.closest("[data-voice-record]");
      if (button) start(button).catch(() => {});
    });
    document.addEventListener("pointerup", () => {
      if (recorder && recorder.state !== "inactive" && !state.locked) recorder.stop();
    });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-voice-control]");
      if (!button || !recorder) return;
      if (button.dataset.voiceControl === "lock") state.locked = true;
      if (button.dataset.voiceControl === "pause" && recorder.state === "recording") {
        recorder.pause();
        state.paused = true;
      }
      if (button.dataset.voiceControl === "resume" && recorder.state === "paused") {
        recorder.resume();
        state.paused = false;
      }
      if (button.dataset.voiceControl === "stop" && recorder.state !== "inactive") recorder.stop();
    });
  }

  function bindCallControls() {
    document.addEventListener("click", async (event) => {
      const target = event.target.closest("[data-call-action]");
      if (!target) return;
      const callId = target.dataset.callId;
      try {
        if (target.dataset.callAction === "quality" && callId) {
          await post(`/calls/api/calls/${callId}/quality`, { event_type: target.dataset.eventType || "network", quality_score: Number(target.dataset.qualityScore || 1) });
        } else if (target.dataset.callAction === "device-settings") {
          await post("/calls/api/calls/device-settings", {
            hd_enabled: target.dataset.hd !== "false",
            noise_suppression: target.dataset.noiseSuppression !== "false",
            background_blur: target.dataset.backgroundBlur === "true"
          });
        } else if (target.dataset.callAction === "add-participant" && callId) {
          const profileId = target.dataset.profileId || prompt("Participant profile ID");
          if (profileId) await post(`/calls/api/calls/${callId}/participants`, { profile_id: profileId });
        }
      } catch (err) {
        target.dispatchEvent(new CustomEvent("chain:phase30-error", { bubbles: true, detail: { error: err.message } }));
      }
    });
  }

  function bindAudioOutputControls() {
    window.chainCanSelectAudioOutput = function () {
      return !!(HTMLMediaElement.prototype && HTMLMediaElement.prototype.setSinkId);
    };
    window.chainSetAudioOutput = async function (element, sinkId) {
      if (!element || !element.setSinkId) return { ok: false, unsupported: true };
      await element.setSinkId(sinkId);
      return { ok: true, sinkId };
    };
    window.chainStartRingbackTone = function () {
      if (window.chainStartOutgoingRing) window.chainStartOutgoingRing();
    };
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindMessageControls();
    bindVoiceControls();
    bindCallControls();
    bindAudioOutputControls();
  });
})();
