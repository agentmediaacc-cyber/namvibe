(function () {
  "use strict";

  var DB_NAME = "NamVibeCache";
  var DB_VERSION = 1;
  var CACHE_MAX_ITEMS = 100;
  var CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;
  var db = null;

  function openDB() {
    return new Promise(function (resolve, reject) {
      if (db) { resolve(db); return; }
      if (!window.indexedDB) { resolve(null); return; }
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var d = e.target.result;
        if (!d.objectStoreNames.contains("feed")) {
          var store = d.createObjectStore("feed", { keyPath: "cache_key" });
          store.createIndex("cached_at", "cached_at", { unique: false });
        }
        if (!d.objectStoreNames.contains("detail")) {
          var s2 = d.createObjectStore("detail", { keyPath: "id" });
          s2.createIndex("cached_at", "cached_at", { unique: false });
        }
        if (!d.objectStoreNames.contains("drafts")) {
          d.createObjectStore("drafts", { keyPath: "draft_id", autoIncrement: true });
        }
      };
      req.onsuccess = function (e) {
        db = e.target.result;
        resolve(db);
      };
      req.onerror = function () { resolve(null); };
    });
  }

  function isDBNotFound(err) {
    return err && (err.name === "NotFoundError" || err.name === "QuotaExceededError");
  }

  function fallbackToLS(key, data) {
    try {
      if (data) {
        localStorage.setItem("nv_" + key, JSON.stringify(data));
      } else {
        var raw = localStorage.getItem("nv_" + key);
        return raw ? JSON.parse(raw) : null;
      }
    } catch (e) { return null; }
  }

  /* ── Public API ── */
  window.NamVibeCache = {
    /* Save feed response */
    saveFeed: function (payload) {
      var entry = {
        cache_key: "homepage_feed",
        stories: payload.stories || [],
        feed_items: payload.feed_items || [],
        reels: payload.reels || [],
        feed_for_you: payload.feed_for_you || [],
        next_cursor: payload.next_cursor || "",
        cached_at: Date.now(),
      };
      return openDB().then(function (d) {
        if (!d) { fallbackToLS("feed", entry); return; }
        var tx = d.transaction("feed", "readwrite");
        tx.objectStore("feed").put(entry);
        cleanupFeed(d);
      }).catch(function () { fallbackToLS("feed", entry); });
    },

    /* Load cached feed */
    loadFeed: function () {
      return openDB().then(function (d) {
        if (!d) { return fallbackToLS("feed"); }
        return new Promise(function (resolve) {
          var tx = d.transaction("feed", "readonly");
          var req = tx.objectStore("feed").get("homepage_feed");
          req.onsuccess = function () {
            var entry = req.result;
            if (!entry || !entry.cached_at) { resolve(null); return; }
            if (Date.now() - entry.cached_at > CACHE_MAX_AGE_MS) {
              resolve(null);
              return;
            }
            resolve(entry);
          };
          req.onerror = function () { resolve(null); };
        });
      }).catch(function () { return fallbackToLS("feed"); });
    },

    /* Save a single detail view (post/reel) */
    saveDetail: function (id, data) {
      var entry = { id: id, data: data, cached_at: Date.now() };
      return openDB().then(function (d) {
        if (!d) { fallbackToLS("detail_" + id, data); return; }
        var tx = d.transaction("detail", "readwrite");
        tx.objectStore("detail").put(entry);
      }).catch(function () { fallbackToLS("detail_" + id, data); });
    },

    /* Load cached detail */
    loadDetail: function (id) {
      return openDB().then(function (d) {
        if (!d) { return fallbackToLS("detail_" + id); }
        return new Promise(function (resolve) {
          var tx = d.transaction("detail", "readonly");
          var req = tx.objectStore("detail").get(id);
          req.onsuccess = function () {
            var entry = req.result;
            if (!entry || Date.now() - entry.cached_at > CACHE_MAX_AGE_MS) { resolve(null); return; }
            resolve(entry.data);
          };
          req.onerror = function () { resolve(null); };
        });
      }).catch(function () { return null; });
    },

    /* Save upload draft */
    saveDraft: function (draft) {
      draft.saved_at = Date.now();
      return openDB().then(function (d) {
        if (!d) {
          var drafts = fallbackToLS("drafts") || [];
          drafts.push(draft);
          fallbackToLS("drafts", drafts);
          return;
        }
        var tx = d.transaction("drafts", "readwrite");
        tx.objectStore("drafts").add(draft);
      }).catch(function () {});
    },

    /* Get all drafts */
    getDrafts: function () {
      return openDB().then(function (d) {
        if (!d) { return fallbackToLS("drafts") || []; }
        return new Promise(function (resolve) {
          var tx = d.transaction("drafts", "readonly");
          var req = tx.objectStore("drafts").getAll();
          req.onsuccess = function () { resolve(req.result || []); };
          req.onerror = function () { resolve([]); };
        });
      }).catch(function () { return []; });
    },

    /* Delete a draft */
    deleteDraft: function (draftId) {
      return openDB().then(function (d) {
        if (!d) return;
        var tx = d.transaction("drafts", "readwrite");
        tx.objectStore("drafts").delete(draftId);
      }).catch(function () {});
    },

    /* Clear all cache */
    clearAll: function () {
      return openDB().then(function (d) {
        if (!d) {
          ["feed", "drafts"].forEach(function (k) { try { localStorage.removeItem("nv_" + k); } catch (e) {} });
          return;
        }
        ["feed", "detail", "drafts"].forEach(function (s) {
          var tx = d.transaction(s, "readwrite");
          tx.objectStore(s).clear();
        });
      }).catch(function () {});
    },

    /* Check if any cached feed exists (synchronous quick check) */
    hasCachedFeed: function () {
      try {
        var raw = localStorage.getItem("namvibe_feed_cache");
        if (raw) return true;
      } catch (e) {}
      return false;
    },
  };

  /* ── Helpers ── */
  function cleanupFeed(db) {
    try {
      var tx = db.transaction("feed", "readonly");
      var req = tx.objectStore("feed").index("cached_at").openCursor(null, "prev");
      var count = 0;
      req.onsuccess = function (e) {
        var cursor = e.target.result;
        if (cursor) {
          count++;
          if (count > CACHE_MAX_ITEMS) {
            var delTx = db.transaction("feed", "readwrite");
            delTx.objectStore("feed").delete(cursor.primaryKey);
          }
          cursor.continue();
        }
      };
    } catch (e) {}
  }

  /* Migrate existing localStorage cache to IndexedDB on load */
  function migrateLegacyCache() {
    try {
      var legacy = localStorage.getItem("namvibe_feed_cache");
      if (legacy) {
        var data = JSON.parse(legacy);
        if (data && (data.feed_items || data.stories)) {
          window.NamVibeCache.saveFeed(data);
          localStorage.removeItem("namvibe_feed_cache");
        }
      }
    } catch (e) {}
  }

  migrateLegacyCache();

})();