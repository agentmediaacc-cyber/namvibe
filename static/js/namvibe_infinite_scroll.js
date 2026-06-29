(function () {
  'use strict';

  var instances = [];

  function init(container, opts) {
    opts = opts || {};
    if (!container) return;

    var endpoint = opts.endpoint || container.dataset.nvEndpoint || '';
    var cursorParam = opts.cursorParam || container.dataset.nvCursor || 'cursor';
    var containerSelector = opts.containerSelector || container.dataset.nvContainer || '';
    var loadOnInit = opts.loadOnInit !== false;

    var sentinel = document.createElement('div');
    sentinel.className = 'nv-infinite-sentinel';
    sentinel.style.cssText = 'height:1px;width:100%;pointer-events:none';
    container.appendChild(sentinel);

    var inst = {
      container: container,
      sentinel: sentinel,
      endpoint: endpoint,
      cursorParam: cursorParam,
      loading: false,
      hasMore: true,
      cursor: null,
      sentinelEl: containerSelector
        ? (container.closest ? container.closest(containerSelector) : null)
        : sentinel,
      observer: null,
      onLoad: opts.onLoad || null,
      onError: opts.onError || null,
    };

    if (loadOnInit) {
      loadPage(inst, true);
    }

    setupObserver(inst);

    instances.push(inst);
    return inst;
  }

  function loadPage(inst, replace) {
    if (inst.loading || !inst.hasMore) return;
    inst.loading = true;

    var params = [];
    if (inst.cursor) {
      params.push(encodeURIComponent(inst.cursorParam) + '=' + encodeURIComponent(inst.cursor));
    }
    if (replace) {
      params.push('replace=1');
    }
    var url = inst.endpoint + (params.length ? '?' + params.join('&') : '');

    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        inst.loading = false;
        if (!data.ok) {
          if (inst.onError) inst.onError(data.error || 'Load failed');
          return;
        }

        inst.hasMore = data.has_more === true;
        inst.cursor = data.next_cursor || null;

        if (replace) {
          var items = inst.container.querySelectorAll('.nv-infinite-item');
          items.forEach(function (el) { el.remove(); });
        }

        var items = data.items || data.data || [];
        if (items.length === 0) {
          inst.hasMore = false;
        }

        if (inst.onLoad) {
          inst.onLoad(items, replace, inst);
        }

        updateSentinel(inst);
      })
      .catch(function (err) {
        inst.loading = false;
        if (inst.onError) inst.onError(err);
      });
  }

  function setupObserver(inst) {
    if (window.IntersectionObserver) {
      inst.observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !inst.loading && inst.hasMore) {
            loadPage(inst, false);
          }
        });
      }, { rootMargin: '300px' });
      inst.observer.observe(inst.sentinel);
    } else {
      inst._scrollHandler = function () {
        if (inst.loading || !inst.hasMore) return;
        var rect = inst.sentinel.getBoundingClientRect();
        if (rect.top < window.innerHeight + 300) {
          loadPage(inst, false);
        }
      };
      window.addEventListener('scroll', inst._scrollHandler, { passive: true });
    }
  }

  function updateSentinel(inst) {
    inst.sentinel.style.display = inst.hasMore ? 'block' : 'none';
  }

  function destroy(inst) {
    if (inst.observer) {
      inst.observer.disconnect();
      inst.observer = null;
    }
    if (inst._scrollHandler) {
      window.removeEventListener('scroll', inst._scrollHandler);
    }
    if (inst.sentinel && inst.sentinel.parentNode) {
      inst.sentinel.parentNode.removeChild(inst.sentinel);
    }
    var idx = instances.indexOf(inst);
    if (idx > -1) instances.splice(idx, 1);
  }

  function destroyAll() {
    for (var i = instances.length - 1; i >= 0; i--) {
      destroy(instances[i]);
    }
  }

  window.NamVibeInfinite = {
    init: init,
    loadPage: function (inst) { return loadPage(inst, false); },
    destroy: destroy,
    destroyAll: destroyAll,
  };
})();
