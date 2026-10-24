(() => {
  'use strict';
  const steps = [
    { id: 'server', title: 'Server prüfen', detail: 'Runtime, Verzeichnisse und Netzwerk vorbereiten.' },
    { id: 'providers', title: 'Agent-Provider', detail: 'Codex oder OpenCode mit dem Server verbinden.' },
    { id: 'github', title: 'GitHub verbinden', detail: 'Konto und Repository-Zugriff einrichten.' },
    { id: 'desktop', title: 'Mac-Desktop', detail: 'Deinen Orca-Desktop mit dem Server verbinden.' },
    { id: 'mobile', title: 'Mobile-App', detail: 'Orca von unterwegs über dein VPN erreichen.' },
    { id: 'mcp', title: 'MCP Bridge', detail: 'Den Zugang für externe Koordinatoren vorbereiten.' },
    { id: 'tunnel', title: 'Secure MCP Tunnel', detail: 'Die bestehende Tunnelverbindung prüfen.' },
  ];
  const app = document.querySelector('#app');
  let state;
  let pending = 0;
  const pill = '<span class="demo-pill">SIMULIERT</span>';

  function reset(scenario = 'fresh') {
    pending += 1; // Invalidate a previous delayed result before changing scenarios.
    state = {
      page: 'overview', scenario, statuses: Object.fromEntries(steps.map(s => [s.id, 'unknown'])),
      providers: { codex: false, opencode: false }, pairing: null, busy: false,
      runtimeFailure: scenario === 'runtime-error', tunnelFailure: scenario === 'tunnel-error',
    };
    if (scenario === 'ready' || scenario === 'tunnel-error') {
      steps.forEach(s => { state.statuses[s.id] = 'done'; });
      state.providers = { codex: true, opencode: true };
    }
    if (scenario === 'runtime-error') state.statuses.server = 'error';
    if (scenario === 'tunnel-error') state.statuses.tunnel = 'error';
    document.querySelector('#scenario').value = scenario;
    render();
  }

  function badge(id) {
    const status = state.statuses[id];
    const labels = { unknown: 'Noch nicht eingerichtet', done: 'Bereit · Demo', skipped: 'Für später', error: 'Fehler · Demo' };
    return `<span class="badge ${status}">${labels[status]}</span>`;
  }

  function notify(text) { document.querySelector('#announcer').textContent = text; }

  function overview() {
    const count = Object.values(state.statuses).filter(s => s === 'done').length;
    const complete = count === steps.length;
    const runtime = state.statuses.server;
    const runtimeText = { done: 'Bereit für deine Projekte', error: 'Orca startet nicht', unknown: 'Dein Server wartet auf die Prüfung', skipped: 'Noch nicht geprüft' }[runtime];
    return `
      <div class="heading-row"><div><span class="eyebrow">DEIN ENTWICKLUNGSSERVER</span>
      <h1>${complete ? 'Dein Server ist startklar.' : 'Alles beginnt mit einer Verbindung.'}</h1>
      <p>${complete ? 'Alle Verbindungen sind in diesem Demo-Szenario eingerichtet.' : 'Richte Orca Schritt für Schritt ein. Alles Weitere kannst du später ergänzen.'}</p></div>${pill}</div>
      ${complete ? '<div class="complete-note"><span class="complete-icon">✓</span><span>Setup durchgespielt. Du kannst einzelne Schritte erneut öffnen.</span></div>' : ''}
      <section class="summary"><div class="panel"><span class="eyebrow">ORCA RUNTIME · DEMO</span>
      <h2><span class="dot ${runtime === 'done' ? 'reachable' : runtime}"></span>${runtimeText}</h2>
      <p>${runtime === 'error' ? 'Im Fehlerszenario fehlt ein schreibbares Datenverzeichnis. Öffne die Serverprüfung, um die Behebung zu simulieren.' : 'Orca 1.4.239 · Debian 13 · 4 vCPU · 8 GB RAM. Beispieldaten für deine Pilot-VM.'}</p>
      <div class="button-row"><button data-action="start">${complete ? 'Einrichtung ansehen' : 'Einrichtung starten'}</button><button class="quiet" data-action="open" data-step="server">Server prüfen</button></div></div>
      <div class="panel"><span class="eyebrow">DEIN FORTSCHRITT</span><h2>${count} von 7 Verbindungen bereit</h2>
      <p>Optionale Schritte lassen sich überspringen. Der Server kann unabhängig davon verwendet werden.</p>
      <div class="progress-track"><span style="width:${Math.round(count / 7 * 100)}%"></span></div><div class="progress-copy"><span>Nur Demo-Zustände</span><span>${Math.round(count / 7 * 100)} %</span></div></div></section>
      <h2 class="section-title">Setup & Verbindungen</h2><div class="steps overview-list">${steps.map((s, i) => `
        <article class="panel step"><span class="number">${String(i + 1).padStart(2, '0')}</span><div class="step-body"><div class="step-title"><h3>${s.title}</h3>${badge(s.id)}</div><p>${s.detail}</p><div class="actions"><button class="step-link" data-action="open" data-step="${s.id}">Einrichtung öffnen →</button></div></div></article>`).join('')}</div>`;
  }

  function rows(items, good = false) {
    return `<div class="checks">${items.map(([name, value]) => `<div class="check-row ${good ? 'good' : ''}"><span>${name}</span><span>${value}</span></div>`).join('')}</div>`;
  }

  function message(title, detail, type = '') {
    return `<div class="notice ${type}" role="status"><strong>${title}</strong><p>${detail}</p></div>`;
  }

  function qrSample() {
    // Deliberately not a QR encoder or a live pairing code.
    return '<svg class="qr-sample" viewBox="0 0 100 100" role="img" aria-label="Nicht scannbares QR-Beispiel mit DEMO-Aufschrift"><g fill="#13352b"><path d="M0 0h30v30H0zM70 0h30v30H70zM0 70h30v30H0z"/><path fill="#deebe5" d="M6 6h18v18H6zM76 6h18v18H76zM6 76h18v18H6z"/><path d="M12 12h6v6h-6zM82 12h6v6h-6zM12 82h6v6h-6zM40 0h8v8h-8zM52 10h8v8h-8zM38 22h10v8H38zM70 76h8v8h-8zM84 86h12v12H84zM42 84h8v14h-8zM57 72h8v8h-8zM0 42h9v8H0zM88 40h12v10H88z"/></g><rect x="1" y="35" width="98" height="30" fill="#deebe5"/><text x="50" y="55" text-anchor="middle" font-family="sans-serif" font-size="17" font-weight="700" fill="#13352b">DEMO</text></svg>';
  }

  function content(id) {
    const done = state.statuses[id] === 'done';
    if (id === 'server') {
      const error = state.statuses.server === 'error';
      return `<p>Prüfe zuerst, ob Orca läuft und seine Daten dauerhaft speichern kann.</p>
        ${rows([['Orca Headless Runtime', done ? '✓ Orca 1.4.239' : error ? 'Nicht gestartet' : 'Prüfung ausstehend'], ['Persistente Daten', done ? '✓ Verfügbar und schreibbar' : error ? 'Schreibrechte fehlen' : 'Noch nicht geprüft'], ['Workspace-Speicher', done ? '✓ 52 GB verfügbar' : 'Noch nicht geprüft'], ['Netzwerk & HTTPS', done ? '✓ Bereit im Demo-Netz' : 'Noch nicht geprüft']], done)}
        ${error ? message('Das Datenverzeichnis ist nicht schreibbar.', 'Im Beispiel hat der Runtime-Benutzer keine Schreibrechte auf sein Datenvolume. Wir können die Korrektur und den erneuten Start simulieren.', 'error') : done ? message('Die Basis ist bereit.', 'Du kannst jetzt Provider und Clients verbinden. Alle Ergebnisse auf dieser Seite sind simuliert.') : ''}
        <button data-action="${error ? 'repair' : 'verify'}" data-step="server">${error ? 'Behebung simulieren & erneut prüfen' : done ? 'Prüfung wiederholen' : 'Server jetzt prüfen'}</button>`;
    }
    if (id === 'providers') {
      return `<p>Verbinde mindestens einen Coding-Agenten. In der echten Installation verwenden wir den nativen Login des jeweiligen Anbieters.</p><div class="provider-grid">${[['codex', 'OpenAI Codex', 'C'], ['opencode', 'OpenCode', 'OC']].map(([key, title, icon]) => `<section class="provider ${state.providers[key] ? 'connected' : ''}"><span class="provider-icon">${icon}</span><h2>${title}</h2><p>${state.providers[key] ? '<span class="connected-label">✓ Verbunden · Demo</span>' : 'Anbieter verbinden und die Verfügbarkeit prüfen.'}</p><button class="quiet" data-action="provider" data-provider="${key}">${state.providers[key] ? 'Demo-Verbindung trennen' : 'Anmeldung simulieren'}</button></section>`).join('')}</div>${message('Keine Zugangsdaten erforderlich.', 'Ein Klick simuliert eine erfolgreiche native Anmeldung. Es wird kein echter Provider aufgerufen.')}`;
    }
    if (id === 'github') {
      return `<p>Verbinde dein GitHub-Konto und prüfe, ob Orca das gewünschte Repository lesen kann.</p><div class="account-card"><span class="avatar">g</span><div><strong>geco91</strong><p>geco91/orca-server-manager</p></div>${pill}</div>
        ${rows([['GitHub-Anmeldung', done ? '✓ Verbunden' : 'Nicht angemeldet'], ['Repository lesen', done ? '✓ Zugriff bestätigt' : 'Noch nicht geprüft'], ['Schreib- und PR-Rechte', done ? '✓ Im Demo-Szenario vorhanden' : 'Noch nicht geprüft']], done)}
        ${done ? message('GitHub ist im Demo-Szenario verbunden.', 'In der echten Einrichtung werden Lese-, Schreib- und API-Zugriff getrennt geprüft.') : ''}<button data-action="verify" data-step="github">${done ? 'Verbindung erneut simulieren' : 'Mit GitHub verbinden · Demo'}</button>`;
    }
    if (id === 'desktop' || id === 'mobile') {
      const mobile = id === 'mobile';
      return `<p>${mobile ? 'Öffne Orca Mobile und verbinde dein Smartphone über LAN oder VPN mit dem Server.' : 'Verbinde die Orca-App auf deinem Mac mit dem Headless-Server. Deine Projekte und Agenten bleiben auf dem Server.'}</p>
        ${done ? message(`${mobile ? 'Mobilgerät' : 'Mac-Desktop'} verbunden · Demo`, `Der Beispiel-Client „${mobile ? 'Tinos iPhone' : 'Tinos MacBook'}“ ist in dieser Simulation verbunden.`) : state.pairing === id ? `<div class="pairing-card">${mobile ? qrSample() : '<span class="provider-icon">Mac</span>'}<div><h2>${mobile ? 'Pairing in Orca Mobile' : 'Server zum Mac hinzufügen'}</h2><div class="pairing-code">ORCA-DEMO</div><p>Nur eine Darstellung. Kein gültiger Pairing-Link und kein scannbarer Code.</p><button data-action="verify" data-step="${id}">Client-Verbindung simulieren</button></div></div>` : `<div class="checks"><div class="check-row"><span>${mobile ? 'Mobile-App' : 'Mac-Desktop'}</span><span>Noch kein Client verbunden</span></div></div><button data-action="pair" data-step="${id}">Pairing-Vorschau öffnen</button>`}
        ${message('Auf demselben LAN oder VPN.', 'Bei der echten Verbindung müssen Client und Server einander erreichen können. Pairing-Zugangsdaten bleiben vertraulich.', 'warn')}`;
    }
    if (id === 'mcp') {
      return `<p>Die Community-Bridge verbindet externe KI-Koordinatoren mit Orca. Beginne mit einem lesenden Funktionstest.</p>
        ${rows([['Community-Bridge', 'orca-mcp 0.3.0 · Beispieldaten'], ['Berechtigungen', 'Nur Status / lesend'], ['Erreichbarkeit & Runtime', done ? '✓ MCP und Orca erreichbar · Demo' : 'Noch nicht geprüft']], done)}
        ${done ? '<div class="preview-terminal"><div class="small-label">SIMULIERTE PROTOKOLLANTWORT</div><div class="ok">✓ initialize</div><div class="ok">✓ tools/list → orca</div><div class="ok">✓ orca · action: health</div><div>Es wurde kein Agent gestartet.</div></div>' : ''}
        <button data-action="verify" data-step="mcp">${done ? 'MCP-Test wiederholen' : 'MCP-Verbindung prüfen · Demo'}</button>`;
    }
    const error = state.statuses.tunnel === 'error';
    const bridgeReady = state.statuses.mcp === 'done';
    return `<p>Verbinde den vorhandenen Secure MCP Tunnel mit der Bridge. Der Manager nutzt dessen bestehende Authentifizierung.</p>
      ${rows([['MCP Bridge', bridgeReady ? '✓ Im Demo-Szenario bereit' : 'Zuerst Bridge prüfen'], ['Tunnel', done ? '✓ Verbunden · Demo' : error ? 'Authentifizierung fehlgeschlagen' : 'Noch nicht geprüft'], ['Funktionaler MCP-Test', done ? '✓ Erfolgreich · Demo' : 'Ausstehend']], done)}
      ${error ? message(bridgeReady ? 'Die Tunnel-Anmeldung wurde abgelehnt.' : 'Die MCP Bridge ist noch nicht bereit.', bridgeReady ? 'Im Demo-Szenario ist die Berechtigung abgelaufen. Simuliere die Erneuerung und prüfe die Verbindung erneut.' : 'Öffne zuerst den MCP-Schritt und führe dort den Funktionstest aus. Der Orca-Server kann unabhängig davon weiterlaufen.', 'error') : done ? message('Verbindungskette vollständig · Demo', 'Koordinator → Secure MCP Tunnel → MCP Bridge → Orca. Dies bestätigt ausschließlich das durchgespielte Szenario.') : ''}
      ${error && !bridgeReady ? '<button data-action="open" data-step="mcp">MCP Bridge einrichten</button>' : `<button data-action="${error ? 'repair' : 'verify'}" data-step="tunnel">${error ? 'Anmeldung erneuern · Demo' : done ? 'Verbindung erneut prüfen · Demo' : 'Tunnel verbinden & prüfen · Demo'}</button>`}`;
  }

  function wizard() {
    const index = steps.findIndex(s => s.id === state.page);
    const step = steps[index];
    return `<button class="back-button" data-action="overview">← Zur Übersicht</button><div class="wizard-layout"><nav class="wizard-nav" aria-label="Einrichtungsschritte">${steps.map((s, i) => `<button data-action="open" data-step="${s.id}" class="${state.page === s.id ? 'active' : ''} ${state.statuses[s.id]}" ${state.page === s.id ? 'aria-current="step"' : ''}><span class="nav-number">${state.statuses[s.id] === 'done' ? '✓' : i + 1}</span>${s.title}</button>`).join('')}<p class="nav-note">Du bestimmst die Reihenfolge. Optionale Verbindungen kannst du später ergänzen.</p></nav>
      <section class="panel wizard-panel"><div class="wizard-head"><span class="eyebrow">SCHRITT ${index + 1} VON 7</span>${pill}</div><h1 tabindex="-1">${step.title}</h1>
      ${content(step.id)}${state.busy ? '<p class="checking" role="status">Demo-Prüfung läuft …</p>' : ''}
      <p class="mock-caption">UI-Prototyp: Alle Aktionen auf dieser Seite verändern nur diese Demo.</p>
      <div class="wizard-actions"><button class="quiet" data-action="previous">${index === 0 ? 'Zur Übersicht' : 'Zurück'}</button><div class="right">${index > 0 ? '<button class="muted-button" data-action="skip">Später einrichten</button>' : ''}<button data-action="next">${index === 6 ? 'Zur Zusammenfassung' : 'Weiter →'}</button></div></div></section></div>`;
  }

  function render(focus = false) {
    app.innerHTML = state.page === 'overview' ? overview() : wizard();
    if (state.busy) {
      app.querySelectorAll('button').forEach(button => { button.disabled = true; });
    }
    if (focus) {
      const heading = app.querySelector('h1');
      heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
    }
  }

  function open(id) {
    pending += 1;
    state.busy = false;
    state.pairing = null;
    state.page = id;
    render(true);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function verify(id, repair = false) {
    if (state.busy) return;
    if (repair && id === 'server') state.runtimeFailure = false;
    if (repair && id === 'tunnel') state.tunnelFailure = false;
    const ticket = ++pending;
    state.busy = true;
    render();
    window.setTimeout(() => {
      if (pending !== ticket) return;
      const failed = (id === 'server' && state.runtimeFailure) ||
        (id === 'tunnel' && (state.tunnelFailure || state.statuses.mcp !== 'done'));
      state.statuses[id] = failed ? 'error' : 'done';
      state.busy = false;
      notify(failed ? 'Demo-Prüfung fehlgeschlagen.' : 'Demo-Verbindung erfolgreich.');
      render();
    }, 450);
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('button[data-action]');
    if (!button || button.disabled) return;
    const { action, step, provider } = button.dataset;
    const index = steps.findIndex(s => s.id === state.page);
    switch (action) {
      case 'help': document.querySelector('#demo-help').showModal(); break;
      case 'close-help': document.querySelector('#demo-help').close(); break;
      case 'reset': reset(); notify('Demo zurückgesetzt.'); break;
      case 'overview': open('overview'); break;
      case 'start': open(steps.find(s => state.statuses[s.id] === 'unknown' || state.statuses[s.id] === 'error')?.id ?? 'server'); break;
      case 'open': open(step); break;
      case 'previous': open(index === 0 ? 'overview' : steps[index - 1].id); break;
      case 'next': open(index === 6 ? 'overview' : steps[index + 1].id); break;
      case 'skip':
        state.statuses[state.page] = 'skipped';
        if (state.page === 'providers') state.providers = { codex: false, opencode: false };
        if (state.page === 'mcp' && state.statuses.tunnel === 'done') state.statuses.tunnel = 'unknown';
        open(index === 6 ? 'overview' : steps[index + 1].id); break;
      case 'pair': state.pairing = step; render(); break;
      case 'verify': verify(step); break;
      case 'repair': verify(step, true); break;
      case 'provider':
        state.providers[provider] = !state.providers[provider];
        state.statuses.providers = Object.values(state.providers).some(Boolean) ? 'done' : 'unknown';
        notify(state.providers[provider] ? 'Provider-Anmeldung simuliert.' : 'Demo-Verbindung getrennt.');
        render(); break;
    }
  });
  document.querySelector('#scenario').addEventListener('change', event => reset(event.target.value));
  reset();
})();
