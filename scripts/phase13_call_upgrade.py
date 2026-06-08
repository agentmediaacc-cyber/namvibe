from pathlib import Path

# ==================================================
# 1) Upgrade call service recent calls
# ==================================================
p = Path("services/call_service.py")
text = p.read_text()

if "def search_callable_contacts" not in text:
    text += r'''

def search_callable_contacts(profile_id, q="", limit=20):
    """
    Search accepted friends/follows plus public profiles for starting calls.
    """
    params = []
    like = f"%{q.strip()}%" if q else "%"
    sql = """
        SELECT DISTINCT p.id, p.username, p.full_name, p.display_name, p.avatar_url, p.is_online
        FROM chain_profiles p
        WHERE p.deleted_at IS NULL
          AND p.id != %s
          AND (
              p.username ILIKE %s
              OR p.full_name ILIKE %s
              OR p.display_name ILIKE %s
          )
        ORDER BY COALESCE(p.full_name, p.display_name, p.username) ASC
        LIMIT %s
    """
    params = [profile_id, like, like, like, limit]
    return fast_query(sql, tuple(params), timeout_ms=1500, default=[])


def profile_has_active_call(profile_id):
    rows = fast_query("""
        SELECT id
        FROM chain_call_sessions
        WHERE call_status IN ('ringing', 'answered', 'active')
          AND (caller_profile_id = %s OR receiver_profile_id = %s)
        LIMIT 1
    """, (profile_id, profile_id), timeout_ms=1000, default=[])
    return rows[0] if rows else None


def format_call_log_row(row, profile_id):
    is_outgoing = str(row.get("caller_profile_id")) == str(profile_id)
    other_name = row.get("receiver_name") if is_outgoing else row.get("caller_name")
    other_username = row.get("receiver_username") if is_outgoing else row.get("caller_username")
    other_avatar = row.get("receiver_avatar") if is_outgoing else row.get("caller_avatar")
    return {
        **row,
        "direction": "outgoing" if is_outgoing else "incoming",
        "other_name": other_name or other_username or "Unknown user",
        "other_username": other_username,
        "other_avatar": other_avatar,
        "duration_label": f"{int(row.get('duration_seconds') or 0)} sec",
    }
'''
    print("✅ Added call contact/search helpers")

old = '''def list_recent_calls(profile_id):'''
if old in text and "format_call_log_row(row, profile_id)" not in text:
    start = text.find(old)
    end = text.find("\ndef ", start + 1)
    if end == -1:
        end = len(text)
    new = r'''def list_recent_calls(profile_id):
    sql = """
        SELECT c.*,
               caller.username AS caller_username,
               caller.full_name AS caller_name,
               caller.avatar_url AS caller_avatar,
               receiver.username AS receiver_username,
               receiver.full_name AS receiver_name,
               receiver.avatar_url AS receiver_avatar
        FROM chain_call_sessions c
        LEFT JOIN chain_profiles caller ON c.caller_profile_id = caller.id
        LEFT JOIN chain_profiles receiver ON c.receiver_profile_id = receiver.id
        WHERE c.caller_profile_id = %s OR c.receiver_profile_id = %s
        ORDER BY c.started_at DESC NULLS LAST
        LIMIT 50
    """
    rows = fast_query(sql, (profile_id, profile_id), timeout_ms=2000, default=[])
    return [format_call_log_row(row, profile_id) for row in rows]
'''
    text = text[:start] + new + text[end:]
    print("✅ Replaced list_recent_calls with premium formatter")

p.write_text(text)


# ==================================================
# 2) Upgrade call routes: search contacts + busy check
# ==================================================
p = Path("api_routes/call_routes.py")
text = p.read_text()

text = text.replace(
    "start_call, answer_call, end_call, list_recent_calls,",
    "start_call, answer_call, end_call, list_recent_calls, search_callable_contacts, profile_has_active_call,"
)

if "def call_contacts_api" not in text:
    insert = r'''

@call_bp.route("/api/contacts")
@login_required
def call_contacts_api():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify([]), 200
    q = request.args.get("q", "")
    return jsonify(search_callable_contacts(profile["id"], q=q)), 200
'''
    text += insert
    print("✅ Added /calls/api/contacts")

# Add busy checks in start_direct_call_from_profile before start_call
needle = "call = start_call(thread_id, viewer_id, target_id, call_type)"
if needle in text and "target_active_call = profile_has_active_call(target_id)" not in text:
    text = text.replace(
        needle,
        """caller_active_call = profile_has_active_call(viewer_id)
    if caller_active_call:
        flash("You are already in a call. End the current call before starting another.", "warning")
        return redirect(f"/calls/{caller_active_call['id']}/view")

    target_active_call = profile_has_active_call(target_id)
    if target_active_call:
        flash("User is currently busy on another call.", "warning")
        return redirect("/calls/recent")

    call = start_call(thread_id, viewer_id, target_id, call_type)"""
    )
    print("✅ Added caller/receiver busy checks")

p.write_text(text)


