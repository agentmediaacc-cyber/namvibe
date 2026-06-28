(function () {
  "use strict";

  var TEMPLATES = [
    { id: "classic", name: "Classic", icon: "square" },
    { id: "modern", name: "Modern", icon: "circle" },
    { id: "bold", name: "Bold", icon: "triangle" },
    { id: "elegant", name: "Elegant", icon: "diamond" },
    { id: "minimal", name: "Minimal", icon: "hexagon" },
    { id: "premium", name: "Premium", icon: "star" },
  ];

  var BG_COLORS = [
    "#ffffff", "#f8fafc", "#f1f5f9", "#e2e8f0", "#cbd5e1",
    "#0f172a", "#1e293b", "#334155", "#475569", "#64748b",
    "#7c3aed", "#6366f1", "#3b82f6", "#06b6d4", "#14b8a6",
    "#10b981", "#84cc16", "#eab308", "#f97316", "#ef4444",
    "#ec4899", "#f43f5e", "#881337", "#1e1b4b", "#042f2e",
  ];

  var TEXT_COLORS = [
    "#000000", "#1e293b", "#334155", "#475569", "#64748b",
    "#ffffff", "#f8fafc", "#cbd5e1", "#7c3aed", "#3b82f6",
    "#06b6d4", "#10b981", "#eab308", "#f97316", "#ef4444",
  ];

  var state = {
    template: "classic",
    businessName: "",
    productText: "",
    price: "",
    contact: "",
    bgColor: "#ffffff",
    textColor: "#000000",
    accentColor: "#7c3aed",
    logoDataUrl: null,
    isPremium: window.NAMVIBE_IS_PREMIUM || false,
  };

  var csrf = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };

  var toastEl = document.getElementById("bfg-toast");
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-visible");
    setTimeout(function () { toastEl.classList.remove("is-visible"); }, 2500);
  }

  /* ── DOM Refs ── */
  var templateGrid = document.getElementById("bfg-templates");
  var bizNameInput = document.getElementById("bfg-business-name");
  var productInput = document.getElementById("bfg-product-text");
  var priceInput = document.getElementById("bfg-price");
  var contactInput = document.getElementById("bfg-contact");
  var logoInput = document.getElementById("bfg-logo-input");
  var logoPreview = document.getElementById("bfg-logo-preview");
  var bgColorContainer = document.getElementById("bfg-bg-colors");
  var textColorContainer = document.getElementById("bfg-text-colors");
  var accentColorInput = document.getElementById("bfg-accent-color");
  var previewCanvas = document.getElementById("bfg-preview-canvas");
  var previewCtx = previewCanvas ? previewCanvas.getContext("2d") : null;
  var previewBtn = document.getElementById("bfg-preview-btn");
  var downloadBtn = document.getElementById("bfg-download-btn");
  var hdBtn = document.getElementById("bfg-hd-btn");
  var upgradeBtn = document.getElementById("bfg-upgrade-btn");
  var lockMsg = document.getElementById("bfg-lock-msg");
  var successBox = document.getElementById("bfg-success");

  /* ── Render templates ── */
  if (templateGrid) {
    TEMPLATES.forEach(function (t) {
      var div = document.createElement("div");
      div.className = "bfg-template-card" + (t.id === state.template ? " is-active" : "");
      div.dataset.template = t.id;
      div.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/></svg>' +
        "<span>" + t.name + "</span>";
      div.addEventListener("click", function () {
        templateGrid.querySelectorAll(".bfg-template-card").forEach(function (c) { c.classList.remove("is-active"); });
        div.classList.add("is-active");
        state.template = t.id;
        generatePreview();
      });
      templateGrid.appendChild(div);
    });
  }

  /* ── Color pickers ── */
  function renderColorButtons(container, colors, current, callback) {
    if (!container) return;
    container.innerHTML = "";
    colors.forEach(function (c) {
      var btn = document.createElement("button");
      btn.className = "bfg-color-btn" + (c === current ? " is-active" : "");
      btn.style.background = c;
      btn.dataset.color = c;
      btn.addEventListener("click", function () {
        container.querySelectorAll(".bfg-color-btn").forEach(function (b) { b.classList.remove("is-active"); });
        btn.classList.add("is-active");
        callback(c);
      });
      container.appendChild(btn);
    });
  }

  renderColorButtons(bgColorContainer, BG_COLORS, state.bgColor, function (c) {
    state.bgColor = c;
    generatePreview();
  });

  renderColorButtons(textColorContainer, TEXT_COLORS, state.textColor, function (c) {
    state.textColor = c;
    generatePreview();
  });

  if (accentColorInput) {
    accentColorInput.addEventListener("input", function () {
      state.accentColor = this.value;
      generatePreview();
    });
  }

  /* ── Inputs ── */
  [bizNameInput, productInput, priceInput, contactInput].forEach(function (el) {
    if (!el) return;
    el.addEventListener("input", function () {
      if (el === bizNameInput) state.businessName = el.value;
      else if (el === productInput) state.productText = el.value;
      else if (el === priceInput) state.price = el.value;
      else if (el === contactInput) state.contact = el.value;
      generatePreview();
    });
  });

  /* ── Logo ── */
  if (logoInput) {
    logoInput.addEventListener("change", function () {
      if (logoInput.files.length) {
        var reader = new FileReader();
        reader.onload = function (e) {
          state.logoDataUrl = e.target.result;
          if (logoPreview) {
            logoPreview.innerHTML = '<img src="' + e.target.result + '" alt="">';
            logoPreview.classList.add("is-visible");
          }
          generatePreview();
        };
        reader.readAsDataURL(logoInput.files[0]);
      }
    });
  }

  /* ── Generate preview ── */
  function generatePreview() {
    if (!previewCanvas || !previewCtx) return;
    previewCanvas.width = 600;
    previewCanvas.height = 800;

    var ctx = previewCtx;
    var w = previewCanvas.width;
    var h = previewCanvas.height;

    ctx.fillStyle = state.bgColor;
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = state.accentColor;
    ctx.globalAlpha = 0.05;
    if (state.template === "classic") {
      ctx.fillRect(0, 0, 12, h);
      ctx.fillRect(w - 12, 0, 12, h);
    } else if (state.template === "modern") {
      ctx.beginPath();
      ctx.arc(w / 2, 0, w * 0.6, 0, Math.PI);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(w / 2, h, w * 0.6, Math.PI, 0);
      ctx.fill();
    } else if (state.template === "bold") {
      ctx.fillRect(0, h * 0.3, w, 4);
      ctx.fillRect(0, h * 0.7, w, 4);
    } else if (state.template === "elegant") {
      var cx = w / 2, cy = h / 2, r = Math.min(w, h) * 0.45;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    } else if (state.template === "premium") {
      ctx.fillRect(0, 0, w, h * 0.08);
      ctx.fillRect(0, h * 0.92, w, h * 0.08);
      var x = w / 2, y = h / 2, s = 60, i, points = "";
      for (i = 0; i < 5; i++) {
        var a1 = (i * 4 * Math.PI) / 5 - Math.PI / 2;
        var a2 = ((i * 4 + 2) * Math.PI) / 5 - Math.PI / 2;
        points += (i === 0 ? "" : ",") + (x + s * Math.cos(a1)) + "," + (y + s * Math.sin(a1));
        points += "," + (x + s * 0.4 * Math.cos(a2)) + "," + (y + s * 0.4 * Math.sin(a2));
      }
      ctx.beginPath();
      ctx.moveTo(x + s * Math.cos(-Math.PI / 2), y + s * Math.sin(-Math.PI / 2));
      for (i = 0; i < 5; i++) {
        var a1 = (i * 4 * Math.PI) / 5 - Math.PI / 2;
        var a2 = ((i * 4 + 2) * Math.PI) / 5 - Math.PI / 2;
        ctx.lineTo(x + s * Math.cos(a1), y + s * Math.sin(a1));
        ctx.lineTo(x + s * 0.4 * Math.cos(a2), y + s * 0.4 * Math.sin(a2));
      }
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    if (state.logoDataUrl) {
      var logo = new Image();
      logo.onload = function () {
        ctx.drawImage(logo, w / 2 - 30, 40, 60, 60);
        drawContent(ctx, w, h);
      };
      logo.src = state.logoDataUrl;
    } else {
      drawContent(ctx, w, h);
    }
  }

  function drawContent(ctx, w, h) {
    ctx.textAlign = "center";
    var y = 140;

    if (state.businessName) {
      ctx.fillStyle = state.textColor;
      ctx.font = "bold 36px Arial, sans-serif";
      ctx.fillText(state.businessName, w / 2, y);
      y += 50;
    }

    if (state.productText) {
      ctx.fillStyle = state.textColor;
      ctx.font = "20px Arial, sans-serif";
      ctx.globalAlpha = 0.8;
      wrapText(ctx, state.productText, w / 2, y, w - 80, 28);
      y += countLines(state.productText, w - 80, 20) * 28 + 10;
      ctx.globalAlpha = 1;
    }

    if (state.price) {
      ctx.fillStyle = state.accentColor;
      ctx.font = "bold 40px Arial, sans-serif";
      ctx.fillText(state.price, w / 2, y + 40);
      y += 80;
    }

    if (state.contact) {
      ctx.fillStyle = state.textColor;
      ctx.font = "16px Arial, sans-serif";
      ctx.globalAlpha = 0.7;
      ctx.fillText(state.contact, w / 2, h - 60);
      ctx.globalAlpha = 1;
    }

    ctx.fillStyle = state.textColor;
    ctx.font = "11px Arial, sans-serif";
    ctx.globalAlpha = 0.3;
    ctx.fillText("Created with NamVibe Flyer Generator", w / 2, h - 20);
    ctx.globalAlpha = 1;
  }

  function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
    var words = text.split(" ");
    var line = "";
    for (var n = 0; n < words.length; n++) {
      var testLine = line + words[n] + " ";
      var metrics = ctx.measureText(testLine);
      if (metrics.width > maxWidth && n > 0) {
        ctx.fillText(line, x, y);
        line = words[n] + " ";
        y += lineHeight;
      } else {
        line = testLine;
      }
    }
    ctx.fillText(line, x, y);
  }

  function countLines(text, maxWidth, fontSize) {
    var ctx2 = document.createElement("canvas").getContext("2d");
    ctx2.font = fontSize + "px Arial, sans-serif";
    var words = text.split(" ");
    var line = "";
    var count = 1;
    for (var n = 0; n < words.length; n++) {
      var testLine = line + words[n] + " ";
      var metrics = ctx2.measureText(testLine);
      if (metrics.width > maxWidth && n > 0) {
        line = words[n] + " ";
        count++;
      } else {
        line = testLine;
      }
    }
    return count;
  }

  /* ── Preview / Generate ── */
  if (previewBtn) {
    previewBtn.addEventListener("click", function () {
      generatePreview();
      showToast("Preview generated!");
    });
  }

  /* ── Download (standard) ── */
  if (downloadBtn) {
    downloadBtn.addEventListener("click", function () {
      if (!previewCanvas) return;
      var link = document.createElement("a");
      link.download = "namvibe-flyer.png";
      link.href = previewCanvas.toDataURL("image/png");
      link.click();
      showToast("Flyer downloaded!");
    });
  }

  /* ── Download HD (premium only) ── */
  if (hdBtn) {
    hdBtn.addEventListener("click", function () {
      if (!state.isPremium) {
        showToast("HD download is for premium members only");
        if (lockMsg) lockMsg.style.display = "flex";
        return;
      }
      if (!previewCanvas) return;
      var hdCanvas = document.createElement("canvas");
      hdCanvas.width = 2400;
      hdCanvas.height = 3200;
      var hdCtx = hdCanvas.getContext("2d");
      hdCtx.drawImage(previewCanvas, 0, 0, 2400, 3200);
      var link = document.createElement("a");
      link.download = "namvibe-flyer-hd.png";
      link.href = hdCanvas.toDataURL("image/png");
      link.click();
      showToast("HD Flyer downloaded!");
    });
  }

  /* ── Initial preview ── */
  setTimeout(generatePreview, 100);

})();