(() => {
  const form = document.getElementById("chain-register-form");
  if (!form) return;

  const steps = Array.from(form.querySelectorAll(".chain-register-step"));
  const nextBtn = document.getElementById("register_next");
  const prevBtn = document.getElementById("register_prev");
  const submitBtn = document.getElementById("register_submit");
  const progressText = document.getElementById("chain-register-progress-text");
  const progressBar = document.getElementById("chain-register-progress-bar");
  const country = document.getElementById("register_country");
  const region = document.getElementById("register_region");
  const town = document.getElementById("register_town");
  const password = document.getElementById("register_password");
  const confirmPassword = document.getElementById("register_confirm_password");
  const confirmStatus = document.getElementById("confirm_password_status");
  const availabilityState = { username: false, email: false, phone: false };
  let stepIndex = 0;

  const updateStep = () => {
    steps.forEach((step, index) => step.classList.toggle("is-active", index === stepIndex));
    progressText.textContent = `Step ${stepIndex + 1} of ${steps.length}`;
    progressBar.style.width = `${((stepIndex + 1) / steps.length) * 100}%`;
    prevBtn.style.visibility = stepIndex === 0 ? "hidden" : "visible";
    nextBtn.style.display = stepIndex === steps.length - 1 ? "none" : "inline-flex";
    submitBtn.style.display = stepIndex === steps.length - 1 ? "inline-flex" : "none";
    validateSubmit();
  };

  const setAvailability = (field, payload) => {
    const node = document.getElementById(`availability_${field}`);
    if (!node) return;
    node.textContent = payload.message || "";
    node.classList.toggle("is-available", Boolean(payload.available));
    node.classList.toggle("is-unavailable", !payload.available);
    availabilityState[field] = Boolean(payload.available);

    const suggestionNode = document.getElementById(`suggestions_${field}`);
    if (suggestionNode) {
      suggestionNode.innerHTML = "";
      (payload.suggestions || []).forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = item;
        button.addEventListener("click", () => {
          document.getElementById(`register_${field}`).value = item;
          debounceCheck(field)();
        });
        suggestionNode.appendChild(button);
      });
    }
    validateSubmit();
  };

  const debounceCheck = (field) => {
    let timer = null;
    return () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        const input = document.getElementById(`register_${field}`);
        if (!input?.value.trim()) return;
        try {
          const params = new URLSearchParams({ field, value: input.value.trim(), town: town?.value || "" });
          const response = await fetch(`/auth/check-availability?${params.toString()}`);
          const payload = await response.json();
          setAvailability(field, payload);
        } catch (e) {
          console.error("Availability check failed", e);
        }
      }, 500);
    };
  };

  const usernameCheck = debounceCheck("username");
  const emailCheck = debounceCheck("email");
  const phoneCheck = debounceCheck("phone");

  const passwordStrength = () => {
    const node = document.getElementById("password_strength");
    if (!node || !password) return;
    const value = password.value || "";
    if (value.length >= 12 && /[A-Z]/.test(value) && /[0-9]/.test(value)) {
      node.textContent = "Strong password.";
      node.classList.add("is-strong");
      node.classList.remove("is-weak");
    } else if (value.length >= 8) {
      node.textContent = "Good enough.";
      node.classList.remove("is-weak");
      node.classList.remove("is-strong");
    } else {
      node.textContent = "Use at least 8 characters.";
      node.classList.add("is-weak");
      node.classList.remove("is-strong");
    }
  };

  const validateConfirmPassword = () => {
    const match = password.value && confirmPassword.value && password.value === confirmPassword.value;
    confirmStatus.textContent = match ? "Passwords match." : "Passwords must match.";
    confirmStatus.style.color = match ? "var(--chain-success)" : "var(--chain-error)";
    confirmStatus.classList.toggle("is-available", match);
    confirmStatus.classList.toggle("is-unavailable", !match && !!confirmPassword.value);
    validateSubmit();
  };

  const validateSubmit = () => {
    const terms = form.querySelector("#terms")?.checked;
    const human = form.querySelector("#human_confirmed")?.checked;
    const passwordsMatch = password.value && password.value === confirmPassword.value && password.value.length >= 8;
    
    // Core fields check
    const required = Array.from(form.querySelectorAll("input[required], select[required]"));
    const allFilled = required.every(input => input.value.trim() !== "");

    const canSubmit = allFilled && passwordsMatch && terms && human;
    submitBtn.disabled = !canSubmit;
    
    if (submitBtn.disabled && stepIndex === 1) {
        // Optional: show some hint why disabled if needed
    }
  };

  const renderCountries = () => {
    if (!country || !window.CHAIN_LOCATIONS) return;
    country.innerHTML = ['<option value="">Select country</option>']
      .concat(window.CHAIN_LOCATIONS.map((item) => `<option value="${item.country}">${item.country}</option>`))
      .join("");
    
    const selected = country.dataset.selected;
    if (selected) country.value = selected;
    else country.value = "Namibia";
    renderRegions();
  };

  const renderRegions = () => {
    const record = window.CHAIN_LOCATIONS?.find((item) => item.country === country.value);
    const regions = record?.regions || [];
    region.innerHTML = ['<option value="">Select region/state</option>']
      .concat(regions.map((item) => `<option value="${item}">${item}</option>`))
      .join("");
    
    const selected = region.dataset.selected;
    if (selected) region.value = selected;
  };

  form.querySelectorAll(".toggle-password").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.target);
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
      button.textContent = input.type === "password" ? "Show" : "Hide";
    });
  });

  form.querySelectorAll("[data-select-signup]").forEach((button) => {
    button.addEventListener("click", () => {
      stepIndex = 1;
      updateStep();
    });
  });

  document.getElementById("register_username")?.addEventListener("input", usernameCheck);
  document.getElementById("register_email")?.addEventListener("input", emailCheck);
  document.getElementById("register_phone")?.addEventListener("input", phoneCheck);
  password?.addEventListener("input", () => {
    passwordStrength();
    validateConfirmPassword();
  });
  confirmPassword?.addEventListener("input", validateConfirmPassword);
  country?.addEventListener("change", renderRegions);
  form.querySelectorAll("input, select").forEach((input) => input.addEventListener("input", validateSubmit));
  form.querySelectorAll("input[type='checkbox']").forEach((input) => input.addEventListener("change", validateSubmit));
  
  nextBtn?.addEventListener("click", () => {
    stepIndex = Math.min(steps.length - 1, stepIndex + 1);
    updateStep();
  });
  prevBtn?.addEventListener("click", () => {
    stepIndex = Math.max(0, stepIndex - 1);
    updateStep();
  });

  renderCountries();
  passwordStrength();
  updateStep();
})();
