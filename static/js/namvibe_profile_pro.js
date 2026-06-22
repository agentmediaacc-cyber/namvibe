(function () {
  'use strict';

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function activateTab(root, key) {
    qsa('[data-tab-target]', root).forEach(function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-tab-target') === key);
    });
    qsa('[data-tab-panel]', root).forEach(function (panel) {
      panel.classList.toggle('is-active', panel.getAttribute('data-tab-panel') === key);
    });
  }

  function initTabs(root) {
    qsa('[data-tab-target]', root).forEach(function (btn) {
      btn.addEventListener('click', function () {
        activateTab(root, btn.getAttribute('data-tab-target'));
      });
    });
  }

  function initUploads(root) {
    qsa('[data-file-trigger]', root).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var input = document.getElementById(btn.getAttribute('data-file-trigger'));
        if (input) input.click();
      });
    });
    qsa('input[type="file"][data-auto-submit]', root).forEach(function (input) {
      input.addEventListener('change', function () {
        if (input.files && input.files.length && input.form) input.form.submit();
      });
    });
  }

  function initProfile(root) {
    initTabs(root);
    initUploads(root);
  }

  document.addEventListener('DOMContentLoaded', function () {
    qsa('[data-namvibe-profile-pro]').forEach(initProfile);
  });
})();
