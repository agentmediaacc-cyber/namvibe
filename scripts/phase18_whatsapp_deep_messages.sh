#!/usr/bin/env bash
set -e

echo "=== PHASE 18: WHATSAPP-STYLE MESSAGES + VOICE NOTES + GROUP ACCESS ==="

mkdir -p backups/phase18
cp templates/messages/index.html backups/phase18/messages_index.bak 2>/dev/null || true
cp api_routes/message_upgrade_routes.py backups/phase18/message_upgrade_routes.bak 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path

p = Path("api_routes/message_upgrade_routes.py")
text = p.read_text()

extra = r'''

@message_upgrade_bp.route("/thread/<thread_id>/attachment", methods=["POST"])
def send_attachment(thread_id):
    file = request.files.get("file")
    kind = request.form.get("kind", "file")
    if not file:
        return jsonify({"ok": False, "error": "No file"}), 400

    msg = {
        "id": str(uuid4()),
        "sender": "You",
        "body": f"📎 Attached {kind}: {file.filename}",
        "filename": file.filename,
        "kind": kind,
        "created_at": _now(),
        "mine": True
    }
    _messages().setdefault(thread_id, []).append(msg)
    session.modified = True
    return jsonify({"ok": True, "message": msg})


@message_upgrade_bp.route("/thread/<thread_id>/voice-note", methods=["POST"])
def send_voice_note(thread_id):
    seconds = request.form.get("seconds") or request.json.get("seconds") if request.is_json else "0"
    msg = {
        "id": str(uuid4()),
        "sender": "You",
        "body": f"🎙 Voice note • {seconds}s",
        "kind": "voice_note",
        "created_at": _now(),
        "mine": True
    }
    _messages().setdefault(thread_id, []).append(msg)
    session.modified = True
    return jsonify({"ok": True, "message": msg})


@message_upgrade_bp.route("/typing/<thread_id>", methods=["POST"])
def typing_status(thread_id):
    return jsonify({
        "ok": True,
        "thread_id": thread_id,
        "status": "typing",
        "text": "Typing..."
    })


@message_upgrade_bp.route("/groups/empty")
def groups_empty():
    groups = _groups()
    return jsonify({
        "ok": True,
        "has_groups": bool(groups),
        "message": "No groups yet. Create a public, private, paid or premium group."
    })
'''

if "send_voice_note" not in text:
    text += extra

# improve create group with access options
text = text.replace(
    '"public": True,',
    '''"public": data.get("public", True) in [True, "true", "on", "1", 1],
        "access_type": data.get("access_type", "public"),
        "join_fee": data.get("join_fee", "0"),
        "premium_only": data.get("premium_only", False) in [True, "true", "on", "1", 1],
        "approve_members": data.get("approve_members", False) in [True, "true", "on", "1", 1],'''
)

p.write_text(text)
print("Backend upgraded")
PY

python3 - <<'PY'
from pathlib import Path

p = Path("templates/messages/index.html")
text = p.read_text()

# add deeper css before </style>
deep_css = r'''
.typing-line{
    color:#00f2ea;
    font-size:12px;
    font-weight:900;
    margin-top:3px;
    display:none;
}
.attach-menu{
    position:fixed;
    left:410px;
    bottom:86px;
    background:#0a0a0a;
    border:1px solid rgba(255,255,255,.14);
    border-radius:24px;
    padding:12px;
    display:none;
    z-index:2500;
    box-shadow:0 20px 80px rgba(0,0,0,.45);
}
.attach-menu.active{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.attach-item{
    border:0;
    border-radius:18px;
    background:rgba(255,255,255,.09);
    color:white;
    padding:14px;
    min-width:96px;
    cursor:pointer;
    font-weight:900;
}
.attach-item i{display:block;font-size:22px;margin-bottom:7px;color:#00f2ea}
.recording-pill{
    display:none;
    align-items:center;
    gap:9px;
    color:white;
    background:#ff0050;
    border-radius:999px;
    padding:10px 14px;
    font-weight:950;
}
.recording-pill.active{display:flex}
.record-dot{
    width:10px;
    height:10px;
    border-radius:50%;
    background:white;
    animation:pulse 1s infinite;
}
.group-empty-card{
    margin:18px;
    padding:22px;
    border-radius:26px;
    background:rgba(255,255,255,.08);
    border:1px dashed rgba(255,255,255,.18);
    text-align:center;
}
.group-access-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
}
.group-access-grid select,
.group-access-grid input{
    width:100%;
}
@media(max-width:850px){
    .attach-menu{left:12px;right:12px;bottom:80px;grid-template-columns:repeat(2,1fr)}
}
'''
text = text.replace("</style>", deep_css + "\n</style>")

