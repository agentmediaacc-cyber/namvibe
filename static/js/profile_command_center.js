/**
 * NamVibe Profile Command Center JS
 * Handles tab switching, social actions, and owner-only interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    initTabSwitching();
    initCopyProfileUrl();
    initShareProfile();
    initQrFallback();
    initCreateDropdown();
    initCompletionCta();
    initSocialActions();
});

function initTabSwitching() {
    const tabs = document.querySelectorAll('.command-tab');
    const panes = document.querySelectorAll('.tab-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.getAttribute('data-tab-target');
            
            // Update tabs
            tabs.forEach(t => t.classList.remove('is-active'));
            tab.classList.add('is-active');

            // Update panes
            panes.forEach(pane => {
                pane.classList.remove('is-active');
                if (pane.id === `${targetId}-tab`) {
                    pane.classList.add('is-active');
                }
            });
            
            // If reels tab, maybe play video or something
            if (targetId === 'reels') {
                const videos = document.querySelectorAll('#reels-tab video');
                videos.forEach(v => {
                    v.muted = true;
                    // v.play().catch(() => {});
                });
            }
        });
    });
}

function initCopyProfileUrl() {
    const copyBtns = document.querySelectorAll('[data-copy-profile]');
    copyBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const url = btn.getAttribute('data-copy-profile');
            if (url) {
                const fullUrl = window.location.origin + url;
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(fullUrl);
                    } else {
                        const input = document.createElement('input');
                        input.value = fullUrl;
                        document.body.appendChild(input);
                        input.select();
                        document.execCommand('copy');
                        input.remove();
                    }
                    showToast('Profile URL copied!');
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '<i class="fas fa-check"></i> Copied';
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                    }, 2000);
                } catch (err) {
                    showToast(fullUrl);
                }
            }
        });
    });
}

function initShareProfile() {
    document.querySelectorAll('[data-share-profile]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const path = btn.getAttribute('data-profile-url') || window.location.pathname;
            const url = path.startsWith('http') ? path : window.location.origin + path;
            if (navigator.share) {
                try {
                    await navigator.share({ title: document.title || 'NamVibe profile', url });
                    return;
                } catch (err) {
                    if (err && err.name === 'AbortError') return;
                }
            }
            copyText(url);
            showToast('Profile link ready to share');
        });
    });
}

function initQrFallback() {
    document.querySelectorAll('[data-profile-qr]').forEach(btn => {
        btn.addEventListener('click', () => {
            const path = btn.getAttribute('data-profile-url') || window.location.pathname;
            const url = path.startsWith('http') ? path : window.location.origin + path;
            copyText(url);
            showToast('QR fallback: profile link copied');
        });
    });
}

function initCreateDropdown() {
    const trigger = document.querySelector('.hero-actions [data-create-dropdown-trigger]');
    const dropdown = document.getElementById('create-dropdown');

    if (trigger && dropdown) {
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.hidden = !dropdown.hidden;
        });

        document.addEventListener('click', () => {
            dropdown.hidden = true;
        });
    }
}

function initCompletionCta() {
    document.querySelectorAll('.completion-card .btn-card.primary').forEach(link => {
        link.addEventListener('click', () => showToast('Opening profile improvements'));
    });
}

function initSocialActions() {
    // Follow / Unfollow
    const followBtns = document.querySelectorAll('[data-profile-follow], [data-follow-profile]');
    followBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const profileId = btn.getAttribute('data-profile-id') || btn.getAttribute('data-follow-profile');
            const isFollowing = btn.getAttribute('data-following') === 'true';
            
            btn.disabled = true;
            btn.style.opacity = '0.5';

            try {
                const response = await fetch(`/social/follow/${profileId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();

                if (data.status === 'ok' || data.ok) {
                    const status = data.follow_status || (data.following ? 'following' : 'none');
                    
                    if (status === 'following') {
                        btn.innerHTML = '<i class="fas fa-user-check"></i> Following';
                        btn.classList.add('secondary');
                        btn.classList.remove('primary');
                        btn.setAttribute('data-following', 'true');
                    } else if (status === 'request_pending') {
                        btn.innerHTML = '<i class="fas fa-user-clock"></i> Requested';
                        btn.classList.add('secondary');
                        btn.classList.remove('primary');
                        btn.disabled = true;
                    } else {
                        btn.innerHTML = '<i class="fas fa-user-plus"></i> Follow';
                        btn.classList.remove('secondary');
                        btn.classList.add('primary');
                        btn.setAttribute('data-following', 'false');
                    }
                } else {
                    showToast('Action failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error(err);
                showToast('Network error');
            } finally {
                if (btn.textContent.trim() !== 'Requested') btn.disabled = false;
                btn.style.opacity = '1';
            }
        });
    });

    // Friend Request (delegated if needed, but here's direct)
    const friendBtns = document.querySelectorAll('[data-friend-action]');
    friendBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const profileId = btn.getAttribute('data-target-id');
            const status = btn.getAttribute('data-friend-status');

            if (status === 'none') {
                btn.disabled = true;
                try {
                    const response = await fetch('/social/friends/request', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ recipient_id: profileId })
                    });
                    const data = await response.json();
                    if (data.success || data.ok) {
                        btn.innerHTML = '<i class="fas fa-check"></i> Request Sent';
                        btn.setAttribute('data-friend-status', 'pending_sent');
                        btn.style.opacity = '0.7';
                    } else {
                        showToast(data.error || 'Could not send request');
                    }
                } catch (err) {
                    showToast('Failed to send request');
                } finally {
                    btn.disabled = false;
                }
            }
        });
    });
}

function copyText(value) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).catch(() => {});
        return;
    }
    const input = document.createElement('input');
    input.value = value;
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    input.remove();
}

function showToast(message) {
    const existing = document.querySelector('.profile-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'profile-toast';
    toast.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: #fff;
        padding: 10px 20px;
        border-radius: 20px;
        z-index: 9999;
        font-size: 14px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s';
        setTimeout(() => toast.remove(), 500);
    }, 2000);
}
