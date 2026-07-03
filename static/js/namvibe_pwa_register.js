(function () {
  "use strict";
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/static/js/namvibe_service_worker.js")
        .catch(function () {});
    });
  }
})();