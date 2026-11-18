'use strict';
(() => {
  const panel = document.querySelector('#forge-login');
  const setup = document.querySelector('#git-setup');
  const signedInAtLoad = setup.classList.contains('signed-in');
  const next = document.querySelector('#forge-continue');
  const start = document.querySelector('#forge-start');
  const signInButtons = Array.from(start.elements).filter(control => control.type === 'submit');
  const disabled = signInButtons[0].disabled;
  const feedback = document.querySelector('#forge-status');
  const offer = document.querySelector('#offer');
  const value = document.querySelector('#offer-value');

  function busy(running) {
    for (const button of signInButtons) {
      button.disabled = disabled || running;
      button.classList.toggle('busy-text', running);
    }
    start.setAttribute('aria-busy', String(running));
  }
  start.addEventListener('submit', () => {
    busy(true);
    offer.hidden = true;
    value.value = '';
    feedback.textContent = 'Waiting for the server…';
  });
  for (const copy of offer.querySelectorAll('button[data-copy]')) {
    const field = document.getElementById(copy.dataset.copy);
    const label = copy.textContent;
    let resetLabel;
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(field.value); copy.textContent = 'Copied'; }
      catch { field.focus(); field.select(); copy.textContent = 'Text selected'; }
      clearTimeout(resetLabel);
      resetLabel = setTimeout(() => { copy.textContent = label; }, 2000);
    });
  }

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
      const signedIn = state === 'authorized' || (signedInAtLoad && !['starting', 'waiting'].includes(state));
      setup.classList.toggle('signed-in', signedIn);
      next?.classList.toggle('quiet', !signedIn);
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
