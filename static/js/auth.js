// NamVibe Authentication JS
console.log("NamVibe Auth System Initialized");

document.addEventListener('DOMContentLoaded', () => {
    // Handle form loading states
    const authForm = document.querySelector('.auth-form');
    if (authForm) {
        authForm.addEventListener('submit', () => {
            const btn = authForm.querySelector('button[type="submit"]');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                btn.style.opacity = '0.7';
                btn.style.pointerEvents = 'none';
            }
        });
    }
});
