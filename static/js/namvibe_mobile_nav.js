(function(){
  "use strict";

  var backSelector = "[data-go-back], .js-go-back, .mobile-back-btn, .auth-back-btn";

  function goBack(e) {
    var target = e.target;
    while (target && target !== document) {
      if (target.matches && target.matches(backSelector)) {
        e.preventDefault();
        if (window.history.length > 1) {
          window.history.back();
        } else {
          window.location.href = "/";
        }
        return;
      }
      target = target.parentNode;
    }
  }

  function init() {
    document.addEventListener("click", goBack);
    document.addEventListener("touchend", goBack);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
