(function () {
  "use strict";
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/static/js/namvibe_service_worker.js")
        .then(function (reg) {
          console.log("NamVibe SW registered:", reg.scope);
        })
        .catch(function (err) {
          console.log("NamVibe SW registration failed:", err);
        });
    });
  }
})();