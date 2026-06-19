/* Phase 84: smart suggestions rail and dismissible recommendation cards. */
(function () {
  'use strict';

  var storageKey = 'namvibe:dismissed-smart-cards';

  function dismissed() {
    try { return JSON.parse(localStorage.getItem(storageKey) || '[]'); } catch (e) { return []; }
  }

  function saveDismissed(list) {
    try { localStorage.setItem(storageKey, JSON.stringify(list)); } catch (e) {}
  }

  function hideDismissed() {
    var ids = dismissed();
    document.querySelectorAll('[data-card-id]').forEach(function (card) {
      if (ids.indexOf(card.dataset.cardId) !== -1) card.remove();
    });
  }

  function dismissCard(id) {
    var ids = dismissed();
    if (ids.indexOf(id) === -1) ids.push(id);
    saveDismissed(ids);
    var card = document.querySelector('[data-card-id="' + CSS.escape(id) + '"]');
    if (card) card.remove();
  }

  function renderCard(card) {
    if (!card || dismissed().indexOf(card.id) !== -1) return '';
    var people = (card.items || []).map(function (item) {
      return '<a class="smart-popout-person" href="/profile/@' + encodeURIComponent(item.username || '') + '">' +
        '<span>' + (item.display_name || item.username || '?').charAt(0).toUpperCase() + '</span>' +
        '<strong>' + (item.display_name || item.username || 'NamVibe member') + '</strong>' +
        '<small>' + (item.reason || 'Suggested for you') + '</small></a>';
    }).join('');
    return '<article class="smart-popout-card" data-card-id="' + card.id + '">' +
      '<button type="button" class="smart-popout-dismiss" data-dismiss-card="' + card.id + '" aria-label="Dismiss">×</button>' +
      '<span class="smart-popout-kicker">' + (card.type || 'suggestion') + '</span>' +
      '<h3>' + (card.title || 'Recommended') + '</h3><p>' + (card.subtitle || '') + '</p>' +
      (people ? '<div class="smart-popout-items">' + people + '</div>' : '<a class="smart-popout-action" href="' + (card.action_url || '/discover/') + '">Open</a>') +
      '</article>';
  }

  function fetchSuggestions() {
    var outlet = document.querySelector('[data-smart-popouts]');
    if (!outlet) return;
    fetch('/api/suggestions/smart?limit=6', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.ok || !data.cards) return;
        if (!outlet.children.length) outlet.innerHTML = data.cards.map(renderCard).join('');
        hideDismissed();
      })
      .catch(function () {});
  }

  document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-dismiss-card]');
    if (!btn) return;
    event.preventDefault();
    dismissCard(btn.getAttribute('data-dismiss-card'));
  });
  document.addEventListener('DOMContentLoaded', function () {
    hideDismissed();
    fetchSuggestions();
  });
})();
