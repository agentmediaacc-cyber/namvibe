(function () {
  "use strict";

  var csrf = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };

  var toastEl = document.getElementById("nvcc-toast");
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-visible");
    setTimeout(function () { toastEl.classList.remove("is-visible"); }, 2500);
  }

  /* ── State ── */
  var state = {
    type: null,       // "story" | "reel" | "post"
    stream: null,
    mediaRecorder: null,
    recordedChunks: [],
    recording: false,
    capturedBlob: null,
    capturedUrl: null,
    capturedType: null, // "photo" | "video"
    mediaFile: null,
    editorMode: false,
  };

  var STICKERS = [
    "\u2b50", "\u2764\ufe0f", "\U0001f525", "\U0001f389", "\U0001f31f", "\U0001f4a0",
    "\U0001f44d", "\U0001f44c", "\U0001f64c", "\U0001f60e", "\U0001f602", "\U0001f618",
    "\U0001f496", "\U0001f49c", "\U0001f49b", "\U0001f49a", "\U0001f308", "\U0001f3b6",
    "\U0001f3a8", "\U0001f4f7", "\u2600\ufe0f", "\u2615", "\U0001f436", "\U0001f431",
  ];

  var EMOJIS = [
    "\U0001f600", "\U0001f601", "\U0001f602", "\U0001f603", "\U0001f604", "\U0001f605",
    "\U0001f606", "\U0001f609", "\U0001f60a", "\U0001f60b", "\U0001f60e", "\U0001f60d",
    "\U0001f618", "\U0001f617", "\U0001f619", "\U0001f61a", "\U0001f642", "\U0001f643",
    "\U0001f614", "\U0001f622", "\U0001f62d", "\U0001f631", "\U0001f621", "\U0001f620",
    "\U0001f44d", "\U0001f44c", "\U0001f44f", "\u2764\ufe0f", "\U0001f49c", "\U0001f49b",
    "\U0001f49a", "\U0001f525", "\u2b50", "\U0001f31f", "\U0001f389", "\U0001f3b6",
  ];

  var FONTS = [
    { name: "Default", value: "sans-serif" },
    { name: "Serif", value: "Georgia, serif" },
    { name: "Monospace", value: "monospace" },
    { name: "Cursive", value: "cursive" },
    { name: "Fantasy", value: "Impact, fantasy" },
    { name: "Handwriting", value: "'Comic Sans MS', cursive" },
  ];

  var BG_COLORS = [
    "#000000", "#1a1a2e", "#16213e", "#0f3460", "#533483",
    "#7c3aed", "#6366f1", "#3b82f6", "#06b6d4", "#14b8a6",
    "#10b981", "#84cc16", "#eab308", "#f97316", "#ef4444",
    "#ec4899", "#f43f5e", "#881337", "#1e293b", "#334155",
    "#475569", "#64748b", "#94a3b8", "#cbd5e1", "#f8fafc",
  ];

  var TEXT_COLORS = [
    "#ffffff", "#f0f0f5", "#d0d0dd", "#9496a8", "#6b6b7a",
    "#ef4444", "#f97316", "#eab308", "#84cc16", "#10b981",
    "#06b6d4", "#3b82f6", "#6366f1", "#7c3aed", "#ec4899",
  ];

  /* ── DOM refs ── */
  var overlay = document.getElementById("nvcc-overlay");
  if (!overlay) return;

  var headerTitle = overlay.querySelector(".nvcc-header h2");
  var preview = overlay.querySelector(".nvcc-camera-preview");
  var previewVideo = overlay.querySelector(".nvcc-camera-preview video");
  var previewImg = overlay.querySelector(".nvcc-camera-preview img");
  var captureBtn = overlay.querySelector(".nvcc-capture-btn");
  var switchBtn = overlay.querySelector(".nvcc-switch-btn");
  var fileBtn = overlay.querySelector(".nvcc-file-btn");
  var fileInput = overlay.querySelector("#nvcc-file-input");
  var timerEl = overlay.querySelector(".nvcc-timer");
  var previewArea = overlay.querySelector(".nvcc-preview-area");
  var previewMedia = overlay.querySelector(".nvcc-preview-media");
  var cancelBtn = overlay.querySelector(".nvcc-cancel-btn");
  var confirmBtn = overlay.querySelector(".nvcc-confirm-btn");
  var retakeBtn = overlay.querySelector(".nvcc-retake-btn");
  var editorTools = overlay.querySelector(".nvcc-editor-tools");
  var editorPanel = overlay.querySelector(".nvcc-editor-panel");
  var canvasWrap = overlay.querySelector(".nvcc-canvas-wrap");
  var captionInput = overlay.querySelector(".nvcc-caption-input");
  var progressBar = overlay.querySelector(".nvcc-progress");
  var progressFill = overlay.querySelector(".nvcc-progress-fill");

  /* ── Open creator ── */
  window.openCameraCreator = function (type) {
    state.type = type || "story";
    headerTitle.textContent = type === "reel" ? "Create Reel" : type === "post" ? "New Post" : "Create Story";
    overlay.classList.add("is-open");
    startCamera();
  };

  /* ── Close ── */
  function closeCreator() {
    overlay.classList.remove("is-open");
    stopCamera();
    resetState();
  }

  overlay.querySelector(".nvcc-close-btn").addEventListener("click", closeCreator);

  /* ── Camera ── */
  function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      fallbackToInput();
      return;
    }
    var facing = state.facingMode || "environment";
    var constraints = {
      video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: state.type === "reel" || state.type === "story",
    };
    navigator.mediaDevices.getUserMedia(constraints)
      .then(function (s) {
        state.stream = s;
        previewVideo.srcObject = s;
        previewVideo.style.display = "block";
        previewImg.style.display = "none";
        preview.style.display = "flex";
        previewArea.classList.remove("is-visible");
        captureBtn.style.display = "flex";
        switchBtn.style.display = "flex";
        fileBtn.style.display = "flex";
        editorTools.style.display = "none";
        editorPanel.classList.remove("is-visible");
      })
      .catch(function () {
        fallbackToInput();
      });
  }

  function stopCamera() {
    if (state.stream) {
      state.stream.getTracks().forEach(function (t) { t.stop(); });
      state.stream = null;
    }
    previewVideo.srcObject = null;
  }

  function fallbackToInput() {
    preview.style.display = "none";
    fileBtn.click();
  }

  /* ── Switch camera ── */
  switchBtn.addEventListener("click", function () {
    state.facingMode = state.facingMode === "environment" ? "user" : "environment";
    stopCamera();
    startCamera();
  });

  /* ── File input ── */
  fileBtn.addEventListener("click", function () {
    fileInput.click();
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files.length) {
      handleCapturedFile(fileInput.files[0]);
    }
  });

  /* ── Capture photo ── */
  captureBtn.addEventListener("click", function () {
    if (state.recording) {
      stopRecording();
      return;
    }
    if (state.type === "reel" || state.type === "story") {
      startRecording();
    } else {
      capturePhoto();
    }
  });

  function capturePhoto() {
    var canvas = document.createElement("canvas");
    canvas.width = previewVideo.videoWidth || 1280;
    canvas.height = previewVideo.videoHeight || 720;
    var ctx = canvas.getContext("2d");
    ctx.drawImage(previewVideo, 0, 0);
    canvas.toBlob(function (blob) {
      handleCapturedBlob(blob, "photo");
    }, "image/jpeg", 0.9);
  }

  /* ── Recording ── */
  function startRecording() {
    if (!state.stream) return;
    state.recordedChunks = [];
    try {
      var mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9"
        : MediaRecorder.isTypeSupported("video/webm;codecs=vp8") ? "video/webm;codecs=vp8"
        : "video/webm";
      state.mediaRecorder = new MediaRecorder(state.stream, { mimeType: mimeType });
    } catch (e) {
      state.mediaRecorder = new MediaRecorder(state.stream);
    }
    state.recording = true;
    captureBtn.classList.add("is-recording");
    timerEl.classList.add("is-visible");
    var startTime = Date.now();
    var maxDuration = state.type === "reel" ? 90 : 120;
    timerEl.textContent = "0:00";
    state.recordingTimer = setInterval(function () {
      var elapsed = Math.floor((Date.now() - startTime) / 1000);
      var mins = Math.floor(elapsed / 60);
      var secs = elapsed % 60;
      timerEl.textContent = mins + ":" + (secs < 10 ? "0" : "") + secs;
      if (elapsed >= maxDuration) {
        stopRecording();
      }
    }, 200);

    state.mediaRecorder.ondataavailable = function (e) {
      if (e.data.size > 0) state.recordedChunks.push(e.data);
    };
    state.mediaRecorder.onstop = function () {
      var blob = new Blob(state.recordedChunks, { type: "video/webm" });
      handleCapturedBlob(blob, "video");
    };
    state.mediaRecorder.start(100);
  }

  function stopRecording() {
    if (!state.recording) return;
    state.recording = false;
    captureBtn.classList.remove("is-recording");
    timerEl.classList.remove("is-visible");
    clearInterval(state.recordingTimer);
    if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
      state.mediaRecorder.stop();
    }
    stopCamera();
  }

  /* ── Handle captured blob ── */
  function handleCapturedBlob(blob, mediaType) {
    state.capturedBlob = blob;
    state.capturedType = mediaType;
    if (state.capturedUrl) URL.revokeObjectURL(state.capturedUrl);
    state.capturedUrl = URL.createObjectURL(blob);
    state.mediaFile = new File([blob], "captured." + (mediaType === "video" ? "webm" : "jpg"), {
      type: mediaType === "video" ? "video/webm" : "image/jpeg",
    });
    showPreview();
  }

  function handleCapturedFile(file) {
    state.mediaFile = file;
    state.capturedType = file.type.startsWith("video/") ? "video" : "photo";
    if (state.capturedUrl) URL.revokeObjectURL(state.capturedUrl);
    state.capturedUrl = URL.createObjectURL(file);
    showPreview();
  }

  function showPreview() {
    stopCamera();
    preview.style.display = "none";
    previewArea.classList.add("is-visible");
    previewMedia.innerHTML = "";
    if (state.capturedType === "video") {
      previewMedia.innerHTML = '<video src="' + state.capturedUrl + '" controls playsinline style="max-width:100%;max-height:100%"></video>';
    } else {
      previewMedia.innerHTML = '<img src="' + state.capturedUrl + '" alt="" style="max-width:100%;max-height:100%;object-fit:contain">';
    }
    captureBtn.style.display = "none";
    switchBtn.style.display = "none";
    fileBtn.style.display = "none";
    editorTools.style.display = "flex";
    editorPanel.classList.remove("is-visible");
    canvasWrap.style.display = "none";
    cancelBtn.style.display = "inline-flex";
    confirmBtn.style.display = "inline-flex";
    retakeBtn.style.display = "inline-flex";
  }

  /* ── Retake ── */
  retakeBtn.addEventListener("click", function () {
    resetState();
    startCamera();
  });

  /* ── Cancel ── */
  cancelBtn.addEventListener("click", function () {
    resetState();
    startCamera();
  });

  /* ── Confirm + Upload ── */
  confirmBtn.addEventListener("click", function () {
    uploadMedia();
  });

  /* ── Reset ── */
  function resetState() {
    if (state.capturedUrl) URL.revokeObjectURL(state.capturedUrl);
    state.capturedBlob = null;
    state.capturedUrl = null;
    state.capturedType = null;
    state.mediaFile = null;
    state.editorMode = false;
    state.recording = false;
    clearInterval(state.recordingTimer);
    previewArea.classList.remove("is-visible");
    preview.style.display = "flex";
    previewMedia.innerHTML = "";
    canvasWrap.style.display = "none";
    editorTools.style.display = "none";
    editorPanel.classList.remove("is-visible");
    captureBtn.style.display = "flex";
    switchBtn.style.display = "flex";
    fileBtn.style.display = "flex";
    cancelBtn.style.display = "none";
    confirmBtn.style.display = "none";
    retakeBtn.style.display = "none";
    progressBar.classList.remove("is-active");
    if (progressFill) progressFill.style.width = "0%";
    captionInput.value = "";
  }

  /* ── Editor Tools ── */
  var activeTool = null;
  var editorCanvas = overlay.querySelector("#nvcc-editor-canvas");
  var editorCtx = editorCanvas ? editorCanvas.getContext("2d") : null;
  var editorText = "";
  var editorFont = "sans-serif";
  var editorTextColor = "#ffffff";
  var editorBgColor = "#000000";
  var editorEmoji = "";
  var editorSticker = "";
  var editorBrightness = 100;
  var editorContrast = 100;
  var editorMusic = { url: "", title: "", artist: "", startSec: 0, durationSec: 0 };

  editorTools.addEventListener("click", function (e) {
    var tool = e.target.closest("[data-editor-tool]");
    if (!tool) return;
    var toolName = tool.dataset.editorTool;
    editorTools.querySelectorAll("[data-editor-tool]").forEach(function (t) { t.classList.remove("is-active"); });
    tool.classList.add("is-active");
    activeTool = toolName;
    showEditorPanel(toolName);
  });

  function showEditorPanel(tool) {
    editorPanel.innerHTML = "";
    editorPanel.classList.add("is-visible");

    if (tool === "text") {
      editorPanel.innerHTML =
        '<div class="nvcc-editor-row"><label>Text</label><input type="text" id="nvcct-text" placeholder="Type your text..." maxlength="200"></div>' +
        '<div class="nvcc-editor-row"><label>Font</label><select id="nvcct-font">' +
        FONTS.map(function (f) { return '<option value="' + f.value + '">' + f.name + "</option>"; }).join("") +
        '</select></div>' +
        '<div class="nvcc-editor-row"><label>Color</label>' +
        TEXT_COLORS.map(function (c) { return '<button class="nvcc-color-btn" style="background:' + c + '" data-color="' + c + '"></button>'; }).join("") +
        '</div>';
      var textInput = editorPanel.querySelector("#nvcct-text");
      if (textInput) {
        textInput.value = editorText;
        textInput.addEventListener("input", function () {
          editorText = this.value;
          applyEditor();
        });
      }
      var fontSelect = editorPanel.querySelector("#nvcct-font");
      if (fontSelect) {
        fontSelect.value = editorFont;
        fontSelect.addEventListener("change", function () {
          editorFont = this.value;
          applyEditor();
        });
      }
      editorPanel.querySelectorAll(".nvcc-color-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          editorTextColor = this.dataset.color;
          editorPanel.querySelectorAll(".nvcc-color-btn").forEach(function (b) { b.classList.remove("is-active"); });
          this.classList.add("is-active");
          applyEditor();
        });
      });
    } else if (tool === "bgcolor") {
      editorPanel.innerHTML =
        '<div class="nvcc-editor-row"><label>Background</label>' +
        BG_COLORS.map(function (c) { return '<button class="nvcc-color-btn" style="background:' + c + '" data-color="' + c + '"></button>'; }).join("") +
        "</div>";
      editorPanel.querySelectorAll(".nvcc-color-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          editorBgColor = this.dataset.color;
          editorPanel.querySelectorAll(".nvcc-color-btn").forEach(function (b) { b.classList.remove("is-active"); });
          this.classList.add("is-active");
          applyEditor();
        });
      });
    } else if (tool === "emoji") {
      editorPanel.innerHTML =
        '<div class="nvcc-emoji-picker">' +
        EMOJIS.map(function (e) { return "<button>" + e + "</button>"; }).join("") +
        "</div>";
      editorPanel.querySelectorAll(".nvcc-emoji-picker button").forEach(function (btn) {
        btn.addEventListener("click", function () {
          editorEmoji += this.textContent;
          applyEditor();
        });
      });
    } else if (tool === "sticker") {
      editorPanel.innerHTML =
        '<div class="nvcc-sticker-picker">' +
        STICKERS.map(function (s) { return "<button>" + s + "</button>"; }).join("") +
        "</div>";
      editorPanel.querySelectorAll(".nvcc-sticker-picker button").forEach(function (btn) {
        btn.addEventListener("click", function () {
          editorSticker = this.textContent;
          applyEditor();
        });
      });
    } else if (tool === "music") {
      editorPanel.innerHTML =
        '<div class="nvcc-editor-row"><label>Upload Music File</label><input type="file" id="nvcct-music-file" accept="audio/mp3,audio/wav,audio/ogg,audio/m4a,audio/flac,audio/aac,audio/*"></div>' +
        '<div class="nvcc-editor-row"><label>Or paste music URL</label><input type="url" id="nvcct-music-url" placeholder="https://example.com/track.mp3" maxlength="500"></div>' +
        '<div class="nvcc-editor-row"><label>Title</label><input type="text" id="nvcct-music-title" placeholder="Song title" maxlength="160"></div>' +
        '<div class="nvcc-editor-row"><label>Artist</label><input type="text" id="nvcct-music-artist" placeholder="Artist name" maxlength="120"></div>' +
        '<div id="nvcct-music-info" style="font-size:14px;color:#10b981;padding:8px 0;display:none">Music selected</div>';
      var musicFile = editorPanel.querySelector("#nvcct-music-file");
      var musicUrl = editorPanel.querySelector("#nvcct-music-url");
      var musicTitle = editorPanel.querySelector("#nvcct-music-title");
      var musicArtist = editorPanel.querySelector("#nvcct-music-artist");
      var musicInfo = editorPanel.querySelector("#nvcct-music-info");
      if (musicFile) {
        musicFile.addEventListener("change", function () {
          if (this.files.length) {
            editorMusic.url = "";
            editorMusic.title = musicTitle ? musicTitle.value : "";
            editorMusic.artist = musicArtist ? musicArtist.value : "";
            if (musicInfo) { musicInfo.textContent = "Music file: " + this.files[0].name; musicInfo.style.display = "block"; }
          }
        });
      }
      if (musicUrl) {
        musicUrl.addEventListener("input", function () {
          if (this.value) {
            editorMusic.file = null;
            editorMusic.url = this.value;
            if (musicInfo) { musicInfo.textContent = "Music URL set"; musicInfo.style.display = "block"; }
          }
        });
      }
      if (musicTitle) {
        musicTitle.addEventListener("input", function () { editorMusic.title = this.value; });
      }
      if (musicArtist) {
        musicArtist.addEventListener("input", function () { editorMusic.artist = this.value; });
      }
    } else if (tool === "adjust") {
      editorPanel.innerHTML =
        '<div class="nvcc-editor-row"><label>Brightness</label><input type="range" id="nvcct-brightness" min="0" max="200" value="' + editorBrightness + '"><span id="nvcct-brightness-val">' + editorBrightness + '%</span></div>' +
        '<div class="nvcc-editor-row"><label>Contrast</label><input type="range" id="nvcct-contrast" min="0" max="200" value="' + editorContrast + '"><span id="nvcct-contrast-val">' + editorContrast + '%</span></div>';
      var brightSlider = editorPanel.querySelector("#nvcct-brightness");
      var brightVal = editorPanel.querySelector("#nvcct-brightness-val");
      if (brightSlider && brightVal) {
        brightSlider.addEventListener("input", function () {
          editorBrightness = parseInt(this.value);
          brightVal.textContent = editorBrightness + "%";
          applyEditor();
        });
      }
      var contrastSlider = editorPanel.querySelector("#nvcct-contrast");
      var contrastVal = editorPanel.querySelector("#nvcct-contrast-val");
      if (contrastSlider && contrastVal) {
        contrastSlider.addEventListener("input", function () {
          editorContrast = parseInt(this.value);
          contrastVal.textContent = editorContrast + "%";
          applyEditor();
        });
      }
    } else {
      editorPanel.classList.remove("is-visible");
    }
  }

  function applyEditor() {
    if (!editorCanvas || !editorCtx || !state.capturedUrl) return;
    var img = new Image();
    img.onload = function () {
      editorCanvas.width = img.width;
      editorCanvas.height = img.height;
      editorCtx.filter = "brightness(" + editorBrightness + "%) contrast(" + editorContrast + "%)";
      editorCtx.drawImage(img, 0, 0);
      editorCtx.filter = "none";
      if (editorText) {
        editorCtx.font = "36px " + editorFont;
        editorCtx.fillStyle = editorTextColor;
        editorCtx.textAlign = "center";
        editorCtx.fillText(editorText, editorCanvas.width / 2, editorCanvas.height / 2);
      }
      if (editorEmoji) {
        editorCtx.font = "48px sans-serif";
        editorCtx.textAlign = "center";
        editorCtx.fillText(editorEmoji, editorCanvas.width / 2, editorCanvas.height - 60);
      }
      if (editorSticker) {
        editorCtx.font = "64px sans-serif";
        editorCtx.textAlign = "center";
        editorCtx.fillText(editorSticker, editorCanvas.width - 60, 60);
      }
    };
    img.src = state.capturedUrl;
  }

  /* ── Upload ── */
  function uploadMedia() {
    if (!state.mediaFile) {
      showToast("No media to upload");
      return;
    }
    confirmBtn.disabled = true;
    progressBar.classList.add("is-active");

    var fd = new FormData();
    fd.append("media", state.mediaFile);
    fd.append("caption", captionInput ? captionInput.value : "");
    var fileType = state.capturedType === "video" ? "video" : "image";
    fd.append("media_type", fileType);
    var visibility = state.type === "story" ? "followers" : "public";
    fd.append("visibility", visibility);
    if (fileType === "video" && state.type === "reel") {
      fd.append("video", state.mediaFile);
    }
    if (editorText) fd.append("text_content", editorText);
    if (editorBgColor && editorBgColor !== "#000000") fd.append("background_color", editorBgColor);
    if (editorMusic.url) {
      fd.append("music_url", editorMusic.url);
      if (editorMusic.title) fd.append("music_title", editorMusic.title);
      if (editorMusic.artist) fd.append("music_artist", editorMusic.artist);
    }
    var musicFileEl = document.getElementById("nvcct-music-file");
    if (musicFileEl && musicFileEl.files && musicFileEl.files.length) {
      fd.append("music_file", musicFileEl.files[0]);
      if (editorMusic.title) fd.append("music_title", editorMusic.title);
      if (editorMusic.artist) fd.append("music_artist", editorMusic.artist);
    }

    var uploadUrl = state.type === "post" ? "/posts/api/posts/create"
      : state.type === "reel" ? "/reels/api/reels/create"
      : "/status/api/status/create";

    var xhr = new XMLHttpRequest();
    xhr.open("POST", uploadUrl, true);
    xhr.setRequestHeader("X-CSRFToken", csrf());

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable && progressFill) {
        var pct = Math.round((e.loaded / e.total) * 100);
        progressFill.style.width = pct + "%";
      }
    };

    xhr.onload = function () {
      progressBar.classList.remove("is-active");
      confirmBtn.disabled = false;
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var resp = JSON.parse(xhr.responseText);
          if (resp.ok || resp.success) {
            showToast("Uploaded successfully!");
            var itemUrl = resp.story && resp.story.id ? "/status/" + resp.story.id
              : resp.post && resp.post.id ? "/post/" + resp.post.id
              : resp.reel_id ? "/reels/" + resp.reel_id
              : resp.reel && resp.reel.id ? "/reels/" + resp.reel.id
              : "/";
            setTimeout(function () {
              closeCreator();
              window.location.href = itemUrl;
            }, 500);
            return;
          }
        } catch (e) {}
        showToast("Upload succeeded!");
        setTimeout(function () { closeCreator(); window.location.reload(); }, 800);
      } else {
        try {
          var err = JSON.parse(xhr.responseText);
          showToast(err.error || err.message || "Upload failed");
        } catch (e) {
          showToast("Upload failed. Try again.");
        }
      }
    };

    xhr.onerror = function () {
      progressBar.classList.remove("is-active");
      confirmBtn.disabled = false;
      showToast("Network error. Check your connection.");
    };

    xhr.send(fd);
  }

  /* ── Init: wire up data-open-camera buttons ── */
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-open-camera]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var type = btn.dataset.openCamera || "story";
        window.openCameraCreator(type);
      });
    });
  });
})();