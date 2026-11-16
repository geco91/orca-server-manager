(() => {
  'use strict';
  const releases = [
    {version:'1.4.261', date:'16 November 2026', note:'Chat storage changes. Read Orca’s release notes for the data conversion and return path.'},
    {version:'1.4.259', date:'14 November 2026', note:'Workspace, terminal recovery and mobile view improvements.'},
    {version:'1.4.258', date:'13 November 2026', note:'Workspace, mobile chat and agent improvements.'},
    {version:'1.4.257', date:'12 November 2026', note:'Long chat, terminal input and remote server diagnostics improvements.'}
  ];
  const services = [
    {id:'providers',title:'Agent providers',icon:'AI',description:'Inspect native Codex and OpenCode accounts on the server.'},
    {id:'github',title:'GitHub',icon:'git',description:'Optional repository access, pushes and pull requests.'},
    {id:'desktop',title:'Mac desktop',icon:'Mac',description:'Pair in Orca. Pairing and current connectivity are separate.'},
    {id:'mobile',title:'Mobile app',icon:'App',description:'Use native Orca pairing over your LAN or VPN.'},
    {id:'mcp',title:'Community MCP bridge',icon:'MCP',description:'Use the existing community bridge for external coordinators.'},
    {id:'tunnel',title:'OpenAI Secure MCP Tunnel',icon:'↗',description:'Connect the selected OpenAI tunnel to the community bridge.'}
  ];
  const evidenceChoices = {
    providers:[['installed','CLIs installed · not signed in'],['authenticated','Native sign-in present'],['expired','Sign-in expired'],['missing','CLIs not installed']],
    github:[['anonymous','GitHub CLI installed · not signed in'],['authenticated','Signed in on the server'],['expired','Sign-in invalid']],
    desktop:[['unpaired','Not paired'],['connected','Paired in Orca and connected'],['offline','Paired · device offline']],
    mobile:[['unpaired','Not paired'],['connected','Paired in Orca and connected'],['offline','Paired · device offline']],
    mcp:[['absent','Bridge not configured'],['ready','Bridge reachable'],['error','Bridge not responding']],
    tunnel:[['unconfigured','Tunnel not connected'],['connected','Tunnel connected'],['error','Tunnel authentication invalid']]
  };
  const processSteps = [
    ['Prepare selected OCI image','Use the version and server package published by Orca.'],
    ['Keep software and data','Stop Orca and preserve a consistent return point.'],
    ['Replace runtime container','Keep the manager available while the runtime changes.'],
    ['Start Orca','Observe its state. Try the selected version yourself.']
  ];
  const app = document.querySelector('#app'), nav = document.querySelector('#main-nav');
  const escapeHtml = v => String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
  const wait = ms => new Promise(resolve=>setTimeout(resolve,ms));
  const time = () => new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());
  const notify = text => {document.querySelector('#announcer').textContent=text;};
  const disabled = condition => condition?' disabled':'';
  const pill = (label,status='') => `<span class="pill ${status}">${escapeHtml(label)}</span>`;
  const notice = (title,text,kind='') => `<div class="notice ${kind}" role="status"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></div>`;
  const rows = items => `<div class="checks">${items.map(([name,value,tone=''])=>`<div class="check-row ${tone}"><span>${escapeHtml(name)}</span><span>${escapeHtml(value)}</span></div>`).join('')}</div>`;
  const command = lines => `<pre><code>${escapeHtml(lines.join('\n'))}</code></pre>`;
  const heading = (eyebrow,title,text) => `<div class="page-heading"><div><span class="eyebrow">${eyebrow}</span><h1 tabindex="-1">${title}</h1><p>${text}</p></div>${pill('Simulated data')}</div>`;
  const sourceLink = (url,title) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`;
  let state, generation=0;

  function reset(scenario='fresh') {
    generation++;
    document.querySelectorAll('dialog[open]').forEach(d=>d.close());
    state={page:'overview',scenario,version:'1.4.239',target:'1.4.261',online:true,runtimeEpoch:0,
      checks:{},revisions:{},evidence:{providers:'installed',github:'anonymous',desktop:'unpaired',mobile:'unpaired',mcp:'absent',tunnel:'unconfigured'},
      busy:null,update:null,recovery:null,history:[],workRevision:0,activeWork:scenario==='active-work',failUpdate:scenario==='update-failure'};
    if (scenario!=='fresh') Object.assign(state.evidence,{providers:'authenticated',github:'authenticated',desktop:'connected',mobile:'connected',mcp:'ready',tunnel:'connected'});
    if (scenario==='paired-offline') state.evidence.desktop=state.evidence.mobile='offline';
    if (scenario==='tunnel-error') state.evidence.tunnel='error';
    if (scenario!=='fresh') ['server',...services.map(s=>s.id)].forEach(id=>{state.checks[id]={...evaluate(id),at:time(),signature:signature(id)};});
    document.querySelector('#scenario').value=scenario;
    render();
  }
  function signature(id) {return [state.runtimeEpoch,state.revisions[id]||0,id==='tunnel'?state.revisions.mcp||0:0].join(':');}
  function evaluate(id) {
    if (id==='server') return {status:state.online?'ready':'error',label:state.online?'Runtime reachable':'Start failed',rows:[['Orca runtime',state.online?'Native RPC responded':'Not reachable'],['Installed software','Orca '+state.version],['Persistent data','Separate data areas in this demo'],['Active work',state.activeWork?'1 task running':'None in this demo scenario'],['Deployment','Native Proxmox OCI · preview']]};
    if (!state.online) return {status:'unknown',label:'Cannot verify',rows:[['Orca runtime','Not reachable'],['Connection','Currently not observable']]};
    const value=state.evidence[id],ready=['authenticated','connected','ready'].includes(value),failed=['expired','error'].includes(value);
    const label=ready?'Connected':failed?'Connection needs attention':value==='offline'?'Paired · offline':'Native setup required';
    if (id==='providers') return {status:ready?'ready':failed?'error':'partial',label:ready?'Native sign-in present':failed?'Sign-in expired':'Native setup required',rows:[['Codex / OpenCode CLI',value==='missing'?'Not installed':'Installed'],['Native account',ready||failed?'Registered in demo':'Not confirmed'],['Native sign-in',ready?'Present in demo':failed?'Expired':'Not confirmed'],['Agent task','Not started by this check']]};
    if (id==='github') return {status:ready?'ready':failed?'error':'partial',label:ready?'Server signed in':failed?'Sign-in invalid':'Server login not verified',rows:[['GitHub CLI','Installed on the server'],['Server identity',ready?'Example account · simulated':'Not confirmed'],['Repository permissions','Not inferred from account sign-in'],['Changes made by this check','No pushes or pull requests']]};
    if (id==='desktop'||id==='mobile') return {status:ready?'ready':value==='offline'?'offline':'partial',label:ready?'Connected':value==='offline'?'Paired · offline':'Not paired',rows:[['Device',id==='desktop'?'Example MacBook':'Example phone'],['Paired in Orca',value==='unpaired'?'No':'Yes'],['Current connection',ready?'Online':'Offline'],['Access path','LAN or VPN']]};
    if (id==='mcp') return {status:ready?'ready':failed?'error':'partial',label:ready?'Bridge reachable':failed?'Bridge not responding':'Bridge not configured',rows:[['Component','BuildContext/orca-mcp'],['MCP initialize',ready?'Succeeded in demo':'Not confirmed'],['Read-only Orca health',ready?'Succeeded in demo':'Not confirmed'],['Agent dispatch','Not performed']]};
    const bridgeReady=state.evidence.mcp==='ready';
    return {status:ready&&bridgeReady?'ready':failed?'error':'partial',label:ready&&bridgeReady?'External MCP path reachable':failed?'Tunnel authentication invalid':'External path not verified',rows:[['Tunnel','OpenAI Secure MCP Tunnel'],['Tunnel connection',ready?'Connected in demo':failed?'Authentication invalid':'Not configured'],['Community bridge',bridgeReady?'Reachable':'Not confirmed'],['Authenticated end-to-end MCP call',ready&&bridgeReady?'Succeeded in demo':'Not confirmed']]};
  }
  function record(id) {
    const result=state.checks[id];
    if (!result) return {status:'unknown',label:'Not verified'};
    return result.signature===signature(id)?result:{...result,status:'unknown',label:'Check again',stale:true};
  }
  function checkTime(id) {return `<p class="check-time">${state.checks[id]?'Last demo observation: '+state.checks[id].at:'Not checked yet.'}</p>`;}
  function cards() {return `<div class="connection-grid">${services.map(s=>{const r=record(s.id);return `<button class="panel connection-card" data-action="navigate" data-page="${s.id}"><div class="card-top"><span class="service-icon">${s.icon}</span>${pill(r.label,r.status)}</div><h3>${s.title}</h3><p>${s.description}</p><span class="card-link">Guide & status →</span></button>`;}).join('')}</div>`;}
  function overview() {
    const r=record('server');
    return heading('YOUR DEVELOPMENT SERVER','Run Orca. Keep connections in view.','Set up accounts and devices in Orca and the native tools. The manager observes their state.')
      +`<div class="hero-grid"><section class="panel runtime-panel"><div class="panel-top"><span class="eyebrow">ORCA RUNTIME</span>${pill(r.label,r.status)}</div><h2 class="runtime-title">Your server, your work.</h2><p>The runtime works independently of optional integrations.</p><div class="metric-row"><div class="metric"><span>Installed version</span><strong>${state.version}</strong></div><div class="metric"><span>Deployment</span><strong>Proxmox OCI</strong></div></div><div class="button-row"><button data-action="check" data-service="server"${disabled(state.busy)}>Refresh server status</button><button class="quiet" data-action="navigate" data-page="updates">Versions & updates</button></div>${checkTime('server')}</section><section class="panel"><span class="eyebrow">CONTINUE IN ORCA</span><h2>Set things up where they belong.</h2><p>Orca manages projects, agents, sessions and worktrees.</p><p>GitHub is optional for repositories, pushes and pull requests.</p>${notice('Independent connections','A missing GitHub login or an unconfigured tunnel does not block Orca.','neutral')}</section></div><div class="section-heading"><h2>Connections</h2><button class="text-button" data-action="navigate" data-page="connections">All guides →</button></div>`+cards();
  }
  function connections() {return heading('OPTIONAL CONNECTIONS','Native setup. Technical status.','Each connection is independent. The manager does not replace native login or pairing.')+`<div class="section-heading"><h2>Guides & connections</h2><button class="quiet" data-action="check-all"${disabled(state.busy)}>Refresh all statuses</button></div>`+cards();}
  function guide(id) {
    if (id==='providers') return `<ol class="guide-list"><li><strong>Provide the agent CLI on the server.</strong> An installed CLI is separate from account authentication.</li><li><strong>Run native setup inside the runtime.</strong> A login on your Mac does not sign in the server.</li><li><strong>Try your first agent task in Orca.</strong> This check does not start paid work.</li></ol><details><summary>Native commands inside the runtime</summary>${command(['orca account add --agent codex','orca account add --agent opencode','orca account list --json'])}</details>`;
    if (id==='github') return `<ol class="guide-list"><li><strong>Set up when a project needs it.</strong> GitHub provides repository, push and pull request access.</li><li><strong>Sign in on the server.</strong> Use the native GitHub CLI inside the runtime.</li><li><strong>Inspect identity and repository permissions.</strong> Your Mac login is separate.</li></ol><details><summary>Native commands inside the runtime</summary>${command(['gh auth login --hostname github.com --web','gh auth setup-git','gh auth status --hostname github.com'])}</details>${notice('Optional','Orca, the MCP tunnel and public Orca releases do not require this GitHub login.','neutral')}`;
    if (id==='desktop'||id==='mobile') return `<ol class="guide-list"><li><strong>Request Orca’s pairing offer.</strong> The server can remain running.</li><li><strong>${id==='mobile'?'Pair in Orca Mobile.':'Add the server in your Mac client.'}</strong> ${id==='mobile'?'Scan the QR code created by Orca.':'Open Settings → Remote Orca Servers → Add Server and use Orca’s pairing link.'}</li><li><strong>Use LAN or VPN access.</strong> Keep pairing links private.</li></ol><details><summary>Native pairing command</summary>${command([id==='mobile'?'orca pair --mobile':'orca pair'])}<p class="guide-note">Orca creates the actual link and QR code. This demo creates no credentials.</p></details>${notice('Paired and online are different','A paired device can be offline. The pilot reports unknown when the native version exposes no reliable client census.','neutral')}`;
    if (id==='mcp') return `<ol class="guide-list"><li><strong>Use the existing community bridge.</strong> It runs alongside Orca and calls its native CLI.</li><li><strong>Expose Orca to external coordinators.</strong> This is the opposite direction to MCP servers used by Orca’s agents.</li><li><strong>Connect the OpenAI tunnel.</strong> The bridge is a separate component.</li></ol>${sourceLink('https://github.com/BuildContext/orca-mcp','Community MCP bridge')}${notice('Read-only check','MCP initialize, tool inventory and Orca health do not start an agent.','neutral')}`;
    return `<div class="flow" aria-label="Connection path"><b>ChatGPT / Codex</b><span>→</span><b>OpenAI Secure MCP Tunnel</b><span>→</span><b>Community bridge</b><span>→</span><b>Orca</b></div><ol class="guide-list"><li><strong>Use the selected OpenAI tunnel.</strong> Reuse its existing configuration and authentication.</li><li><strong>Connect the bridge as its target.</strong> The manager does not build another tunnel.</li><li><strong>Verify the whole path.</strong> A local process or open port does not prove end-to-end MCP access.</li></ol>${notice('Simulated integration','The real pilot keeps external tunnel status unverified until an authenticated call is observed.','neutral')}`;
  }
  function connection(id) {
    const s=services.find(s=>s.id===id),r=record(id);
    return `<button class="back-button" data-action="navigate" data-page="connections">← All connections</button>`+heading('GUIDE & STATUS',s.title,s.description)
      +`<div class="detail-grid"><section class="panel"><span class="eyebrow">NATIVE SETUP</span><h2>Guide</h2>${guide(id)}</section><section class="panel"><div class="panel-top"><span class="eyebrow">SERVER OBSERVATION</span>${pill(r.label,r.status)}</div><h2>Check technical status</h2><p>This reads the state. It does not sign in or pair a device.</p>${r.stale?notice('The state changed','The previous result describes an earlier state. Refresh the observation.','warn'):''}${rows(r.rows||[['Status','Not verified']])}<button data-action="check" data-service="${id}"${disabled(state.busy)}>Refresh technical status</button>${checkTime(id)}<div class="demo-evidence"><label for="native-state">Demo control · state outside the manager</label><select id="native-state" data-service="${id}"${disabled(state.busy)}>${evidenceChoices[id].map(([v,label])=>`<option value="${v}"${state.evidence[id]===v?' selected':''}>${label}</option>`).join('')}</select><p>Simulate a native change. Refresh the status to reflect it in the dashboard.</p></div></section></div>`;
  }
  function server() {const r=record('server');return heading('BASIC OPERATION','Inspect the Orca server.','Optional integrations can be configured later.')+`<section class="panel">${pill(r.label,r.status)}${rows(r.rows||[['Status','Not verified']])}<button data-action="check" data-service="server"${disabled(state.busy)}>Refresh server status</button>${checkTime('server')}</section>`;}
  function updates() {
    const target=releases.find(r=>r.version===state.target),u=state.update,inProgress=state.busy&&['update','rollback'].includes(state.busy.kind);
    let result='';
    if (u?.outcome==='success') result=notice('The selected version is running.','Try it yourself in Orca. The previous software and its data backup remain available for rollback.');
    if (u?.outcome==='failed') result=notice('The new version did not start.','Orca is not reachable in this demo. The previous software and its saved data remain available.','error');
    if (u?.outcome==='rolled-back') result=notice('Rollback completed.',u.restoreData?'The previous software and saved data were restored.':'The previous software was restored; newer data was retained. Data compatibility is not confirmed.',u.restoreData?'':'warn');
    return heading('VERSIONS & OPERATION','You choose the Orca version.','Release metadata comes from Orca. The manager arranges the change and return path. You try the chosen version yourself.')+result
      +`<div class="update-grid"><section class="panel"><span class="eyebrow">OFFICIAL ORCA RELEASES</span><div class="version-pair"><div><span class="small-label">Currently installed</span><strong data-testid="installed-version">${state.version}</strong></div><span class="version-arrow">→</span><div><span class="small-label">Your selection</span><strong>${state.target}</strong></div></div><p class="small-label">Offline release snapshot · 16 November 2026</p><div class="release-list" role="radiogroup" aria-label="Orca target version">${releases.map(r=>`<label class="release-option ${state.target===r.version?'selected':''}"><input type="radio" name="release" value="${r.version}"${state.target===r.version?' checked':''}${disabled(state.busy)}><span class="release-copy"><strong>Orca ${r.version}${state.version===r.version?' · installed':''}</strong><span>${r.date} · Release, as labelled by Orca</span></span>${sourceLink('https://github.com/stablyai/orca/releases/tag/v'+r.version,'Notes')}</label>`).join('')}</div><div class="release-notes"><strong class="small-label">ORCA RELEASE NOTES</strong><p>${target.note}</p></div>${state.activeWork?notice('An agent task is still running.','Finish the work in Orca before stopping its runtime for the version change.','warn'):''}<div class="button-row"><button data-action="update"${disabled(state.busy||state.activeWork||state.version===state.target)}>${state.version===state.target?'Already installed':'Switch to selected version'}</button><button class="quiet" data-action="check" data-service="server"${disabled(state.busy)}>Read runtime status</button></div><details><summary>How does the Proxmox OCI change work?</summary><p class="guide-note">The selected official server package is used to build the OCI image. This is a deployment step, not a local approval or stability rating.</p><p class="guide-note">The host worker replaces the runtime while keeping the manager available. The pilot still needs a real test-host deployment; this demo is simulated.</p></details></section><div><section class="panel"><div class="panel-top"><span class="eyebrow">ORDERED PROCESS</span>${pill(inProgress?'Running':'Started by you',inProgress?'partial':'')}</div><ol class="update-process">${processSteps.map(([title,detail],i)=>{const failed=u?.outcome==='failed'&&i===3,complete=!failed&&u&&(u.outcome||u.step>i),current=inProgress&&state.busy.kind==='update'&&u?.step===i;return `<li class="${failed?'failed':complete?'complete':current?'current':''}"><span class="process-mark">${failed?'!':complete?'✓':i+1}</span><div>${failed?'Orca not reachable':title}<small>${failed?'The saved return path remains available.':detail}</small></div></li>`;}).join('')}</ol><p class="small-label">${inProgress?'Demo process running. You can browse other sections.':'There is no additional local version approval or acceptance stage.'}</p></section><section class="panel" style="margin-top:20px"><span class="eyebrow">ROLLBACK</span><h2>Keep the previous state.</h2>${state.recovery?`<div class="recovery-version">Orca ${state.recovery.version}</div><p>Software and data saved at ${state.recovery.at} · simulated.</p><p>${state.workRevision>state.recovery.workRevision?'There are newer changes since this backup.':'No newer changes have been simulated.'}</p><button class="quiet" data-action="rollback-dialog"${disabled(state.busy)}>Choose rollback</button>`:'<p>The previous software and a consistent data backup will appear here after a version change.</p>'}</section></div></div>`
      +`<div class="demo-evidence"><span class="small-label">DEMO CONTROL · NO REAL TASKS OR FILES</span><div class="button-row">${state.activeWork?'<button class="quiet" data-action="finish-work">Mark agent task as finished</button>':''}<button class="quiet" data-action="data-change"${disabled(state.busy||!state.recovery)}>Simulate a change after update</button></div><p>Demo data revisions: <strong data-testid="work-revision">${state.workRevision}</strong>. Choose “New version fails to start” above to inspect recovery.</p></div>`
      +(state.history.length?`<section class="panel"><span class="eyebrow">HISTORY IN THIS TAB</span>${state.history.map(h=>`<div class="history-item">${escapeHtml(h.text)}<small>${h.at} · simulated</small></div>`).join('')}</section>`:'');
  }
  function render(focus=false) {
    const active=services.some(s=>s.id===state.page)?'connections':state.page;
    nav.innerHTML=[['overview','Overview'],['connections','Connections'],['updates','Versions & updates']].map(([page,title])=>`<button class="nav-button" data-action="navigate" data-page="${page}"${active===page||page==='overview'&&active==='server'?' aria-current="page"':''}>${title}</button>`).join('');
    app.innerHTML=state.page==='overview'?overview():state.page==='connections'?connections():state.page==='updates'?updates():state.page==='server'?server():connection(state.page);
    app.setAttribute('aria-busy',state.busy?'true':'false');
    if (focus) app.querySelector('h1')?.focus({preventScroll:true});
  }
  function navigate(page) {if (!['overview','connections','updates','server',...services.map(s=>s.id)].includes(page)) return;state.page=page;render(true);scrollTo({top:0,behavior:'instant'});}
  async function check(ids) {
    if (state.busy) return;
    const ticket=generation;state.busy={kind:'check'};render();await wait(400);if(ticket!==generation)return;
    ids.forEach(id=>{state.checks[id]={...evaluate(id),at:time(),signature:signature(id)};});state.busy=null;render();notify('Status read. No connection was configured.');
  }
  async function updateVersion() {
    if(state.busy||state.activeWork||state.version===state.target)return;
    const ticket=generation,previous=state.version,target=state.target;
    state.busy={kind:'update'};state.update={step:0,outcome:null};state.recovery=null;
    for(let i=0;i<processSteps.length;i++) {
      state.update.step=i;if(i===2){state.online=false;state.runtimeEpoch++;}if(i===3)state.version=target;
      render();await wait(550);if(ticket!==generation)return;
      if(i===1)state.recovery={version:previous,at:time(),workRevision:state.workRevision,evidence:{...state.evidence}};
    }
    state.online=!state.failUpdate;state.runtimeEpoch++;state.update.outcome=state.failUpdate?'failed':'success';state.busy=null;
    state.history.unshift({text:previous+' → '+target+(state.failUpdate?' · start failed':' · started'),at:time()});render();notify(state.failUpdate?'New version not reachable. Rollback available.':'Version change completed. Try Orca yourself.');
  }
  function rollbackDialog() {
    if(!state.recovery||state.busy)return;
    document.querySelector('#rollback-body').innerHTML=`<span class="eyebrow">RESTORE THE PREVIOUS STATE</span><h2 id="rollback-title">Back to Orca ${state.recovery.version}</h2><p>Backup from ${state.recovery.at}. Choose the rollback scope.</p><div role="radiogroup" aria-label="Rollback scope"><label class="rollback-option"><input type="radio" name="rollback-mode" value="full" checked><span><strong>Restore software and saved data</strong><small>Restore the Orca profile, connections and workspaces to the saved point.</small></span></label><label class="rollback-option"><input type="radio" name="rollback-mode" value="software"><span><strong>Switch software only</strong><small>Keep newer data. Compatibility with the previous version is not confirmed.</small></span></label></div><div id="rollback-impact"></div><div class="button-row"><button id="rollback-start" data-action="rollback">Restore software & data</button><button class="quiet" data-action="cancel-rollback">Cancel</button></div>`;
    rollbackImpact();document.querySelector('#rollback-dialog').showModal();
  }
  function rollbackImpact() {
    const full=document.querySelector('input[name="rollback-mode"]:checked')?.value==='full';
    document.querySelector('#rollback-impact').innerHTML=full?notice('Data will be reset to the backup.',state.workRevision>state.recovery.workRevision?'Newer changes will be discarded by this rollback. This demo only changes simulated data.':'Changes made after the backup would be discarded. None have been added in this scenario.','warn'):notice('Newer data will be kept.','Switching software alone does not undo data migrations. Older software may be unable to read the newer data.','warn');
    document.querySelector('#rollback-start').textContent=full?'Restore software & data':'Switch software only';
  }
  async function rollback() {
    if(!state.recovery||state.busy)return;
    const ticket=generation,backup=state.recovery,restoreData=document.querySelector('input[name="rollback-mode"]:checked')?.value==='full';
    document.querySelector('#rollback-dialog').close();state.busy={kind:'rollback'};state.online=false;state.runtimeEpoch++;render();await wait(900);if(ticket!==generation)return;
    state.version=backup.version;if(restoreData){state.workRevision=backup.workRevision;state.evidence={...backup.evidence};}
    state.online=true;state.runtimeEpoch++;state.recovery=null;state.update={step:4,outcome:'rolled-back',restoreData};state.busy=null;
    state.history.unshift({text:'Back to '+state.version+(restoreData?' · software and data restored':' · newer data kept'),at:time()});render();notify('Rollback completed. Refresh runtime and connection statuses.');
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('button[data-action]');if(!button||button.disabled)return;
    const {action,page,service}=button.dataset;
    if(action==='navigate')navigate(page);
    else if(action==='help')document.querySelector('#demo-help').showModal();
    else if(action==='close-help')document.querySelector('#demo-help').close();
    else if(action==='reset'){reset(state.scenario);notify('Current scenario reset.');}
    else if(action==='check')check([service]);
    else if(action==='check-all')check(['server',...services.map(s=>s.id)]);
    else if(action==='update')updateVersion();
    else if(action==='rollback-dialog')rollbackDialog();
    else if(action==='cancel-rollback')document.querySelector('#rollback-dialog').close();
    else if(action==='rollback')rollback();
    else if(action==='finish-work'&&!state.busy){state.activeWork=false;state.runtimeEpoch++;render();notify('The demo task has finished.');}
    else if(action==='data-change'&&state.recovery&&!state.busy){state.workRevision++;render();notify('A new demo data revision was added.');}
  });
  document.addEventListener('change',event=>{
    const t=event.target;
    if(t.id==='scenario'){reset(t.value);notify('Demo scenario changed.');}
    else if(t.id==='native-state'&&!state.busy){const id=t.dataset.service;if(!evidenceChoices[id].some(([v])=>v===t.value))return;state.evidence[id]=t.value;state.revisions[id]=(state.revisions[id]||0)+1;render();document.querySelector('#native-state')?.focus();notify('Native state changed in the demo. Refresh its status.');}
    else if(t.name==='release'&&!state.busy&&releases.some(r=>r.version===t.value)){state.target=t.value;render();document.querySelector('input[name="release"]:checked')?.focus();}
    else if(t.name==='rollback-mode')rollbackImpact();
  });
  reset();
})();
