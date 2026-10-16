document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".application-form");
  if (!form) return;

  const steps = [...form.querySelectorAll(".form-step")];
  const indicators = [...document.querySelectorAll("[data-step-indicator]")];
  const previous = form.querySelector("[data-previous]");
  const next = form.querySelector("[data-next]");
  const finish = form.querySelector("[data-finish]");
  let currentStep = 0;

  const setStep = (index) => {
    currentStep = index;
    steps.forEach((step, stepIndex) => {
      step.hidden = stepIndex !== currentStep;
    });
    indicators.forEach((indicator, stepIndex) => {
      indicator.classList.toggle("is-current", stepIndex === currentStep);
      indicator.classList.toggle("is-complete", stepIndex < currentStep);
      if (stepIndex === currentStep)
        indicator.setAttribute("aria-current", "step");
      else indicator.removeAttribute("aria-current");
    });
    previous.hidden = currentStep === 0;
    next.hidden = currentStep === steps.length - 1;
    finish.hidden = currentStep !== steps.length - 1;
  };

  const validateStep = (index) => {
    for (const field of steps[index].querySelectorAll(
      "input, textarea, select",
    )) {
      if (field.required && !field.checkValidity()) {
        field.reportValidity();
        return false;
      }
      if (field.type === "file") {
        const file = field.files[0];
        const isPdf =
          !file ||
          file.type === "application/pdf" ||
          file.name.toLowerCase().endsWith(".pdf");
        field.setCustomValidity(
          file && !isPdf ? "Veuillez choisir un fichier PDF." : "",
        );
        if (file && !isPdf) {
          field.reportValidity();
          return false;
        }
        if (file && file.size > 5 * 1024 * 1024) {
          field.setCustomValidity("Le fichier ne doit pas dépasser 5 Mo.");
          field.reportValidity();
          return false;
        }
      }
    }
    return true;
  };

  const updateSummary = () => {
    const selected = form.querySelector('input[name="formation"]:checked');
    const label = selected
      ?.closest(".course-option")
      ?.querySelector(".course-label")
      ?.textContent.trim();
    document.querySelector("#review-formation").textContent =
      label || "Choisissez une formation";
    document.querySelector("#side-formation").textContent =
      label || "Aucune formation sélectionnée";
    document.querySelector("#review-name").textContent =
      form.elements.nom_prenom.value || "—";
    document.querySelector("#review-email").textContent =
      form.elements.email.value || "—";
    document.querySelector("#review-phone").textContent =
      form.elements.telephone.value || "—";
    document.querySelector("#review-cv").textContent =
      form.elements.cv.files[0]?.name || "À joindre";
    document.querySelector("#review-diploma").textContent =
      form.elements.diplome.files[0]?.name || "Non ajouté";
  };

  form.addEventListener("input", updateSummary);
  form.addEventListener("change", (event) => {
    if (event.target.name === "formation") {
      form.querySelectorAll(".course-option").forEach((option) => {
        option.classList.toggle("is-selected", option.contains(event.target));
      });
    }
    updateSummary();
  });
  next.addEventListener("click", () => {
    if (validateStep(currentStep)) {
      updateSummary();
      setStep(Math.min(currentStep + 1, steps.length - 1));
    }
  });
  previous.addEventListener("click", () =>
    setStep(Math.max(currentStep - 1, 0)),
  );
  finish.addEventListener("click", () => {
    for (let index = 0; index < steps.length - 1; index += 1) {
      if (!validateStep(index)) {
        setStep(index);
        return;
      }
    }
    document.querySelector(".local-only-note").focus();
  });

  updateSummary();
  setStep(currentStep);
});
