'use strict';
(() => {
  const panel = document.querySelector('#web-pairing');
  if (!panel?.dataset.statusUrl) return;
  const status = document.querySelector('#pairing-status');
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
        status.textContent = 'Your private pairing link is ready. Orca will confirm when this browser is connected.';
        if (panel.dataset.autoOpen === 'true') location.replace(target.href);
        return;
      }
      status.textContent = data.message || 'Requesting the native Orca pairing link…';
      if (['expired','failed'].includes(data.state)) return;
      if (++attempts < 125) setTimeout(poll, 1000);
      else status.textContent = 'The worker has not finished yet. Refresh the server status and prepare another link.';
    } catch {
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
