'use strict';
// The official clients own the device grant and store credentials in the Orca user's HOME.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const {spawn, spawnSync} = require('node:child_process');

const lifetime = 600_000;
const clients = {
  github: ['gh', 'auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https'],
  gitlab: ['glab', 'auth', 'login', '--hostname', 'gitlab.com', '--device', '--git-protocol', 'https',
    '--api-protocol', 'https', '--setup-git-credential-helper'],
};
const codePattern = /^[A-Z0-9]{4}-?[A-Z0-9]{4}$/;
const privateRoot = path.join(os.tmpdir(), 'osm-git-' + process.getuid());

function privateDirectory(directory) {
  try { fs.mkdirSync(directory, {mode: 0o700}); } catch (error) { if (error.code !== 'EEXIST') throw error; }
  const info = fs.lstatSync(directory);
  if (!info.isDirectory() || info.uid !== process.getuid() || (info.mode & 0o077)) throw new Error('Private directory unavailable.');
}

function save(file, state) {
  const temporary = file + '.' + randomUUID();
  fs.writeFileSync(temporary, JSON.stringify(state), {flag: 'wx', mode: 0o600});
  fs.renameSync(temporary, file);
}

function read(file) {
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  try {
    const info = fs.fstatSync(fd);
    if (!info.isFile() || info.uid !== process.getuid() || (info.mode & 0o077) || info.size > 1024) throw new Error('Invalid state.');
    return JSON.parse(fs.readFileSync(fd, 'utf8'));
  } finally { fs.closeSync(fd); }
}

function extractUserCode(output) {
  const plain = output.replace(/\x1b\[[0-9;]*m/g, '');
  const code = /one-time code:\s*([a-z0-9-]+)(?=\s)/i.exec(plain)?.[1]?.toUpperCase();
  return code && codePattern.test(code) ? code : null;
}

function authorize(provider, file) {
  const [command, ...args] = clients[provider];
  const env = {...process.env, BROWSER: '/bin/true', GH_BROWSER: '/bin/true', GH_PROMPT_DISABLED: '1',
    GLAB_PROMPT_DISABLED: 'true', NO_COLOR: '1', LC_ALL: 'C', GIT_TERMINAL_PROMPT: '0'};
  const child = spawn(command, args, {env, stdio: ['ignore', 'pipe', 'pipe']});
  let waiting = false;
  let expired = false;
  const expiry = setTimeout(() => {
    expired = true;
    child.kill('SIGKILL');
  }, lifetime);
  // Parse only the human-facing user code. Discard all raw CLI output.
  for (const stream of [child.stdout, child.stderr]) {
    let suffix = '';
    stream.setEncoding('utf8');
    stream.on('data', chunk => {
      if (waiting) return;
      suffix = (suffix + chunk).slice(-4096);
      const code = extractUserCode(suffix);
      if (code) {
        waiting = true;
        suffix = '';
        save(file, {state: 'waiting', code});
      }
    });
  }
  child.on('error', () => {}); // "close" also fires for an unavailable executable.
  child.on('close', status => {
    clearTimeout(expiry);
    let success = status === 0;
    if (success && provider === 'github') {
      success = spawnSync('gh', ['auth', 'setup-git', '--hostname', 'github.com'],
        {env, stdio: 'ignore', timeout: 10000}).status === 0;
    }
    save(file, {state: expired ? 'expired' : success ? 'authorized' : 'failed'});
  });
}

function forgejoKey() {
  const ssh = path.join(os.homedir(), '.ssh');
  if (!fs.existsSync(ssh)) fs.mkdirSync(ssh, {mode: 0o700});
  const info = fs.lstatSync(ssh);
  if (!info.isDirectory() || info.uid !== process.getuid() || (info.mode & 0o022)) throw new Error('SSH directory unavailable.');
  const key = path.join(ssh, 'id_ed25519');
  if (!fs.lstatSync(key, {throwIfNoEntry: false})) {
    if (fs.lstatSync(key + '.pub', {throwIfNoEntry: false})) throw new Error('An existing public key has no matching identity.');
    const created = spawnSync('ssh-keygen', ['-q', '-t', 'ed25519', '-N', '', '-C', 'Orca runtime', '-f', key],
      {stdio: 'ignore', timeout: 10000});
    if (created.status !== 0) throw new Error('Key preparation failed.');
  }
  const identity = fs.lstatSync(key);
  if (!identity.isFile() || identity.uid !== process.getuid() || (identity.mode & 0o077)) throw new Error('SSH identity unavailable.');
  const fd = fs.openSync(key + '.pub', fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  let publicKey;
  try {
    const info = fs.fstatSync(fd);
    if (!info.isFile() || info.uid !== process.getuid() || (info.mode & 0o022) || info.size > 4096) throw new Error('Invalid public key file.');
    const buffer = Buffer.alloc(4097);
    const count = fs.readSync(fd, buffer, 0, buffer.length, 0);
    if (count > 4096) throw new Error('Invalid public key file.');
    publicKey = buffer.subarray(0,count).toString('utf8').trim().split(/\s+/).slice(0, 2).join(' ');
  } finally { fs.closeSync(fd); }
  if (!/^ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI[A-Za-z0-9+/]{43}$/.test(publicKey)) throw new Error('Public key unavailable.');
  return {state: 'key_ready', public_key: publicKey};
}

async function main([operation, provider, id]) {
  if (!/^[a-f0-9]{32}$/.test(id || '')) throw new Error('Invalid attempt.');
  if (operation === 'start' && provider === 'forgejo') return forgejoKey();
  if (!Object.hasOwn(clients, provider)) throw new Error('Invalid provider.');
  privateDirectory(privateRoot);
  const file = path.join(privateRoot, provider + '-' + id + '.json');
  if (operation === 'authorize') { authorize(provider, file); return; }
  if (operation === 'read') return read(file);
  if (operation !== 'start') throw new Error('Invalid operation.');
  for (const entry of fs.readdirSync(privateRoot)) {
    if (!/^(github|gitlab)-[a-f0-9]{32}\.json$/.test(entry)) continue;
    const previous = path.join(privateRoot, entry);
    if (Date.now() - fs.lstatSync(previous).mtimeMs > lifetime + 60_000) fs.unlinkSync(previous);
  }
  if (fs.existsSync(file)) return read(file);
  save(file, {state: 'starting'});
  const daemon = spawn(process.execPath, [__filename, 'authorize', provider, id],
    {detached: true, stdio: 'ignore', cwd: os.homedir()});
  daemon.unref();
  // Most offers arrive immediately. A slow provider can be observed on the next worker tick.
  for (let i = 0; i < 25; i++) {
    await new Promise(resolve => setTimeout(resolve, 200));
    const state = read(file);
    if (state.state !== 'starting') return state;
  }
  return {state: 'starting'};
}

module.exports = {extractUserCode};
if (require.main === module) {
  main(process.argv.slice(2)).then(value => {
    if (value) process.stdout.write(JSON.stringify(value));
  }).catch(() => { process.exitCode = 1; });
}
