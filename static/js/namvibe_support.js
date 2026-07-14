(function () {
  "use strict";

  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  function apiPost(url, body, cb) {
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { if (cb) cb(d); })
      .catch(function () {});
  }

  function apiGet(url, cb) {
    fetch(url, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRF() },
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { if (cb) cb(d); })
      .catch(function () {});
  }

  function toast(msg) {
    if (window.NamVibeToast) {
      window.NamVibeToast.show(msg);
    } else {
      alert(msg);
    }
  }

  function toastSuccess(msg) {
    if (window.NamVibeToast && window.NamVibeToast.success) {
      window.NamVibeToast.success(msg);
    } else {
      toast(msg);
    }
  }

  function escapeHtml(text) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }

  // ─── USER-SIDE ───────────────────────────────────────────

  window.NamVibeSupport = {
    searchArticles: function (query) {
      var list = document.getElementById("stArticleList");
      if (!list) return;
      var cards = list.querySelectorAll(".st-article-card");
      var q = query.toLowerCase().trim();
      cards.forEach(function (c) {
        var text = c.textContent.toLowerCase();
        c.style.display = !q || text.indexOf(q) !== -1 ? "" : "none";
      });
    },

    onCategoryChange: function () {
      var sel = document.getElementById("stCategory");
      var container = document.getElementById("stRelatedFields");
      var content = document.getElementById("stRelatedContent");
      if (!sel || !container || !content) return;
      var val = sel.value;
      if (val === "marketplace_dispute" && window.relatedOrder) {
        container.style.display = "block";
        content.innerHTML = "<p>Order ID: <strong>" + escapeHtml(window.relatedOrder) + "</strong></p>";
      } else if (val === "payment_wallet_issue" && window.relatedTransaction) {
        container.style.display = "block";
        content.innerHTML = "<p>Transaction: <strong>" + escapeHtml(window.relatedTransaction) + "</strong></p>";
      } else {
        container.style.display = "none";
      }
    },

    onFilesSelected: function (e) {
      var preview = document.getElementById("stFilePreview");
      if (!preview) return;
      preview.innerHTML = "";
      Array.from(e.target.files).forEach(function (f) {
        var div = document.createElement("div");
        div.className = "st-file-chip";
        div.textContent = f.name + " (" + (f.size / 1024).toFixed(1) + " KB)";
        preview.appendChild(div);
      });
    },

    createTicket: function (e) {
      e.preventDefault();
      var category = document.getElementById("stCategory")?.value;
      var subject = document.getElementById("stSubject")?.value.trim();
      var description = document.getElementById("stDescription")?.value.trim();
      var priority = document.getElementById("stPriority")?.value || "medium";

      if (!category || !subject || !description) {
        toast("Please fill in all required fields");
        return false;
      }

      var body = {
        category: category,
        subject: subject,
        description: description,
        priority: priority,
      };

      if (window.relatedOrder) body.related_order_id = window.relatedOrder;
      if (window.relatedTransaction) body.related_transaction_id = window.relatedTransaction;
      if (window.relatedProfile) body.related_profile_id = window.relatedProfile;
      if (window.relatedPost) body.related_post_id = window.relatedPost;

      apiPost("/api/support/tickets", body, function (d) {
        if (d.ok && d.ticket_id) {
          toastSuccess("Ticket created: " + d.ticket_id);
          window.location.href = "/support/tickets/" + d.ticket_id;
        } else {
          toast(d.error || "Failed to create ticket");
        }
      });

      return false;
    },

    filterTickets: function (status) {
      var buttons = document.querySelectorAll(".st-filter-btn");
      buttons.forEach(function (b) {
        b.classList.toggle("active", b.getAttribute("data-filter") === status);
      });
      var rows = document.querySelectorAll(".st-ticket-row");
      rows.forEach(function (r) {
        if (status === "all") {
          r.style.display = "";
        } else {
          r.style.display = r.getAttribute("data-status") === status ? "" : "none";
        }
      });
    },

    sendReply: function () {
      var input = document.getElementById("stReplyInput");
      if (!input) return;
      var msg = input.value.trim();
      if (!msg) return;

      apiPost(
        "/api/support/tickets/" + window.currentTicketId + "/messages",
        { message: msg },
        function (d) {
          if (d.ok) {
            input.value = "";
            location.reload();
          } else {
            toast(d.error || "Failed to send");
          }
        }
      );
    },

    onReplyInput: function () {
      // Typing indicator could go here
    },

    reopenTicket: function () {
      if (!confirm("Reopen this ticket?")) return;
      apiPost(
        "/api/support/tickets/" + window.currentTicketId + "/reopen",
        {},
        function (d) {
          if (d.ok) {
            toastSuccess("Ticket reopened");
            location.reload();
          } else {
            toast(d.error || "Failed to reopen");
          }
        }
      );
    },

    showFeedback: function () {
      var rating = prompt("Rate your support experience (1-5):");
      if (!rating) return;
      var num = parseInt(rating, 10);
      if (num < 1 || num > 5) {
        toast("Please enter a number between 1 and 5");
        return;
      }
      var comment = prompt("Any additional comments? (optional)") || "";
      apiPost(
        "/api/support/tickets/" + window.currentTicketId + "/feedback",
        { rating: num, comment: comment },
        function (d) {
          if (d.ok) {
            toastSuccess("Thank you for your feedback!");
          } else {
            toast(d.error || "Failed to submit feedback");
          }
        }
      );
    },

    helpful: function (yes) {
      toast(yes ? "Glad this helped!" : "Sorry this wasn't helpful.");
    },
  };

  // ─── ADMIN-SIDE ──────────────────────────────────────────

  window.NamVibeSupportAdmin = {
    init: function () {
      this.loadTickets();
      this.loadAgents();
    },

    switchView: function (view) {
      document.querySelectorAll(".st-admin-nav .st-btn").forEach(function (b) {
        b.classList.toggle("active", b.getAttribute("data-view") === view);
      });
      document.getElementById("stTicketTable").style.display = view === "tickets" ? "" : "none";
      var statsView = document.getElementById("stAdminStatsView");
      var agentsView = document.getElementById("stAdminAgentsView");
      if (statsView) statsView.style.display = view === "stats" ? "" : "none";
      if (agentsView) agentsView.style.display = view === "agents" ? "" : "none";
      if (view === "stats") this.loadStats();
      if (view === "agents") this.loadAgents();
    },

    loadTickets: function () {
      var tbody = document.getElementById("stTableBody");
      if (!tbody) return;
      tbody.innerHTML = '<div class="st-loading">Loading tickets...</div>';

      var status = document.getElementById("stFilterStatus")?.value || "";
      var category = document.getElementById("stFilterCategory")?.value || "";
      var priority = document.getElementById("stFilterPriority")?.value || "";
      var params = new URLSearchParams();
      if (status) params.set("status", status);
      if (category) params.set("category", category);
      if (priority) params.set("priority", priority);

      apiGet("/api/support/admin/tickets?" + params.toString(), function (d) {
        if (!d.ok || !d.tickets) {
          tbody.innerHTML = '<div class="st-loading">Failed to load tickets</div>';
          return;
        }
        if (d.tickets.length === 0) {
          tbody.innerHTML = '<div class="st-loading">No tickets found</div>';
          return;
        }
        var html = "";
        d.tickets.forEach(function (t) {
          html +=
            '<a href="/admin/support/tickets/' +
            escapeHtml(t.ticket_id) +
            '" class="st-ticket-row-admin">' +
            "<span>" + escapeHtml(t.ticket_id) + "</span>" +
            "<span>" + escapeHtml(t.subject) + "</span>" +
            "<span>" + escapeHtml(t.username || "?") + "</span>" +
            "<span>" + escapeHtml(t.category) + "</span>" +
            '<span><span class="st-badge st-priority-' + escapeHtml(t.priority) + '">' + escapeHtml(t.priority) + "</span></span>" +
            '<span><span class="st-badge st-badge-' + escapeHtml(t.status) + '">' + escapeHtml(t.status.replace(/_/g, " ")) + "</span></span>" +
            "<span>" + escapeHtml(t.agent_name || "Unassigned") + "</span>" +
            "<span>" + (t.last_activity_at || "") + "</span>" +
            "</a>";
        });
        tbody.innerHTML = html;
      });
    },

    loadStats: function () {
      var grid = document.getElementById("stStatsGrid");
      if (!grid) return;
      apiGet("/api/support/admin/dashboard", function (d) {
        if (!d.ok || !d.stats) return;
        var s = d.stats;
        var html = "";
        Object.keys(s.by_status || {}).forEach(function (k) {
          html +=
            '<div class="st-stat-card"><span class="st-stat-num">' +
            s.by_status[k] +
            '</span><span>' +
            k.replace(/_/g, " ") +
            "</span></div>";
        });
        grid.innerHTML = html;
      });
    },

    loadAgents: function () {
      var list = document.getElementById("stAgentsList");
      if (!list) return;
      apiGet("/api/support/admin/agents", function (d) {
        if (!d.ok || !d.agents) return;
        var html = "";
        d.agents.forEach(function (a) {
          html +=
            '<div class="st-sidebar-card">' +
            "<strong>" + escapeHtml(a.display_name || a.username) + "</strong>" +
            " <span class='st-badge'>" + escapeHtml(a.role) + "</span>" +
            "<br><small>Assigned: " + (a.assigned_count || 0) + " / " + (a.max_assigned || 20) + "</small>" +
            "</div>";
        });
        list.innerHTML = html || "<p>No agents found</p>";
      });
    },

    initTicket: function () {
      this.loadAgentSelect();
    },

    loadAgentSelect: function () {
      var sel = document.getElementById("stAssignSelect");
      if (!sel) return;
      apiGet("/api/support/admin/agents", function (d) {
        if (!d.ok || !d.agents) return;
        sel.innerHTML = '<option value="">Select agent...</option>';
        d.agents.forEach(function (a) {
          var opt = document.createElement("option");
          opt.value = a.profile_id;
          opt.textContent = (a.display_name || a.username) + " (" + (a.assigned_count || 0) + "/" + (a.max_assigned || 20) + ")";
          sel.appendChild(opt);
        });
      });
    },

    sendReply: function () {
      var input = document.getElementById("stAdminReply");
      if (!input) return;
      var msg = input.value.trim();
      if (!msg) return;
      var isInternal = document.getElementById("stInternalNote")?.checked || false;

      apiPost(
        "/api/support/admin/tickets/" + window.currentTicketId + "/message",
        { message: msg, is_internal: isInternal },
        function (d) {
          if (d.ok) {
            input.value = "";
            location.reload();
          } else {
            toast(d.error || "Failed to send");
          }
        }
      );
    },

    updateStatus: function () {
      var sel = document.getElementById("stStatusSelect");
      if (!sel) return;
      var status = sel.value;
      var reason = prompt("Reason for status change:") || "";
      apiPost(
        "/api/support/admin/tickets/" + window.currentTicketId + "/status",
        { status: status, reason: reason },
        function (d) {
          if (d.ok) {
            toastSuccess("Status updated");
            location.reload();
          } else {
            toast(d.error || "Failed to update");
          }
        }
      );
    },

    assignTicket: function () {
      var sel = document.getElementById("stAssignSelect");
      if (!sel || !sel.value) {
        toast("Select an agent");
        return;
      }
      var reason = prompt("Assignment reason:") || "";
      apiPost(
        "/api/support/admin/tickets/" + window.currentTicketId + "/assign",
        { agent_profile_id: parseInt(sel.value, 10), reason: reason },
        function (d) {
          if (d.ok) {
            toastSuccess("Ticket assigned");
            location.reload();
          } else {
            toast(d.error || "Failed to assign");
          }
        }
      );
    },

    escalate: function () {
      var sel = document.getElementById("stEscalateTo");
      if (!sel || !sel.value) {
        toast("Select a team");
        return;
      }
      var reason = prompt("Reason for escalation:") || "";
      apiPost(
        "/api/support/admin/tickets/" + window.currentTicketId + "/status",
        { status: "escalated", reason: "Escalated to " + sel.value + ": " + reason },
        function (d) {
          if (d.ok) {
            toastSuccess("Escalated to " + sel.value);
            location.reload();
          } else {
            toast(d.error || "Failed to escalate");
          }
        }
      );
    },

    suspendUser: function () {
      if (!confirm("Are you sure you want to suspend this user?")) return;
      toast("Suspension requires additional permissions. Please use the admin panel.");
    },
  };
})();
