const { spawnSync } = require('node:child_process');
const result = spawnSync('orca', ['status', '--json'], { encoding: 'utf8', timeout: 8000 });
try {
  const status = JSON.parse(result.stdout);
  process.exit(result.status === 0 && status.ok === true && status.result?.runtime?.reachable === true ? 0 : 1);
} catch {
  process.exit(1);
}