# add typing line after chatSub p
text = text.replace(
    '<div><h2 id="chatTitle">CHAIN Chat</h2><p id="chatSub">Select chat or start new conversation</p></div>',
    '<div><h2 id="chatTitle">CHAIN Chat</h2><p id="chatSub">Select chat or start new conversation</p><div class="typing-line" id="typingLine">Typing...</div></div>'
)

# replace composer with richer composer
old = r'''<div class="composer">
            <select id="keyboardLang">
                <option value="en">EN</option>
                <option value="af">AF</option>
                <option value="de">DE</option>
                <option value="pt">PT</option>
                <option value="oshiwambo">Oshiwambo</option>
                <option value="kavango">Kavango</option>
                <option value="herero">Otjiherero</option>
                <option value="nama">Nama/Damara</option>
            </select>
            <button class="premium-btn" id="emojiBtn" type="button">😊</button>
            <input id="messageInput" placeholder="Type message, advert, post or comment...">
            <button class="premium-btn primary" id="sendBtn" type="button"><i class="fas fa-paper-plane"></i></button>
        </div>'''

new = r'''<div class="composer">
            <select id="keyboardLang">
                <option value="en">EN</option>
                <option value="af">AF</option>
                <option value="de">DE</option>
                <option value="pt">PT</option>
                <option value="oshiwambo">Oshiwambo</option>
                <option value="kavango">Kavango</option>
                <option value="herero">Otjiherero</option>
                <option value="nama">Nama/Damara</option>
            </select>

            <button class="premium-btn" id="attachBtn" type="button"><i class="fas fa-paperclip"></i></button>
            <button class="premium-btn" id="emojiBtn" type="button">😊</button>

            <div class="recording-pill" id="recordingPill">
                <span class="record-dot"></span>
                <span id="recordTimer">0s</span>
            </div>

            <input id="messageInput" placeholder="Type message, advert, post or comment...">

            <button class="premium-btn" id="voiceBtn" type="button"><i class="fas fa-microphone"></i></button>
            <button class="premium-btn primary" id="sendBtn" type="button"><i class="fas fa-paper-plane"></i></button>

            <input type="file" id="hiddenFile" hidden>
        </div>

        <div class="attach-menu" id="attachMenu">
            <button class="attach-item" data-kind="photo"><i class="fas fa-image"></i>Photo</button>
            <button class="attach-item" data-kind="video"><i class="fas fa-video"></i>Video</button>
            <button class="attach-item" data-kind="document"><i class="fas fa-file"></i>Document</button>
            <button class="attach-item" data-kind="contact"><i class="fas fa-address-book"></i>Contact</button>
            <button class="attach-item" data-kind="location"><i class="fas fa-map-marker-alt"></i>Location</button>
            <button class="attach-item" data-kind="advert"><i class="fas fa-bullhorn"></i>Advert</button>
        </div>'''

text = text.replace(old, new)

# upgrade group modal fields
text = text.replace(
    '<input class="field" id="groupMembers" placeholder="Members usernames separated by comma">',
    '''<input class="field" id="groupMembers" placeholder="Members usernames separated by comma">
        <div class="group-access-grid">
            <select class="field" id="groupAccessType">
                <option value="public">Public - anyone can search and join</option>
                <option value="private">Private - invite or approval only</option>
                <option value="paid">Paid - join with funds</option>
                <option value="premium">Premium members only</option>
            </select>
            <input class="field" id="groupJoinFee" placeholder="Join fee e.g. 20" value="0">
        </div>'''
)

# add public/private check rows
text = text.replace(
    '<div class="check-row"><span>Allow members to invite others</span><input type="checkbox" id="allowInvite"></div>',
    '''<div class="check-row"><span>Allow members to invite others</span><input type="checkbox" id="allowInvite"></div>
        <div class="check-row"><span>Require host approval</span><input type="checkbox" id="approveMembers"></div>
        <div class="check-row"><span>Premium members only</span><input type="checkbox" id="premiumOnly"></div>'''
)

