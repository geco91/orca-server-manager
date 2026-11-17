'use strict';
(() => {
  const panel = document.querySelector('#web-pairing');
  if (!panel) return;
  const status = document.querySelector('#pairing-status');
  const form = document.querySelector('#pairing-form');
  const submit = form.querySelector('button');
  const unavailable = submit.disabled;
  function setBusy(busy) {
    panel.setAttribute('aria-busy', String(busy));
    status.classList.toggle('busy-text', busy);
    submit.classList.toggle('busy-text', busy);
    submit.disabled = busy || unavailable;
    submit.textContent = busy ? 'Preparing pairing link…' : 'Prepare pairing link';
  }
  form.addEventListener('submit', () => {
    setBusy(true);
    status.textContent = 'Preparing your pairing link. This can take a few seconds…';
  });
  setBusy(Boolean(panel.dataset.statusUrl));
  if (!panel.dataset.statusUrl) return;
  let attempts = 0;
  async function poll() {
    try {
      const response = await fetch(panel.dataset.statusUrl, {credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error();
      const data = await response.json();
      if (data.state === 'ready') {
        const target = new URL(data.pairing.browser_url);
        if (target.origin !== location.origin || target.pathname !== '/orca/web-index.html' || target.search || new URLSearchParams(target.hash.slice(1)).get('pairing') !== data.pairing.pairing_url) throw new Error();
        document.querySelector('#pairing-url').value = data.pairing.pairing_url;
        document.querySelector('#pairing-code').value = data.pairing.code;
        document.querySelector('#pairing-open').href = target.href;
        document.querySelector('#pairing-ready').hidden = false;
        setBusy(false);
        status.textContent = 'Your private pairing link is ready. Orca will confirm when this browser is connected.';
        if (panel.dataset.autoOpen === 'true') location.replace(target.href);
        return;
      }
      status.textContent = data.message || 'Requesting the native Orca pairing link…';
      if (['expired','failed'].includes(data.state)) {setBusy(false); return;}
      if (++attempts < 125) setTimeout(poll, 1000);
      else {setBusy(false); status.textContent = 'The worker has not finished yet. Refresh the server status and prepare another link.';}
    } catch {
      setBusy(false);
      status.textContent = 'The connection link could not be loaded. Check that you are signed in and try preparing it again.';
    }
  }
  panel.addEventListener('click', async event => {
    const button = event.target.closest('[data-copy]');
    if (!button) return;
    const field = document.getElementById(button.dataset.copy);
    try {await navigator.clipboard.writeText(field.value); status.textContent = 'Copied. Paste it into Orca’s “Pairing URL or code” field.';}
    catch {field.focus(); field.select(); status.textContent = 'The link is selected. Copy it and paste it into Orca.';}
  });
  poll();
})();
