(function () {
  'use strict';

  var API = {
    balanceSummary: '/wallet/api/wallet/balance-summary',
    earningsBreakdown: '/wallet/api/wallet/earnings-breakdown',
    transactions: '/wallet/api/transactions',
    tip: '/wallet/api/tip',
    gift: '/wallet/api/gift',
    gifts: '/wallet/api/gifts',
    subscribe: '/wallet/api/subscribe',
    purchase: '/wallet/api/wallet/purchase',
    refund: '/wallet/api/wallet/refund',
    payoutMethods: '/wallet/api/wallet/payout-methods',
    payoutRequest: '/wallet/api/payouts/request',
    deposit: '/wallet/api/wallet/deposit',
  };

  function $(id) { return document.getElementById(id); }

  function esc(str) { if (!str) return ''; var d = document.createElement('div'); d.appendChild(document.createTextNode(str)); return d.innerHTML; }

  function toast(msg, type) {
    var el = document.createElement('div');
    el.className = 'wp-toast' + (type === 'error' ? ' wp-toast-error' : type === 'success' ? ' wp-toast-success' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { if (el.parentNode) el.remove(); }, 3000);
  }

  function fetchJSON(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onload = function () { try { cb(JSON.parse(xhr.responseText)); } catch (e) { cb(null); } };
    xhr.onerror = function () { cb(null); };
    xhr.send();
  }

  function postJSON(url, body, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () { try { cb(JSON.parse(xhr.responseText)); } catch (e) { cb(null); } };
    xhr.onerror = function () { cb(null); };
    xhr.send(JSON.stringify(body));
  }

  function deleteReq(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('DELETE', url, true);
    xhr.onload = function () { try { cb(JSON.parse(xhr.responseText)); } catch (e) { cb(null); } };
    xhr.onerror = function () { cb(null); };
    xhr.send();
  }

  // ─── Tabs ───
  var tabBtns = document.querySelectorAll('.wp-tab');
  tabBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabBtns.forEach(function (b) { b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      document.querySelectorAll('.wp-panel').forEach(function (p) { p.classList.remove('is-active'); });
      var panel = document.getElementById('panel-' + btn.getAttribute('data-tab'));
      if (panel) panel.classList.add('is-active');
    });
  });

  // ─── Modals ───
  function openModal(id) {
    var el = $(id);
    if (el) el.classList.add('is-open');
  }
  function closeModal(id) {
    var el = $(id);
    if (el) el.classList.remove('is-open');
  }

  document.querySelectorAll('.wp-modal-overlay').forEach(function (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) modal.classList.remove('is-open');
    });
    modal.querySelectorAll('.wp-modal-close').forEach(function (b) {
      b.addEventListener('click', function () { modal.classList.remove('is-open'); });
    });
  });

  // ─── Quick Actions ───
  if ($('wpQuickDeposit')) {
    $('wpQuickDeposit').addEventListener('click', function () {
      tabBtns.forEach(function (b) { b.classList.remove('is-active'); });
      document.querySelectorAll('.wp-panel').forEach(function (p) { p.classList.remove('is-active'); });
      var depositTab = document.querySelector('.wp-tab[data-tab="deposit"]');
      if (depositTab) depositTab.classList.add('is-active');
      var depositPanel = $('panel-deposit');
      if (depositPanel) depositPanel.classList.add('is-active');
    });
  }
  if ($('wpQuickSend')) {
    $('wpQuickSend').addEventListener('click', function () { openModal('wpTipModal'); });
  }
  if ($('wpQuickPayout')) {
    $('wpQuickPayout').addEventListener('click', function () {
      tabBtns.forEach(function (b) { b.classList.remove('is-active'); });
      document.querySelectorAll('.wp-panel').forEach(function (p) { p.classList.remove('is-active'); });
      var payoutTab = document.querySelector('.wp-tab[data-tab="payouts"]');
      if (payoutTab) payoutTab.classList.add('is-active');
      var payoutPanel = $('panel-payouts');
      if (payoutPanel) payoutPanel.classList.add('is-active');
    });
  }

  // ─── Send Tip ───
  if ($('wpSendTipBtn')) {
    $('wpSendTipBtn').addEventListener('click', function () { openModal('wpTipModal'); });
  }
  if ($('wpTipSend')) {
    $('wpTipSend').addEventListener('click', function () {
      var receiver = ($('wpTipReceiver').value || '').trim();
      var amount = parseInt($('wpTipAmount').value) || 0;
      var message = ($('wpTipMessage').value || '').trim();
      if (!receiver) { toast('Enter recipient ID', 'error'); return; }
      if (amount <= 0) { toast('Enter a valid amount', 'error'); return; }
      $('wpTipSend').disabled = true;
      postJSON(API.tip, { receiver_profile_id: receiver, amount_cents: amount, message: message }, function (res) {
        $('wpTipSend').disabled = false;
        if (res && res.ok) { toast('Tip sent: ' + amount + ' coins!', 'success'); closeModal('wpTipModal'); }
        else { toast(res && res.error ? res.error : 'Tip failed', 'error'); }
      });
    });
  }

  // ─── Send Gift ───
  if ($('wpSendGiftBtn')) {
    $('wpSendGiftBtn').addEventListener('click', function () {
      openModal('wpGiftModal');
      loadGiftPicker();
    });
  }

  var selectedGiftId = null;

  function loadGiftPicker() {
    var picker = $('wpGiftPicker');
    if (!picker) return;
    selectedGiftId = null;
    fetchJSON(API.gifts, function (data) {
      if (!data || !data.gifts || !data.gifts.length) {
        picker.innerHTML = '<div class="wp-empty"><p>No gifts available.</p></div>';
        return;
      }
      var html = '';
      data.gifts.forEach(function (g) {
        html += '<div class="wp-gift-option" data-id="' + esc(g.id) + '" data-price="' + (g.coin_price || g.price_cents || 0) + '">';
        html += '<span class="wp-gift-emoji">' + (g.gift_icon || '🎁') + '</span>';
        html += '<strong>' + esc(g.gift_name) + '</strong>';
        html += '<small>' + (g.coin_price || g.price_cents || 0) + ' coins</small>';
        html += '</div>';
      });
      picker.innerHTML = html;
      picker.querySelectorAll('.wp-gift-option').forEach(function (opt) {
        opt.addEventListener('click', function () {
          picker.querySelectorAll('.wp-gift-option').forEach(function (o) { o.classList.remove('is-selected'); });
          opt.classList.add('is-selected');
          selectedGiftId = opt.getAttribute('data-id');
        });
      });
    });
  }

  if ($('wpGiftSend')) {
    $('wpGiftSend').addEventListener('click', function () {
      var receiver = ($('wpGiftReceiver').value || '').trim();
      if (!receiver) { toast('Enter recipient ID', 'error'); return; }
      if (!selectedGiftId) { toast('Select a gift', 'error'); return; }
      $('wpGiftSend').disabled = true;
      postJSON(API.gift, { receiver_profile_id: receiver, gift_id: selectedGiftId }, function (res) {
        $('wpGiftSend').disabled = false;
        if (res && res.ok) { toast('Gift sent!', 'success'); closeModal('wpGiftModal'); }
        else { toast(res && res.error ? res.error : 'Gift failed', 'error'); }
      });
    });
  }

  // ─── Subscribe ───
  if ($('wpSubscribeBtn')) {
    $('wpSubscribeBtn').addEventListener('click', function () { openModal('wpSubscribeModal'); });
  }
  if ($('wpSubSend')) {
    $('wpSubSend').addEventListener('click', function () {
      var creator = ($('wpSubCreator').value || '').trim();
      var tier = $('wpSubTier').value;
      var price = parseInt($('wpSubPrice').value) || 0;
      if (!creator) { toast('Enter creator ID', 'error'); return; }
      if (price <= 0) { toast('Enter a valid price', 'error'); return; }
      $('wpSubSend').disabled = true;
      postJSON(API.subscribe, { creator_profile_id: creator, tier_name: tier, price_cents: price }, function (res) {
        $('wpSubSend').disabled = false;
        if (res && res.ok) { toast('Subscribed!', 'success'); closeModal('wpSubscribeModal'); }
        else { toast(res && res.error ? res.error : 'Subscription failed', 'error'); }
      });
    });
  }

  // ─── Purchase ───
  if ($('wpPurchaseBtn')) {
    $('wpPurchaseBtn').addEventListener('click', function () { openModal('wpPurchaseModal'); });
  }
  if ($('wpPurchaseBuy')) {
    $('wpPurchaseBuy').addEventListener('click', function () {
      var seller = ($('wpPurchaseSeller').value || '').trim();
      var amount = parseInt($('wpPurchaseAmount').value) || 0;
      var itemId = ($('wpPurchaseItem').value || '').trim();
      var itemType = $('wpPurchaseType').value;
      if (!seller) { toast('Enter seller ID', 'error'); return; }
      if (amount <= 0) { toast('Enter a valid amount', 'error'); return; }
      $('wpPurchaseBuy').disabled = true;
      postJSON(API.purchase, { seller_profile_id: seller, amount_cents: amount, item_id: itemId || undefined, item_type: itemType }, function (res) {
        $('wpPurchaseBuy').disabled = false;
        if (res && res.ok) { toast('Purchase complete!', 'success'); closeModal('wpPurchaseModal'); }
        else { toast(res && res.error ? res.error : 'Purchase failed', 'error'); }
      });
    });
  }

  // ─── Deposit ───
  if ($('wpDepositBtn')) {
    $('wpDepositBtn').addEventListener('click', function () {
      var amount = parseInt($('wpDepositAmount').value) || 0;
      if (amount <= 0) { toast('Enter a valid amount', 'error'); return; }
      $('wpDepositBtn').disabled = true;
      postJSON(API.deposit, { amount_cents: amount }, function (res) {
        $('wpDepositBtn').disabled = false;
        if (res && res.ok) { toast('Deposited ' + amount + ' coins!', 'success'); }
        else { toast(res && res.error ? res.error : 'Deposit failed', 'error'); }
      });
    });
  }

  // ─── Payout Methods ───
  if ($('wpAddPayoutBtn')) {
    $('wpAddPayoutBtn').addEventListener('click', function () { openModal('wpAddPayoutModal'); });
  }
  if ($('wpPayoutSave')) {
    $('wpPayoutSave').addEventListener('click', function () {
      var provider = $('wpPayoutProvider').value;
      var accountName = ($('wpPayoutAccountName').value || '').trim();
      var masked = ($('wpPayoutMasked').value || '').trim();
      var isDefault = $('wpPayoutDefault').checked;
      if (!accountName) { toast('Enter account name', 'error'); return; }
      if (!masked) { toast('Enter account info', 'error'); return; }
      $('wpPayoutSave').disabled = true;
      postJSON(API.payoutMethods, { provider: provider, account_name: accountName, masked_account: masked, is_default: isDefault }, function (res) {
        $('wpPayoutSave').disabled = false;
        if (res && res.ok) { toast('Payout method added!', 'success'); closeModal('wpAddPayoutModal'); location.reload(); }
        else { toast(res && res.error ? res.error : 'Failed to add method', 'error'); }
      });
    });
  }

  // ─── Delete Payout Method ───
  var deleteTargetId = null;
  document.querySelectorAll('.wp-delete-payout').forEach(function (btn) {
    btn.addEventListener('click', function () {
      deleteTargetId = btn.getAttribute('data-id');
      openModal('wpDeletePayoutModal');
    });
  });
  if ($('wpDeletePayoutConfirm')) {
    $('wpDeletePayoutConfirm').addEventListener('click', function () {
      if (!deleteTargetId) { closeModal('wpDeletePayoutModal'); return; }
      $('wpDeletePayoutConfirm').disabled = true;
      deleteReq(API.payoutMethods + '/' + deleteTargetId, function (res) {
        $('wpDeletePayoutConfirm').disabled = false;
        if (res && res.ok) { toast('Payout method deleted', 'success'); closeModal('wpDeletePayoutModal'); location.reload(); }
        else { toast(res && res.error ? res.error : 'Failed to delete', 'error'); }
      });
    });
  }

  // ─── Transaction Filter ───
  if ($('wpTxTypeFilter')) {
    $('wpTxTypeFilter').addEventListener('change', function () {
      var txType = this.value;
      var rows = document.querySelectorAll('#wpTxBody tr');
      rows.forEach(function (row) {
        if (!txType) { row.style.display = ''; return; }
        var typeCell = row.querySelector('td:first-child');
        if (!typeCell) return;
        if (typeCell.textContent.toLowerCase().indexOf(txType) !== -1) { row.style.display = ''; }
        else { row.style.display = 'none'; }
      });
    });
  }

})();