# JS additions before closing IIFE
js_add = r'''
    // Deep WhatsApp-style extras
    let typingTimeout = null;
    let recordTimer = null;
    let recordSeconds = 0;
    let isRecording = false;
    let selectedAttachKind = "file";

    function showTyping(){
        if(!currentThreadId) return;
        const line = $('typingLine');
        if(line){
            line.style.display = 'block';
            line.textContent = 'You are typing...';
        }
        fetch('/messages/typing/' + encodeURIComponent(currentThreadId), {method:'POST'}).catch(()=>{});
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(()=>{
            if(line) line.style.display = 'none';
        }, 1200);
    }

    $('messageInput')?.addEventListener('input', showTyping);

    $('attachBtn')?.addEventListener('click',()=>{
        $('attachMenu')?.classList.toggle('active');
    });

    document.querySelectorAll('.attach-item').forEach(btn=>{
        btn.addEventListener('click',()=>{
            selectedAttachKind = btn.dataset.kind || 'file';
            $('attachMenu')?.classList.remove('active');

            if(selectedAttachKind === 'location'){
                if(currentThreadId){
                    $('messageInput').value = '📍 Shared location: Windhoek, Namibia';
                    $('sendBtn').click();
                }
                return;
            }

            if(selectedAttachKind === 'contact'){
                $('messageInput').value = '👤 Shared contact card';
                $('sendBtn').click();
                return;
            }

            if(selectedAttachKind === 'advert'){
                $('messageInput').value = '📢 Advert: ';
                $('messageInput').focus();
                return;
            }

            $('hiddenFile').click();
        });
    });

    $('hiddenFile')?.addEventListener('change', async ()=>{
        if(!currentThreadId || !$('hiddenFile').files.length) return;
        const form = new FormData();
        form.append('file', $('hiddenFile').files[0]);
        form.append('kind', selectedAttachKind);
        await fetch('/messages/thread/' + encodeURIComponent(currentThreadId) + '/attachment', {
            method:'POST',
            body:form
        });
        $('hiddenFile').value = '';
        openThread(currentThreadId,currentThreadName,currentThreadType);
    });

    $('voiceBtn')?.addEventListener('click', async ()=>{
        if(!currentThreadId){
            alert('Open a chat first.');
            return;
        }

        if(!isRecording){
            isRecording = true;
            recordSeconds = 0;
            $('recordingPill')?.classList.add('active');
            $('messageInput').style.display = 'none';
            recordTimer = setInterval(()=>{
                recordSeconds++;
                $('recordTimer').textContent = recordSeconds + 's';
            }, 1000);
            return;
        }

        isRecording = false;
        clearInterval(recordTimer);
        $('recordingPill')?.classList.remove('active');
        $('messageInput').style.display = '';

        const form = new FormData();
        form.append('seconds', String(recordSeconds));
        await fetch('/messages/thread/' + encodeURIComponent(currentThreadId) + '/voice-note', {
            method:'POST',
            body:form
        });
        openThread(currentThreadId,currentThreadName,currentThreadType);
    });

    async function checkGroupEmpty(){
        const groupsTab = document.querySelector('[data-tab="groups"]');
        groupsTab?.addEventListener('click',async()=>{
            const visibleGroups = Array.from(document.querySelectorAll('.thread-card')).filter(c => c.dataset.type === 'group');
            if(visibleGroups.length === 0){
                $('threadList').insertAdjacentHTML('afterbegin', `
                    <div class="group-empty-card" id="groupEmptyCard">
                        <h3>No groups yet</h3>
                        <p>Create a public, private, paid or premium group.</p>
                        <button class="premium-btn primary" onclick="document.getElementById('groupModal').classList.add('active')">Create Group</button>
                    </div>
                `);
            }
        });
    }
    checkGroupEmpty();
'''

text = text.replace("})();", js_add + "\n})();")

# improve group payload
text = text.replace(
    "allow_invite:$('allowInvite').checked",
    """allow_invite:$('allowInvite').checked,
            access_type:$('groupAccessType').value,
            join_fee:$('groupJoinFee').value,
            premium_only:$('premiumOnly').checked,
            approve_members:$('approveMembers').checked,
            public:$('groupAccessType').value === 'public'"""
)

p.write_text(text)
print("Frontend upgraded")
PY

python3 -m py_compile app.py api_routes/*.py services/*.py

echo ""
echo "✅ Phase 18 complete."
echo "Restart Flask and open: http://127.0.0.1:5000/messages/"
