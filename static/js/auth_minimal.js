(function(){
  "use strict";

  var form = document.querySelector(".auth-submit-form, #chain-register-form");
  if (!form) return;

  var submitBtn = form.querySelector('[type="submit"]');
  var overlay = document.getElementById("register-loading-overlay");

  form.querySelectorAll(".toggle-password").forEach(function(button){
    button.addEventListener("click", function(){
      var target = document.getElementById(button.getAttribute("data-target"));
      if (!target) return;
      target.type = target.type === "password" ? "text" : "password";
      button.textContent = target.type === "password" ? "Show" : "Hide";
    });
  });

  form.addEventListener("submit", function(){
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = submitBtn.getAttribute("data-loading-text") || "Creating account...";
    }
    if (overlay) {
      overlay.classList.add("is-visible");
      overlay.setAttribute("aria-hidden", "false");
    }
  });
})();
