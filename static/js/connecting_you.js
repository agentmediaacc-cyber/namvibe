/* ── Connecting You — Client-side JS ── */
const CY = {
  csrf: () => document.querySelector('meta[name="csrf-token"]')?.content || '',
  headers() { return { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf() } },

  async api(url, opts = {}) {
    try {
      const r = await fetch(url, { ...opts, headers: { ...this.headers(), ...(opts.headers || {}) } });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error || j.detail || `HTTP ${r.status}`);
      }
      return await r.json();
    } catch (e) {
      this.toast(e.message, 'error');
      throw e;
    }
  },

  toast(msg, type = 'info') {
    if (window.NamVibeToast) {
      if (type === 'error') window.NamVibeToast.show(msg);
      else window.NamVibeToast.success(msg);
    } else {
      const el = document.createElement('div');
      el.className = `cy-alert cy-alert-${type === 'error' ? 'error' : 'success'}`;
      el.textContent = msg;
      el.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;max-width:400px;animation:cySlideIn .3s';
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 4000);
    }
  },

  redirect(url) { setTimeout(() => window.location.href = url, 600); }
};

/* ── ENROLL ── */
const CYEnroll = {
  init() {
    const form = document.getElementById('cy-enroll-form');
    if (!form) return;
    form.addEventListener('submit', e => this.submit(e));

    form.querySelectorAll('[data-min-age]').forEach(sel => {
      sel.addEventListener('change', () => this.updateAgeRange());
    });
    this.updateAgeRange();
  },

  updateAgeRange() {
    const ageEl = document.getElementById('cy-age-range');
    const minSel = document.querySelector('[name="min_age"]');
    const maxSel = document.querySelector('[name="max_age"]');
    if (ageEl && minSel && maxSel) {
      ageEl.textContent = `${minSel.value}–${maxSel.value} years`;
    }
  },

  async submit(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    const data = Object.fromEntries(new FormData(form));
    data.min_age = parseInt(data.min_age);
    data.max_age = parseInt(data.max_age);
    data.lat = parseFloat(data.lat) || null;
    data.lng = parseFloat(data.lng) || null;

    btn.disabled = true;
    btn.textContent = 'Enrolling...';

    try {
      await CY.api('/dating/connecting-you/api/enroll', { method: 'POST', body: JSON.stringify(data) });
      CY.toast('Welcome to Connecting You! Starting your assessment...', 'success');
      CY.redirect('/dating/connecting-you/assessment');
    } catch {
      btn.disabled = false;
      btn.textContent = 'Join Connecting You';
    }
  }
};

/* ── ASSESSMENT ── */
const CYAssessment = {
  answers: {},
  current: 0,
  total: 0,

  init() {
    const grid = document.getElementById('cy-questions');
    if (!grid) return;
    this.total = grid.querySelectorAll('.cy-assess-card').length;
    this.bind();
    this.updateProgress();
  },

  bind() {
    document.querySelectorAll('.cy-assess-opt input').forEach(inp => {
      inp.addEventListener('change', () => {
        const card = inp.closest('.cy-assess-card');
        card.querySelectorAll('.cy-assess-opt').forEach(o => o.classList.remove('cy-assess-opt-active'));
        inp.closest('.cy-assess-opt').classList.add('cy-assess-opt-active');
        this.answers[inp.name] = inp.value;
        this.updateProgress();
      });
    });
  },

  updateProgress() {
    const answered = Object.keys(this.answers).length;
    const pct = this.total ? Math.round((answered / this.total) * 100) : 0;
    const fill = document.getElementById('cy-progress-fill');
    const label = document.getElementById('cy-progress-label');
    if (fill) fill.style.width = pct + '%';
    if (label) label.textContent = `${answered}/${this.total}`;
    const submit = document.getElementById('cy-submit-assess');
    if (submit) submit.disabled = answered < this.total;
  },

  async submit() {
    const btn = document.getElementById('cy-submit-assess');
    btn.disabled = true;
    btn.textContent = 'Analyzing...';

    try {
      await CY.api('/dating/connecting-you/api/assessment/submit', {
        method: 'POST',
        body: JSON.stringify({ answers: this.answers })
      });
      CY.toast('Assessment complete! Finding your best matches...', 'success');
      CY.redirect('/dating/connecting-you/browse');
    } catch {
      btn.disabled = false;
      btn.textContent = 'Submit Assessment';
    }
  }
};

