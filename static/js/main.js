document.addEventListener('DOMContentLoaded', () => {
    const isAuthenticated = document.body?.dataset?.authenticated === 'true';
    const currentPath = window.location.pathname;
    const links = document.querySelectorAll('.sidebar-link, .mobile-link');

    links.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    const skeletons = document.querySelectorAll('.skeleton');
    if (skeletons.length > 0) {
        setTimeout(() => {
            skeletons.forEach(s => s.classList.remove('skeleton'));
        }, 1500);
    }

    const getNotifBadge = () => {
        const notifLink = document.querySelector('.notif-badge');
        if (!notifLink) {
            return null;
        }

        let badge = notifLink.querySelector('.notif-count');
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notif-count';
            badge.style.display = 'none';
            notifLink.appendChild(badge);
        }
        return badge;
    };

    const updateNotifCount = (count) => {
        const badge = getNotifBadge();
        if (!badge) {
            return;
        }

        const nextCount = Number.isFinite(Number(count)) ? Number(count) : 0;
        badge.innerText = nextCount;
        badge.style.display = nextCount > 0 ? 'grid' : 'none';
    };

    const refreshNotifCount = async () => {
        try {
            const response = await fetch('/api/notifications/unread-count', {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' },
                cache: 'no-store'
            });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            updateNotifCount(data.count || 0);
        } catch (error) {
        } finally {
            if (isAuthenticated) {
                setTimeout(refreshNotifCount, 20000);
            }
        }
    };

    if (isAuthenticated) {
        refreshNotifCount();
    } else {
        updateNotifCount(0);
    }
});
