/* ============================================================
   NamVibe Message Retry & Delivery
   ============================================================ */

let CHAIN_MESSAGE_RETRY = {
    pendingMessages: [],
    maxRetries: 5,
    retryDelay: 3000,
    online: navigator.onLine,
};

function mrInit() {
    loadPendingMessages();
    bindOnlineOffline();
}

function loadPendingMessages() {
    try {
        const stored = localStorage.getItem('chain_pending_messages');
        if (stored) {
            CHAIN_MESSAGE_RETRY.pendingMessages = JSON.parse(stored);
        }
    } catch (e) {
        CHAIN_MESSAGE_RETRY.pendingMessages = [];
    }
}

function savePendingMessages() {
    try {
        localStorage.setItem('chain_pending_messages', JSON.stringify(CHAIN_MESSAGE_RETRY.pendingMessages));
    } catch (e) {}
}

function addPendingMessage(msg) {
    msg.retryCount = msg.retryCount || 0;
    msg.status = 'pending';
    CHAIN_MESSAGE_RETRY.pendingMessages.push(msg);
    savePendingMessages();
    showSendingSpinner(msg.clientMessageId);
}

function removePendingMessage(clientMessageId) {
    CHAIN_MESSAGE_RETRY.pendingMessages = CHAIN_MESSAGE_RETRY.pendingMessages.filter(function(m) {
        return m.clientMessageId !== clientMessageId;
    });
    savePendingMessages();
    hideSendingSpinner(clientMessageId);
}

function retryPendingMessage(clientMessageId) {
    var msg = CHAIN_MESSAGE_RETRY.pendingMessages.find(function(m) {
        return m.clientMessageId === clientMessageId;
    });
    if (!msg || msg.retryCount >= CHAIN_MESSAGE_RETRY.maxRetries) return;
    msg.retryCount++;
    msg.status = 'retrying';
    savePendingMessages();
    showSendingSpinner(clientMessageId);
    fetch('/messages/api/retry/' + msg.messageId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            removePendingMessage(clientMessageId);
            showDeliveredCheck(clientMessageId);
        } else {
            if (msg.retryCount < CHAIN_MESSAGE_RETRY.maxRetries) {
                setTimeout(function() { retryPendingMessage(clientMessageId); }, CHAIN_MESSAGE_RETRY.retryDelay * msg.retryCount);
            } else {
                showFailedRetryButton(clientMessageId, msg);
            }
        }
    })
    .catch(function() {
        if (msg.retryCount < CHAIN_MESSAGE_RETRY.maxRetries) {
            setTimeout(function() { retryPendingMessage(clientMessageId); }, CHAIN_MESSAGE_RETRY.retryDelay * msg.retryCount);
        } else {
            showFailedRetryButton(clientMessageId, msg);
        }
    });
}

function retryAllPending() {
    CHAIN_MESSAGE_RETRY.pendingMessages.forEach(function(msg) {
        if (msg.status === 'failed' && msg.retryCount < CHAIN_MESSAGE_RETRY.maxRetries) {
            retryPendingMessage(msg.clientMessageId);
        }
    });
}

/* ---- UI Helpers ---- */

function showSendingSpinner(clientMessageId) {
    var el = document.querySelector('[data-msg-id="' + clientMessageId + '"] .msg-status');
    if (el) {
        el.innerHTML = '<i class="fas fa-spinner fa-spin" style="color:#9ca3af;font-size:12px;" title="Sending..."></i>';
    }
}

function hideSendingSpinner(clientMessageId) {
    var el = document.querySelector('[data-msg-id="' + clientMessageId + '"] .msg-status');
    if (el) el.innerHTML = '';
}

function showDeliveredCheck(clientMessageId) {
    var el = document.querySelector('[data-msg-id="' + clientMessageId + '"] .msg-status');
    if (el) {
        el.innerHTML = '<i class="fas fa-check" style="color:#22c55e;font-size:12px;" title="Delivered"></i>';
    }
    setTimeout(function() {
        var el2 = document.querySelector('[data-msg-id="' + clientMessageId + '"] .msg-status');
        if (el2) el2.innerHTML = '<i class="fas fa-check-double" style="color:#22c55e;font-size:12px;" title="Seen"></i>';
    }, 3000);
}

