const modal = document.querySelector("#waitlist-modal");
const form = document.querySelector("#waitlist-form");
const emailInput = document.querySelector("#waitlist-email");
const openButtons = document.querySelectorAll("[data-open-waitlist]");
const closeButtons = document.querySelectorAll("[data-close-waitlist]");
const scrollLinks = document.querySelectorAll("[data-scroll-target]");
const howSection = document.querySelector("#how-it-works");
let previousFocus = null;
let submitTimer = null;

const openModal = (event) => {
  event?.preventDefault();
  previousFocus = document.activeElement;
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  window.setTimeout(() => emailInput.focus(), 80);
};

const closeModal = () => {
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  window.clearTimeout(submitTimer);
  form.classList.remove("is-submitting");
  previousFocus?.focus?.();
};

const mockSubmit = (event) => {
  event.preventDefault();

  if (!form.reportValidity()) {
    return;
  }

  form.classList.remove("is-success");
  form.classList.add("is-submitting");

  submitTimer = window.setTimeout(() => {
    form.classList.remove("is-submitting");
    form.classList.add("is-success");
  }, 650);
};

openButtons.forEach((button) => {
  button.addEventListener("click", openModal);
});

closeButtons.forEach((button) => {
  button.addEventListener("click", closeModal);
});

form.addEventListener("submit", mockSubmit);

const easeInOutCubic = (progress) => {
  return progress < 0.5
    ? 4 * progress * progress * progress
    : 1 - Math.pow(-2 * progress + 2, 3) / 2;
};

const smoothScrollTo = (target) => {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const startY = window.scrollY;
  const targetY = target.getBoundingClientRect().top + window.scrollY - 20;
  const distance = targetY - startY;
  const duration = prefersReducedMotion ? 0 : 720;
  const startTime = performance.now();

  if (!duration) {
    window.scrollTo(0, targetY);
    target.classList.add("is-visible");
    return;
  }

  const tick = (now) => {
    const elapsed = Math.min((now - startTime) / duration, 1);
    const eased = easeInOutCubic(elapsed);
    window.scrollTo(0, startY + distance * eased);

    if (elapsed < 1) {
      window.requestAnimationFrame(tick);
    } else {
      target.classList.add("is-visible");
    }
  };

  window.requestAnimationFrame(tick);
};

scrollLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const target = document.getElementById(link.dataset.scrollTarget);

    if (target) {
      smoothScrollTo(target);
    }
  });
});

if (howSection) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        howSection.classList.add("is-visible");
        observer.disconnect();
      }
    });
  }, { threshold: 0.28 });

  observer.observe(howSection);
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && modal.getAttribute("aria-hidden") === "false") {
    closeModal();
  }
});
