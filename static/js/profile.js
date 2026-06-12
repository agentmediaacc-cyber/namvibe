// NamVibe premium profile interactions
document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;

  document.querySelectorAll("[data-file-trigger]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.fileTrigger);
      if (input) input.click();
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.files && input.files.length && input.form) input.form.submit();
    });
  });

  const setActiveTab = (tabId) => {
    document.querySelectorAll("[data-tab-target]").forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.tabTarget === tabId);
    });
    document.querySelectorAll(".tab-content").forEach((panel) => {
      panel.hidden = panel.id !== `${tabId}-content`;
    });
    if (window.history && tabId) {
      window.history.replaceState(null, "", `#${tabId}`);
    }
  };

  document.querySelectorAll("[data-tab-target]").forEach((tab) => {
    tab.addEventListener("click", () => setActiveTab(tab.dataset.tabTarget));
  });

  const initialHash = window.location.hash.replace("#", "");
  if (initialHash && document.getElementById(`${initialHash}-content`)) {
    setActiveTab(initialHash);
  } else {
    setActiveTab("posts");
  }

  const miniProfile = document.querySelector("[data-mini-profile]");
  if (miniProfile) {
    const updateMiniHeader = () => {
      miniProfile.classList.toggle("is-visible", window.scrollY > 360);
    };
    updateMiniHeader();
    window.addEventListener("scroll", updateMiniHeader, { passive: true });
  }

  document.querySelectorAll("[data-copy-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const path = button.dataset.copyProfile || window.location.pathname;
      const url = `${window.location.origin}${path}`;
      try {
        await navigator.clipboard.writeText(url);
        button.textContent = "Copied";
        window.setTimeout(() => {
          button.innerHTML = '<i class="fas fa-copy"></i>Copy';
        }, 1200);
      } catch (error) {
        console.error("Profile link copy failed", error);
      }
    });
  });

  document.querySelectorAll("[data-share-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = window.location.href;
      if (navigator.share) {
        try {
          await navigator.share({ title: document.title, url });
          return;
        } catch (error) {
          if (error && error.name === "AbortError") return;
        }
      }
      try {
        await navigator.clipboard.writeText(url);
      } catch (error) {
        console.error("Profile share fallback failed", error);
      }
    });
  });

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      Array.from(body.classList)
        .filter((className) => className.startsWith("profile-theme-"))
        .forEach((className) => body.classList.remove(className));
      body.classList.add(`profile-theme-${button.dataset.themeChoice}`);
    });
  });

  const followButton = document.getElementById("follow-btn");
  if (followButton) {
    followButton.addEventListener("click", async () => {
      const profileId = followButton.dataset.profileId;
      if (!profileId) return;
      followButton.disabled = true;
      try {
        const response = await fetch(`/profile/${profileId}/follow`, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || payload.message || "Follow failed");
        const following = Boolean(payload.following);
        followButton.dataset.following = following ? "true" : "false";
        followButton.innerHTML = following
          ? '<i class="fas fa-user-check"></i><span>Following</span>'
          : '<i class="fas fa-user-plus"></i><span>Follow</span>';
      } catch (error) {
        console.error("Follow action failed", error);
      } finally {
        followButton.disabled = false;
      }
    });
  }
});
