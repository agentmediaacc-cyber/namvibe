#!/usr/bin/env bash
set -e

echo "=== PHASE 19: CLEAN MESSAGE COMPOSER + HOLD VOICE PREVIEW ==="

mkdir -p backups/phase19
cp templates/messages/index.html backups/phase19/messages_index.bak 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path

p = Path("templates/messages/index.html")
text = p.read_text()

extra_css = r'''
/* PHASE 19 CLEAN COMPOSER */
.composer{
    align-items:center;
    background:rgba(5,5,5,.92);
    backdrop-filter:blur(18px);
}
.composer select#keyboardLang{
    display:none!important;
}
.composer input#messageInput{
    min-height:48px;
    font-size:15px;
    padding-left:16px;
}
.composer .premium-btn{
    min-width:46px;
    height:46px;
    padding:0;
    display:grid;
    place-items:center;
}
.composer-tools{
    position:relative;
    display:flex;
    gap:8px;
}
.keyboard-menu{
    position:fixed;
    right:18px;
    bottom:86px;
    width:min(320px,92vw);
    background:#0a0a0a;
    border:1px solid rgba(255,255,255,.14);
    border-radius:24px;
    padding:12px;
    display:none;
    z-index:2600;
}
.keyboard-menu.active{
    display:block;
}
.keyboard-menu h4{
    margin:4px 4px 10px;
}
.keyboard-options{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:8px;
}
.keyboard-options button{
    border:0;
    border-radius:14px;
    padding:11px;
    background:rgba(255,255,255,.08);
    color:white;
    font-weight:900;
    cursor:pointer;
}
.keyboard-options button.active{
    background:linear-gradient(135deg,#00f2ea,#ff0050);
    color:#050505;
}
.voice-preview{
    display:none;
    align-items:center;
    gap:10px;
    margin:0 14px 10px;
    padding:12px;
    background:rgba(255,255,255,.08);
    border:1px solid rgba(255,255,255,.12);
    border-radius:22px;
}
.voice-preview.active{
    display:flex;
}
.voice-wave{
    flex:1;
    height:34px;
    display:flex;
    align-items:center;
    gap:4px;
}
.voice-wave span{
    width:4px;
    border-radius:99px;
    background:#00f2ea;
    animation:wave 1s infinite ease-in-out;
}
.voice-wave span:nth-child(2n){height:22px}
.voice-wave span:nth-child(3n){height:30px}
.voice-wave span:nth-child(4n){height:15px}
@keyframes wave{
    0%,100%{opacity:.45;transform:scaleY(.7)}
    50%{opacity:1;transform:scaleY(1.2)}
}
.voice-preview button{
    border:0;
    width:42px;
    height:42px;
    border-radius:50%;
    color:white;
    cursor:pointer;
}
.voice-delete{
    background:#ef4444;
}
.voice-send{
    background:linear-gradient(135deg,#00f2ea,#ff0050);
    color:#050505!important;
}
.voice-time{
    min-width:42px;
    font-weight:950;
}
#voiceBtn.recording{
    background:#ff0050!important;
    animation:pulse 1s infinite;
}
.emoji-panel{
    position:fixed;
    bottom:86px;
    right:18px;
    width:min(360px,92vw);
    background:#0a0a0a;
    border:1px solid rgba(255,255,255,.14);
    border-radius:24px;
    padding:12px;
    display:none;
    z-index:2600;
}
.emoji-panel.active{
    display:grid;
    grid-template-columns:repeat(8,1fr);
    gap:7px;
}
.emoji-panel button{
    border:0;
    background:rgba(255,255,255,.08);
    border-radius:12px;
    padding:9px;
    cursor:pointer;
    font-size:20px;
}
@media(max-width:850px){
    .composer{
        gap:6px;
        padding:10px;
    }
    .composer input#messageInput{
        min-width:0;
    }
}
'''
text = text.replace("</style>", extra_css + "\n</style>")

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
        </div>'''

new = r'''<div class="voice-preview" id="voicePreview">
            <button class="voice-delete" id="deleteVoicePreview" type="button"><i class="fas fa-trash"></i></button>
            <div class="voice-time" id="voicePreviewTime">0s</div>
            <div class="voice-wave">
                <span style="height:18px"></span><span></span><span></span><span></span><span></span>
                <span></span><span></span><span></span><span></span><span></span>
            </div>
            <button class="voice-send" id="sendVoicePreview" type="button"><i class="fas fa-paper-plane"></i></button>
        </div>

        <div class="composer">
            <button class="premium-btn" id="attachBtn" type="button"><i class="fas fa-paperclip"></i></button>

            <input id="messageInput" placeholder="Message">

            <div class="composer-tools">
                <button class="premium-btn" id="emojiBtn" type="button">😊</button>
                <button class="premium-btn" id="keyboardBtn" type="button"><i class="fas fa-keyboard"></i></button>
                <button class="premium-btn" id="voiceBtn" type="button"><i class="fas fa-microphone"></i></button>
                <button class="premium-btn primary" id="sendBtn" type="button"><i class="fas fa-paper-plane"></i></button>
            </div>

            <select id="keyboardLang">
                <option value="en">English</option>
                <option value="af">Afrikaans</option>
                <option value="de">German</option>
                <option value="pt">Portuguese</option>
                <option value="oshiwambo">Oshiwambo</option>
                <option value="kavango">Kavango</option>
                <option value="herero">Otjiherero</option>
                <option value="nama">Nama/Damara</option>
            </select>

            <input type="file" id="hiddenFile" hidden>
        </div>

        <div class="keyboard-menu" id="keyboardMenu">
            <h4>Typing language</h4>
            <div class="keyboard-options">
                <button data-lang="en" class="active">English</button>
                <button data-lang="af">Afrikaans</button>
                <button data-lang="oshiwambo">Oshiwambo</button>
                <button data-lang="kavango">Kavango</button>
                <button data-lang="herero">Otjiherero</button>
                <button data-lang="nama">Nama/Damara</button>
                <button data-lang="pt">Portuguese</button>
                <button data-lang="de">German</button>
            </div>
        </div>

        <div class="emoji-panel" id="emojiPanel">
            <button>😀</button><button>😂</button><button>😍</button><button>🥰</button>
            <button>🙏</button><button>🔥</button><button>❤️</button><button>👍</button>
            <button>🎉</button><button>📢</button><button>💰</button><button>📞</button>
            <button>🎥</button><button>😎</button><button>😭</button><button>👏</button>
            <button>💯</button><button>⭐</button><button>🚀</button><button>✅</button>
            <button>🇳🇦</button><button>🫶</button><button>😅</button><button>🤝</button>
        </div>'''

if old not in text:
    print("Old composer not found, applying fallback replacements")
else:
    text = text.replace(old, new)

# remove old random emoji handler
text = text.replace(
"""    $('emojiBtn')?.addEventListener('click',()=>{
        const emojis = ['😀','😂','😍','🙏','🔥','❤️','👍','🎉','📢','💰','📞','🎥'];
        $('messageInput').value += emojis[Math.floor(Math.random()*emojis.length)];
        $('messageInput').focus();
    });""",
"""    $('emojiBtn')?.addEventListener('click',()=>{
        $('emojiPanel')?.classList.toggle('active');
        $('keyboardMenu')?.classList.remove('active');
    });

    document.querySelectorAll('#emojiPanel button').forEach(btn=>{
        btn.addEventListener('click',()=>{
            $('messageInput').value += btn.textContent;
            $('messageInput').focus();
            showTyping();
        });
    });

    $('keyboardBtn')?.addEventListener('click',()=>{
        $('keyboardMenu')?.classList.toggle('active');
        $('emojiPanel')?.classList.remove('active');
    });

    document.querySelectorAll('.keyboard-options button').forEach(btn=>{
        btn.addEventListener('click',()=>{
            document.querySelectorAll('.keyboard-options button').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
            $('keyboardLang').value = btn.dataset.lang;
            $('messageInput').placeholder = 'Message • ' + btn.textContent;
            $('keyboardMenu')?.classList.remove('active');
            $('messageInput').focus();
        });
    });"""
)

# replace old click voice logic with hold-to-record preview
old_voice = r'''    $('voiceBtn')?.addEventListener('click', async ()=>{
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
    });'''

new_voice = r'''    function startVoiceHold(){
        if(!currentThreadId){
            alert('Open a chat first.');
            return;
        }
        if(isRecording) return;
        isRecording = true;
        recordSeconds = 0;
        $('voiceBtn')?.classList.add('recording');
        $('voiceBtn').innerHTML = '<i class="fas fa-stop"></i>';
        $('voicePreview')?.classList.remove('active');
        recordTimer = setInterval(()=>{
            recordSeconds++;
            if($('voicePreviewTime')) $('voicePreviewTime').textContent = recordSeconds + 's';
        }, 1000);
    }

    function stopVoiceHold(){
        if(!isRecording) return;
        isRecording = false;
        clearInterval(recordTimer);
        $('voiceBtn')?.classList.remove('recording');
        $('voiceBtn').innerHTML = '<i class="fas fa-microphone"></i>';

        if(recordSeconds < 1) recordSeconds = 1;
        $('voicePreviewTime').textContent = recordSeconds + 's';
        $('voicePreview')?.classList.add('active');
    }

    const voiceBtn = $('voiceBtn');
    voiceBtn?.addEventListener('mousedown', startVoiceHold);
    voiceBtn?.addEventListener('mouseup', stopVoiceHold);
    voiceBtn?.addEventListener('mouseleave', stopVoiceHold);
    voiceBtn?.addEventListener('touchstart', e=>{e.preventDefault();startVoiceHold();});
    voiceBtn?.addEventListener('touchend', e=>{e.preventDefault();stopVoiceHold();});

    $('deleteVoicePreview')?.addEventListener('click',()=>{
        recordSeconds = 0;
        $('voicePreview')?.classList.remove('active');
    });

    $('sendVoicePreview')?.addEventListener('click', async ()=>{
        if(!currentThreadId || recordSeconds < 1) return;
        const form = new FormData();
        form.append('seconds', String(recordSeconds));
        await fetch('/messages/thread/' + encodeURIComponent(currentThreadId) + '/voice-note', {
            method:'POST',
            body:form
        });
        $('voicePreview')?.classList.remove('active');
        recordSeconds = 0;
        openThread(currentThreadId,currentThreadName,currentThreadType);
    });'''

if old_voice in text:
    text = text.replace(old_voice, new_voice)
else:
    print("Old voice block not found")

# remove duplicated group empty card when switching groups
text = text.replace(
"""            if(visibleGroups.length === 0){
                $('threadList').insertAdjacentHTML('afterbegin', `""",
"""            if(visibleGroups.length === 0 && !document.getElementById('groupEmptyCard')){
                $('threadList').insertAdjacentHTML('afterbegin', `"""
)

p.write_text(text)
print("Composer cleaned and voice preview patched")
PY

python3 -m py_compile app.py api_routes/*.py services/*.py

echo ""
echo "✅ Phase 19 complete."
echo "Restart Flask and open: http://127.0.0.1:5000/messages/"
