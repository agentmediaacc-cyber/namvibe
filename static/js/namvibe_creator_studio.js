/* ─── Creator Studio JS ─── */
(function () {
  "use strict";

  const BASE = "/creator-studio/api";
  const state = { currentTab: "dashboard", loading: false };

  function showToast(msg, type) {
    const existing = document.querySelector(".studio-toast");
    if (existing) existing.remove();
    const t = document.createElement("div");
    t.className = "studio-toast " + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

  async function apiFetch(path, opts) {
    try {
      const res = await fetch(BASE + path, {
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        ...opts,
      });
      return await res.json();
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  // ─── Navigation ───
  function initNav() {
    $$(".studio-nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".studio-nav-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.tab || "dashboard";
        switchTab(tab);
      });
    });
  }

  function switchTab(tab) {
    state.currentTab = tab;
    $$(".studio-panel").forEach((p) => p.classList.remove("active"));
    const panel = document.getElementById("studio-panel-" + tab);
    if (panel) {
      panel.classList.add("active");
      loadTab(tab);
    }
  }

  function loadTab(tab) {
    const panel = document.getElementById("studio-panel-" + tab);
    if (!panel) return;
    if (panel.dataset.loaded) return;
    panel.dataset.loaded = "1";
    switch (tab) {
      case "dashboard": loadDashboard(); break;
      case "analytics": loadAnalytics(); break;
      case "earnings": loadEarnings(); break;
      case "content": loadContent(); break;
      case "moderation": loadModeration(); break;
      case "business": loadBusiness(); break;
      case "milestones": loadMilestones(); break;
    }
  }

  // ─── Dashboard ───
  async function loadDashboard() {
    const panel = document.getElementById("studio-panel-dashboard");
    if (!panel) return;
    panel.innerHTML = '<div class="studio-loading"><div class="studio-spinner"></div></div>';
    const data = await apiFetch("/dashboard");
    if (!data.ok) {
      panel.innerHTML = '<div class="studio-empty"><div class="studio-empty-title">Failed to load</div></div>';
      return;
    }
    const d = data.data || {};
    const ov = d.overview || {};
    const topPosts = d.top_posts || [];
    const topGivers = d.top_givers || [];
    let html = '<div class="studio-overview">';
    const cards = [
      { label: "Followers", value: ov.followers ?? 0, change: ov.follower_change },
      { label: "Views", value: ov.views ?? 0, change: ov.view_change },
      { label: "Earnings", value: "$" + ((ov.earnings_cents ?? 0) / 100).toFixed(2), change: ov.earnings_change },
      { label: "Engagement", value: (ov.engagement_rate ?? 0).toFixed(1) + "%" },
    ];
    cards.forEach((c) => {
      const ch = c.change !== undefined
        ? `<div class="studio-card-change ${c.change >= 0 ? 'positive' : 'negative'}">${c.change >= 0 ? "+" : ""}${c.change}</div>`
        : "";
      html += `<div class="studio-card">
        <div class="studio-card-label">${c.label}</div>
        <div class="studio-card-value">${c.value}</div>
        ${ch}
      </div>`;
    });
    html += "</div>";
    // Top posts
    if (topPosts.length) {
      html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Top Posts</div></div><div class="studio-list">';
      topPosts.forEach((p, i) => {
        html += `<div class="studio-list-item">
          <span class="item-rank">#${i + 1}</span>
          <span class="item-title">${p.title || "Untitled"}</span>
          <span class="item-stat">${p.views ?? 0} views</span>
        </div>`;
      });
      html += "</div></div>";
    }
    // Top givers
    if (topGivers.length) {
      html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Top Supporters</div></div><div class="studio-list">';
      topGivers.forEach((g, i) => {
        html += `<div class="studio-list-item">
          <span class="item-rank">#${i + 1}</span>
          <span class="item-title">${g.display_name || g.profile_id || "User"}</span>
          <span class="item-stat">$${(g.total_cents / 100).toFixed(2)}</span>
        </div>`;
      });
      html += "</div></div>";
    }
    if (!topPosts.length && !topGivers.length) {
      html += '<div class="studio-empty"><div class="studio-empty-title">Welcome to Creator Studio</div><div class="studio-empty-subtitle">Your dashboard insights will appear here</div></div>';
    }
    panel.innerHTML = html;
  }

  // ─── Analytics ───
  async function loadAnalytics() {
    const panel = document.getElementById("studio-panel-analytics");
    if (!panel) return;
    panel.innerHTML = '<div class="studio-loading"><div class="studio-spinner"></div></div>';
    const data = await apiFetch("/analytics?period=weekly&days=30");
    if (!data.ok) {
      panel.innerHTML = '<div class="studio-empty"><div class="studio-empty-title">Failed to load analytics</div></div>';
      return;
    }
    const a = data.analytics || {};
    const views = a.daily_views || [];
    let html = '<div class="studio-panel-title">Analytics</div>';
    if (views.length) {
      const maxVal = Math.max(...views.map((v) => v.count || 0), 1);
      html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Daily Views (30 days)</div></div><div class="studio-chart"><div class="studio-chart-bar">';
      views.forEach((v) => {
        const pct = ((v.count || 0) / maxVal) * 100;
        html += `<div class="studio-bar" style="height:${Math.max(pct, 2)}%" title="${v.date || ""}: ${v.count || 0}"></div>`;
      });
      html += '</div></div></div>';
    } else {
      html += '<div class="studio-section"><div class="studio-empty"><div class="studio-empty-title">No analytics data yet</div></div></div>';
    }
    panel.innerHTML = html;
  }

  // ─── Earnings ───
  async function loadEarnings() {
    const panel = document.getElementById("studio-panel-earnings");
    if (!panel) return;
    panel.innerHTML = '<div class="studio-loading"><div class="studio-spinner"></div></div>';
    const [eData, typeData] = await Promise.all([
      apiFetch("/earnings"),
      apiFetch("/earnings/by-type?days=90"),
    ]);
    let html = '<div class="studio-panel-title">Earnings</div>';
    // Summary card
    if (eData.ok) {
      const e = eData.earnings || {};
      html += `<div class="studio-summary-card">
        <div class="summary-title">Total Earnings</div>
        <div class="summary-value">$${((e.total_cents || 0) / 100).toFixed(2)}</div>
        <div class="studio-summary-grid">
          <div class="studio-summary-item"><div class="si-label">Available</div><div class="si-value">$${((e.available_cents || 0) / 100).toFixed(2)}</div></div>
          <div class="studio-summary-item"><div class="si-label">Pending</div><div class="si-value">$${((e.pending_cents || 0) / 100).toFixed(2)}</div></div>
          <div class="studio-summary-item"><div class="si-label">Withdrawn</div><div class="si-value">$${((e.withdrawn_cents || 0) / 100).toFixed(2)}</div></div>
          <div class="studio-summary-item"><div class="si-label">Platform Fees</div><div class="si-value">$${((e.platform_fees_cents || 0) / 100).toFixed(2)}</div></div>
        </div>
      </div>`;
    }
    // Breakdown by type
    if (typeData.ok && typeData.by_type) {
      html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">By Type (90 days)</div></div><div class="studio-earnings-grid">';
      Object.entries(typeData.by_type).forEach(([key, val]) => {
        html += `<div class="studio-earnings-card">
          <div class="studio-earnings-amount">$${(val / 100).toFixed(2)}</div>
          <div class="studio-earnings-label">${key}</div>
        </div>`;
      });
      html += '</div></div>';
    }
    // Transactions
    const txData = await apiFetch("/transactions?limit=20");
    if (txData.ok && txData.transactions && txData.transactions.length) {
      html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Recent Transactions</div></div><div class="studio-list">';
      txData.transactions.forEach((tx) => {
        const sign = tx.type === "credit" ? "+" : "-";
        const cls = tx.type === "credit" ? "positive" : "negative";
        html += `<div class="studio-list-item">
          <span class="item-title">${tx.description || tx.earnings_type || "Transaction"}</span>
          <span class="item-stat ${cls}">${sign}$${(Math.abs(tx.amount_cents || 0) / 100).toFixed(2)}</span>
        </div>`;
      });
      html += '</div></div>';
    }
    if (!eData.ok && !typeData.ok) {
      html += '<div class="studio-empty"><div class="studio-empty-title">No earnings data yet</div></div>';
    }
    panel.innerHTML = html;
  }

  // ─── Content ───
  async function loadContent() {
    const panel = document.getElementById("studio-panel-content");
    if (!panel) return;
    // Fetch drafts + scheduled + archived
    const [drafts, scheduled, archived] = await Promise.all([
      apiFetch("/drafts"),
      apiFetch("/scheduled"),
      apiFetch("/archived"),
    ]);
    let html = '<div class="studio-panel-title">Content Management</div>';
    // Drafts
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Drafts</div></div>';
    if (drafts.ok && drafts.drafts && drafts.drafts.length) {
      html += '<div class="studio-list">';
      drafts.drafts.forEach((d) => {
        html += `<div class="studio-list-item">
          <span class="item-title">${d.title || "Untitled Draft"}</span>
          <span class="item-stat">${d.content_type || "post"}</span>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No drafts saved</div></div>';
    }
    html += '</div>';
    // Scheduled
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Scheduled Posts</div></div>';
    if (scheduled.ok && scheduled.scheduled && scheduled.scheduled.length) {
      html += '<div class="studio-list">';
      scheduled.scheduled.forEach((s) => {
        html += `<div class="studio-list-item">
          <span class="item-title">${s.title || "Scheduled Post"}</span>
          <span class="item-stat">${s.scheduled_at ? new Date(s.scheduled_at).toLocaleDateString() : ""}</span>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No scheduled posts</div></div>';
    }
    html += '</div>';
    // Archived
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Archived Content</div></div>';
    if (archived.ok && archived.archived && archived.archived.length) {
      html += '<div class="studio-list">';
      archived.archived.forEach((a) => {
        html += `<div class="studio-list-item">
          <span class="item-title">${a.entity_type || "Content"}</span>
          <span class="item-stat">${a.archived_at ? new Date(a.archived_at).toLocaleDateString() : ""}</span>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No archived content</div></div>';
    }
    html += '</div>';
    panel.innerHTML = html;
  }

  // ─── Moderation ───
  async function loadModeration() {
    const panel = document.getElementById("studio-panel-moderation");
    if (!panel) return;
    const [keywords, hidden, queue] = await Promise.all([
      apiFetch("/moderation/keywords"),
      apiFetch("/moderation/hidden-words"),
      apiFetch("/moderation/review-queue?status=pending"),
    ]);
    let html = '<div class="studio-panel-title">Moderation Tools</div>';
    // Keyword filters
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Keyword Filters</div></div>';
    if (keywords.ok && keywords.filters && keywords.filters.length) {
      html += '<div class="studio-list">';
      keywords.filters.forEach((f) => {
        html += `<div class="studio-mod-item">
          <span class="mod-keyword">${f.keyword}</span>
          <span class="mod-action">${f.action}</span>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No keyword filters set</div></div>';
    }
    html += '</div>';
    // Hidden words
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Hidden Words</div></div>';
    if (hidden.ok && hidden.hidden_words && hidden.hidden_words.length) {
      html += '<div class="studio-list">';
      hidden.hidden_words.forEach((w) => {
        html += `<div class="studio-mod-item"><span class="mod-keyword">${w.word}</span></div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No hidden words</div></div>';
    }
    html += '</div>';
    // Review queue
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Review Queue</div></div>';
    if (queue.ok && queue.queue && queue.queue.length) {
      html += '<div class="studio-list">';
      queue.queue.forEach((q) => {
        html += `<div class="studio-list-item"><span class="item-title">${q.comment_text || "Pending review"}</span></div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No items pending review</div></div>';
    }
    html += '</div>';
    panel.innerHTML = html;
  }

  // ─── Business ───
  async function loadBusiness() {
    const panel = document.getElementById("studio-panel-business");
    if (!panel) return;
    const [links, contact, hours, bpData] = await Promise.all([
      apiFetch("/business/links"),
      apiFetch("/business/contact"),
      apiFetch("/business/hours"),
      apiFetch("/dashboard"),
    ]);
    let html = '<div class="studio-panel-title">Business Tools</div>';
    // Link hub
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Link Hub</div></div>';
    if (links.ok && links.links && links.links.length) {
      html += '<div class="studio-list">';
      links.links.forEach((l) => {
        html += `<div class="studio-link-item">
          <span class="link-title">${l.title || "Link"}</span>
          <span class="link-url">${l.url}</span>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No links added</div></div>';
    }
    html += '</div>';
    // Contact info
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Contact Info</div></div>';
    if (contact.ok && contact.contact) {
      const c = contact.contact;
      html += `<div class="studio-list-item">
        <span class="item-title">${c.contact_type || "N/A"}</span>
        <span class="item-stat">${c.contact_value || ""}</span>
      </div>`;
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No contact info set</div></div>';
    }
    html += '</div>';
    // Business hours
    html += '<div class="studio-section"><div class="studio-section-header"><div class="studio-section-title">Business Hours</div></div>';
    if (hours.ok && hours.hours && hours.hours.length) {
      html += '<div class="studio-hours-grid">';
      const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      hours.hours.forEach((h) => {
        const closed = h.is_closed ? "closed" : "";
        html += `<div class="studio-hours-day ${closed}">
          <div class="day-name">${dayNames[h.day_of_week] || h.day_of_week}</div>
          <div class="day-time">${h.is_closed ? "Closed" : (h.open_time + " - " + h.close_time)}</div>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="studio-empty"><div class="studio-empty-subtitle">No business hours set</div></div>';
    }
    html += '</div>';
    panel.innerHTML = html;
  }

  // ─── Milestones ───
  async function loadMilestones() {
    const panel = document.getElementById("studio-panel-milestones");
    if (!panel) return;
    panel.innerHTML = '<div class="studio-loading"><div class="studio-spinner"></div></div>';
    const data = await apiFetch("/milestones");
    if (!data.ok) {
      panel.innerHTML = '<div class="studio-empty"><div class="studio-empty-title">Failed to load milestones</div></div>';
      return;
    }
    let html = '<div class="studio-panel-title">Milestones</div>';
    const all = data.milestones || [];
    if (all.length) {
      html += '<div class="studio-section">';
      all.forEach((m) => {
        const icons = { followers: "👥", earnings: "💰", views: "👁️" };
        html += `<div class="studio-milestone">
          <div class="studio-milestone-icon">${icons[m.milestone_type] || "⭐"}</div>
          <div class="studio-milestone-info">
            <div class="studio-milestone-label">${m.milestone_label || m.milestone_type || "Milestone"}</div>
            <div class="studio-milestone-date">${m.achieved_at ? new Date(m.achieved_at).toLocaleDateString() : ""}</div>
          </div>
        </div>`;
      });
      html += '</div>';
    }
    // Also show weekly summary
    const ws = await apiFetch("/weekly-summary");
    if (ws.ok && ws.summary) {
      const s = ws.summary;
      html += `<div class="studio-summary-card">
        <div class="summary-title">Weekly Summary</div>
        <div class="summary-value">+${s.new_followers || 0} followers</div>
        <div class="studio-summary-grid">
          <div class="studio-summary-item"><div class="si-label">Views</div><div class="si-value">${s.total_views || 0}</div></div>
          <div class="studio-summary-item"><div class="si-label">Earnings</div><div class="si-value">$${((s.total_earnings_cents || 0) / 100).toFixed(2)}</div></div>
          <div class="studio-summary-item"><div class="si-label">Posts</div><div class="si-value">${s.posts_count || 0}</div></div>
          <div class="studio-summary-item"><div class="si-label">Engagement</div><div class="si-value">${(s.engagement_rate || 0).toFixed(1)}%</div></div>
        </div>
      </div>`;
    }
    if (!all.length && (!ws.ok || !ws.summary)) {
      html += '<div class="studio-empty"><div class="studio-empty-title">No milestones yet</div><div class="studio-empty-subtitle">Milestones will auto-detect as you grow</div></div>';
    }
    panel.innerHTML = html;
  }

  // ─── Init ───
  document.addEventListener("DOMContentLoaded", () => {
    initNav();
    // Load default tab
    const activeBtn = document.querySelector(".studio-nav-btn.active");
    if (activeBtn) {
      switchTab(activeBtn.dataset.tab || "dashboard");
    }
  });
})();
