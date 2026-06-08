(function() {
  'use strict';

  var expected = {
    '--chain-bg': '#050505',
    '--chain-bg-soft': '#0b0b0f',
    '--chain-card': '#111118',
    '--chain-card-2': '#1a1a24',
    '--chain-text': '#ffffff',
    '--chain-muted': '#a1a1aa',
    '--chain-cyan': '#00f2ea',
    '--chain-pink': '#ff0050',
    '--chain-purple': '#833ab4',
    '--chain-orange': '#fd1d1d',
    '--chain-gold': '#fcb045'
  };

  var issues = [];

  function check() {
    var root = document.documentElement;
    var style = getComputedStyle(root);
    issues = [];

    Object.keys(expected).forEach(function(v) {
      var val = style.getPropertyValue(v).trim();
      if (!val) {
        issues.push({ variable: v, status: 'missing', expected: expected[v], actual: val });
      } else if (val.toLowerCase() !== expected[v].toLowerCase()) {
        issues.push({ variable: v, status: 'mismatch', expected: expected[v], actual: val });
      }
    });

    var bodyBg = style.getPropertyValue('--chain-bg').trim() || '#050505';
    var actualBg = window.getComputedStyle(document.body).backgroundColor;
    var rgbMatch = actualBg.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
    if (rgbMatch) {
      var hex = '#' + [1,2,3].map(function(i) {
        return ('0' + parseInt(rgbMatch[i]).toString(16)).slice(-2);
      }).join('');
      if (hex !== bodyBg && hex !== '#050505') {
        issues.push({ variable: 'body background', status: 'mismatch', expected: bodyBg, actual: hex });
      }
    }

    var cards = document.querySelectorAll('.chain-card, .chain-home__story-card, .chain-home__live-card, .chain-home__post-card, .chain-home__match-card, .chain-home__quick-card, .message-panel, .px-card, .discover-card');
    var lowContrastCount = 0;
    cards.forEach(function(card) {
      var cardBg = window.getComputedStyle(card).backgroundColor;
      if (cardBg === 'rgba(0, 0, 0, 0)' || cardBg === 'transparent') return;
      if (cardBg.indexOf('255,255,255') !== -1 && bodyBg === '#050505') {
        lowContrastCount++;
      }
    });

    return {
      variables: issues,
      checked: Object.keys(expected).length,
      missing: issues.filter(function(i) { return i.status === 'missing'; }).length,
      mismatched: issues.filter(function(i) { return i.status === 'mismatch'; }).length,
      ok: issues.length === 0,
      potential_light_cards_dark_bg: lowContrastCount,
      theme: style.getPropertyValue('--chain-bg').trim() || 'not set',
      body_bg: actualBg
    };
  }

  window.chainThemeAudit = {
    check: check,
    report: function() {
      var r = check();
      console.log('[CHAIN Theme Audit]');
      console.log('  OK:', r.ok);
      console.log('  Checked:', r.checked, 'variables');
      if (r.missing) console.log('  MISSING:', r.missing);
      if (r.mismatched) console.log('  MISMATCHED:', r.mismatched);
      console.log('  Theme:', r.theme);
      console.log('  Body BG:', r.body_bg);
      if (r.potential_light_cards_dark_bg) {
        console.log('  WARN:', r.potential_light_cards_dark_bg, 'cards may be light on dark bg');
      }
      r.issues = r.variables;
      return r;
    }
  };

  if (document.readyState === 'complete') {
    window.chainThemeAudit.report();
  } else {
    window.addEventListener('load', function() {
      setTimeout(function() { window.chainThemeAudit.report(); }, 500);
    });
  }
})();