/* ── BROWSE ── */
const CYBrowse = {
  init() {},

  async sendInterest(targetId, btn) {
    btn.disabled = true;
    btn.textContent = 'Sending...';
    try {
      await CY.api('/dating/connecting-you/api/introductions/create', {
        method: 'POST', body: JSON.stringify({ target_profile_id: targetId })
      });
      btn.textContent = 'Interest Sent';
      btn.classList.remove('cy-btn-primary');
      btn.classList.add('cy-btn-pending');
      CY.toast('Interest sent! We\'ll notify you if it\'s mutual.', 'success');
    } catch {
      btn.disabled = false;
      btn.textContent = 'Connect';
    }
  }
};

/* ── MATCHES / INTRODUCTIONS ── */
const CYMatches = {
  async respond(introId, action, btn) {
    btn.disabled = true;
    try {
      await CY.api(`/dating/connecting-you/api/introductions/${introId}/respond`, {
        method: 'POST', body: JSON.stringify({ action })
      });
      CY.toast(action === 'accept' ? 'Matched! 🎉' : 'Introduction declined', 'success');
      const card = btn.closest('.cy-intro-card');
      if (card && action === 'decline') card.style.opacity = '0.3';
      if (action === 'accept') setTimeout(() => window.location.reload(), 800);
    } catch {
      btn.disabled = false;
    }
  }
};

/* ── EVENTS ── */
const CYEvents = {
  async register(eventId, btn) {
    btn.disabled = true;
    btn.textContent = 'Registering...';
    try {
      const res = await CY.api(`/dating/connecting-you/api/events/${eventId}/register`, { method: 'POST' });
      btn.textContent = 'Registered';
      btn.classList.remove('cy-btn-primary');
      btn.classList.add('cy-btn-pending');
      CY.toast('Registered! We\'ll send you a reminder.', 'success');
    } catch {
      btn.disabled = false;
      btn.textContent = 'Register Now';
    }
  },

  async popBalloon(eventId, btn) {
    btn.disabled = true;
    btn.textContent = 'Popping...';
    try {
      const res = await CY.api(`/dating/connecting-you/api/events/${eventId}/pop-balloon`, { method: 'POST' });
      CY.toast(`You popped a balloon! 💕 ${res.message || ''}`, 'success');
      setTimeout(() => window.location.reload(), 1500);
    } catch {
      btn.disabled = false;
      btn.textContent = 'Pop a Balloon';
    }
  }
};

/* ── ADMIN ── */
const CYAdmin = {
  async approve(profileId, btn) {
    btn.disabled = true;
    try {
      await CY.api(`/dating/admin/api/enrollments/${profileId}/approve`, { method: 'POST' });
      const row = btn.closest('tr');
      if (row) {
        const status = row.querySelector('.cy-admin-status');
        if (status) { status.textContent = 'approved'; status.style.color = '#22c55e'; }
        btn.remove();
      }
      CY.toast('User approved', 'success');
    } catch { btn.disabled = false; }
  },

  async suspend(profileId, btn) {
    btn.disabled = true;
    try {
      await CY.api(`/dating/admin/api/enrollments/${profileId}/suspend`, { method: 'POST' });
      const row = btn.closest('tr');
      if (row) row.style.opacity = '0.3';
      CY.toast('User suspended', 'success');
    } catch { btn.disabled = false; }
  },

  initCreateEvent() {
    const form = document.getElementById('cy-create-event-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      data.capacity = parseInt(data.capacity) || 20;
      if (data.starts_at) data.starts_at = new Date(data.starts_at).toISOString();
      try {
        await CY.api('/dating/admin/api/events/create', { method: 'POST', body: JSON.stringify(data) });
        CY.toast('Event created!', 'success');
        form.reset();
        setTimeout(() => window.location.reload(), 600);
      } catch {}
    });
  },

  initCreateIntro() {
    const form = document.getElementById('cy-create-intro-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      try {
        await CY.api('/dating/admin/api/introductions/create', { method: 'POST', body: JSON.stringify(data) });
        CY.toast('Introduction created!', 'success');
        form.reset();
        setTimeout(() => window.location.reload(), 600);
      } catch {}
    });
  }
};

/* ── LOCATION ── */
function cyGetLocation() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(pos => {
    const latEl = document.querySelector('[name="lat"]');
    const lngEl = document.querySelector('[name="lng"]');
    if (latEl) latEl.value = pos.coords.latitude.toFixed(6);
    if (lngEl) lngEl.value = pos.coords.longitude.toFixed(6);
  }, () => {});
}

/* ── INIT ── */
document.addEventListener('DOMContentLoaded', () => {
  CYEnroll.init();
  CYAssessment.init();
  CYBrowse.init();
  CYEvents.init();
  CYAdmin.initCreateEvent();
  CYAdmin.initCreateIntro();
  if (document.getElementById('cy-enroll-form')) cyGetLocation();
});
