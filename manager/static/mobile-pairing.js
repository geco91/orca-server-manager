'use strict';
document.querySelector('#mobile-form')?.addEventListener('submit', event => {
  const form = event.currentTarget;
  const button = form.querySelector('button');
  form.setAttribute('aria-busy', 'true');
  button.classList.add('busy-text');
  button.textContent = 'Preparing QR code…';
  button.disabled = true;
});
