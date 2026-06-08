#!/usr/bin/env bash
set -e

echo "=== CHAIN PHASE 14: MESSAGE UI UPGRADE ==="

mkdir -p backups/phase14
cp templates/messages/index.html backups/phase14/index.html.bak 2>/dev/null || true

cat > templates/messages/index.html <<'HTML'
{% extends "base.html" %}
{% block title %}Messages | CHAIN{% endblock %}

{% block extra_css %}
<style>
.message-shell{
    display:grid;
    grid-template-columns:380px 1fr;
    gap:18px;
    max-width:1250px;
    margin:0 auto;
    padding:18px;
}
.message-sidebar,.message-empty{
    background:rgba(255,255,255,.92);
    border:1px solid rgba(15,23,42,.08);
    border-radius:28px;
    box-shadow:0 18px 50px rgba(15,23,42,.08);
}
.message-sidebar{
    overflow:hidden;
}
.message-top{
    padding:20px;
    border-bottom:1px solid rgba(15,23,42,.08);
}
.message-title-row{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
}
.message-title-row h2{
    margin:0;
    font-size:26px;
    font-weight:900;
    color:#0f172a;
}
.new-chat-btn{
    border:0;
    background:#111827;
    color:#fff;
    border-radius:999px;
    padding:11px 15px;
    font-weight:800;
    cursor:pointer;
}
.search-wrap{
    margin-top:16px;
    position:relative;
}
.search-wrap i{
    position:absolute;
    left:15px;
    top:50%;
    transform:translateY(-50%);
    color:#64748b;
}
#chat-search{
    width:100%;
    border:1px solid rgba(15,23,42,.1);
    background:#f8fafc;
    border-radius:18px;
    padding:14px 16px 14px 42px;
    font-weight:700;
    outline:none;
}
.message-tabs{
    display:flex;
    gap:8px;
    margin-top:14px;
    overflow:auto;
}
.message-tabs a{
    text-decoration:none;
    color:#475569;
    background:#f1f5f9;
    border-radius:999px;
    padding:9px 13px;
    font-weight:800;
    white-space:nowrap;
}
.message-tabs a.active{
    background:#111827;
    color:white;
}
.thread-list{
    max-height:calc(100vh - 260px);
    overflow:auto;
}
.thread-card{
    display:flex;
    gap:13px;
    padding:16px 18px;
    text-decoration:none;
    color:inherit;
    border-bottom:1px solid rgba(15,23,42,.06);
    transition:.2s ease;
}
.thread-card:hover{
    background:#f8fafc;
}
.thread-avatar{
    width:52px;
    height:52px;
    border-radius:18px;
    background:linear-gradient(135deg,#111827,#475569);
    color:#fff;
    display:grid;
    place-items:center;
    overflow:hidden;
    flex-shrink:0;
}
.thread-avatar img{
    width:100%;
    height:100%;
    object-fit:cover;
}
.thread-body{
    min-width:0;
    flex:1;
}
.thread-line{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
}
.thread-name{
    font-weight:900;
    color:#0f172a;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
.thread-time{
    font-size:12px;
    color:#94a3b8;
    white-space:nowrap;
}
.thread-preview-row{
    margin-top:5px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:8px;
}
.thread-preview{
    color:#64748b;
    font-size:14px;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
.unread-badge{
    background:#ef4444;
    color:white;
    min-width:22px;
    height:22px;
    border-radius:999px;
    display:grid;
    place-items:center;
    font-size:12px;
    font-weight:900;
}
.thread-tags{
    margin-top:8px;
    display:flex;
    gap:6px;
}
.thread-tag{
    font-size:11px;
    font-weight:800;
    color:#475569;
    background:#e2e8f0;
    border-radius:999px;
    padding:4px 7px;
}
.message-empty{
    min-height:620px;
    display:grid;
    place-items:center;
    text-align:center;
    padding:35px;
}
.message-empty-icon{
    width:96px;
    height:96px;
    border-radius:32px;
    background:#f1f5f9;
    display:grid;
    place-items:center;
    margin:0 auto 22px;
    color:#475569;
    font-size:42px;
}
.message-empty h3{
    font-size:28px;
    margin:0 0 8px;
    color:#0f172a;
}
.message-empty p{
    color:#64748b;
    margin:0 0 20px;
}
.empty-actions{
    display:flex;
    gap:10px;
    justify-content:center;
    flex-wrap:wrap;
}
.empty-actions a,.empty-actions button{
    border:0;
    text-decoration:none;
    border-radius:999px;
    padding:12px 16px;
    font-weight:900;
    cursor:pointer;
}
.primary-action{
    background:#111827;
    color:#fff;
}
.secondary-action{
    background:#e2e8f0;
    color:#0f172a;
}
.no-results{
    display:none;
    padding:35px 18px;
    text-align:center;
    color:#64748b;
    font-weight:800;
}
.modal-backdrop{
    position:fixed;
    inset:0;
    background:rgba(15,23,42,.58);
    display:none;
    align-items:center;
    justify-content:center;
    z-index:1000;
    padding:20px;
}
.modal-card{
    width:min(520px,100%);
    background:white;
    border-radius:28px;
    padding:22px;
    box-shadow:0 30px 90px rgba(0,0,0,.25);
}
.modal-head{
    display:flex;
    justify-content:space-between;
    align-items:center;
}
.modal-head h3{
    margin:0;
    font-size:24px;
}
.close-modal{
    border:0;
    background:#f1f5f9;
    width:40px;
    height:40px;
    border-radius:999px;
    cursor:pointer;
}
.username-input{
    width:100%;
    margin-top:18px;
    padding:15px;
    border-radius:16px;
    border:1px solid #cbd5e1;
    font-weight:800;
}
.start-chat-submit{
    width:100%;
    margin-top:12px;
    border:0;
    background:#111827;
    color:white;
    padding:14px;
    border-radius:16px;
    font-weight:900;
    cursor:pointer;
}
.help-text{
    color:#64748b;
    font-size:13px;
    margin-top:10px;
}
@media(max-width:900px){
    .message-shell{
        grid-template-columns:1fr;
        padding:10px;
    }
    .message-empty{
        display:none;
    }
    .thread-list{
        max-height:none;
    }
}
</style>
{% endblock %}

{% block content %}
<div class="message-shell">
    <aside class="message-sidebar">
        <div class="message-top">
            <div class="message-title-row">
                <h2>Messages</h2>
                <button class="new-chat-btn" type="button" id="openNewChat">
                    <i class="fas fa-plus"></i> New Chat
                </button>
            </div>

            <div class="search-wrap">
                <i class="fas fa-search"></i>
                <input id="chat-search" type="search" placeholder="Search messages, names, groups...">
            </div>

            <nav class="message-tabs">
                <a class="{{ 'active' if not active_folder or active_folder == 'all' else '' }}" href="/messages/?folder=all">All</a>
                <a class="{{ 'active' if active_folder == 'unread' else '' }}" href="/messages/?folder=unread">Unread</a>
                <a class="{{ 'active' if active_folder == 'archived' else '' }}" href="/messages/?folder=archived">Archived</a>
                <a class="{{ 'active' if active_folder == 'groups' else '' }}" href="/messages/?folder=groups">Groups</a>
            </nav>
        </div>

        <div class="thread-list" id="threadList">
            {% if threads %}
                {% for t in threads %}
                <a class="thread-card"
                   href="/messages/{{ t.id }}"
                   data-search="{{ (t.display_name ~ ' ' ~ (t.last_message or '') ~ ' ' ~ (t.thread_type or ''))|lower }}">
                    <div class="thread-avatar">
                        {% if t.display_avatar %}
                        <img src="{{ t.display_avatar }}" loading="lazy" alt="">
                        {% else %}
                        <i class="fas fa-{{ 'users' if t.thread_type == 'group' else 'user' }}"></i>
                        {% endif %}
                    </div>

                    <div class="thread-body">
                        <div class="thread-line">
                            <span class="thread-name">{{ t.display_name or 'Conversation' }}</span>
                            <span class="thread-time">{{ t.last_message_at|datetime if t.last_message_at else '' }}</span>
                        </div>

                        <div class="thread-preview-row">
                            <span class="thread-preview">{{ t.last_message or 'No messages yet' }}</span>
                            {% if t.unread_count and t.unread_count > 0 %}
                            <span class="unread-badge">{{ t.unread_count }}</span>
                            {% endif %}
                        </div>

                        <div class="thread-tags">
                            <span class="thread-tag">{{ 'Group' if t.thread_type == 'group' else 'Direct' }}</span>
                            {% if t.folder_type %}
                            <span class="thread-tag">{{ t.folder_type|title }}</span>
                            {% endif %}
                        </div>
                    </div>
                </a>
                {% endfor %}
            {% else %}
                <div style="padding:40px 18px;text-align:center;color:#64748b;">
                    <i class="fas fa-comment-slash fa-3x" style="margin-bottom:18px;opacity:.35;"></i>
                    <p style="font-weight:900;">No conversations yet</p>
                    <p>Start by searching a username or opening a profile and pressing Message.</p>
                </div>
            {% endif %}
        </div>

        <div class="no-results" id="noResults">
            No messages found.
        </div>
    </aside>

    <main class="message-empty">
        <div>
            <div class="message-empty-icon">
                <i class="fas fa-comments"></i>
            </div>
            <h3>Your Messages</h3>
            <p>Select a conversation or start a new private/group chat.</p>
            <div class="empty-actions">
                <button class="primary-action" type="button" id="openNewChatMain">Start New Chat</button>
                <a class="secondary-action" href="/profile/">My Profile</a>
            </div>
        </div>
    </main>
</div>

<div class="modal-backdrop" id="newChatModal">
    <div class="modal-card">
        <div class="modal-head">
            <h3>Start New Chat</h3>
            <button class="close-modal" type="button" id="closeNewChat">
                <i class="fas fa-times"></i>
            </button>
        </div>

        <input class="username-input" id="newChatUsername" placeholder="Enter username, e.g. desertking_na">
        <button class="start-chat-submit" type="button" id="startChatBtn">
            Open Chat
        </button>

        <div class="help-text">
            Tip: open a user profile and press Message, or type their username here.
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
(function(){
    const search = document.getElementById('chat-search');
    const cards = Array.from(document.querySelectorAll('.thread-card'));
    const noResults = document.getElementById('noResults');

    if(search){
        search.addEventListener('input', function(){
            const q = this.value.trim().toLowerCase();
            let visible = 0;

            cards.forEach(card => {
                const haystack = card.dataset.search || '';
                const show = !q || haystack.includes(q);
                card.style.display = show ? 'flex' : 'none';
                if(show) visible++;
            });

            if(noResults){
                noResults.style.display = q && visible === 0 ? 'block' : 'none';
            }
        });
    }

    const modal = document.getElementById('newChatModal');
    const input = document.getElementById('newChatUsername');

    function openModal(){
        modal.style.display = 'flex';
        setTimeout(() => input.focus(), 50);
    }

    function closeModal(){
        modal.style.display = 'none';
    }

    function startChat(){
        let username = input.value.trim();
        if(!username){
            input.focus();
            return;
        }
        username = username.replace(/^@/, '');
        window.location.href = '/messages/@' + encodeURIComponent(username);
    }

    document.getElementById('openNewChat')?.addEventListener('click', openModal);
    document.getElementById('openNewChatMain')?.addEventListener('click', openModal);
    document.getElementById('closeNewChat')?.addEventListener('click', closeModal);
    document.getElementById('startChatBtn')?.addEventListener('click', startChat);

    input?.addEventListener('keydown', function(e){
        if(e.key === 'Enter') startChat();
        if(e.key === 'Escape') closeModal();
    });

    modal?.addEventListener('click', function(e){
        if(e.target === modal) closeModal();
    });
})();
</script>
{% endblock %}
HTML

python3 -m py_compile app.py services/*.py api_routes/*.py

echo ""
echo "=== CHECK MESSAGE ROUTES ==="
PYTHONPATH=. python3 - <<'PY'
from app import app
for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
    rule = str(r)
    if "messages" in rule:
        print(rule, "=>", r.endpoint)
PY

echo ""
echo "✅ Message inbox upgraded."
echo "Now restart Flask and open: http://127.0.0.1:5000/messages/"
