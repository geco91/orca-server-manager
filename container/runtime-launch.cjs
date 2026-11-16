'use strict';
const {spawn} = require('node:child_process');
const fs = require('node:fs');

const children = new Set();
let stopping = false;
function start(command, args, environment, optional = false) {
  // Optional upstream services may print token-bearing endpoint URLs. Keep those
  // streams private; report their lifecycle and technical health separately.
  const child = spawn(command, args, {env: environment, stdio: optional ? 'ignore' : 'inherit', detached: true});
  children.add(child);
  child.on('error', () => {
    console.error(optional ? 'Optional integration could not start.' : 'Orca could not start.');
    if (!optional) shutdown(1);
  });
  child.on('exit', (code) => {
    children.delete(child);
    if (!stopping && !optional) shutdown(code || 1);
    else if (!stopping && optional) console.error('An optional integration stopped; Orca remains available.');
  });
  return child;
}
function shutdown(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    try {process.kill(-child.pid, 'SIGTERM');} catch {}
  }
  const timer = setTimeout(() => {
    for (const child of children) {
      try {process.kill(-child.pid, 'SIGKILL');} catch {}
    }
    process.exit(code);
  }, 15000);
  const interval = setInterval(() => {
    if (!children.size) {clearTimeout(timer); clearInterval(interval); process.exit(code);}
  }, 100);
}
process.on('SIGTERM', () => shutdown());
process.on('SIGINT', () => shutdown());
start('/usr/local/bin/orca', ['serve', '--bind', '0.0.0.0', '--port', '6768', '--no-pairing'], process.env);
const tokenFile = '/run/secrets/bridge_token';
if (fs.existsSync(tokenFile)) {
  const token = fs.readFileSync(tokenFile, 'utf8').trim();
  const toolsetsFile = '/run/secrets/bridge-toolsets';
  const requested = fs.existsSync(toolsetsFile) ? fs.readFileSync(toolsetsFile, 'utf8').trim() : process.env.ORCA_BRIDGE_TOOLSETS;
  const toolsets = requested === 'status,dispatch' ? requested : 'status';
  if (token.length >= 32) {
    start(process.execPath, ['/opt/orca-mcp/server.mjs', '--port', '8787'],
      {...process.env, ORCA_CLI_COMMAND: '/usr/local/bin/orca', ORCA_BRIDGE_TOKEN: token, ORCA_BRIDGE_TOOLSETS: toolsets, ORCA_BRIDGE_CLI_HARDENING: '1'}, true);
  }
}
// An existing tunnel binary/profile can be mounted by the administrator.
// Never accept commands or credentials from a browser request.
const tunnelCommand = '/run/secrets/tunnel-command.json';
if (fs.existsSync(tunnelCommand)) {
  try {
    const argv = JSON.parse(fs.readFileSync(tunnelCommand, 'utf8'));
    if (!Array.isArray(argv) || !argv.length || argv.length > 32 ||
        argv.some(arg => typeof arg !== 'string') || !argv[0].startsWith('/opt/tunnel/')) {
      throw new Error('Invalid tunnel command');
    }
    start(argv[0], argv.slice(1), process.env, true);
  } catch {console.error('Tunnel configuration is unavailable or invalid.');}
}
