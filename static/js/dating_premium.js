(function () {
  "use strict";

  var API = {
    discover: "/dating/api/discover",
    like: "/dating/api/like",
    pass: "/dating/api/pass",
    superlike: "/dating/api/super-like",
    undo: "/dating/api/undo",
    matches: "/dating/api/matches",
    likesYou: "/dating/api/likes-you",
    block: "/dating/api/block",
    report: "/dating/api/report",
    preferences: "/dating/api/preferences",
    mode: "/dating/api/mode",
    compatibility: "/dating/api/compatibility",
    datingProfile: "/dating/api/profile",
    restrict: "/dating/api/restrict",
  };

  var S = {
    profiles: [],
    currentIndex: 0,
    currentTab: "discover",
    matches: [],
    likesYou: [],
  };

  function fetchJSON(url) {
    return fetch(url).then(function (r) { return r.json(); });
  }

  function postJSON(url, data) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    }).then(function (r) { return r.json(); });
  }

  var toastTimer = null;
  function toast(msg, type) {
    var el = document.createElement("div");
    el.className = "dt-toast" + (type ? " dt-toast-" + type : "");
    el.textContent = msg;
    document.body.appendChild(el);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.remove(); }, 2500);
  }

  function esc(str) {
    if (!str) return "";
    var d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function renderProfileCard(p) {
    if (!p) return "";
    var name = esc(p.display_name || p.full_name || p.username || "User");
    var bio = esc(p.bio || "No bio yet.");
    var loc = esc(p.location_preference || "Nearby");
    var compat = p.compatibility_score || 50;
    var photo = p.photos && p.photos.length ? p.photos[0] : (p.avatar_url || "");
    var interests = p.interests || [];
    var verified = p.verification_status === "verified";
    return '<div class="dt-card" data-profile-id="' + esc(p.profile_id) + '">' +
      '<div class="dt-card-photo" style="background-image:url(\'' + esc(photo) + '\');background-color:#1a1a2e;">' +
      '<div class="dt-compat-badge">' + compat + '% Match</div>' +
      (verified ? '<div class="dt-verified-badge"><i class="fas fa-check"></i></div>' : "") +
      "</div>" +
      '<div class="dt-card-body"><h2>' + name + "</h2>" +
      '<p class="dt-card-location"><i class="fas fa-map-marker-alt"></i> ' + loc + "</p>" +
      '<p class="dt-card-bio">' + esc(bio) + "</p>" +
      '<div class="dt-card-interests">' +
      interests.slice(0, 5).map(function (i) { return "<span>" + esc(i) + "</span>"; }).join("") +
      "</div></div></div>";
  }

  function renderGridCard(p, type) {
    var name = esc(p.display_name || p.full_name || p.match_display_name || p.username || "User");
    var photo = p.avatar_url || p.match_avatar_url || "";
    var compat = p.compatibility_score || p.match_score || "";
    return '<div class="dt-grid-card">' +
      '<div class="dt-grid-card-img" style="background-image:url(\'' + esc(photo) + '\');background-color:#1a1a2e;"></div>' +
      '<div class="dt-grid-card-body"><h4>' + name + "</h4>" +
      (compat ? '<p>' + compat + '% match</p>' : "") +
      "</div></div>";
  }

  function loadDiscover() {
    var stack = document.getElementById("dtCardStack");
    var empty = document.getElementById("dtDiscoverEmpty");
    if (!stack) return;
    stack.innerHTML = '<div class="dt-skeleton dt-skeleton-card"></div><div class="dt-skeleton dt-skeleton-card"></div>';
    fetchJSON(API.discover).then(function (res) {
      if (!res.ok || !res.data || !res.data.length) {
        stack.innerHTML = "";
        if (empty) empty.style.display = "block";
        return;
      }
      if (empty) empty.style.display = "none";
      S.profiles = res.data;
      S.currentIndex = 0;
      renderCardStack();
    });
  }

  function renderCardStack() {
    var stack = document.getElementById("dtCardStack");
    if (!stack) return;
    stack.innerHTML = "";
    if (S.currentIndex >= S.profiles.length) {
      var empty = document.getElementById("dtDiscoverEmpty");
      if (empty) empty.style.display = "block";
      return;
    }
    var slice = S.profiles.slice(S.currentIndex, S.currentIndex + 3);
    slice.forEach(function (p, i) {
      var div = document.createElement("div");
      div.innerHTML = renderProfileCard(p);
      var card = div.firstElementChild;
      if (card) {
        card.style.zIndex = 10 - i;
        card.style.transform = "scale(" + (1 - i * 0.03) + ") translateY(" + (i * 6) + "px)";
        stack.appendChild(card);
      }
    });
  }

  function animateCard(dir, cb) {
    var stack = document.getElementById("dtCardStack");
    if (!stack || !stack.firstChild) return;
    var card = stack.firstChild;
    var tx = 0, ty = 0, rot = 0;
    if (dir === "left") { tx = -800; rot = -30; }
    else if (dir === "right") { tx = 800; rot = 30; }
    else if (dir === "up") { ty = -800; }
    card.style.transition = "transform 0.4s ease, opacity 0.4s ease";
    card.style.transform = "translate(" + tx + "px, " + ty + "px) rotate(" + rot + "deg)";
    card.style.opacity = "0";
    setTimeout(function () {
      if (card.parentNode) card.parentNode.removeChild(card);
      S.currentIndex++;
      renderCardStack();
      if (cb) cb();
    }, 400);
  }

  function swipeLike() {
    var p = S.profiles[S.currentIndex];
    if (!p) return;
    postJSON(API.like, { target_id: p.profile_id }).then(function (res) {
      if (res.is_match) {
        showMatchOverlay(p);
      } else if (!res.ok) {
        toast(res.error || "Already interacted", "error");
      }
      animateCard("right");
    })["catch"](function () { animateCard("right"); });
  }

  function swipePass() {
    var p = S.profiles[S.currentIndex];
    if (!p) return;
    postJSON(API.pass, { target_id: p.profile_id }).then(function () {
      animateCard("left");
    })["catch"](function () { animateCard("left"); });
  }

  function swipeSuperLike() {
    var p = S.profiles[S.currentIndex];
    if (!p) return;
    postJSON(API.superlike, { target_id: p.profile_id }).then(function (res) {
      if (res.is_match) {
        showMatchOverlay(p);
      } else if (!res.ok) {
        toast(res.error || "Already interacted", "error");
      }
      animateCard("up");
    })["catch"](function () { animateCard("up"); });
  }

  function undoAction() {
    postJSON(API.undo, {}).then(function (res) {
      if (res.ok) {
        toast("Undone: " + res.undone, "success");
        loadDiscover();
      } else {
        toast(res.error || "Nothing to undo", "error");
      }
    });
  }

  function showMatchOverlay(p) {
    var overlay = document.getElementById("dtMatchOverlay");
    var nameEl = document.getElementById("dtMatchName");
    if (!overlay) return;
    if (nameEl) {
      nameEl.textContent = "You and " + (p.display_name || p.full_name || "someone special") + " liked each other.";
    }
    overlay.style.display = "flex";
    var keep = document.getElementById("dtMatchKeepSwiping");
    if (keep) {
      keep.onclick = function () { overlay.style.display = "none"; };
    }
    var chat = document.getElementById("dtMatchChat");
    if (chat) {
      chat.onclick = function () {
        overlay.style.display = "none";
        window.location.href = "/messages/";
      };
    }
  }

  function loadMatches() {
    var grid = document.getElementById("dtMatchesGrid");
    var empty = document.getElementById("dtMatchesEmpty");
    if (!grid) return;
    grid.innerHTML = '<div class="dt-skeleton dt-skeleton-card-sm"></div><div class="dt-skeleton dt-skeleton-card-sm"></div>';
    fetchJSON(API.matches).then(function (res) {
      grid.innerHTML = "";
      if (!res.ok || !res.data || !res.data.length) {
        if (empty) empty.style.display = "block";
        return;
      }
      if (empty) empty.style.display = "none";
      res.data.forEach(function (m) {
        var div = document.createElement("div");
        div.innerHTML = renderGridCard(m, "match");
        grid.appendChild(div.firstElementChild);
      });
      var badge = document.getElementById("dtMatchCount");
      if (badge) badge.textContent = res.data.length;
    });
  }

  function loadLikesYou() {
    var grid = document.getElementById("dtLikesGrid");
    var empty = document.getElementById("dtLikesEmpty");
    if (!grid) return;
    grid.innerHTML = '<div class="dt-skeleton dt-skeleton-card-sm"></div><div class="dt-skeleton dt-skeleton-card-sm"></div>';
    fetchJSON(API.likesYou).then(function (res) {
      grid.innerHTML = "";
      if (!res.ok || !res.data || !res.data.length) {
        if (empty) empty.style.display = "block";
        return;
      }
      if (empty) empty.style.display = "none";
      res.data.forEach(function (l) {
        var div = document.createElement("div");
        div.innerHTML = renderGridCard(l, "like");
        grid.appendChild(div.firstElementChild);
      });
    });
  }

  function loadSafety() {
    fetchJSON(API.preferences).then(function (res) {
      if (!res.ok) return;
      var dp = res.dating_profile;
      if (!dp) return;
      var modeCheck = document.getElementById("dtSafetyMode");
      if (modeCheck) modeCheck.checked = dp.dating_mode_on !== false;
      var hideCheck = document.getElementById("dtHideContacts");
      if (hideCheck) hideCheck.checked = dp.hide_from_contacts === true;
      var verifiedCheck = document.getElementById("dtVerifiedOnly");
      if (verifiedCheck) verifiedCheck.checked = dp.visible_to_verified_only === true;
      var trustFill = document.getElementById("dtTrustFill");
      var trustLabel = document.getElementById("dtTrustLabel");
      var trust = dp.trust_score || 50;
      if (trustFill) trustFill.style.width = trust + "%";
      if (trustLabel) trustLabel.textContent = "Score: " + trust;
      var badgeEl = document.getElementById("dtSafetyBadgeStatus");
      if (badgeEl) {
        badgeEl.innerHTML = dp.safety_badge
          ? '<i class="fas fa-shield-alt" style="color:var(--dt-cyan);"></i> Earned'
          : 'Not earned yet. <button class="dt-btn dt-btn-sm" id="dtRequestVerification">Request Verification</button>';
      }
    });
  }

  function loadTab(tab) {
    if (tab === "discover") loadDiscover();
    else if (tab === "matches") loadMatches();
    else if (tab === "likes-you") loadLikesYou();
    else if (tab === "safety") loadSafety();
  }

  function switchTab(tab) {
    S.currentTab = tab;
    document.querySelectorAll(".dt-tab").forEach(function (t) {
      t.classList.toggle("is-active", t.getAttribute("data-tab") === tab);
    });
    document.querySelectorAll(".dt-panel").forEach(function (p) {
      p.classList.toggle("is-active", p.id === "dtPanel-" + tab);
    });
    loadTab(tab);
  }

  function initSearch() {
    // Placeholder - could be extended for dating search
  }

  function initModeToggle() {
    var btn = document.getElementById("dtModeToggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      fetchJSON(API.preferences).then(function (res) {
        if (!res.ok) return;
        var current = res.dating_profile ? res.dating_profile.dating_mode_on !== false : true;
        var newMode = !current;
        postJSON(API.mode, { on: newMode }).then(function (r) {
          if (r.ok) {
            var label = document.getElementById("dtModeLabel");
            if (label) label.textContent = newMode ? "On" : "Off";
            toast("Dating mode " + (newMode ? "ON" : "OFF"));
          }
        });
      });
    });
  }

  function initSafetyControls() {
    var hideBtn = document.getElementById("dtHideContacts");
    if (hideBtn) {
      hideBtn.addEventListener("change", function () {
        postJSON(API.restrict, {
          hide_from_contacts: hideBtn.checked,
          visible_to_verified_only: document.getElementById("dtVerifiedOnly")?.checked || false,
        }).then(function (r) {
          if (r.ok) toast("Visibility updated", "success");
          else toast("Update failed", "error");
        });
      });
    }
    var verifiedBtn = document.getElementById("dtVerifiedOnly");
    if (verifiedBtn) {
      verifiedBtn.addEventListener("change", function () {
        postJSON(API.restrict, {
          hide_from_contacts: document.getElementById("dtHideContacts")?.checked || false,
          visible_to_verified_only: verifiedBtn.checked,
        }).then(function (r) {
          if (r.ok) toast("Visibility updated", "success");
          else toast("Update failed", "error");
        });
      });
    }
    var reportBtn = document.getElementById("dtReportBtn");
    if (reportBtn) {
      reportBtn.addEventListener("click", function () {
        var target = document.getElementById("dtReportTarget");
        var reason = document.getElementById("dtReportReason");
        var details = document.getElementById("dtReportDetails");
        if (!target || !target.value) { toast("Enter a profile ID", "error"); return; }
        if (!reason || !reason.value) { toast("Select a reason", "error"); return; }
        postJSON(API.report, {
          target_id: target.value,
          reason: reason.value,
          details: details ? details.value : "",
        }).then(function (r) {
          if (r.ok) {
            toast("Report submitted", "success");
            if (target) target.value = "";
            if (details) details.value = "";
            if (reason) reason.value = "";
          } else {
            toast(r.error || "Report failed", "error");
          }
        });
      });
    }
    var blockBtn = document.getElementById("dtBlockBtn");
    if (blockBtn) {
      blockBtn.addEventListener("click", function () {
        var target = document.getElementById("dtBlockTarget");
        if (!target || !target.value) { toast("Enter a profile ID", "error"); return; }
        postJSON(API.block, { target_id: target.value }).then(function (r) {
          if (r.ok) {
            toast("User blocked", "success");
            if (target) target.value = "";
          } else {
            toast(r.error || "Block failed", "error");
          }
        });
      });
    }
    var reqVerification = document.getElementById("dtRequestVerification");
    if (reqVerification) {
      reqVerification.addEventListener("click", function () {
        toast("Verification request submitted", "success");
      });
    }
  }

  function init() {
    document.querySelectorAll(".dt-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        switchTab(this.getAttribute("data-tab"));
      });
    });

    var likeBtn = document.getElementById("dtBtnLike");
    if (likeBtn) likeBtn.addEventListener("click", swipeLike);

    var passBtn = document.getElementById("dtBtnPass");
    if (passBtn) passBtn.addEventListener("click", swipePass);

    var superBtn = document.getElementById("dtBtnSuper");
    if (superBtn) superBtn.addEventListener("click", swipeSuperLike);

    initModeToggle();
    initSafetyControls();
    loadDiscover();
    loadMatches();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
