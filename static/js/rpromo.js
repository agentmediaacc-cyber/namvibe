(function () {
  "use strict";

  var uploadModal = document.getElementById("rp-upload-modal");
  var uploadForm = document.getElementById("rp-upload-form");
  var uploadBtn = document.getElementById("rp-upload-btn");
  var cancelBtn = document.getElementById("rp-cancel-upload");
  var submitBtn = document.getElementById("rp-submit-upload");
  var fileInput = document.getElementById("rp-video-file");
  var fileLabel = document.querySelector(".rp-file-label");
  var grid = document.getElementById("rp-grid");
  var lightbox = document.getElementById("rp-lightbox");
  var lightboxVideo = lightbox && lightbox.querySelector(".rp-lightbox-video");
  var lightboxTitle = document.getElementById("rp-lightbox-title");
  var lightboxDesc = document.getElementById("rp-lightbox-desc");

  var CSRF = document.querySelector('meta[name="csrf-token"]');
  CSRF = CSRF && CSRF.getAttribute("content");

  function csrfHeaders() {
    var h = {"Content-Type": "application/json"};
    if (CSRF) h["X-CSRFToken"] = CSRF;
    return h;
  }

  function showToast(msg) {
    if (window.NamVibeToast && window.NamVibeToast.success) {
      window.NamVibeToast.success(msg);
    } else {
      alert(msg);
    }
  }

  /* ── Upload Modal ── */
  if (uploadBtn && uploadModal) {
    uploadBtn.addEventListener("click", function () {
      uploadModal.classList.add("is-open");
    });
    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        uploadModal.classList.remove("is-open");
      });
    }
    uploadModal.addEventListener("click", function (e) {
      if (e.target === uploadModal) uploadModal.classList.remove("is-open");
    });

    if (fileInput && fileLabel) {
      fileInput.addEventListener("change", function () {
        fileLabel.textContent = this.files && this.files[0] ? this.files[0].name : "Choose video...";
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var formData = new FormData(uploadForm);
        var title = formData.get("title");
        var video = formData.get("video");
        if (!title || !title.trim()) {
          showToast("Please enter a title.");
          return;
        }
        if (!video || !video.size) {
          showToast("Please select a video file.");
          return;
        }
        if (video.size > 100 * 1024 * 1024) {
          showToast("Video is too large. Max 100MB.");
          return;
        }
        var btnText = submitBtn.querySelector(".rp-btn-text");
        var btnLoading = submitBtn.querySelector(".rp-btn-loading");
        if (btnText) btnText.style.display = "none";
        if (btnLoading) btnLoading.style.display = "inline";
        submitBtn.disabled = true;

        fetch("/rpromo/api/upload", {
          method: "POST",
          headers: {"X-CSRFToken": CSRF},
          body: formData,
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) {
              showToast(data.error);
              return;
            }
            uploadModal.classList.remove("is-open");
            uploadForm.reset();
            if (fileLabel) fileLabel.textContent = "Choose video...";
            showToast("Promo video uploaded!");
            setTimeout(function () { window.location.reload(); }, 800);
          })
          .catch(function () {
            showToast("Upload failed. Please try again.");
          })
          .finally(function () {
            if (btnText) btnText.style.display = "inline";
            if (btnLoading) btnLoading.style.display = "none";
            submitBtn.disabled = false;
          });
      });
    }
  }

  /* ── Play video (lightbox) ── */
  function openLightbox(videoUrl, title, description) {
    if (!lightbox || !lightboxVideo) return;
    lightboxVideo.src = videoUrl;
    lightboxVideo.load();
    lightboxVideo.play().catch(function () {});
    if (lightboxTitle) lightboxTitle.textContent = title || "";
    if (lightboxDesc) lightboxDesc.textContent = description || "";
    lightbox.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    if (!lightbox || !lightboxVideo) return;
    lightbox.classList.remove("is-open");
    lightboxVideo.pause();
    lightboxVideo.removeAttribute("src");
    document.body.style.overflow = "";
  }

  if (lightbox) {
    var lightboxClose = lightbox.querySelector(".rp-lightbox-close");
    if (lightboxClose) lightboxClose.addEventListener("click", closeLightbox);
    lightbox.addEventListener("click", function (e) {
      if (e.target === lightbox) closeLightbox();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && lightbox.classList.contains("is-open")) closeLightbox();
    });
  }

  /* ── Grid card interactions ── */
  if (grid) {
    grid.addEventListener("click", function (e) {
      var playBtn = e.target.closest(".rp-play-btn");
      var likeBtn = e.target.closest(".rp-like-btn");
      var deleteBtn = e.target.closest(".rp-delete-btn");

      if (playBtn) {
        var card = playBtn.closest(".rp-card");
        if (!card) return;
        var video = card.querySelector(".rp-video");
        var title = card.querySelector(".rp-card-title");
        var desc = card.querySelector(".rp-card-desc");
        if (video && video.dataset.id) {
          var videoId = video.dataset.id;
          fetch("/rpromo/api/video/" + videoId + "/view", { method: "POST" }).catch(function () {});
        }
        openLightbox(
          video ? video.src : "",
          title ? title.textContent : "",
          desc ? desc.textContent : ""
        );
      }

      if (likeBtn) {
        var videoId = likeBtn.getAttribute("data-id");
        if (!videoId) return;
        fetch("/rpromo/api/video/" + videoId + "/like", {
          method: "POST",
          headers: csrfHeaders(),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) {
              showToast(data.error);
              return;
            }
            likeBtn.classList.toggle("is-liked", data.liked);
            var svg = likeBtn.querySelector("svg");
            if (svg) svg.setAttribute("fill", data.liked ? "currentColor" : "none");
            var countEl = likeBtn.querySelector(".rp-like-count");
            if (countEl) countEl.textContent = data.likes_count;
          })
          .catch(function () {});
      }

      if (deleteBtn) {
        var videoId = deleteBtn.getAttribute("data-id");
        if (!videoId) return;
        if (!confirm("Delete this promo video?")) return;
        fetch("/rpromo/api/video/" + videoId + "/delete", {
          method: "POST",
          headers: csrfHeaders(),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) {
              showToast(data.error);
              return;
            }
            var card = deleteBtn.closest(".rp-card");
            if (card) card.remove();
            showToast("Video deleted.");
          })
          .catch(function () {
            showToast("Delete failed.");
          });
      }
    });
  }

  /* ── Keyboard: Escape closes modals ── */
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (uploadModal && uploadModal.classList.contains("is-open")) {
        uploadModal.classList.remove("is-open");
      }
    }
  });
})();
