(function () {
  'use strict';

  var API = {
    products: '/marketplace/api/products',
    services: '/marketplace/api/services',
    shops: '/marketplace/api/shops',
    dashboard: '/marketplace/api/dashboard',
    search: '/marketplace/api/search',
    saved: '/marketplace/api/saved',
    reviews: '/marketplace/api/reviews',
    bookings: '/marketplace/api/bookings',
  };

  var S = {
    activeTab: 'products',
    page: 1,
    loading: false,
    hasMore: true,
  };

  function $(id) { return document.getElementById(id); }

  function esc(str) { if (!str) return ''; var d = document.createElement('div'); d.appendChild(document.createTextNode(str)); return d.innerHTML; }

  function toast(msg, isError) {
    var el = document.createElement('div');
    el.className = 'mp-toast' + (isError ? ' mp-toast-error' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 3000);
  }

  function fetchJSON(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onload = function () {
      try { cb(JSON.parse(xhr.responseText)); }
      catch (e) { cb(null); }
    };
    xhr.onerror = function () { cb(null); };
    xhr.send();
  }

  function postJSON(url, body, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
      try { cb(JSON.parse(xhr.responseText)); }
      catch (e) { cb(null); }
    };
    xhr.onerror = function () { cb(null); };
    xhr.send(JSON.stringify(body || {}));
  }

  function renderProduct(p) {
    var images = p.images || [];
    var imgHtml = images.length ? '<img src="' + esc(images[0]) + '" alt="' + esc(p.title) + '" style="width:100%;height:100%;object-fit:cover">' : '<i class="fas fa-box"></i>';
    var price = (p.price_cents / 100).toFixed(2);
    return '<div class="mp-item-card" data-id="' + esc(p.id) + '">' +
      '<div class="mp-item-img">' + imgHtml + '</div>' +
      '<div class="mp-item-body">' +
      '<div class="mp-item-title">' + esc(p.title) + '</div>' +
      '<div class="mp-item-price">N$ ' + price + '</div>' +
      '<div class="mp-item-meta">' + esc(p.category || 'general') + (p.location ? ' &middot; ' + esc(p.location) : '') + '</div>' +
      '<div class="mp-item-actions">' +
      '<button class="mp-btn mp-btn-sm mp-btn-primary" onclick="event.stopPropagation();mpSave(\'' + esc(p.id) + '\')"><i class="fas fa-heart"></i></button>' +
      '<button class="mp-btn mp-btn-sm mp-btn-outline" onclick="event.stopPropagation();alert(\'Share: ' + esc(p.id) + '\')"><i class="fas fa-share"></i></button>' +
      '</div></div></div>';
  }

  function renderService(s) {
    var rate = (s.hourly_rate_cents / 100).toFixed(2);
    return '<div class="mp-item-card" data-id="' + esc(s.id) + '">' +
      '<div class="mp-item-body">' +
      '<div class="mp-item-title">' + esc(s.title) + '</div>' +
      '<div class="mp-item-price">N$ ' + rate + '/hr</div>' +
      '<div class="mp-item-meta">' + esc(s.category || 'general') + (s.service_area ? ' &middot; ' + esc(s.service_area) : '') + '</div>' +
      '<div style="margin-top:8px;font-size:12px;color:var(--mp-muted)">' + esc(s.availability || '') + '</div>' +
      '</div></div>';
  }

  function renderShop(sh) {
    var logoHtml = sh.logo_url ? '<img src="' + esc(sh.logo_url) + '" alt="' + esc(sh.name) + '">' : '<i class="fas fa-store"></i>';
    var badgeHtml = sh.is_verified ? '<span class="mp-shop-badge"><i class="fas fa-check-circle"></i> Verified</span>' : '';
    return '<div class="mp-item-card" data-id="' + esc(sh.id) + '">' +
      '<div class="mp-item-body">' +
      '<div class="mp-shop-header">' +
      '<div class="mp-shop-logo">' + logoHtml + '</div>' +
      '<div><div class="mp-shop-name">' + esc(sh.name) + ' ' + badgeHtml + '</div>' +
      '<div style="font-size:12px;color:var(--mp-muted)">' + esc(sh.category || 'general') + '</div></div>' +
      '</div>' +
      '<div style="font-size:13px;color:var(--mp-muted);margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">' + esc(sh.description || '') + '</div>' +
      '<div class="mp-shop-stats">' +
      '<span class="mp-shop-stat"><strong>' + (sh.products_count || 0) + '</strong> Products</span>' +
      '<span class="mp-shop-stat"><strong>' + (sh.services_count || 0) + '</strong> Services</span>' +
      '<span class="mp-shop-stat"><strong>' + (sh.followers_count || 0) + '</strong> Followers</span>' +
      '</div></div></div>';
  }

  function loadTab(tab) {
    var grid;
    if (tab === 'products') grid = $('mpProductsGrid');
    else if (tab === 'services') grid = $('mpServicesGrid');
    else if (tab === 'shops') grid = $('mpShopsGrid');
    else if (tab === 'trending') grid = $('mpTrendingGrid');
    if (!grid) return;

    if (tab === 'trending') {
      fetchJSON(API.products + '?sort=trending', function (res) {
        if (res && res.ok && res.data) {
          grid.innerHTML = res.data.length ? res.data.map(renderProduct).join('') : '<div class="mp-empty" style="grid-column:1/-1"><i class="fas fa-fire"></i><p>No trending items yet.</p></div>';
        } else {
          grid.innerHTML = '<div class="mp-empty" style="grid-column:1/-1"><i class="fas fa-exclamation-circle"></i><p>Could not load.</p></div>';
        }
      });
      return;
    }
    if (tab === 'digital') {
      fetchJSON(API.products + '?category=electronics', function (res) {
        var g = $('mpDigitalGrid');
        if (g) g.innerHTML = res && res.ok && res.data && res.data.length ? res.data.map(renderProduct).join('') : '<div class="mp-empty" style="grid-column:1/-1"><i class="fas fa-download"></i><p>No digital items yet.</p></div>';
      });
      return;
    }

    var url = API[tab];
    if (!url) return;
    fetchJSON(url, function (res) {
      if (res && res.ok && res.data) {
        var renderFn = tab === 'products' ? renderProduct : tab === 'services' ? renderService : tab === 'shops' ? renderShop : renderProduct;
        grid.innerHTML = res.data.length ? res.data.map(renderFn).join('') : '<div class="mp-empty" style="grid-column:1/-1"><i class="fas fa-' + (tab === 'products' ? 'box' : tab === 'services' ? 'concierge-bell' : 'store') + '"></i><p>No ' + tab + ' yet.</p></div>';
      } else {
        grid.innerHTML = '<div class="mp-empty" style="grid-column:1/-1"><i class="fas fa-exclamation-circle"></i><p>Could not load ' + tab + '.</p></div>';
      }
    });
  }

  function switchTab(tab) {
    S.activeTab = tab;
    var tabs = document.querySelectorAll('.mp-tab');
    for (var i = 0; i < tabs.length; i++) tabs[i].classList.toggle('is-active', tabs[i].dataset.tab === tab);
    var panels = document.querySelectorAll('.mp-panel');
    for (var j = 0; j < panels.length; j++) panels[j].classList.toggle('is-active', panels[j].id === 'mpPanel-' + tab);
    loadTab(tab);
  }

  function initSearch() {
    var btn = $('mpSearchBtn');
    var input = $('mpSearch');
    if (!btn || !input) return;
    function doSearch() {
      var q = input.value.trim();
      if (!q) { loadTab(S.activeTab); return; }
      fetchJSON(API.search + '?q=' + encodeURIComponent(q), function (res) {
        var g = $('mpProductsGrid');
        if (!g) return;
        if (res && res.ok && res.data) {
          var all = [].concat(res.data.products || [], res.data.services || [], res.data.shops || []);
          g.innerHTML = all.length ? all.map(function (x) { return x.hourly_rate_cents !== undefined ? renderService(x) : x.shop_type ? renderShop(x) : renderProduct(x); }).join('') : '<div class="mp-empty" style="grid-column:1/-1"><i class="fas fa-search"></i><p>No results for "' + esc(q) + '".</p></div>';
        }
      });
    }
    btn.addEventListener('click', doSearch);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
  }

  function initShopForm() {
    var createBtn = $('mpCreateShopBtn');
    var form = $('mpCreateShopForm');
    var saveBtn = $('mpSaveShopBtn');
    if (createBtn && form) {
      createBtn.addEventListener('click', function () { form.style.display = 'block'; createBtn.style.display = 'none'; });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var body = {
          name: $('mpShopName') ? $('mpShopName').value : '',
          shop_type: $('mpShopType') ? $('mpShopType').value : 'personal',
          description: $('mpShopDesc') ? $('mpShopDesc').value : '',
          category: $('mpShopCategory') ? $('mpShopCategory').value : '',
          contact_email: $('mpShopEmail') ? $('mpShopEmail').value : '',
          whatsapp: $('mpShopWhatsApp') ? $('mpShopWhatsApp').value : '',
          location: $('mpShopLocation') ? $('mpShopLocation').value : '',
        };
        if (!body.name) { toast('Shop name is required', true); return; }
        postJSON(API.shops, body, function (res) {
          if (res && res.ok) { toast('Shop created!'); setTimeout(function () { location.reload(); }, 1000); }
          else { toast((res && res.error) || 'Failed to create shop', true); }
        });
      });
    }
  }

  window.mpSave = function (productId) {
    postJSON('/marketplace/api/products/' + productId + '/save', {}, function (res) {
      if (res && res.ok) toast('Saved!');
      else toast((res && res.error) || 'Already saved', true);
    });
  };

  document.addEventListener('DOMContentLoaded', function () {
    // Tab clicks
    var tabs = document.querySelectorAll('.mp-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', function () { switchTab(this.dataset.tab); });
    }
    initSearch();
    initShopForm();
    loadTab('products');
    loadTab('trending');
  });
})();
