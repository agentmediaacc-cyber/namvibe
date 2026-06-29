(function () {
  'use strict';

  var MAX_QUEUE_SIZE = 100;
  var STORAGE_KEY = 'nv_offline_queue';
  var queue = [];
  var processing = false;
  var isOnline = navigator.onLine;

  function init() {
    loadQueue();
    window.addEventListener('online', function () {
      isOnline = true;
      processQueue();
    });
    window.addEventListener('offline', function () {
      isOnline = false;
    });
  }

  function enqueue(action, data) {
    if (queue.length >= MAX_QUEUE_SIZE) {
      return null;
    }

    var id = 'offline_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    var item = {
      id: id,
      action: action,
      data: data,
      createdAt: Date.now(),
      retries: 0,
      maxRetries: 3,
      status: 'queued',
    };

    queue.push(item);
    saveQueue();
    emitChange();

    if (isOnline) {
      processQueue();
    }

    return id;
  }

  function processQueue() {
    if (processing || !isOnline) return;
    processing = true;

    var promises = [];

    for (var i = queue.length - 1; i >= 0; i--) {
      var item = queue[i];
      if (item.status === 'completed') {
        queue.splice(i, 1);
        continue;
      }
      if (item.status === 'failed' && item.retries >= item.maxRetries) {
        continue;
      }
    }

    for (var j = 0; j < queue.length; j++) {
      var q = queue[j];
      if (q.status !== 'queued') continue;

      q.status = 'processing';
      emitChange();

      promises.push(executeItem(q));
    }

    if (promises.length === 0) {
      processing = false;
      return;
    }

    Promise.allSettled(promises).then(function () {
      cleanupCompleted();
      processing = false;
      saveQueue();
      emitChange();

      var pending = queue.filter(function (q) {
        return q.status === 'queued' || q.status === 'processing';
      });
      if (pending.length > 0 && isOnline) {
        setTimeout(processQueue, 2000);
      }
    });
  }

  function executeItem(item) {
    return new Promise(function (resolve) {
      var url = getActionUrl(item.action);
      if (!url) {
        item.status = 'failed';
        item.error = 'No URL for action: ' + item.action;
        resolve();
        return;
      }

      var payload = item.data || {};
      payload._offline_id = item.id;

      var options = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      };

      fetch(url, options)
        .then(function (resp) {
          if (resp.ok || resp.status === 404 || resp.status === 410) {
            item.status = 'completed';
          } else {
            throw new Error('HTTP ' + resp.status);
          }
        })
        .catch(function (err) {
          item.retries++;
          if (item.retries >= item.maxRetries) {
            item.status = 'failed';
            item.error = err.message;
          } else {
            item.status = 'queued';
          }
        })
        .finally(function () {
          resolve();
        });
    });
  }

  function getActionUrl(action) {
    var urls = {
      'message_send': '/api/messages/send',
      'message_react': '/api/messages/react',
      'post_like': '/api/posts/like',
      'post_comment': '/api/posts/comment',
      'reel_like': '/api/reels/like',
      'reel_comment': '/api/reels/comment',
      'story_like': '/api/stories/like',
      'follow': '/api/follow',
      'unfollow': '/api/follow/remove',
    };
    return urls[action] || null;
  }

  function cleanupCompleted() {
    queue = queue.filter(function (q) {
      return q.status !== 'completed';
    });
  }

  function getQueue() {
    return queue.slice();
  }

  function getPendingCount() {
    return queue.filter(function (q) {
      return q.status === 'queued' || q.status === 'processing';
    }).length;
  }

  function clearFailed() {
    queue = queue.filter(function (q) {
      return q.status !== 'failed';
    });
    saveQueue();
    emitChange();
  }

  function clearAll() {
    queue = [];
    saveQueue();
    emitChange();
  }

  function saveQueue() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
    } catch (e) {}
  }

  function loadQueue() {
    try {
      var data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        queue = JSON.parse(data);
        queue.forEach(function (q) {
          if (q.status === 'processing') {
            q.status = 'queued';
          }
        });
      }
    } catch (e) {
      queue = [];
    }
  }

  var changeListeners = [];
  function onChange(fn) {
    changeListeners.push(fn);
  }
  function emitChange() {
    for (var i = 0; i < changeListeners.length; i++) {
      try { changeListeners[i](queue.slice()); } catch (e) {}
    }
  }

  window.NamVibeOffline = {
    init: init,
    enqueue: enqueue,
    processQueue: processQueue,
    getQueue: getQueue,
    getPendingCount: getPendingCount,
    clearFailed: clearFailed,
    clearAll: clearAll,
    onChange: onChange,
    isOnline: function () { return isOnline; },
  };
})();
