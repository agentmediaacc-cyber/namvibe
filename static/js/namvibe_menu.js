(function () {
  "use strict";

  if (window.__NAMVIBE_MENU_CONTROLLER__) {
    return;
  }
  window.__NAMVIBE_MENU_CONTROLLER__ = true;

  function getTarget(toggle) {
    if (!toggle) return null;
    var id = toggle.getAttribute("data-nv-menu-target")
      || toggle.getAttribute("aria-controls")
      || toggle.dataset.drawerTarget
      || toggle.dataset.menuTarget;
    if (!id) return null;
    return document.getElementById(id) || document.querySelector(id);
  }

  function getBackdrop(panel) {
    if (!panel) return null;
    var id = panel.id ? '[data-nv-menu-backdrop][data-nv-menu-target="' + panel.id + '"]' : '';
    return id ? document.querySelector(id) : null;
  }

  function setOpen(toggle, open) {
    var panel = getTarget(toggle);
    if (!panel) return;
    var backdrop = getBackdrop(panel);
    panel.classList.toggle("is-open", open);
    panel.hidden = !open;
    panel.setAttribute("aria-hidden", open ? "false" : "true");
    if (backdrop) {
      backdrop.hidden = !open;
      backdrop.classList.toggle("is-open", open);
    }
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("nv-menu-open", open);
    document.body.style.overflow = open ? "hidden" : "";
  }

  function closePanel(panel) {
    if (!panel) return;
    var toggle = document.querySelector('[data-nv-menu-toggle][data-nv-menu-target="' + panel.id + '"], [aria-controls="' + panel.id + '"]');
    if (toggle) {
      setOpen(toggle, false);
      return;
    }
    panel.classList.remove("is-open");
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    var backdrop = getBackdrop(panel);
    if (backdrop) {
      backdrop.hidden = true;
      backdrop.classList.remove("is-open");
    }
    document.body.classList.remove("nv-menu-open");
    document.body.style.overflow = "";
  }

  function resolveToggle(eventTarget) {
    return eventTarget.closest("[data-nv-menu-toggle], [data-social-drawer-open], [data-drawer-toggle], [data-action='open-menu']");
  }

  document.addEventListener("click", function (event) {
    var toggle = resolveToggle(event.target);
    if (toggle) {
      event.preventDefault();
      setOpen(toggle, true);
      return;
    }

    var closeButton = event.target.closest("[data-nv-menu-close], [data-social-drawer-close], [data-drawer-close], [data-action='close-menu']");
    if (closeButton) {
      event.preventDefault();
      closePanel(getTarget(closeButton));
      return;
    }

    var backdrop = event.target.closest("[data-nv-menu-backdrop], [data-social-drawer-close].social-drawer-backdrop, .nv-drawer-backdrop");
    if (backdrop) {
      var targetId = backdrop.getAttribute("data-nv-menu-target") || backdrop.getAttribute("data-drawer-target") || "social-drawer";
      closePanel(document.getElementById(targetId));
      return;
    }

    document.querySelectorAll("[data-nv-menu-panel].is-open, .social-drawer.is-open, .nv-mobile-drawer.is-open").forEach(function (panel) {
      if (!panel.contains(event.target) && !event.target.closest("[data-nv-menu-toggle], [data-social-drawer-open], [data-drawer-toggle], [data-action='open-menu']")) {
        closePanel(panel);
      }
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document.querySelectorAll("[data-nv-menu-panel].is-open, .social-drawer.is-open, .nv-mobile-drawer.is-open").forEach(closePanel);
  });
})();