function showFailedRetryButton(clientMessageId, msg) {
    var el = document.querySelector('[data-msg-id="' + clientMessageId + '"] .msg-status');
    if (el) {
        var btn = document.createElement('button');
        btn.className = 'retry-btn';
        btn.setAttribute('data-retry-id', clientMessageId);
        btn.style.cssText = 'background:none;border:none;color:#ef4444;cursor:pointer;font-size:12px;padding:0;';
        btn.title = 'Retry';
        btn.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
        btn.onclick = function() { retryPendingMessage(this.getAttribute('data-retry-id')); };
        el.appendChild(btn);
    }
    msg.status = 'failed';
    savePendingMessages();
}

/* ---- Offline/Online ---- */

function bindOnlineOffline() {
    window.addEventListener('online', function() {
        CHAIN_MESSAGE_RETRY.online = true;
        hideOfflineBanner();
        retryAllPending();
    });
    window.addEventListener('offline', function() {
        CHAIN_MESSAGE_RETRY.online = false;
        showOfflineBanner();
    });
}

function showOfflineBanner() {
    var banner = document.getElementById('offline-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'offline-banner';
        banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#ef4444;color:#fff;text-align:center;padding:8px 16px;font-size:13px;z-index:10000;font-weight:500;';
        banner.textContent = 'You are offline. Messages will be sent when reconnected.';
        document.body.insertBefore(banner, document.body.firstChild);
    }
    banner.style.display = 'block';
}

function hideOfflineBanner() {
    var banner = document.getElementById('offline-banner');
    if (banner) banner.style.display = 'none';
}

/* ---- Debounced Typing ---- */
var _typingDebounceTimers = {};

function debouncedTypingStart(threadId) {
    if (_typingDebounceTimers[threadId]) {
        clearTimeout(_typingDebounceTimers[threadId]);
    }
    _typingDebounceTimers[threadId] = setTimeout(function() {
        var socket = window.CHAIN_WEBRTC && CHAIN_WEBRTC.socket;
        if (socket) {
            socket.emit('typing:start', { thread_id: threadId });
        }
    }, 300);
}

function debouncedTypingStop(threadId) {
    if (_typingDebounceTimers[threadId]) {
        clearTimeout(_typingDebounceTimers[threadId]);
        delete _typingDebounceTimers[threadId];
    }
    setTimeout(function() {
        var socket = window.CHAIN_WEBRTC && CHAIN_WEBRTC.socket;
        if (socket) {
            socket.emit('typing:stop', { thread_id: threadId });
        }
    }, 1000);
}

/* ---- Batch Seen Receipts ---- */
var _seenBatchQueue = {};
var _seenBatchTimer = null;

function batchMarkSeen(threadId, messageId) {
    _seenBatchQueue[threadId] = messageId;
    if (_seenBatchTimer) clearTimeout(_seenBatchTimer);
    _seenBatchTimer = setTimeout(function() {
        var keys = Object.keys(_seenBatchQueue);
        keys.forEach(function(tid) {
            var socket = window.CHAIN_WEBRTC && CHAIN_WEBRTC.socket;
            if (socket) {
                socket.emit('message:seen', { thread_id: tid });
            }
        });
        _seenBatchQueue = {};
    }, 500);
}

/* ---- Init ---- */
document.addEventListener('DOMContentLoaded', mrInit);

/* Expose globals */
window.mrInit = mrInit;
window.addPendingMessage = addPendingMessage;
window.removePendingMessage = removePendingMessage;
window.retryPendingMessage = retryPendingMessage;
window.retryAllPending = retryAllPending;
window.showSendingSpinner = showSendingSpinner;
window.showDeliveredCheck = showDeliveredCheck;
window.showFailedRetryButton = showFailedRetryButton;
window.debouncedTypingStart = debouncedTypingStart;
window.debouncedTypingStop = debouncedTypingStop;
window.batchMarkSeen = batchMarkSeen;
