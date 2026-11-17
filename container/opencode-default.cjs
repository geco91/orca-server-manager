'use strict';
// One-time native host preference. No account, credential or task is created.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const {randomUUID} = require('node:crypto');

const MAX_BYTES = 512 * 1024;
function privateFile(file, limit = MAX_BYTES) {
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  try {
    const info = fs.fstatSync(fd);
    if (!info.isFile() || info.uid !== process.getuid() || info.nlink !== 1 ||
        (info.mode & 0o077) || info.size > limit) throw new Error('Private native state is unavailable.');
    const buffer = Buffer.alloc(limit + 1);
    const length = fs.readSync(fd, buffer, 0, limit + 1, 0);
    if (length > limit) throw new Error('Private native state is too large.');
    return JSON.parse(buffer.subarray(0, length).toString('utf8'));
  } finally {fs.closeSync(fd);}
}

function nativeSettings(userData, updates, timeout = 5000) {
  const metadata = privateFile(path.join(userData, 'orca-runtime.json'));
  const transport = (metadata.transports || []).find(item => item.kind === 'unix');
  if (!transport || !path.isAbsolute(transport.endpoint) || typeof metadata.authToken !== 'string' ||
      !metadata.authToken || typeof metadata.runtimeId !== 'string') throw new Error('Native settings are unavailable.');
  const parent = fs.lstatSync(path.dirname(transport.endpoint));
  const endpoint = fs.lstatSync(transport.endpoint);
  if (!parent.isDirectory() || parent.uid !== process.getuid() || (parent.mode & 0o022) ||
      !endpoint.isSocket() || endpoint.uid !== process.getuid()) throw new Error('The native socket is not private.');
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const socket = net.createConnection(transport.endpoint);
    let buffer = '', finished = false;
    function finish(error, settings) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      socket.destroy();
      if (error) reject(new Error('The native settings request did not complete.'));
      else resolve(settings);
    }
    const timer = setTimeout(() => finish(true), timeout);
    socket.setEncoding('utf8');
    socket.on('error', () => finish(true));
    socket.on('close', () => {if (!finished) finish(true);});
    socket.on('connect', () => socket.write(JSON.stringify({id, authToken:metadata.authToken,
      method:updates ? 'settings.update' : 'settings.get', ...(updates ? {params:updates} : {})}) + '\n'));
    socket.on('data', chunk => {
      buffer += chunk;
      if (Buffer.byteLength(buffer) > MAX_BYTES) return finish(true);
      let split;
      while (!finished && (split = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, split); buffer = buffer.slice(split + 1);
        if (!line.trim()) continue;
        try {
          const reply = JSON.parse(line);
          if (reply._keepalive === true) continue;
          if (reply.id !== id || reply.ok !== true || reply._meta?.runtimeId !== metadata.runtimeId ||
              !reply.result?.settings || typeof reply.result.settings !== 'object' || Array.isArray(reply.result.settings)) return finish(true);
          finish(false, reply.result.settings);
        } catch {finish(true);}
      }
    });
  });
}

function readSettings(userData, timeout) {return nativeSettings(userData, null, timeout);}

async function configure({userData, executable = '/usr/local/bin/opencode', timeout = 60000}) {
  fs.accessSync(executable, fs.constants.X_OK);
  const marker = path.join(userData, '.osm-opencode-default.json');
  if (fs.existsSync(marker)) {
    const saved = privateFile(marker, 4096);
    if (saved.schema !== 1) throw new Error('The host default record is not supported.');
    return {state:'preserved'};
  }
  const deadline = Date.now() + timeout;
  let settings;
  while (Date.now() < deadline) {
    try {settings = await readSettings(userData, Math.min(5000, Math.max(1, deadline - Date.now()))); break;}
    catch {await new Promise(resolve => setTimeout(resolve, 250));}
  }
  if (!settings) throw new Error('Orca settings are not ready.');
  const previous = settings.defaultTuiAgent;
  const apply = previous === null || previous === undefined;
  if (apply) {
    const result = await nativeSettings(userData, {defaultTuiAgent:'opencode'});
    if (result.defaultTuiAgent !== 'opencode') throw new Error('The native host default was not saved.');
  }
  const temporary = marker + '.' + randomUUID();
  try {
    fs.writeFileSync(temporary, JSON.stringify({schema:1,applied:apply}), {mode:0o600,flag:'wx'});
    fs.renameSync(temporary, marker);
  } finally {try {fs.unlinkSync(temporary);} catch {}}
  return {state:apply ? 'configured' : 'preserved'};
}

module.exports = {configure, readSettings};
if (require.main === module) {
  const userData = process.env.ORCA_USER_DATA_PATH || path.join(os.homedir(), '.config', 'Orca');
  configure({userData}).catch(() => {
    console.error('OpenCode default setup is pending. Native account and provider setup remains available.');
    process.exitCode = 1;
  });
}
