document.addEventListener('DOMContentLoaded', () => {
    const isAuthenticated = document.body?.dataset?.authenticated === 'true';
    const currentPath = window.location.pathname;
    const links = document.querySelectorAll('.sidebar-link, .mobile-link');
    const isDevelopment = ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname);
    const NOTIFICATION_POLL_INTERVAL_MS = 60000;
    let notificationPollTimer = null;
    let notificationRequestActive = false;
    let lastNotificationRequestAt = 0;

    const applyTheme = (mode) => {
        const selected = ['light', 'dark', 'system'].includes(mode) ? mode : 'system';
        document.documentElement.dataset.chainTheme = selected;
        localStorage.setItem('chain-theme-mode', selected);
        document.querySelectorAll('[data-theme-option]').forEach((btn) => {
            btn.classList.toggle('is-active', btn.dataset.themeOption === selected);
        });
    };

    applyTheme(localStorage.getItem('chain-theme-mode') || 'system');

    document.querySelector('[data-theme-toggle]')?.addEventListener('click', (event) => {
        event.stopPropagation();
        const menu = document.querySelector('[data-theme-menu]');
        if (menu) menu.hidden = !menu.hidden;
    });

    document.querySelectorAll('[data-theme-option]').forEach((btn) => {
        btn.addEventListener('click', () => {
            applyTheme(btn.dataset.themeOption);
            const menu = document.querySelector('[data-theme-menu]');
            if (menu) menu.hidden = true;
        });
    });

    document.addEventListener('click', (event) => {
        const switcher = document.querySelector('[data-theme-switcher]');
        const menu = document.querySelector('[data-theme-menu]');
        if (switcher && menu && !switcher.contains(event.target)) menu.hidden = true;
    });

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

    const logNotificationPolling = (message, detail = {}) => {
        if (isDevelopment) {
            console.debug(`[NamVibe] notification polling ${message}`, detail);
        }
    };

    const notificationDropdownIsClosed = () => {
        const dropdown = document.querySelector('[data-notification-dropdown], .notification-dropdown, #notification-dropdown');
        if (!dropdown) {
            return false;
        }
        const trigger = document.querySelector('[data-notification-toggle], .notif-badge[aria-expanded]');
        const ariaExpanded = trigger?.getAttribute('aria-expanded');
        return dropdown.hidden || dropdown.classList.contains('hidden') || ariaExpanded === 'false';
    };

    const shouldPollNotifications = () => {
        if (!isAuthenticated) {
            return { ok: false, reason: 'user is not logged in' };
        }
        if (document.hidden) {
            return { ok: false, reason: 'page tab is hidden' };
        }
        if (notificationDropdownIsClosed()) {
            return { ok: false, reason: 'notification dropdown is closed' };
        }
        if (notificationRequestActive) {
            return { ok: false, reason: 'request already active' };
        }
        if (Date.now() - lastNotificationRequestAt < NOTIFICATION_POLL_INTERVAL_MS - 1000) {
            return { ok: false, reason: 'duplicate request skipped' };
        }
        return { ok: true };
    };

    const refreshNotifCount = async (source = 'poll') => {
        const allowed = shouldPollNotifications();
        if (!allowed.ok) {
            logNotificationPolling('skipped', { reason: allowed.reason, source });
            return;
        }

        notificationRequestActive = true;
        lastNotificationRequestAt = Date.now();
        logNotificationPolling('started', { source });
        try {
            const response = await fetch('/api/notifications/unread-count', {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' },
                cache: 'no-store'
            });
            if (!response.ok) {
                logNotificationPolling('skipped', { reason: `http ${response.status}`, source });
                return;
            }
            const data = await response.json();
            updateNotifCount(data.count || 0);
            logNotificationPolling('completed', { count: data.count || 0, source });
        } catch (error) {
            logNotificationPolling('skipped', { reason: error?.message || 'request failed', source });
        } finally {
            notificationRequestActive = false;
        }
    };

    const startNotificationPolling = () => {
        if (!isAuthenticated || notificationPollTimer) {
            return;
        }
        logNotificationPolling('started', { intervalMs: NOTIFICATION_POLL_INTERVAL_MS });
        notificationPollTimer = window.setInterval(() => {
            refreshNotifCount('interval');
        }, NOTIFICATION_POLL_INTERVAL_MS);
    };

    const wireNotificationPush = () => {
        if (!isAuthenticated || typeof window.io !== 'function') {
            return false;
        }
        try {
            const socket = window.chainSocket || window.io();
            window.chainSocket = socket;
            socket.on('notification:new', (payload) => {
                if (typeof payload?.count !== 'undefined') {
                    updateNotifCount(payload.count);
                } else {
                    refreshNotifCount('socket');
                }
            });
            socket.on('notifications:unread-count', (payload) => {
                updateNotifCount(payload?.count || 0);
            });
            return true;
        } catch (error) {
            logNotificationPolling('skipped', { reason: error?.message || 'socket unavailable', source: 'socket' });
            return false;
        }
    };

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            refreshNotifCount('visible');
        } else {
            logNotificationPolling('skipped', { reason: 'page tab is hidden', source: 'visibilitychange' });
        }
    });

    if (isAuthenticated) {
        wireNotificationPush();
        startNotificationPolling();
    } else {
        updateNotifCount(0);
    }

    // Push Notification Registration
    if (isAuthenticated && 'serviceWorker' in navigator && 'PushManager' in window) {
        const pushScript = document.createElement('script');
        pushScript.src = '/static/js/push_notifications.js';
        pushScript.async = true;
        document.body.appendChild(pushScript);
    }

    // Online/Offline Check
    const errorBanner = document.getElementById('error-retry-banner');
    window.addEventListener('online', () => {
        if (errorBanner) errorBanner.style.display = 'none';
    });
    window.addEventListener('offline', () => {
        if (errorBanner) errorBanner.style.display = 'block';
    });
});
