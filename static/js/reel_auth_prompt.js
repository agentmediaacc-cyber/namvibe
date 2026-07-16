(function () {
  'use strict';

  if (window.NamVibeReelAuthPrompt) return;

  function ensureModal() {
    var modal = document.getElementById('reel-auth-prompt');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'reel-auth-prompt';
    modal.className = 'reel-auth-prompt';
    modal.hidden = true;
    modal.innerHTML = [
      '<div class="reel-auth-prompt__backdrop" data-auth-close></div>',
      '<div class="reel-auth-prompt__card" role="dialog" aria-modal="true" aria-labelledby="reel-auth-title">',
      '  <h2 id="reel-auth-title">Join NamVibe to connect</h2>',
      '  <p>Watch public reels freely. Sign in or create an account to like, comment, save, follow, or message.</p>',
      '  <div class="reel-auth-prompt__actions">',
      '    <a class="px-btn px-btn--gold" data-auth-login href="/auth/login">Log in</a>',
      '    <a class="px-btn px-btn--outline" data-auth-register href="/auth/register">Create account</a>',
      '    <button type="button" class="px-btn px-btn--ghost" data-auth-close>Not now</button>',
      '  </div>',
      '</div>',
    ].join('');
    document.body.appendChild(modal);
    modal.addEventListener('click', function (event) {
      if (event.target.closest('[data-auth-close]')) {
        modal.hidden = true;
      }
    });
    return modal;
  }

  function currentUrl() {
    return window.location.pathname + window.location.search + window.location.hash;
  }

  function show(loginUrl, registerUrl) {
    var modal = ensureModal();
    var login = modal.querySelector('[data-auth-login]');
    var register = modal.querySelector('[data-auth-register]');
    var next = encodeURIComponent(currentUrl());
    if (login) login.href = loginUrl || ('/auth/login?next=' + next);
    if (register) register.href = registerUrl || ('/auth/register?next=' + next);
    modal.hidden = false;
    var focusable = modal.querySelector('a,button');
    if (focusable) focusable.focus();
  }

  function shouldHandleAuthResponse(data) {
    if (!data || typeof data !== 'object') return false;
    var error = String(data.error || data.message || '').toLowerCase();
    return error.indexOf('auth') !== -1 || error === 'authentication_required';
  }

  window.NamVibeReelAuthPrompt = {
    ensure: ensureModal,
    show: show,
    shouldHandleAuthResponse: shouldHandleAuthResponse,
  };
})();
