(() => {
  console.log("NamVibe REGISTER V7 LOADED");
  const form = document.getElementById("chain-register-form");
  if (!form) return;

  const steps = Array.from(form.querySelectorAll(".chain-register-step"));
  const stepDots = Array.from(form.querySelectorAll("[data-jump-step]"));
  const nextBtn = document.getElementById("register_next");
  const prevBtn = document.getElementById("register_prev");
  const submitBtn = document.getElementById("register_submit");
  const successPanel = document.getElementById("chain-register-success");
  const progressText = document.getElementById("chain-register-progress-text");
  const progressBar = document.getElementById("chain-register-progress-bar");
  const signupMethod = document.getElementById("signup_method") || form.querySelector("input[name='signup_method']");
  const countryOrigin = document.getElementById("register_country_origin");
  const currentCountry = document.getElementById("register_current_country");
  const region = document.getElementById("register_region");
  const town = document.getElementById("register_town");
  const phoneCode = document.getElementById("register_phone_code");
  const password = document.getElementById("register_password");
  const confirmPassword = document.getElementById("register_confirm_password");
  const confirmStatus = document.getElementById("confirm_password_status");
  const strengthText = document.getElementById("password_strength");
  const strengthBar = document.getElementById("password_strength_bar");
  const availabilityState = { username: null, email: null, phone: null };
  const countries = window.CHAIN_LOCATIONS || [];
  const namibiaRegions = window.CHAIN_NAMIBIA_REGIONS || [];
  let stepIndex = 0;
  let stepMessage = document.getElementById("chain-register-step-message");

  if (!stepMessage) {
    stepMessage = document.createElement("div");
    stepMessage.id = "chain-register-step-message";
    stepMessage.className = "chain-auth-alert chain-auth-alert--error chain-step-message";
    stepMessage.hidden = true;
    progressBar?.closest(".chain-auth-progress")?.after(stepMessage);
  }

  const log = (message, detail) => {
    if (detail !== undefined) console.log(`[NamVibe register] ${message}`, detail);
    else console.log(`[NamVibe register] ${message}`);
  };

  const normalize = (value) => String(value || "").trim().toLowerCase();
  const countryNames = countries.map((item) => item.country).filter(Boolean);

  const getCountryRecord = (value) => {
    const key = normalize(value);
    return countries.find((item) => normalize(item.country) === key || normalize(item.code) === key) || null;
  };

  const activeCountry = () => getCountryRecord(currentCountry?.value) || getCountryRecord(countryOrigin?.value);
  const isNamibia = () => {
    const selected = activeCountry();
    return selected?.code === "NA" || normalize(currentCountry.value) === "namibia" || normalize(countryOrigin.value) === "namibia";
  };

  const filtered = (items, query, limit = 8) => {
    const needle = normalize(query);
    const source = Array.from(new Set(items.filter(Boolean)));
    if (!needle) return source.slice(0, limit);
    return source
      .filter((item) => normalize(item).includes(needle))
      .slice(0, limit);
  };

  const closeResults = (box) => {
    if (!box) return;
    box.innerHTML = "";
    box.classList.remove("is-open");
  };

  const renderResults = (input, box, items, onPick) => {
    if (!input || !box) return;
    const matches = filtered(items, input.value);
    box.innerHTML = "";
    if (!matches.length) {
      closeResults(box);
      return;
    }
    matches.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item;
      button.addEventListener("click", () => {
        input.value = item;
        closeResults(box);
        onPick?.(item);
        validateSubmit();
      });
      box.appendChild(button);
    });
    box.classList.add("is-open");
  };

  const countryBoxFor = (input) => document.getElementById(input.id === "register_country_origin" ? "country_origin_results" : "current_country_results");

  const setupCountrySearch = (input) => {
    if (!input) return;
    const box = countryBoxFor(input);
    const pick = (value) => {
      log("country selected", value);
      updatePhoneCode();
      loadRegionSuggestions();
    };
    input.addEventListener("focus", () => renderResults(input, box, countryNames, pick));
    input.addEventListener("input", () => {
      renderResults(input, box, countryNames, pick);
      updatePhoneCode();
      loadRegionSuggestions();
    });
    input.addEventListener("blur", () => window.setTimeout(() => closeResults(box), 120));
  };

  const updatePhoneCode = () => {
    const selected = activeCountry();
    if (phoneCode && selected?.phoneCode) phoneCode.value = selected.phoneCode;
  };

  const loadRegionSuggestions = () => {
    if (!region) return;
    const record = activeCountry();
    const regionItems = isNamibia() ? namibiaRegions : (record?.regions || []);
    region.dataset.suggestions = JSON.stringify(regionItems);
    log("region suggestions loaded", { country: record?.country || currentCountry.value || countryOrigin.value, count: regionItems.length });
  };

  const setupRegionSearch = () => {
    if (!region) return;
    const box = document.getElementById("region_results");
    const render = () => {
      let items = [];
      try {
        items = JSON.parse(region.dataset.suggestions || "[]");
      } catch {
        items = [];
      }
      renderResults(region, box, items, () => renderTownSuggestions());
    };
    region.addEventListener("focus", render);
    region.addEventListener("input", () => {
      render();
      renderTownSuggestions();
    });
    region.addEventListener("blur", () => window.setTimeout(() => closeResults(box), 120));
  };

  const renderTownSuggestions = () => {
    if (!town) return;
    const box = document.getElementById("town_results");
    const record = activeCountry();
    let towns = [];
    if (isNamibia()) {
      const regionKey = namibiaRegions.find((item) => normalize(item) === normalize(region.value));
      towns = regionKey ? (window.CHAIN_NAMIBIA_TOWNS?.[regionKey] || []) : ["Windhoek"];
    } else if (record?.towns && typeof record.towns === "object") {
      towns = Object.values(record.towns).flat();
    }
    renderResults(town, box, towns, null);
  };

  const setupTownSearch = () => {
    if (!town) return;
    const box = document.getElementById("town_results");
    town.addEventListener("focus", renderTownSuggestions);
    town.addEventListener("input", renderTownSuggestions);
    town.addEventListener("blur", () => window.setTimeout(() => closeResults(box), 120));
  };

  const availabilityReady = (field, value) => {
    if (field === "email") return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    if (field === "phone") return value.replace(/\D/g, "").length >= 6;
    if (field === "username") return value.trim().length >= 3;
    return false;
  };

  const setAvailability = (field, payload) => {
    const node = document.getElementById(`availability_${field}`);
    if (!node) return;
    node.textContent = payload.message || "";
    node.classList.toggle("is-available", Boolean(payload.available));
    node.classList.toggle("is-unavailable", payload.available === false);
    availabilityState[field] = Boolean(payload.available);

    const suggestionNode = document.getElementById(`suggestions_${field}`);
    if (suggestionNode) {
      suggestionNode.innerHTML = "";
      (payload.suggestions || []).forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = item;
        button.addEventListener("click", () => {
          const input = document.getElementById(`register_${field}`);
          if (input) input.value = item;
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
        const value = input?.value.trim() || "";
        if (!availabilityReady(field, value)) {
          availabilityState[field] = null;
          return;
        }
        try {
          const params = new URLSearchParams({ field, value, town: town?.value || "" });
          const response = await fetch(`/auth/check-availability?${params.toString()}`);
          const payload = await response.json();
          setAvailability(field, payload);
        } catch (error) {
          console.error("[NamVibe register] availability check failed", error);
        }
      }, 700);
    };
  };

  const passwordScore = () => {
    if (!password) return 0;
    const value = password.value || "";
    let score = 0;
    if (value.length >= 8) score += 1;
    if (value.length >= 12) score += 1;
    if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1;
    if (/[0-9]/.test(value)) score += 1;
    if (/[^A-Za-z0-9]/.test(value)) score += 1;
    return score;
  };

  const passwordStrength = () => {
    if (!strengthText || !password) return;
    const score = passwordScore();
    const width = Math.min(score * 20, 100);
    strengthBar.style.width = `${width}%`;
    strengthBar.dataset.score = String(score);
    if (score >= 4) {
      strengthText.textContent = "Strong password.";
      strengthText.classList.add("is-strong");
      strengthText.classList.remove("is-weak");
    } else if ((password.value || "").length >= 8) {
      strengthText.textContent = "Good enough. Add numbers or symbols for extra strength.";
      strengthText.classList.remove("is-weak", "is-strong");
    } else {
      strengthText.textContent = "Use at least 8 characters.";
      strengthText.classList.add("is-weak");
      strengthText.classList.remove("is-strong");
    }
  };

  const validateConfirmPassword = () => {
    if (!password || !confirmPassword || !confirmStatus) return;
    const hasConfirm = Boolean(confirmPassword.value);
    const match = password.value && hasConfirm && password.value === confirmPassword.value;
    confirmStatus.textContent = match ? "Passwords match." : (hasConfirm ? "Passwords must match." : "");
    confirmStatus.classList.toggle("is-available", Boolean(match));
    confirmStatus.classList.toggle("is-unavailable", !match && hasConfirm);
    validateSubmit();
  };

  const requiredForStep = (index) => {
    const step = steps[index];
    if (!step) return [];
    return Array.from(step.querySelectorAll("input[required], select[required], textarea[required]")).filter((input) => !input.disabled && !input.hidden);
  };

  const showStepMessage = (message) => {
    if (!message) {
      if (stepMessage) {
        stepMessage.textContent = "";
        stepMessage.hidden = true;
      }
      return;
    }
    if (stepMessage) {
      stepMessage.textContent = message;
      stepMessage.hidden = false;
    }
    console.warn("[NamVibe register] validation blocked", message);
  };

  const stepValid = (index, report = false) => {
    const step = steps[index];
    if (!step) return false;
    const required = requiredForStep(index);
    const firstInvalid = required.find((input) => {
      if (input.type === "checkbox") return !input.checked;
      return !input.value.trim() || !input.checkValidity();
    });
    if (firstInvalid) {
      const label = firstInvalid.closest("label")?.querySelector("span")?.textContent?.replace("*", "").trim();
      const message = firstInvalid.validationMessage || `${label || firstInvalid.name || "This field"} is required.`;
      if (report) {
        showStepMessage(message);
        firstInvalid.focus();
        firstInvalid.reportValidity?.();
      }
      return false;
    }
    if (step.dataset.stepName === "password") {
      const ok = password.value.length >= 8 && password.value === confirmPassword.value;
      if (!ok && report) {
        const message = password.value.length < 8 ? "Password must be at least 8 characters." : "Passwords must match.";
        showStepMessage(message);
        (confirmPassword.value ? confirmPassword : password).reportValidity?.();
      }
      return ok;
    }
    if (report) showStepMessage("");
    return true;
  };

  const validateSubmit = () => {
    const allStepsValid = steps.every((_, index) => stepValid(index));
    submitBtn.disabled = !allStepsValid;
  };

  const setStep = (index) => {
    stepIndex = Math.max(0, Math.min(index, steps.length - 1));
    steps.forEach((step, idx) => step.classList.toggle("is-active", idx === stepIndex));
    stepDots.forEach((dot, idx) => {
      dot.classList.toggle("is-active", idx === stepIndex);
      dot.classList.toggle("is-complete", idx < stepIndex);
    });
    progressText.textContent = `Step ${stepIndex + 1} of ${steps.length}`;
    progressBar.style.width = `${((stepIndex + 1) / steps.length) * 100}%`;
    prevBtn.style.visibility = stepIndex === 0 ? "hidden" : "visible";
    nextBtn.style.display = stepIndex === steps.length - 1 ? "none" : "inline-flex";
    nextBtn.textContent = stepIndex === 0 ? "Get Started" : "Continue";
    submitBtn.style.display = stepIndex === steps.length - 1 ? "inline-flex" : "none";
    log("step changed", { step: stepIndex + 1 });
    showStepMessage("");
    validateSubmit();
  };

  form.querySelectorAll(".toggle-password").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.target);
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
      button.textContent = input.type === "password" ? "Show" : "Hide";
    });
  });

  document.getElementById("register_username")?.addEventListener("input", debounceCheck("username"));
  document.getElementById("register_email")?.addEventListener("input", debounceCheck("email"));
  document.getElementById("register_phone")?.addEventListener("input", debounceCheck("phone"));
  password?.addEventListener("input", () => {
    passwordStrength();
    validateConfirmPassword();
  });
  confirmPassword?.addEventListener("input", validateConfirmPassword);
  form.querySelectorAll("input").forEach((input) => input.addEventListener("input", validateSubmit));
  form.querySelectorAll("input[type='checkbox']").forEach((input) => input.addEventListener("change", validateSubmit));
  form.querySelectorAll("[data-select-signup]").forEach((button) => {
    button.addEventListener("click", () => {
      const method = button.dataset.selectSignup || "email";
      if (signupMethod) signupMethod.value = method;
      form.querySelectorAll("[data-select-signup]").forEach((item) => item.classList.toggle("is-selected", item === button));
      log("signup method selected", method);
      validateSubmit();
    });
  });

  nextBtn?.addEventListener("click", () => {
    const currentStep = stepIndex + 1;
    const nextStep = Math.min(steps.length, stepIndex + 2);
    console.log("NEXT CLICKED");
    console.log("CURRENT STEP", currentStep);
    console.log("GOING TO STEP", nextStep);
    if (!stepValid(stepIndex, true)) return;
    setStep(stepIndex + 1);
  });
  prevBtn?.addEventListener("click", () => setStep(stepIndex - 1));
  stepDots.forEach((dot) => {
    dot.addEventListener("click", () => {
      const target = Number(dot.dataset.jumpStep || 0);
      if (target <= stepIndex || steps.slice(0, target).every((_, index) => stepValid(index, true))) {
        setStep(target);
      }
    });
  });

  form.addEventListener("submit", (event) => {
    if (!steps.every((_, index) => stepValid(index, true))) {
      event.preventDefault();
      return;
    }
    log("submit started");
    form.classList.add("is-submitting");
    if (successPanel) successPanel.classList.add("is-visible");
    submitBtn.disabled = true;
    submitBtn.textContent = "Creating account...";
    window.setTimeout(() => log("submit finished"), 0);
  });

  setupCountrySearch(countryOrigin);
  setupCountrySearch(currentCountry);
  setupRegionSearch();
  setupTownSearch();
  updatePhoneCode();
  loadRegionSuggestions();
  passwordStrength();
  setStep(0);
})();
