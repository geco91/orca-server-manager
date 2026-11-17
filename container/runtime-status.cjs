'use strict';
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function run(command, args, timeout = 7000) {
  return spawnSync(command, args, {encoding:'utf8',timeout,maxBuffer:512*1024,env:process.env});
}
function cli(args) {
  const result = run('/usr/local/bin/orca', args);
  if (result.status !== 0) return null;
  try {return JSON.parse(result.stdout);} catch {return null;}
}
function installed(command) {
  return (process.env.PATH || '').split(':').some(directory => {
    try {fs.accessSync(path.join(directory,command),fs.constants.X_OK);return true;} catch {return false;}
  });
}
const status = cli(['status','--json']);
const native = status?.result?.runtime;
const reachable = status?.ok === true && native?.reachable === true;
const webCheck = reachable && fs.existsSync('/opt/orca/out/web/web-index.html') &&
  run(process.execPath,['-e',`const http=require('node:http');const req=http.request('http://127.0.0.1:6768/web-index.html',{method:'HEAD'},res=>{res.resume();process.exit(res.statusCode===200&&String(res.headers['content-type']).includes('text/html')?0:1)});req.on('error',()=>process.exit(1));req.setTimeout(2000,()=>{req.destroy();process.exit(1)});req.end();`],3000).status===0;
const address=Object.values(os.networkInterfaces()).flat().find(entry=>entry?.family==='IPv4'&&!entry.internal)?.address;
const webUrl=webCheck&&address?`http://${address}:6768/web-index.html`:'';
let version = 'Unknown';
try {version=fs.readFileSync('/opt/orca/VERSION','utf8').match(/^orca (.+)$/m)?.[1] || 'Unknown';} catch {}
const terminals = reachable ? cli(['terminal','list','--json']) : null;
const terminalRows = terminals?.result?.terminals;
const terminalResult = terminals?.result;
const completeCensus = terminals?.ok === true && terminalResult?.truncated === false &&
  terminalResult?.hostScope?.hostIds?.includes('local') &&
  !terminalResult?.hostScope?.omittedHostIds?.includes('local');
const activeTerminals = completeCensus && Array.isArray(terminalRows) ? terminalRows.length : null;
const accounts = reachable ? cli(['account','list','--json']) : null;
const hasCodex = installed('codex'), hasOpenCode = installed('opencode');
const codexAuth = hasCodex ? run('codex',['login','status']).status === 0 : false;
const accountResult = accounts?.result || {};
function accountCount(key) {
  const rows = accountResult[key]?.accounts;
  return Array.isArray(rows) ? rows.length : null;
}
const providers = {
  state: codexAuth ? 'ready' : 'partial',
  label: codexAuth ? 'Codex reports a native login' : 'Native setup required',
  detail:'Install and sign in inside the runtime. A registered account alone does not prove a successful agent task.',
  checks:[
    {name:'Codex CLI',value:hasCodex?'Installed':'Not installed'},
    {name:'OpenCode CLI',value:hasOpenCode?'Installed':'Not installed'},
    {name:'Managed Codex accounts',value:String(accountCount('codex') ?? 'Not observable')},
    {name:'Managed OpenCode accounts',value:String(accountCount('opencode') ?? 'Not observable')},
    {name:'Native Codex login',value:codexAuth?'Present according to Codex CLI':'Not confirmed'},
    {name:'Agent task',value:'Not started by this status check'}
  ]
};
const github = {state:'partial',label:'Server login not verified',detail:'GitHub is optional. Sign in with the native GitHub CLI on the runtime.',checks:[]};
if (installed('gh')) {
  const result = run('gh',['api','user','--jq','.login']);
  const login = result.status===0 ? result.stdout.trim() : '';
  if (/^[a-zA-Z0-9-]{1,40}$/.test(login)) {
    github.state='ready';github.label='Server signed in';
    github.detail='The server-owned GitHub identity was read through the native CLI.';
    github.checks=[{name:'Server identity',value:login},{name:'Repository permissions',value:'Depend on the selected repository; not inferred from this login.'}];
  }
} else {github.label='GitHub CLI missing';}
const clients = {state:'unknown',label:'Inspect in Orca',detail:'This adapter has no supported native client census. Pairing and current connectivity are not inferred from an open port.',checks:[]};
const bridge = {state:'partial',label:'Bridge token not configured',detail:'The existing community bridge is optional and starts after its private token is configured.',checks:[]};
if (fs.existsSync('/run/secrets/bridge_token')) {
  const result=run(process.execPath,['/opt/osm/mcp-health.mjs'],20000);
  const verified = result.status===0 && reachable;
  bridge.state=verified?'ready':'error';
  bridge.label=verified?'MCP and Orca reachable':'Bridge health not confirmed';
  bridge.detail=verified?'MCP initialize, tools/list and a read-only Orca health call succeeded. No agent was started.':'Inspect the bridge configuration and runtime; no credentials are included in this result.';
}
const tunnel={state:'unknown',label:'External path not verified',detail:'Use the existing OpenAI Secure MCP Tunnel. A local process alone does not prove that an external coordinator can reach Orca.',checks:[]};
if (fs.existsSync('/run/secrets/tunnel-command.json')) {
  const local = run(process.execPath, ['-e', "fetch('http://127.0.0.1:8080/readyz',{signal:AbortSignal.timeout(2000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"], 4000);
  tunnel.state='partial';
  tunnel.label=local.status===0?'Local tunnel readiness responded':'Tunnel configured; readiness not confirmed';
  tunnel.checks=[{name:'Local /readyz',value:local.status===0?'Responded successfully':'Not confirmed'},
    {name:'Authenticated end-to-end MCP call',value:'Not verified by this local probe'}];
}
console.log(JSON.stringify({schema:1,runtime:{reachable,version,active_terminals:activeTerminals,web_url:webUrl},
  integrations:{providers,github,desktop:clients,mobile:clients,mcp:bridge,tunnel}}));
