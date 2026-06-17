(() => {
  "use strict";

  const form = document.getElementById("chain-register-form");
  if (!form) return;

  const submitBtn = document.getElementById("register_submit");
  const password = document.getElementById("register_password");
  const confirmPassword = document.getElementById("register_confirm_password");
  const confirmStatus = document.getElementById("confirm_password_status");
  const strengthText = document.getElementById("password_strength");
  const strengthBar = document.getElementById("password_strength_bar");

  form.querySelectorAll(".toggle-password").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.target);
      if (!target) return;
      target.type = target.type === "password" ? "text" : "password";
      button.textContent = target.type === "password" ? "Show" : "Hide";
    });
  });

  function scorePassword() {
    const text = password ? password.value : "";
    let score = 0;
    if (text.length >= 8) score += 1;
    if (text.length >= 12) score += 1;
    if (/[A-Z]/.test(text) && /[a-z]/.test(text)) score += 1;
    if (/[0-9]/.test(text)) score += 1;
    if (/[^A-Za-z0-9]/.test(text)) score += 1;
    return score;
  }

  function updatePasswordHints() {
    if (!strengthText || !password) return;
    const score = scorePassword();
    if (strengthBar) {
      strengthBar.style.width = Math.min(score * 20, 100) + "%";
      strengthBar.dataset.score = String(score);
    }
    if (score >= 4) {
      strengthText.textContent = "Strong password.";
      strengthText.className = "field-hint is-available";
    } else if (password.value.length >= 8) {
      strengthText.textContent = "Add numbers or symbols for extra strength.";
      strengthText.className = "field-hint";
    } else {
      strengthText.textContent = "Use at least 8 characters.";
      strengthText.className = "field-hint is-unavailable";
    }
  }

  function updateConfirmHint() {
    if (!password || !confirmPassword || !confirmStatus) return;
    const hasText = Boolean(confirmPassword.value);
    const matched = hasText && password.value === confirmPassword.value;
    confirmStatus.textContent = matched ? "Passwords match." : (hasText ? "Passwords must match." : "");
    confirmStatus.className = "field-hint";
    if (matched) confirmStatus.classList.add("is-available");
    else if (hasText) confirmStatus.classList.add("is-unavailable");
  }

  password?.addEventListener("input", () => {
    updatePasswordHints();
    updateConfirmHint();
  }, { passive: true });
  confirmPassword?.addEventListener("input", updateConfirmHint, { passive: true });

  const overlay = document.getElementById("register-loading-overlay");
  const overlayHint = document.getElementById("register-loading-hint");
  let overlayTimers = [];

  function hideOverlay() {
    if (!overlay) return;
    overlay.classList.remove("is-visible");
    overlay.setAttribute("aria-hidden", "true");
    overlayTimers.forEach(window.clearTimeout);
    overlayTimers = [];
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Create Account";
    }
  }

  function showOverlay() {
    if (!overlay) return;
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    overlayTimers.forEach(window.clearTimeout);
    overlayTimers = [];

    if (overlayHint) {
      overlayTimers.push(window.setTimeout(() => {
        overlayHint.textContent = "Still working… almost there! Good things take a moment.";
      }, 8000));
      overlayTimers.push(window.setTimeout(() => {
        overlayHint.textContent = "We're experiencing higher load than usual. Please keep waiting — your account is being created.";
      }, 18000));
    }
  }

  form.addEventListener("submit", () => {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating account...";
    }
    showOverlay();
  });

  updatePasswordHints();

  fetch("/auth/api/prewarm-register", {
    method: "GET",
    credentials: "same-origin",
    keepalive: true
  }).catch(() => {});
})();
