/**
 * Follow Request Controls — handles Follow, Request Follow, Approve, and Decline actions.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ─── Follow / Request Follow ──────────────────────────────────────────
    document.body.addEventListener('click', async (e) => {
        const followBtn = e.target.closest('[data-profile-follow], [data-follow-profile]');
        if (!followBtn) return;

        const profileId = followBtn.dataset.profileId || followBtn.dataset.followProfile;
        if (!profileId) return;

        followBtn.disabled = true;
        const originalText = followBtn.innerHTML;
        followBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            const response = await fetch(`/social/follow/${profileId}`, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }
            });
            
            if (response.redirected) {
                window.location.href = response.url;
                return;
            }

            const data = await response.json();
            if (data.status === 'ok') {
                if (data.follow_status === 'following') {
                    followBtn.innerHTML = '<i class="fas fa-user-check"></i><span>Following</span>';
                    followBtn.classList.add('is-active');
                    followBtn.dataset.following = 'true';
                } else if (data.follow_status === 'request_pending') {
                    followBtn.innerHTML = '<i class="fas fa-clock"></i><span>Requested</span>';
                    followBtn.disabled = true;
                    followBtn.style.opacity = '0.7';
                } else if (data.follow_status === 'none') {
                    followBtn.innerHTML = '<i class="fas fa-user-plus"></i><span>Follow</span>';
                    followBtn.classList.remove('is-active');
                    followBtn.dataset.following = 'false';
                    followBtn.disabled = false;
                }
            } else {
                console.error('Follow action failed:', data.error);
                followBtn.innerHTML = originalText;
                followBtn.disabled = false;
            }
        } catch (err) {
            console.error('Follow request error:', err);
            followBtn.innerHTML = originalText;
            followBtn.disabled = false;
        }
    });

    // ─── Approve / Decline ──────────────────────────────────────────────
    document.body.addEventListener('click', async (e) => {
        const approveBtn = e.target.closest('[data-follow-approve]');
        const declineBtn = e.target.closest('[data-follow-decline]');
        
        if (!approveBtn && !declineBtn) return;

        const btn = approveBtn || declineBtn;
        const requestId = btn.dataset.requestId;
        const isApprove = !!approveBtn;
        const action = isApprove ? 'approve' : 'decline';

        btn.disabled = true;
        const container = btn.closest('.request-actions') || btn.parentElement;

        try {
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            const response = await fetch(`/api/follow/${action}/${requestId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }
            });
            const data = await response.json();

            if (data.ok) {
                if (container) {
                    container.innerHTML = `<span class="status-msg">${isApprove ? 'Approved' : 'Declined'}</span>`;
                } else {
                    btn.textContent = isApprove ? 'Approved' : 'Declined';
                }
                
                // Optional: trigger notification count refresh
                if (window.refreshNotificationBadge) window.refreshNotificationBadge();
            } else {
                alert(data.error || `Failed to ${action} request`);
                btn.disabled = false;
            }
        } catch (err) {
            console.error(`Follow ${action} error:`, err);
            btn.disabled = false;
        }
    });
});
