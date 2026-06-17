(() => {
  const drawer = document.getElementById("chain-home-drawer");
  const toggles = document.querySelectorAll("[data-drawer-toggle]");
  const closers = document.querySelectorAll("[data-drawer-close]");
  const backdrop = document.querySelector(".chain-home__drawer-backdrop");

  if (!drawer) {
    return;
  }

  const setDrawerState = (open) => {
    drawer.classList.toggle("is-open", open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    toggles.forEach((toggle) => toggle.setAttribute("aria-expanded", open ? "true" : "false"));
    if (backdrop) {
      backdrop.hidden = !open;
    }
    document.body.style.overflow = open ? "hidden" : "";
  };

  toggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      setDrawerState(!drawer.classList.contains("is-open"));
    });
  });

  closers.forEach((closer) => {
    closer.addEventListener("click", () => setDrawerState(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setDrawerState(false);
    }
  });
})();

/* ================================================================
   Phase 58 — Additional polish
=============================================================== */
(() => {
  // Active nav item highlighting
  const currentPath = window.location.pathname;
  document.querySelectorAll(".home-nav-item, .mobile-nav-item, .chain-home__drawer-nav a").forEach((link) => {
    const href = link.getAttribute("href");
    if (href && href !== "#" && href !== "/") {
      if (currentPath.indexOf(href) === 0) {
        link.classList.add("is-active");
      }
    } else if (href === "/" && currentPath === "/") {
      link.classList.add("is-active");
    }
  });

  // Bottom nav active state
  document.querySelectorAll(".mobile-nav-item").forEach((item) => {
    const href = item.getAttribute("href");
    if (href && currentPath.indexOf(href) === 0) {
      item.classList.add("is-active");
    }
  });

  // Smooth scroll for story strip
  const storyStrip = document.querySelector(".story-strip");
  if (storyStrip) {
    let isDown = false, startX, scrollLeftPos;
    storyStrip.addEventListener("mousedown", (e) => {
      isDown = true;
      startX = e.pageX - storyStrip.offsetLeft;
      scrollLeftPos = storyStrip.scrollLeft;
      storyStrip.style.cursor = "grabbing";
    });
    storyStrip.addEventListener("mouseleave", () => {
      isDown = false;
      storyStrip.style.cursor = "grab";
    });
    storyStrip.addEventListener("mouseup", () => {
      isDown = false;
      storyStrip.style.cursor = "grab";
    });
    storyStrip.addEventListener("mousemove", (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - storyStrip.offsetLeft;
      const walk = (x - startX) * 1.5;
      storyStrip.scrollLeft = scrollLeftPos - walk;
    });
  }
})();

(() => {
  const parseTarget = (value) => {
    const [type, id] = String(value || "").split(":");
    return { type, id };
  };

  const fetchJson = async (url, options = {}) => {
    const method = String(options.method || "GET").toUpperCase();
    const unsafe = ["POST", "PATCH", "PUT", "DELETE"].indexOf(method) !== -1;
    const finalOptions = Object.assign({}, options);
    if (unsafe) {
      const headers = window.chainCsrfHeaders
        ? window.chainCsrfHeaders(finalOptions.headers)
        : new Headers(finalOptions.headers || {});
      if (!headers.has("X-CSRFToken")) {
        const meta = document.querySelector('meta[name="csrf-token"]');
        const token = meta ? meta.getAttribute("content") : "";
        if (token) headers.set("X-CSRFToken", token);
      }
      finalOptions.headers = headers;
    }
    const response = await fetch(url, finalOptions);
    if (response.redirected) {
      window.location.href = response.url;
      return null;
    }
    if (response.status === 401 || response.status === 403) {
      window.location.href = "/auth/login";
      return null;
    }
    return response.json();
  };

  const updateCount = (type, id, kind, value) => {
    const node = document.querySelector(`[data-social-count="${type}:${id}:${kind}"]`);
    if (node && Number.isFinite(Number(value))) {
      node.textContent = value;
    }
  };

  document.querySelectorAll("[data-social-like]").forEach((button) => {
    button.addEventListener("click", async () => {
      const { type, id } = parseTarget(button.dataset.socialLike);
      if (!type || !id) return;
      button.disabled = true;
      const data = await fetchJson(`/api/social/${type}/${id}/like`, { method: "POST" });
      if (data?.success) {
        button.classList.toggle("is-active", Boolean(data.liked));
        updateCount(type, id, "like", data.count);
      }
      button.disabled = false;
    });
  });

  document.querySelectorAll("[data-social-comment]").forEach((button) => {
    button.addEventListener("click", async () => {
      const { type, id } = parseTarget(button.dataset.socialComment);
      const body = window.prompt("Add a comment");
      if (!type || !id || !body || !body.trim()) return;
      button.disabled = true;
      const data = await fetchJson(`/api/social/${type}/${id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      });
      if (data?.success) {
        updateCount(type, id, "comment", data.count);
      }
      button.disabled = false;
    });
  });

  document.querySelectorAll("[data-social-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      const { type, id } = parseTarget(button.dataset.socialSave);
      if (!type || !id) return;
      button.disabled = true;
      const data = await fetchJson(`/api/social/${type}/${id}/save`, { method: "POST" });
      if (data?.success) {
        button.classList.toggle("is-active", Boolean(data.saved));
      }
      button.disabled = false;
    });
  });

  document.querySelectorAll("[data-follow-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const profileId = button.dataset.followProfile;
      if (!profileId) return;
      button.disabled = true;
      const data = await fetchJson(`/api/social/profiles/${profileId}/follow`, { method: "POST" });
      if (data?.success) {
        button.classList.toggle("is-active", Boolean(data.following));
        button.textContent = data.following ? "Following" : "Follow";
      }
      button.disabled = false;
    });
  });
})();
