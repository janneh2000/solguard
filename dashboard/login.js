const form = document.querySelector("#login-form");
const emailInput = document.querySelector("#login-email");
let submitTimer = null;

const mockSubmit = (event) => {
  event.preventDefault();

  if (!form.reportValidity()) {
    return;
  }

  window.clearTimeout(submitTimer);
  form.classList.remove("is-blocked");
  form.classList.add("is-submitting");

  submitTimer = window.setTimeout(() => {
    form.classList.remove("is-submitting");
    form.classList.add("is-blocked");
    emailInput.blur();
  }, 650);
};

form.addEventListener("submit", mockSubmit);