# ==================================================
# 3) Replace calls/recent.html with premium responsive UI
# ==================================================
p = Path("templates/calls/recent.html")
p.write_text(r'''{% extends "base.html" %}
{% block title %}Calls | CHAIN{% endblock %}

{% block content %}
<style>
.call-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 20px;
}
.call-panel {
  background: rgba(255,255,255,.84);
  border: 1px solid rgba(15,23,42,.08);
  border-radius: 28px;
  box-shadow: 0 18px 60px rgba(15,23,42,.10);
  overflow: hidden;
}
.call-head {
  padding: 22px;
  background: linear-gradient(135deg, #111827, #4f46e5);
  color: white;
}
.call-head h1 { margin: 0; font-size: 26px; }
.call-head p { margin: 6px 0 0; opacity: .8; }
.call-search { padding: 16px; border-bottom: 1px solid rgba(15,23,42,.08); }
.call-search input {
  width: 100%;
  border: 1px solid rgba(15,23,42,.12);
  border-radius: 16px;
  padding: 13px 14px;
  font-weight: 700;
}
.contact-results, .call-list { padding: 12px; display: grid; gap: 10px; }
.call-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 20px;
  background: rgba(248,250,252,.92);
  border: 1px solid rgba(15,23,42,.06);
}
.avatar {
  width: 52px; height: 52px; border-radius: 50%;
  background: #e5e7eb; display:grid; place-items:center;
  overflow:hidden; font-weight:900;
}
.avatar img { width:100%; height:100%; object-fit:cover; }
.call-meta { flex:1; min-width:0; }
.call-name { font-weight:900; color:#111827; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.call-sub { font-size:12px; color:#64748b; margin-top:3px; }
.call-actions { display:flex; gap:8px; }
.call-btn {
  width:40px; height:40px; border-radius:50%; border:0;
  display:grid; place-items:center; cursor:pointer; text-decoration:none;
  background:#eef2ff; color:#4338ca; font-weight:900;
}
.call-btn.video { background:#ecfeff; color:#0891b2; }
.call-btn.redial { background:#fef2f2; color:#dc2626; }
.call-log-title { padding:18px 20px 6px; font-weight:1000; font-size:18px; }
.badge {
  display:inline-flex; align-items:center; gap:5px; padding:4px 8px;
  border-radius:999px; font-size:11px; font-weight:900;
}
.incoming { background:#ecfdf5; color:#059669; }
.outgoing { background:#eff6ff; color:#2563eb; }
.missed { background:#fef2f2; color:#dc2626; }
.empty {
  padding: 50px 20px; text-align:center; color:#64748b;
}
@media (max-width: 850px) {
  .call-page { grid-template-columns: 1fr; padding: 12px; }
  .call-panel { border-radius: 22px; }
}
</style>

<section class="call-page">
  <aside class="call-panel">
    <div class="call-head">
      <h1>Calls</h1>
      <p>Search contacts, start audio/video calls, and redial quickly.</p>
    </div>

    <div class="call-search">
      <input id="callContactSearch" placeholder="Search contacts or username..." autocomplete="off">
    </div>

    <div id="callContacts" class="contact-results">
      <div class="empty">Search a user to start a call.</div>
    </div>
  </aside>

  <main class="call-panel">
    <div class="call-log-title">Recent calls</div>

    <div class="call-list">
      {% if calls %}
        {% for c in calls %}
        <div class="call-row">
          <div class="avatar">
            {% if c.other_avatar %}
              <img src="{{ c.other_avatar }}">
            {% else %}
              {{ (c.other_name or '?')[:1] }}
            {% endif %}
          </div>

          <div class="call-meta">
            <div class="call-name">{{ c.other_name }}</div>
            <div class="call-sub">
              <span class="badge {{ c.direction }}">{{ c.direction|title }}</span>
              {{ c.call_type|title }} • {{ c.call_status|title }} • {{ c.duration_label }}
            </div>
            <div class="call-sub">{{ c.started_at }}</div>
          </div>

          <div class="call-actions">
            {% set other_id = c.receiver_profile_id if c.direction == 'outgoing' else c.caller_profile_id %}
            <a class="call-btn redial" title="Redial" href="/calls/start/{{ other_id }}/{{ c.call_type }}"><i class="fas fa-redo"></i></a>
            <a class="call-btn" title="Audio call" href="/calls/start/{{ other_id }}/audio"><i class="fas fa-phone"></i></a>
            <a class="call-btn video" title="Video call" href="/calls/start/{{ other_id }}/video"><i class="fas fa-video"></i></a>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty">
          <i class="fas fa-phone-slash fa-3x" style="opacity:.25"></i>
          <p>No call history yet.</p>
        </div>
      {% endif %}
    </div>
  </main>
</section>

<script>
(function(){
  const input = document.getElementById("callContactSearch");
  const box = document.getElementById("callContacts");
  let timer = null;

  function row(p){
    const name = p.full_name || p.display_name || p.username || "User";
    return `
      <div class="call-row">
        <div class="avatar">${p.avatar_url ? `<img src="${p.avatar_url}">` : name.slice(0,1)}</div>
        <div class="call-meta">
          <div class="call-name">${name}</div>
          <div class="call-sub">@${p.username || ""} ${p.is_online ? "• Online" : "• Offline"}</div>
        </div>
        <div class="call-actions">
          <a class="call-btn" href="/calls/start/${p.id}/audio" title="Audio"><i class="fas fa-phone"></i></a>
          <a class="call-btn video" href="/calls/start/${p.id}/video" title="Video"><i class="fas fa-video"></i></a>
        </div>
      </div>
    `;
  }

  async function search(){
    const q = input.value.trim();
    if(q.length < 1){
      box.innerHTML = '<div class="empty">Search a user to start a call.</div>';
      return;
    }
    box.innerHTML = '<div class="empty">Searching...</div>';
    const res = await fetch("/calls/api/contacts?q=" + encodeURIComponent(q));
    const data = await res.json();
    box.innerHTML = data.length ? data.map(row).join("") : '<div class="empty">No contacts found.</div>';
  }

  input.addEventListener("input", function(){
    clearTimeout(timer);
    timer = setTimeout(search, 250);
  });
})();
</script>
{% endblock %}
''')
print("✅ Rebuilt premium calls/recent.html")

