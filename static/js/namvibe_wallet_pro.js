(function () {
  'use strict';

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

  // Transaction filter
  var filter = $('wpTxTypeFilter');
  if (filter) {
    filter.addEventListener('change', function () {
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

  // Deposit
  var depBtn = $('wpDepositBtn');
  if (depBtn) {
    depBtn.addEventListener('click', function () {
      var amount = parseInt($('wpDepositAmount').value) || 0;
      if (amount <= 0) { toast('Enter a valid amount', 'error'); return; }
      depBtn.disabled = true;
      postJSON('/wallet/api/wallet/deposit', { amount_cents: amount }, function (res) {
        depBtn.disabled = false;
        if (res && res.ok) { toast('Deposited ' + amount + ' coins!', 'success'); }
        else { toast(res && res.error ? res.error : 'Deposit failed', 'error'); }
      });
    });
  }
})();
