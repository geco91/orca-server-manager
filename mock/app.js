(() => {
  'use strict';

  const releases = [
    { version: '1.4.261', date: '16. November 2026', note: 'Neue Chat-Speicherung. Orca beschreibt die Datenkonvertierung und den Rückweg in den Release-Hinweisen.' },
    { version: '1.4.259', date: '14. November 2026', note: 'Verbesserungen bei Arbeitsbereichen, Terminal-Wiederherstellung und mobilen Ansichten.' },
    { version: '1.4.258', date: '13. November 2026', note: 'Verbesserungen bei Arbeitsbereichen, mobilen Chats und Agenten.' },
    { version: '1.4.257', date: '12. November 2026', note: 'Verbesserungen bei langen Chats, Terminaleingaben und Remote-Server-Diagnose.' }
  ];
  const services = [
    { id: 'providers', title: 'Agent-Provider', icon: 'AI', description: 'Native Konten von Codex und OpenCode auf dem Server prüfen.', source: 'Orca CLI und native Provider-Anmeldung' },
    { id: 'github', title: 'GitHub', icon: 'git', description: 'Optional für Repositories, Pushes und Pull Requests.', source: 'GitHub CLI auf der Orca-Runtime' },
    { id: 'desktop', title: 'Mac-Desktop', icon: 'Mac', description: 'In Orca koppeln. Kopplung und aktive Verbindung getrennt sehen.', source: 'Orcas Kopplungs- und Verbindungsstatus' },
    { id: 'mobile', title: 'Mobile-App', icon: 'App', description: 'Orca Mobile per nativem Pairing über LAN oder VPN verbinden.', source: 'Orcas Kopplungs- und Verbindungsstatus' },
    { id: 'mcp', title: 'Community-MCP-Bridge', icon: 'MCP', description: 'Externe Koordinatoren über die bestehende Bridge anbinden.', source: 'MCP-Protokoll und Orca-Runtime' },
    { id: 'tunnel', title: 'OpenAI Secure MCP Tunnel', icon: '↗', description: 'Den festgelegten OpenAI-Tunnel mit der Community-Bridge koppeln.', source: 'Tunnelverbindung und authentifizierter MCP-Aufruf' }
  ];
  const evidenceChoices = {
    providers: [['installed', 'CLIs vorhanden · noch nicht angemeldet'], ['authenticated', 'Nativ eingerichtet und angemeldet'], ['expired', 'Anmeldung abgelaufen'], ['missing', 'CLIs nicht installiert']],
    github: [['anonymous', 'GitHub CLI vorhanden · nicht angemeldet'], ['authenticated', 'Auf dem Server angemeldet'], ['expired', 'Anmeldung ungültig']],
    desktop: [['unpaired', 'Noch nicht gekoppelt'], ['connected', 'In Orca gekoppelt und verbunden'], ['offline', 'Kopplung vorhanden · Gerät offline']],
    mobile: [['unpaired', 'Noch nicht gekoppelt'], ['connected', 'In Orca gekoppelt und verbunden'], ['offline', 'Kopplung vorhanden · Gerät offline']],
    mcp: [['absent', 'Bridge noch nicht bereitgestellt'], ['ready', 'Bridge vorhanden und erreichbar'], ['error', 'Bridge antwortet nicht']],
    tunnel: [['unconfigured', 'Tunnel noch nicht angebunden'], ['connected', 'Tunnel angebunden'], ['error', 'Tunnel-Anmeldung ungültig']]
  };
  const processSteps = [
    ['OCI-Bereitstellung vorbereiten', 'Die gewählte Orca-Version und ihr Serverpaket übernehmen.'],
    ['Software und Daten sichern', 'Bisherige Version und zusammengehörigen Datenstand erhalten.'],
    ['Container wechseln', 'Orca geordnet stoppen und die neue Container-Version bereitstellen.'],
    ['Orca starten', 'Startzustand anzeigen. Du erprobst die Version anschließend selbst.']
  ];
  const app = document.querySelector('#app');
  const nav = document.querySelector('#main-nav');
  let state;
  let generation = 0;
  const wait = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const time = () => new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'Europe/Berlin' }).format(new Date());
  const notify = text => { document.querySelector('#announcer').textContent = text; };
  const disabled = condition => condition ? ' disabled' : '';
  const pill = (label, status = '') => `<span class="pill ${status}">${escapeHtml(label)}</span>`;
  const notice = (title, text, kind = '') => `<div class="notice ${kind}" role="status"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></div>`;
  const command = lines => `<pre><code>${escapeHtml(lines.join('\n'))}</code></pre>`;
  const rows = items => `<div class="checks">${items.map(([name, value, tone = '']) => `<div class="check-row ${tone}"><span>${escapeHtml(name)}</span><span>${escapeHtml(value)}</span></div>`).join('')}</div>`;
  const sourceLink = (url, title) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`;
  const heading = (eyebrow, title, text) => `<div class="page-heading"><div><span class="eyebrow">${eyebrow}</span><h1 tabindex="-1">${title}</h1><p>${text}</p></div>${pill('Simulierte Daten')}</div>`;

  function reset(scenario = 'fresh', page = 'overview') {
    generation += 1;
    document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
    state = {
      page, scenario, version: '1.4.239', target: '1.4.261', online: true, runtimeEpoch: 0,
      checks: {}, revisions: {}, evidence: { providers: 'installed', github: 'anonymous', desktop: 'unpaired', mobile: 'unpaired', mcp: 'absent', tunnel: 'unconfigured' },
      busy: null, update: null, recovery: null, history: [], workRevision: 0,
      activeWork: scenario === 'active-work', failUpdate: scenario === 'update-failure'
    };
    if (scenario !== 'fresh') {
      Object.assign(state.evidence, { providers: 'authenticated', github: 'authenticated', desktop: 'connected', mobile: 'connected', mcp: 'ready', tunnel: 'connected' });
    }
    if (scenario === 'paired-offline') state.evidence.desktop = state.evidence.mobile = 'offline';
    if (scenario === 'tunnel-error') state.evidence.tunnel = 'error';
    if (scenario !== 'fresh') {
      ['server', ...services.map(service => service.id)].forEach(id => {
        state.checks[id] = { ...evaluate(id), at: time(), signature: signature(id) };
      });
    }
    document.querySelector('#scenario').value = scenario;
    render();
  }

  function signature(id) {
    return [state.runtimeEpoch, state.revisions[id] || 0, id === 'tunnel' ? state.revisions.mcp || 0 : 0].join(':');
  }

  function evaluate(id) {
    if (id === 'server') {
      return {
        status: state.online ? 'ready' : 'error', label: state.online ? 'Runtime erreichbar' : 'Start fehlgeschlagen',
        rows: [
          ['Orca-Runtime', state.online ? 'Antwortet über native RPC' : 'Nicht erreichbar', state.online ? 'good' : 'bad'],
          ['Installierte Software', 'Orca ' + state.version],
          ['Persistente Daten', 'Separate Datenbereiche im Demo-Modell', 'good'],
          ['Laufende Agentaufträge', state.activeWork ? '1 Auftrag läuft' : 'Keine im Demo-Szenario', state.activeWork ? 'warn' : ''],
          ['Bereitstellung', 'Direktes Proxmox-OCI · Vorschau']
        ]
      };
    }
    if (!state.online) return { status: 'unknown', label: 'Nicht überprüfbar', rows: [['Orca-Runtime', 'Nicht erreichbar', 'bad'], ['Verbindungsstatus', 'Derzeit nicht überprüfbar']] };
    const value = state.evidence[id];
    if (id === 'providers') {
      const signedIn = value === 'authenticated', installed = value !== 'missing';
      return {
        status: signedIn ? 'ready' : value === 'expired' ? 'error' : 'partial',
        label: signedIn ? 'Angemeldet' : value === 'expired' ? 'Anmeldung abgelaufen' : installed ? 'Anmeldung offen' : 'CLIs fehlen',
        rows: [['Codex / OpenCode CLI', installed ? 'Vorhanden' : 'Nicht installiert', installed ? 'good' : 'warn'], ['Orca-Konto', signedIn || value === 'expired' ? 'Registriert' : 'Nicht festgestellt'], ['Native Anmeldung', signedIn ? 'Gültig im Demo-Szenario' : value === 'expired' ? 'Abgelaufen' : 'Nicht angemeldet', signedIn ? 'good' : 'warn'], ['Agentauftrag', 'Noch nicht erprobt']]
      };
    }
    if (id === 'github') {
      const signedIn = value === 'authenticated';
      return {
        status: signedIn ? 'ready' : value === 'expired' ? 'error' : 'partial', label: signedIn ? 'Server angemeldet' : value === 'expired' ? 'Anmeldung ungültig' : 'Anmeldung offen',
        rows: [['GitHub CLI', 'Auf dem Server vorhanden', 'good'], ['Server-Identität', signedIn ? 'geco91 · Beispieldaten' : 'Nicht bestätigt'], ['GitHub API', signedIn ? 'Identität lesbar' : 'Nicht authentifiziert', signedIn ? 'good' : 'warn'], ['Repository-Zugriff', signedIn ? 'Leserechte und Push-Recht laut API' : 'Nicht geprüft', signedIn ? 'good' : ''], ['Änderungen für diese Prüfung', 'Keine Pushes oder Pull Requests erzeugt']]
      };
    }
    if (id === 'desktop' || id === 'mobile') {
      const paired = value !== 'unpaired', connected = value === 'connected';
      return {
        status: connected ? 'ready' : paired ? 'offline' : 'partial',
        label: connected ? 'Verbunden' : paired ? 'Gekoppelt · offline' : 'Nicht gekoppelt',
        rows: [['Gerät', id === 'desktop' ? 'MacBook · Beispieldaten' : 'iPhone · Beispieldaten'], ['Kopplung in Orca', paired ? 'Vorhanden' : 'Nicht vorhanden', paired ? 'good' : ''], ['Aktuelle Verbindung', connected ? 'Online' : 'Offline', connected ? 'good' : 'warn'], ['Zugriffsweg', 'LAN oder VPN']]
      };
    }
    if (id === 'mcp') {
      const ready = value === 'ready';
      return {
        status: ready ? 'ready' : value === 'absent' ? 'partial' : 'error', label: ready ? 'Bridge erreichbar' : value === 'absent' ? 'Noch nicht eingerichtet' : 'Bridge nicht erreichbar',
        rows: [['Bridge', 'BuildContext · separates Community-Projekt'], ['MCP-Protokoll', ready ? 'initialize und tools/list erfolgreich' : 'Keine erfolgreiche Antwort', ready ? 'good' : 'warn'], ['Orca hinter der Bridge', ready ? 'Health-Aufruf erfolgreich' : 'Nicht bestätigt', ready ? 'good' : ''], ['Prüfumfang', 'Lesender Status · kein Agent gestartet']]
      };
    }
    const bridgeReady = state.evidence.mcp === 'ready', connected = value === 'connected' && bridgeReady;
    return {
      status: connected ? 'ready' : value === 'unconfigured' ? 'partial' : 'error',
      label: connected ? 'Durchgängig erreichbar' : !bridgeReady && value === 'connected' ? 'Bridge nicht bereit' : value === 'error' ? 'Anmeldung ungültig' : 'Anbindung offen',
      rows: [['Tunnel', 'OpenAI Secure MCP Tunnel'], ['Community-Bridge lokal', bridgeReady ? 'Erreichbar' : 'Nicht bereit', bridgeReady ? 'good' : 'warn'], ['Tunnel-Authentifizierung', value === 'connected' ? 'Im Demo-Szenario gültig' : value === 'error' ? 'Ungültig' : 'Nicht eingerichtet', value === 'connected' ? 'good' : 'warn'], ['MCP über den Tunnel', connected ? 'Authentifizierter Health-Aufruf erfolgreich' : 'Nicht bestätigt', connected ? 'good' : 'warn']]
    };
  }

  function record(id) {
    const saved = state.checks[id];
    if (!saved) return { status: 'unknown', label: 'Noch nicht geprüft', at: null };
    return saved.signature === signature(id) ? saved : { ...saved, status: 'stale', label: 'Erneut prüfen', stale: true };
  }

  function checkTime(id) {
    const result = record(id);
    return `<div class="check-time">${result.at ? `${result.stale ? 'Letztes Ergebnis' : 'Geprüft'} um ${result.at} Uhr · simuliert` : 'Noch kein Prüfergebnis'}${id === 'server' ? '' : `<br>Quelle: ${services.find(service => service.id === id).source}`}</div>`;
  }

  function cards() {
    return `<div class="connection-grid">${services.map(service => {
      const result = record(service.id);
      return `<article class="panel connection-card"><div class="card-top"><span class="service-icon" aria-hidden="true">${service.icon}</span>${pill(result.label, result.status)}</div><h3>${service.title}</h3><p>${service.description}</p><div class="card-bottom"><button class="text-button" data-action="navigate" data-page="${service.id}">Anleitung & Status →</button>${checkTime(service.id)}</div></article>`;
    }).join('')}</div>`;
  }

  function overview() {
    const runtime = record('server');
    return heading('DEIN ENTWICKLUNGSSERVER', 'Orca betreiben. Verbindungen im Blick.', 'Die Basis läuft unabhängig von optionalen Integrationen. Konten und Geräte richtest du mit den nativen Werkzeugen ein.')
      + `<div class="hero-grid"><section class="panel runtime-panel"><div class="panel-top"><span class="eyebrow">ORCA RUNTIME</span>${pill(runtime.label, runtime.status)}</div><h2 class="runtime-title">${state.online ? 'Dein Server, deine Arbeit.' : 'Orca ist derzeit nicht erreichbar.'}</h2><p>${state.online ? 'Die Entwicklungsarbeit bleibt in Orca. Hier prüfst du den Betrieb und verwaltest Versionswechsel.' : 'Der Start der gewählten Version ist im Demo-Szenario fehlgeschlagen. Der Rücksprung ist weiterhin erreichbar.'}</p><div class="metric-row"><div class="metric"><span>Installierte Version</span><strong>${state.version}</strong></div><div class="metric"><span>Bereitstellung</span><strong>Proxmox · OCI</strong></div><div class="metric"><span>Agentaufträge</span><strong>${state.activeWork ? '1 aktiv' : 'Keine aktiv'}</strong></div></div><div class="button-row"><button data-action="check" data-service="server"${disabled(state.busy)}>Server prüfen</button><button class="quiet" data-action="navigate" data-page="updates">Versionen & Updates</button></div>${checkTime('server')}</section><section class="panel"><span class="eyebrow">IN ORCA WEITERARBEITEN</span><h2>Einrichten, wo es hingehört.</h2><p>Agentkonten, Projekte, Repositories und Geräte werden in Orca oder mit den jeweiligen nativen Werkzeugen eingerichtet.</p><p>GitHub ist nur dann nötig, wenn du GitHub-Repositories und Pull Requests verwenden möchtest.</p><button class="quiet" data-action="navigate" data-page="connections">Anleitungen & Verbindungen</button>${notice('Optionale Verbindungen', 'Eine fehlende GitHub-Anmeldung oder ein noch nicht angebundener Tunnel blockiert den Orca-Grundbetrieb nicht.', 'neutral')}</section></div><div class="section-heading"><h2>Verbindungen</h2><button class="text-button" data-action="check-all"${disabled(state.busy)}>Alle Status prüfen</button></div>${cards()}`;
  }

  function connections() {
    return heading('ANLEITUNG & TECHNISCHER STATUS', 'Einrichtung mit Orcas Werkzeugen.', 'Wähle eine Verbindung, lies die native Anleitung und prüfe anschließend den Zustand auf dem Server.')
      + `<div class="section-heading"><p>Alle Integrationen sind optional.</p><button class="quiet" data-action="check-all"${disabled(state.busy)}>Alle Status prüfen</button></div>${cards()}`;
  }

  function guide(id) {
    if (id === 'providers') return `<ol class="guide-list"><li><strong>Agent-CLI auf dem Server bereitstellen.</strong> Codex und OpenCode müssen in der Orca-Runtime verfügbar sein.</li><li><strong>Nativen Login verwenden.</strong> Auf einem Headless-Server meldest du Konten in dessen Terminal an. Die Anmeldung auf deinem Mac wird nicht übernommen.</li><li><strong>In Orca arbeiten.</strong> Starte deinen Agentauftrag dort selbst. Der Manager liest anschließend den Verbindungsstatus.</li></ol><details><summary>Native Befehle auf dem Server</summary>${command(['orca account add --agent codex', 'orca account add --agent opencode', 'orca account list --json'])}<p class="guide-note">Die Login-Dialoge gehören Orca beziehungsweise dem Provider. Der Manager fragt keine Zugangsdaten ab.</p></details>${sourceLink('https://github.com/stablyai/orca/blob/v1.4.261/src/cli/specs/account.ts', 'Orcas Account-Befehle')}`;
    if (id === 'github') return `<ol class="guide-list"><li><strong>Nur bei Bedarf einrichten.</strong> GitHub ermöglicht Repository-Zugriff, Pushes und Pull Requests für die Entwicklungsarbeit.</li><li><strong>Auf dem Server anmelden.</strong> Öffne ein Terminal der Orca-Runtime und verwende die GitHub CLI.</li><li><strong>Identität und Rechte prüfen.</strong> Die Mac-Anmeldung gilt nicht automatisch auf dem Server.</li></ol><details><summary>Native Befehle auf dem Server</summary>${command(['gh auth login --hostname github.com --web', 'gh auth setup-git', 'gh auth status --hostname github.com'])}</details>${notice('Kein Pflichtschritt', 'Orca, der MCP-Tunnel und öffentliche Orca-Releases benötigen diese GitHub-Anmeldung nicht.', 'neutral')}${sourceLink('https://github.com/stablyai/orca/blob/v1.4.261/docs/site/content/docs/github-errors.mdx', 'GitHub in Orca')}`;
    if (id === 'desktop' || id === 'mobile') {
      const mobile = id === 'mobile';
      return `<ol class="guide-list"><li><strong>Orcas Pairing auf dem Server aufrufen.</strong> Das geht bei laufender Runtime ohne Neustart.</li><li><strong>${mobile ? 'In Orca Mobile koppeln.' : 'Im Mac-Client den Server hinzufügen.'}</strong> ${mobile ? 'Scanne den von Orca erzeugten QR-Code in der App.' : 'Öffne Settings → Remote Orca Servers → Add Server und verwende den von Orca erzeugten Link.'}</li><li><strong>LAN oder VPN verwenden.</strong> Prüfe danach die bestehende Verbindung hier.</li></ol><details><summary>Nativer Pairing-Befehl</summary>${command([mobile ? 'orca pair --mobile' : 'orca pair'])}<p class="guide-note">Link und QR-Code werden direkt von Orca erzeugt. Diese Demo zeigt keine Zugangsdaten und erzeugt keinen Pairing-Code.</p></details>${notice('Gekoppelt bedeutet nicht immer online', 'Eine bestehende Kopplung bleibt erhalten, wenn dein Gerät gerade offline ist.', 'neutral')}${sourceLink('https://github.com/stablyai/orca/blob/v1.4.261/src/cli/specs/pair.ts', 'Orcas Pairing')}`;
    }
    if (id === 'mcp') return `<ol class="guide-list"><li><strong>Vorhandene Community-Bridge verwenden.</strong> BuildContexts Bridge läuft zusätzlich zur Orca-Runtime und nutzt deren native CLI.</li><li><strong>Orca für externe Koordinatoren erreichbar machen.</strong> Das ist die Gegenrichtung zu MCP-Servern, die Orcas eigene Agenten verwenden.</li><li><strong>Mit dem OpenAI-Tunnel koppeln.</strong> Die zusätzliche Verbindung wird im Tunnelbereich beschrieben.</li></ol>${sourceLink('https://github.com/BuildContext/orca-mcp', 'Community-MCP-Bridge')}${notice('Zusätzliche Komponente', 'Die externe Steuerung über diese Bridge ist kein eingebauter Orca-Dienst. Der Statusaufruf startet keinen Agenten.', 'neutral')}`;
    return `<div class="flow" aria-label="Verbindungskette"><b>ChatGPT / Codex</b><span>→</span><b>OpenAI Secure MCP Tunnel</b><span>→</span><b>Community-Bridge</b><span>→</span><b>Orca</b></div><ol class="guide-list"><li><strong>Den festgelegten OpenAI-Tunnel verwenden.</strong> Die Tunnelwahl gehört bereits zum Konzept.</li><li><strong>Die Community-Bridge als Ziel anbinden.</strong> Verwende die vorhandenen Einrichtungs- und Authentifizierungsmechanismen des Tunnels.</li><li><strong>Die gesamte Verbindung prüfen.</strong> Ein offener Port allein bestätigt noch keinen erfolgreichen MCP-Aufruf.</li></ol>${notice('Einrichtung begleiten', 'Der Manager unterstützt die Anbindung vorhandener Komponenten. Die praktische Kopplung ist in dieser Vorschau simuliert.', 'neutral')}`;
  }

  function connection(id) {
    const service = services.find(item => item.id === id), result = record(id);
    const detailRows = result.rows || [['Status', 'Noch nicht geprüft'], ['Prüfumfang', service.source]];
    return `<button class="back-button" data-action="navigate" data-page="connections">← Alle Verbindungen</button>`
      + heading('OPTIONALE VERBINDUNG', service.title, service.description)
      + `<div class="detail-grid"><section class="panel"><span class="eyebrow">NATIV EINRICHTEN</span><h2>Anleitung</h2>${guide(id)}</section><section class="panel"><div class="panel-top"><span class="eyebrow">STATUS AUF DEM SERVER</span>${pill(result.label, result.status)}</div><h2>Verbindung technisch prüfen</h2><p>Die Prüfung liest den Zustand. Sie führt keine Anmeldung oder Kopplung durch.</p>${result.stale ? notice('Zustand wurde geändert', 'Das bisherige Ergebnis beschreibt einen früheren Zustand. Lies den Status erneut.', 'warn') : ''}${rows(detailRows)}<button data-action="check" data-service="${id}"${disabled(state.busy)}>Status erneut prüfen</button>${checkTime(id)}<div class="demo-evidence"><label for="native-state">Demo steuern · Zustand außerhalb des Managers</label><select id="native-state" data-service="${id}"${disabled(state.busy)}>${evidenceChoices[id].map(([value, label]) => `<option value="${value}"${state.evidence[id] === value ? ' selected' : ''}>${label}</option>`).join('')}</select><p>Spielt eine Änderung in Orca oder im nativen Werkzeug nach. Erst „Status erneut prüfen“ übernimmt sie ins Dashboard.</p></div></section></div>`;
  }

  function server() {
    const result = record('server');
    return `<button class="back-button" data-action="navigate" data-page="overview">← Übersicht</button>`
      + heading('GRUNDBETRIEB', 'Den Orca-Server prüfen.', 'Die Runtime und ihre Datenbereiche sind die Basis. Optionale Verbindungen kannst du später einrichten.')
      + `<section class="panel"><div class="panel-top"><h2>Technischer Betriebsstatus</h2>${pill(result.label, result.status)}</div>${rows(result.rows || [['Status', 'Noch nicht geprüft'], ['Installierte Software', 'Orca ' + state.version]])}<button data-action="check" data-service="server"${disabled(state.busy)}>Serverstatus prüfen</button>${checkTime('server')}</section>`;
  }

  function updates() {
    const target = releases.find(item => item.version === state.target);
    const inProgress = state.busy && ['update', 'rollback'].includes(state.busy.kind);
    const update = state.update;
    let result = '';
    if (update && update.outcome === 'success') result = notice('Die gewählte Version läuft.', 'Probiere sie in Orca aus. Du entscheidest, ob sie für deine Arbeit passt. Die vorherige Version und ihre Sicherung bleiben für den Rücksprung erhalten.');
    if (update && update.outcome === 'failed') result = notice('Die neue Version startet nicht.', 'Der Versionswechsel ist abgeschlossen, aber Orca ist im Demo-Szenario nicht erreichbar. Du kannst zur vorherigen Version und ihrem gesicherten Datenstand zurückkehren.', 'error');
    if (update && update.outcome === 'rolled-back') result = notice('Rücksprung abgeschlossen.', update.restoreData ? 'Vorherige Software und zugehöriger Datenstand wurden im Demo-Szenario wiederhergestellt.' : 'Die vorherige Software wurde wiederhergestellt. Der neuere Datenstand wurde beibehalten; seine Kompatibilität ist nicht bestätigt.', update.restoreData ? '' : 'warn');
    return heading('VERSIONEN & BETRIEB', 'Du wählst die Orca-Version.', 'Die Release-Angaben kommen von Orca. Der Manager organisiert den Wechsel und den Rückweg; du erprobst die Version selbst.')
      + result
      + `<div class="update-grid"><section class="panel"><span class="eyebrow">ORCA-RELEASES</span><div class="version-pair"><div><span class="small-label">Aktuell installiert</span><strong data-testid="installed-version">${state.version}</strong></div><span class="version-arrow" aria-hidden="true">→</span><div><span class="small-label">Deine Auswahl</span><strong>${state.target}</strong></div></div><p class="small-label">Offizielle Release-Daten als Offline-Beispiel · Stand 16. November 2026</p><div class="release-list" role="radiogroup" aria-label="Orca-Zielversion">${releases.map(release => `<label class="release-option ${state.target === release.version ? 'selected' : ''}"><input type="radio" name="release" value="${release.version}"${state.target === release.version ? ' checked' : ''}${disabled(state.busy)}><span class="release-copy"><strong>Orca ${release.version}${state.version === release.version ? ' · installiert' : ''}</strong><span>${release.date} · reguläres Release laut Orca</span></span><a href="https://github.com/stablyai/orca/releases/tag/v${release.version}" target="_blank" rel="noopener noreferrer" aria-label="Orca ${release.version} Release-Hinweise">Hinweise</a></label>`).join('')}</div><div class="release-notes"><strong class="small-label">ORCAS RELEASE-HINWEISE</strong><p>${escapeHtml(target.note)}</p></div>${state.activeWork ? notice('Ein Agentauftrag läuft noch.', 'Für den Containerwechsel muss Orca gestoppt werden. Beende die Arbeit in Orca und starte den Wechsel anschließend.', 'warn') : ''}<div class="button-row"><button data-action="update"${disabled(state.busy || state.activeWork || state.version === state.target)}>${state.version === state.target ? 'Bereits installiert' : 'Auf gewählte Version wechseln'}</button><button class="quiet" data-action="check" data-service="server"${disabled(state.busy)}>Betriebsstatus lesen</button></div><details><summary>Wie läuft der Wechsel unter Proxmox-OCI?</summary><p class="guide-note">Das Serverpaket stammt aus dem ausgewählten Orca-Release. Ein passendes OCI-Image wird als technischer Bereitstellungsschritt übernommen oder gebaut. Daraus folgt keine eigene Versionsbewertung.</p><p class="guide-note">Diese Vorschau zeigt eine geordnete Neuerstellung der Runtime mit expliziten Daten-Mountpoints. Die Ausführung muss außerhalb der zu ersetzenden Container erfolgen. Der Prototyp belegt keine fertige native Proxmox-Update-Funktion.</p></details></section><div><section class="panel"><div class="panel-top"><span class="eyebrow">GEORDNETER ABLAUF</span>${inProgress ? pill('Läuft', 'partial') : pill('Manuell gestartet')}</div><ol class="update-process">${processSteps.map(([title, detail], index) => {
        const failed = update && update.outcome === 'failed' && index === 3;
        const complete = !failed && update && (update.outcome || update.step > index);
        const current = inProgress && state.busy.kind === 'update' && update.step === index;
        return `<li class="${failed ? 'failed' : complete ? 'complete' : current ? 'current' : ''}"><span class="process-mark">${failed ? '!' : complete ? '✓' : index + 1}</span><div>${failed ? 'Orca nicht erreichbar' : title}<small>${failed ? 'Start fehlgeschlagen. Der gesicherte Rückweg bleibt verfügbar.' : detail}</small></div></li>`;
      }).join('')}</ol>${inProgress ? '<p class="busy-text">Demo-Ablauf läuft. Du kannst andere Bereiche öffnen.</p>' : '<p class="small-label">Nach dem Start gibt es keine zusätzliche Versionsfreigabe oder vorgelagerte Teststufe.</p>'}</section><section class="panel" style="margin-top:20px"><span class="eyebrow">RÜCKSPRUNG</span><h2>Den vorherigen Stand erhalten.</h2>${state.recovery ? `<div class="recovery-version">Orca ${state.recovery.version}</div><p>Software und Datenstand gesichert um ${state.recovery.at} Uhr · simuliert.</p><p class="small-label">${state.workRevision > state.recovery.workRevision ? 'Seit dieser Sicherung gibt es neue Änderungen im Demo-Datenstand.' : 'Seit dieser Sicherung wurden keine neuen Änderungen simuliert.'}</p><button class="quiet" data-action="rollback-dialog"${disabled(state.busy)}>Rücksprung wählen</button>` : '<p>Beim nächsten Versionswechsel wird hier die vorherige Version mit dem zugehörigen Datenstand bereitgehalten.</p>'}</section></div></div>`
      + `<div class="demo-evidence"><span class="small-label">DEMO STEUERN · KEINE ECHTEN AUFTRÄGE ODER DATEIEN</span><div class="button-row" style="margin-top:10px">${state.activeWork ? '<button class="quiet" data-action="finish-work">Agentauftrag als beendet darstellen</button>' : ''}<button class="quiet" data-action="data-change"${disabled(state.busy || !state.recovery)}>Änderung nach dem Update simulieren</button></div><p>Änderungen im Demo-Datenstand: <strong data-testid="work-revision">${state.workRevision}</strong>. Für einen fehlgeschlagenen Start oben das Szenario „Neue Version startet nicht“ wählen.</p></div>`
      + (state.history.length ? `<section class="panel"><span class="eyebrow">VERLAUF IN DIESEM TAB</span>${state.history.map(item => `<div class="history-item">${escapeHtml(item.text)}<small>${item.at} Uhr · simuliert</small></div>`).join('')}</section>` : '');
  }

  function render(focus = false) {
    const activePage = services.some(item => item.id === state.page) ? 'connections' : state.page;
    nav.innerHTML = [['overview', 'Übersicht'], ['connections', 'Verbindungen'], ['updates', 'Versionen & Updates']].map(([page, title]) => `<button class="nav-button" data-action="navigate" data-page="${page}"${activePage === page || page === 'overview' && activePage === 'server' ? ' aria-current="page"' : ''}>${title}</button>`).join('');
    app.innerHTML = state.page === 'overview' ? overview() : state.page === 'connections' ? connections() : state.page === 'updates' ? updates() : state.page === 'server' ? server() : connection(state.page);
    app.setAttribute('aria-busy', state.busy ? 'true' : 'false');
    if (focus) app.querySelector('h1')?.focus({ preventScroll: true });
  }

  function navigate(page) {
    if (!['overview', 'connections', 'updates', 'server', ...services.map(item => item.id)].includes(page)) return;
    state.page = page;
    render(true);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  async function check(ids) {
    if (state.busy) return;
    const ticket = generation;
    state.busy = { kind: 'check' };
    render();
    notify('Status wird im Demo-Szenario gelesen.');
    await wait(400);
    if (ticket !== generation) return;
    ids.forEach(id => { state.checks[id] = { ...evaluate(id), at: time(), signature: signature(id) }; });
    state.busy = null;
    render();
    notify('Status gelesen. Es wurde keine Verbindung eingerichtet.');
  }

  async function updateVersion() {
    if (state.busy || state.activeWork || state.version === state.target) return;
    const ticket = generation, previous = state.version, target = state.target;
    state.busy = { kind: 'update' };
    state.update = { step: 0, outcome: null };
    state.recovery = null;
    for (let index = 0; index < processSteps.length; index++) {
      if (ticket !== generation) return;
      state.update.step = index;
      if (index === 2) { state.online = false; state.runtimeEpoch += 1; }
      if (index === 3) state.version = target;
      render();
      await wait(550);
      if (ticket !== generation) return;
      if (index === 1) state.recovery = { version: previous, at: time(), workRevision: state.workRevision, evidence: { ...state.evidence } };
    }
    state.online = !state.failUpdate;
    state.runtimeEpoch += 1;
    state.update.outcome = state.failUpdate ? 'failed' : 'success';
    state.busy = null;
    state.history.unshift({ text: previous + ' → ' + target + (state.failUpdate ? ' · Start fehlgeschlagen' : ' · gestartet'), at: time() });
    render();
    notify(state.failUpdate ? 'Neue Version nicht erreichbar. Rücksprung verfügbar.' : 'Versionswechsel abgeschlossen. Du kannst Orca jetzt selbst erproben.');
  }

  function rollbackDialog() {
    if (!state.recovery || state.busy) return;
    const backup = state.recovery;
    document.querySelector('#rollback-body').innerHTML = `<span class="eyebrow">VORHERIGEN STAND WIEDERHERSTELLEN</span><h2 id="rollback-title">Zurück zu Orca ${backup.version}</h2><p>Sicherung von ${backup.at} Uhr. Wähle den Umfang des Rücksprungs.</p><div role="radiogroup" aria-label="Umfang des Rücksprungs"><label class="rollback-option"><input type="radio" name="rollback-mode" value="full" checked><span><strong>Software und gesicherten Datenstand wiederherstellen</strong><small>Orca-Profil, Verbindungen und Arbeitsdaten auf den Stand vor dem Wechsel zurücksetzen.</small></span></label><label class="rollback-option"><input type="radio" name="rollback-mode" value="software"><span><strong>Nur die Software zurückwechseln</strong><small>Neuere Daten bleiben erhalten. Ob die ältere Orca-Version sie lesen kann, ist damit nicht bestätigt.</small></span></label></div><div id="rollback-impact"></div><div class="button-row"><button id="rollback-start" data-action="rollback">Software & Daten wiederherstellen</button><button class="quiet" data-action="cancel-rollback">Abbrechen</button></div>`;
    rollbackImpact();
    document.querySelector('#rollback-dialog').showModal();
  }

  function rollbackImpact() {
    const full = document.querySelector('input[name="rollback-mode"]:checked')?.value === 'full';
    const changed = state.recovery && state.workRevision > state.recovery.workRevision;
    document.querySelector('#rollback-impact').innerHTML = full
      ? notice('Daten werden auf die Sicherung zurückgesetzt.', changed ? 'Seit der Sicherung gibt es neue Änderungen. Sie werden bei diesem Rücksprung verworfen. In dieser Demo betrifft das nur den simulierten Datenstand.' : 'Spätere Änderungen an den gesicherten Daten würden verworfen. Derzeit wurden in diesem Demo-Szenario keine solchen Änderungen hinzugefügt.', 'warn')
      : notice('Neuerer Datenstand bleibt erhalten.', 'Die vorherige Software wird mit den aktuellen Daten gestartet. Ein Software-Rücksprung allein macht Datenmigrationen nicht rückgängig.', 'warn');
    document.querySelector('#rollback-start').textContent = full ? 'Software & Daten wiederherstellen' : 'Nur Software zurückwechseln';
  }

  async function rollback() {
    if (!state.recovery || state.busy) return;
    const ticket = generation, backup = state.recovery;
    const restoreData = document.querySelector('input[name="rollback-mode"]:checked')?.value === 'full';
    document.querySelector('#rollback-dialog').close();
    state.busy = { kind: 'rollback' };
    state.online = false;
    state.runtimeEpoch += 1;
    render();
    await wait(900);
    if (ticket !== generation) return;
    state.version = backup.version;
    if (restoreData) { state.workRevision = backup.workRevision; state.evidence = { ...backup.evidence }; }
    state.online = true;
    state.runtimeEpoch += 1;
    state.recovery = null;
    state.update = { step: 4, outcome: 'rolled-back', restoreData };
    state.history.unshift({ text: 'Zurück zu ' + state.version + (restoreData ? ' · Software und Datenstand wiederhergestellt' : ' · neueren Datenstand beibehalten'), at: time() });
    state.busy = null;
    render();
    notify('Rücksprung abgeschlossen. Betriebsstatus und Verbindungen können erneut gelesen werden.');
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('button[data-action]');
    if (!button || button.disabled) return;
    const { action, page, service } = button.dataset;
    if (action === 'navigate') navigate(page);
    else if (action === 'help') document.querySelector('#demo-help').showModal();
    else if (action === 'close-help') document.querySelector('#demo-help').close();
    else if (action === 'reset') { reset(state.scenario); notify('Aktuelles Szenario zurückgesetzt.'); }
    else if (action === 'check') check([service]);
    else if (action === 'check-all') check(['server', ...services.map(item => item.id)]);
    else if (action === 'update') updateVersion();
    else if (action === 'rollback-dialog') rollbackDialog();
    else if (action === 'cancel-rollback') document.querySelector('#rollback-dialog').close();
    else if (action === 'rollback') rollback();
    else if (action === 'finish-work' && !state.busy) { state.activeWork = false; state.runtimeEpoch += 1; render(); notify('Im Demo-Szenario ist der Agentauftrag beendet.'); }
    else if (action === 'data-change' && state.recovery && !state.busy) { state.workRevision += 1; render(); notify('Eine neue Änderung im Demo-Datenstand hinzugefügt.'); }
  });

  document.addEventListener('change', event => {
    if (event.target.id === 'scenario') { reset(event.target.value); notify('Demo-Szenario gewechselt.'); }
    else if (event.target.id === 'native-state' && !state.busy) {
      const id = event.target.dataset.service;
      if (!evidenceChoices[id].some(([value]) => value === event.target.value)) return;
      state.evidence[id] = event.target.value;
      state.revisions[id] = (state.revisions[id] || 0) + 1;
      render();
      document.querySelector('#native-state')?.focus();
      notify('Nativer Zustand im Demo-Szenario geändert. Status erneut prüfen.');
    } else if (event.target.name === 'release' && !state.busy && releases.some(item => item.version === event.target.value)) {
      state.target = event.target.value;
      render();
      document.querySelector('input[name="release"]:checked')?.focus();
    } else if (event.target.name === 'rollback-mode') rollbackImpact();
  });

  reset();
})();
