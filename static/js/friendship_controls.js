/**
 * Friendship Controls — Handles friend request UI, Socket.IO events, notification actions.
 */
(function () {
    'use strict';

    const SOCIAL_API = '/social';

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function showToast(message, type) {
        const container = document.getElementById('toast-container') || (function () {
            const c = document.createElement('div');
            c.id = 'toast-container';
            c.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px';
            document.body.appendChild(c);
            return c;
        })();
        const toast = document.createElement('div');
        toast.className = 'friendship-toast';
        toast.style.cssText = 'padding:12px 20px;border-radius:8px;color:#fff;font-size:14px;animation:fadeIn 0.3s;max-width:360px;box-shadow:0 4px 12px rgba(0,0,0,0.15)';
        toast.style.background = type === 'error' ? '#e74c3c' : type === 'success' ? '#2ecc71' : '#3498db';
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    async function apiPost(path, data) {
        try {
            const resp = await fetch(path, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
                body: data ? JSON.stringify(data) : undefined,
            });
            return await resp.json();
        } catch (e) {
            return { ok: false, error: e.message };
        }
    }

    async function apiGet(path) {
        try {
            const resp = await fetch(path, {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' },
            });
            return await resp.json();
        } catch (e) {
            return { ok: false, error: e.message };
        }
    }

    function updateFriendButton(btn, status, requestId) {
        if (!btn) return;
        const icon = btn.querySelector('i') || btn;
        const textSpan = btn.querySelector('.btn-text') || btn;
        btn.dataset.friendStatus = status;

        switch (status) {
            case 'friends':
                btn.innerHTML = '<i class="fas fa-user-check"></i><span class="btn-text">Friends</span>';
                btn.className = btn.className.replace(/btn-\w+/g, '') + ' profile-btn friends-btn';
                btn.disabled = true;
                break;
            case 'pending_sent':
                btn.innerHTML = '<i class="fas fa-clock"></i><span class="btn-text">Request Pending</span>';
                btn.className = btn.className.replace(/btn-\w+/g, '') + ' profile-btn pending-btn';
                btn.disabled = true;
                break;
            case 'pending_received':
                btn.innerHTML = '<i class="fas fa-user-clock"></i><span class="btn-text">Respond to Request</span>';
                btn.className = btn.className.replace(/btn-\w+/g, '') + ' profile-btn respond-btn';
                btn.dataset.requestId = requestId;
                btn.disabled = false;
                btn.onclick = function (e) {
                    e.preventDefault();
                    showFriendRequestModal(requestId);
                };
                break;
            case 'none':
            default:
                btn.innerHTML = '<i class="fas fa-user-plus"></i><span class="btn-text">Add Friend</span>';
                btn.className = btn.className.replace(/btn-\w+/g, '') + ' profile-btn add-friend-btn';
                btn.disabled = false;
                btn.onclick = function (e) {
                    e.preventDefault();
                    sendFriendRequest(btn.dataset.targetId || btn.dataset.profileId, btn);
                };
                break;
        }
    }

    async function sendFriendRequest(targetId, btn) {
        if (!targetId) return;
        const result = await apiPost(`/social/friends/request`, {recipient_id: targetId});
        if (result.success || result.ok) {
            showToast('Friend request sent!', 'success');
            updateFriendButton(btn, 'pending_sent');
        } else {
            showToast(result.error || result.msg || 'Failed to send request', 'error');
        }
    }

    async function acceptFriendRequest(requestId) {
        const result = await apiPost(`/social/friends/accept`, {request_id: requestId});
        if (result.success || result.ok) {
            showToast('Friend request accepted!', 'success');
            return true;
        }
        showToast(result.error || result.msg || 'Failed to accept', 'error');
        return false;
    }

    async function declineFriendRequest(requestId) {
        const result = await apiPost(`/social/friends/decline`, {request_id: requestId});
        if (result.success || result.ok) {
            showToast('Friend request declined', 'info');
            return true;
        }
        return false;
    }

    async function cancelFriendRequest(requestId) {
        const result = await apiPost(`/social/friends/cancel`, {request_id: requestId});
        if (result.success || result.ok) {
            showToast('Friend request cancelled', 'info');
            return true;
        }
        return false;
    }

    function showFriendRequestModal(requestId) {
        const existing = document.getElementById('friend-request-modal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'friend-request-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:10000;display:flex;align-items:center;justify-content:center';

        const card = document.createElement('div');
        card.style.cssText = 'background:#1a1a2e;border-radius:16px;padding:32px;max-width:400px;width:90%;text-align:center;color:#fff';

        card.innerHTML = `
            <h3 style="margin-bottom:12px;font-size:20px">Friend Request</h3>
            <p style="margin-bottom:24px;color:#aaa">This user sent you a friend request.</p>
            <div style="display:flex;gap:12px;justify-content:center">
                <button id="fr-accept-btn" class="profile-btn primary" style="background:#2ecc71;border:none;padding:10px 24px;border-radius:8px;color:#fff;cursor:pointer">
                    <i class="fas fa-check"></i> Accept
                </button>
                <button id="fr-decline-btn" class="profile-btn" style="background:#e74c3c;border:none;padding:10px 24px;border-radius:8px;color:#fff;cursor:pointer">
                    <i class="fas fa-times"></i> Decline
                </button>
            </div>
            <button id="fr-close-modal" style="margin-top:16px;background:none;border:none;color:#888;cursor:pointer;font-size:14px">Close</button>
        `;

        modal.appendChild(card);
        document.body.appendChild(modal);

        document.getElementById('fr-accept-btn').onclick = async function () {
            const ok = await acceptFriendRequest(requestId);
            if (ok) {
                modal.remove();
                showToast('You are now friends! Start chatting, calling, and sending gifts.', 'success');
                const btn = document.querySelector('[data-friend-action]');
                if (btn) updateFriendButton(btn, 'friends');
                document.querySelectorAll('[data-friend-request-item]').forEach(el => {
                    if (el.dataset.requestId === requestId) {
                        el.innerHTML = '<span style="color:#2ecc71"><i class="fas fa-check"></i> Accepted</span>';
                    }
                });
            }
        };

        document.getElementById('fr-decline-btn').onclick = async function () {
            const ok = await declineFriendRequest(requestId);
            if (ok) {
                modal.remove();
                document.querySelectorAll('[data-friend-request-item]').forEach(el => {
                    if (el.dataset.requestId === requestId) {
                        el.innerHTML = '<span style="color:#e74c3c"><i class="fas fa-times"></i> Declined</span>';
                    }
                });
            }
        };

        document.getElementById('fr-close-modal').onclick = function () {
            modal.remove();
        };

        modal.onclick = function (e) {
            if (e.target === modal) modal.remove();
        };
    }

    function initFriendButtons() {
        document.querySelectorAll('[data-friend-action]').forEach(function (btn) {
            const profileId = btn.dataset.targetId || btn.dataset.profileId;
            if (!profileId) return;

            const existingStatus = btn.dataset.friendStatus;
            if (existingStatus && existingStatus !== 'unknown') {
                updateFriendButton(btn, existingStatus, btn.dataset.requestId);
                return;
            }

            apiGet(`/social/api/status/${profileId}`).then(function (data) {
                if (data.ok || data.status) {
                    updateFriendButton(btn, data.status, data.request_id || data.requestId);
                }
            });
        });
    }

    function initNotificationActions() {
        document.querySelectorAll('[data-notification-action]').forEach(function (el) {
            const action = el.dataset.notificationAction;
            const requestId = el.dataset.requestId;
            const notifId = el.dataset.notificationId;

            if (action === 'accept' && requestId) {
                el.onclick = async function (e) {
                    e.preventDefault();
                    const ok = await acceptFriendRequest(requestId);
                    if (ok) {
                        el.innerHTML = '<i class="fas fa-check"></i> Accepted';
                        el.className = 'accepted-btn';
                        el.disabled = true;
                        const msgBtn = document.createElement('a');
                        msgBtn.href = '/messages/';
                        msgBtn.className = 'profile-btn';
                        msgBtn.innerHTML = '<i class="fas fa-comment"></i> Message';
                        el.parentNode.appendChild(msgBtn);
                        showToast('You are now friends!', 'success');
                    }
                };
            } else if (action === 'decline' && requestId) {
                el.onclick = async function (e) {
                    e.preventDefault();
                    const ok = await declineFriendRequest(requestId);
                    if (ok) {
                        el.innerHTML = '<i class="fas fa-times"></i> Declined';
                        el.className = 'declined-btn';
                        el.disabled = true;
                    }
                };
            } else if (action === 'open_profile') {
                el.onclick = function (e) {
                    const url = el.dataset.actionUrl || el.getAttribute('href');
                    if (url) window.location.href = url;
                };
            } else if (action === 'message') {
                el.onclick = function (e) {
                    const url = el.dataset.actionUrl || '/messages/';
                    window.location.href = url;
                };
            }
        });
    }

    function initSocketListeners() {
        const socket = window.chainSocket || (window.io ? window.io() : null);
        if (!socket) return;
        if (!window.friendshipSocketInitialized) {
            window.friendshipSocketInitialized = true;

            socket.on('notification:new', function (payload) {
                if (payload && payload.event_type && payload.event_type.startsWith('friend_request')) {
                    showToast(payload.title + ': ' + (payload.body || ''), 'info');
                }
            });

            socket.on('friend_request:new', function (payload) {
                showToast(payload.sender_name + ' sent you a friend request!', 'info');
                const btn = document.querySelector('[data-friend-action]');
                if (btn && (btn.dataset.targetId === payload.sender_id || btn.dataset.profileId === payload.sender_id)) {
                    updateFriendButton(btn, 'pending_received', payload.request_id);
                }
            });

            socket.on('friend_request:accepted', function (payload) {
                showToast(payload.accepter_name + ' accepted your friend request!', 'success');
                const btn = document.querySelector('[data-friend-action]');
                if (btn && (btn.dataset.targetId === payload.accepter_id || btn.dataset.profileId === payload.accepter_id)) {
                    updateFriendButton(btn, 'friends');
                }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initFriendButtons();
        initNotificationActions();
        initSocketListeners();
    });

    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .friends-btn { background: #2ecc71 !important; color: #fff !important; cursor: default !important; opacity: 0.8; }
        .pending-btn { background: #f39c12 !important; color: #fff !important; cursor: default !important; opacity: 0.8; }
        .respond-btn { background: #3498db !important; color: #fff !important; }
        .add-friend-btn { background: #6c5ce7 !important; color: #fff !important; }
        .accepted-btn { background: #2ecc71; color: #fff; border: none; padding: 6px 12px; border-radius: 6px; cursor: default; }
        .declined-btn { background: #e74c3c; color: #fff; border: none; padding: 6px 12px; border-radius: 6px; cursor: default; }
    `;
    document.head.appendChild(style);
})();
