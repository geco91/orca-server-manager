'use strict';
(() => {
  const panel = document.querySelector('#forge-login');
  const start = document.querySelector('#forge-start');
  const button = start.querySelector('button');
  const disabled = button.disabled;
  const feedback = document.querySelector('#forge-status');
  const offer = document.querySelector('#offer');
  const value = document.querySelector('#offer-value');
  const copy = document.querySelector('#copy-offer');

  function busy(running) {
    button.disabled = disabled || running;
    button.classList.toggle('busy-text', running);
    start.setAttribute('aria-busy', String(running));
  }
  start.addEventListener('submit', () => {
    busy(true);
    offer.hidden = true;
    value.value = '';
    feedback.textContent = 'Waiting for the server…';
  });
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(value.value); copy.textContent = 'Copied'; }
    catch { value.focus(); value.select(); }
  });

  const instance = document.querySelector('#forge-instance');
  if (instance) {
    function instanceLinks() {
      const links = document.querySelector('#instance-links');
      links.hidden = true;
      try {
        const url = new URL(instance.value.trim());
        if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) return;
        if (!url.pathname.endsWith('/')) url.pathname += '/';
        document.querySelector('#forge-keys').href = new URL('user/settings/keys', url).href;
        document.querySelector('#forge-signup').href = new URL('user/sign_up', url).href;
        links.hidden = false;
      } catch { /* Keep links hidden until the address is valid. */ }
    }
    try { instance.value = sessionStorage.getItem('osm.forgejo.instance') || ''; } catch {}
    instanceLinks();
    instance.addEventListener('input', () => {
      instanceLinks();
      try {
        if (document.querySelector('#instance-links').hidden) sessionStorage.removeItem('osm.forgejo.instance');
        else sessionStorage.setItem('osm.forgejo.instance', instance.value.trim());
      } catch {}
    });
  }

  if (!panel.dataset.progress) return;
  const messages = {
    starting: 'Requesting a code from your Git provider…',
    waiting: 'Enter this code on the provider’s authorization page.',
    authorized: 'Connected. The server is signed in and Git is configured.',
    key_ready: 'Public key ready. Add it to your Forgejo account.',
    failed: 'Sign-in could not finish. Try again or use the runtime terminal.',
    expired: 'This request expired. Start a new request.',
    unavailable: 'Waiting for the deployment worker…',
  };
  if (instance) messages.starting = 'Preparing the runtime’s public SSH key…';
  const deadline = Date.now() + 605_000;
  async function poll() {
    try {
      const res = await fetch(panel.dataset.progress, {cache: 'no-store', credentials: 'same-origin'});
      if (!res.ok || !res.headers.get('content-type')?.includes('application/json')) throw new Error();
      const data = await res.json();
      let state = Object.hasOwn(messages, data.state) ? data.state : 'failed';
      if (Date.now() >= deadline && ['starting', 'waiting', 'unavailable'].includes(state)) state = 'expired';
      const pending = ['starting', 'waiting', 'unavailable'].includes(state);
      const text = state === 'waiting' ? data.code : state === 'key_ready' ? data.public_key : '';
      if (value.value !== (text || '')) value.value = text || '';
      offer.hidden = !text;
      feedback.textContent = messages[state];
      feedback.classList.toggle('busy-text', pending && state !== 'waiting');
      busy(pending);
      if (pending) setTimeout(poll, 2500);
    } catch {
      busy(false);
      feedback.classList.remove('busy-text');
      value.value = '';
      offer.hidden = true;
      feedback.textContent = 'The request could not be read. Reload this page to check it again.';
    }
  }
  busy(true);
  poll();
})();
