(function () {
  'use strict';

  var UPLOAD_CONCURRENCY = 3;
  var activeUploads = 0;
  var queue = [];
  var uploadMap = {};

  function init() {
    loadMetadata();
  }

  function enqueue(file, opts) {
    opts = opts || {};
    var id = 'upload_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    var item = {
      id: id,
      file: file,
      name: file.name,
      size: file.size,
      mime: file.type,
      url: opts.url || '/api/upload',
      method: opts.method || 'POST',
      fieldName: opts.fieldName || 'file',
      extraFields: opts.extraFields || {},
      headers: opts.headers || {},
      onProgress: opts.onProgress || null,
      onComplete: opts.onComplete || null,
      onError: opts.onError || null,
      status: 'queued',
      progress: 0,
      xhr: null,
      retries: 0,
      maxRetries: opts.maxRetries || 3,
      paused: false,
      cancelled: false,
      startedAt: null,
    };

    queue.push(item);
    uploadMap[id] = item;
    saveMetadata();
    emitChange();
    processQueue();
    return id;
  }

  function processQueue() {
    while (activeUploads < UPLOAD_CONCURRENCY && queue.length > 0) {
      var idx = -1;
      for (var i = 0; i < queue.length; i++) {
        if (queue[i].status === 'queued' && !queue[i].paused) {
          idx = i;
          break;
        }
      }
      if (idx === -1) break;
      startUpload(idx);
    }
  }

  function startUpload(idx) {
    var item = queue[idx];
    if (!item || item.cancelled) return;

    activeUploads++;
    item.status = 'uploading';
    item.startedAt = Date.now();
    item.progress = 0;
    emitChange();

    var formData = new FormData();
    formData.append(item.fieldName, item.file);
    for (var key in item.extraFields) {
      if (item.extraFields.hasOwnProperty(key)) {
        formData.append(key, item.extraFields[key]);
      }
    }

    var xhr = new XMLHttpRequest();
    item.xhr = xhr;

    xhr.upload.addEventListener('progress', function (e) {
      if (e.lengthComputable && !item.paused && !item.cancelled) {
        item.progress = Math.round((e.loaded / e.total) * 100);
        emitChange();
        if (item.onProgress) item.onProgress(item.progress, item);
      }
    });

    xhr.addEventListener('load', function () {
      activeUploads--;
      if (item.cancelled) return;
      if (xhr.status >= 200 && xhr.status < 300) {
        item.status = 'completed';
        item.progress = 100;
        var responseText = xhr.responseText;
        try { responseText = JSON.parse(responseText); } catch (e) {}
        if (item.onComplete) item.onComplete(responseText, item);
      } else {
        handleUploadError(item, xhr.status);
      }
      saveMetadata();
      emitChange();
      removeFromQueue(item.id);
      processQueue();
    });

    xhr.addEventListener('error', function () {
      activeUploads--;
      if (item.cancelled) return;
      handleUploadError(item, 0);
      saveMetadata();
      emitChange();
      processQueue();
    });

    xhr.addEventListener('abort', function () {
      activeUploads--;
      if (!item.cancelled) {
        item.status = 'queued';
        item.progress = 0;
        emitChange();
      }
      processQueue();
    });

    xhr.open(item.method, item.url);
    for (var h in item.headers) {
      if (item.headers.hasOwnProperty(h)) {
        xhr.setRequestHeader(h, item.headers[h]);
      }
    }
    xhr.send(formData);
  }

  function handleUploadError(item, status) {
    if (item.cancelled) return;
    item.retries++;
    if (item.retries <= item.maxRetries) {
      item.status = 'queued';
      item.progress = 0;
      item.xhr = null;
      emitChange();
      setTimeout(processQueue, Math.min(1000 * item.retries, 10000));
    } else {
      item.status = 'failed';
      if (item.onError) item.onError(status || 'Network error', item);
      emitChange();
    }
  }

  function pauseUpload(id) {
    var item = uploadMap[id];
    if (!item || item.status !== 'uploading') return;
    item.paused = true;
    if (item.xhr) item.xhr.abort();
    item.status = 'paused';
    emitChange();
  }

  function resumeUpload(id) {
    var item = uploadMap[id];
    if (!item || item.status !== 'paused') return;
    item.paused = false;
    item.status = 'queued';
    item.xhr = null;
    emitChange();
    processQueue();
  }

  function cancelUpload(id) {
    var item = uploadMap[id];
    if (!item) return;
    item.cancelled = true;
    if (item.xhr) item.xhr.abort();
    removeFromQueue(id);
    saveMetadata();
    emitChange();
  }

  function retryUpload(id) {
    var item = uploadMap[id];
    if (!item || item.status !== 'failed') return;
    item.status = 'queued';
    item.progress = 0;
    item.retries = 0;
    item.xhr = null;
    item.cancelled = false;
    emitChange();
    processQueue();
  }

  function removeFromQueue(id) {
    queue = queue.filter(function (q) { return q.id !== id; });
    delete uploadMap[id];
    saveMetadata();
    emitChange();
  }

  function getUpload(id) {
    return uploadMap[id] || null;
  }

  function getQueue() {
    return queue.slice();
  }

  function getActiveCount() {
    return activeUploads;
  }

  function saveMetadata() {
    var meta = queue.map(function (item) {
      return {
        id: item.id,
        name: item.name,
        size: item.size,
        mime: item.mime,
        url: item.url,
        status: item.status,
        progress: item.progress,
        retries: item.retries,
      };
    });
    try {
      localStorage.setItem('nv_upload_queue', JSON.stringify(meta));
    } catch (e) {}
  }

  function loadMetadata() {
    try {
      var data = localStorage.getItem('nv_upload_queue');
      if (data) {
        var meta = JSON.parse(data);
        meta.forEach(function (m) {
          if (m.status === 'uploading' || m.status === 'paused') {
            m.status = 'queued';
            m.progress = 0;
            m.retries = 0;
          }
        });
        localStorage.setItem('nv_upload_queue', JSON.stringify(meta));
      }
    } catch (e) {}
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

  window.NamVibeUpload = {
    init: init,
    enqueue: enqueue,
    pause: pauseUpload,
    resume: resumeUpload,
    cancel: cancelUpload,
    retry: retryUpload,
    get: getUpload,
    getQueue: getQueue,
    getActiveCount: getActiveCount,
    onChange: onChange,
  };
})();
