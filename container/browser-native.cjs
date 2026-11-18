'use strict';

// Run only with the Node interpreter shipped in the checksum-verified Orca desktop.
const fs = require('node:fs');
const path = require('node:path');
const out = '/opt/Orca/resources/app.asar.unpacked/out';
const { RuntimeClient } = require(path.join(out, 'cli/runtime/client.js'));
const { parsePairingCode } = require(path.join(out, 'shared/remote-runtime/pairing/pairing.js'));
const { exchangeCliPairingCode } = require(path.join(out, 'cli/runtime/pairing/environment-pairing-exchange.js'));
const store = require(path.join(out, 'shared/remote-runtime/host-store/runtime-environment-store.js'));
const profile = process.env.ORCA_USER_DATA_PATH;
const internal = 'ws://127.0.0.1:6768';
const name = 'Workspace server';
const local = new RuntimeClient(profile, 4000, null, null);

async function run() {
  const action = process.argv[2];
  if (action === 'enroll') {
    // Bearer credentials enter on stdin. Only the public environment ID leaves this process.
    const { pairingUrl } = JSON.parse(fs.readFileSync(0, 'utf8'));
    const offer = parsePairingCode(pairingUrl);
    if (offer?.scope !== 'runtime' || offer.endpoint !== internal) throw new Error();
    const pairingCode = await exchangeCliPairingCode(pairingUrl);
    const identity = process.argv[3];
    const env = identity
      ? await store.updateEnvironmentFromPairingCode(profile, identity, { pairingCode })
      : await store.addEnvironmentFromPairingCode(profile, { name, pairingCode });
    const remote = new RuntimeClient(profile, 6000, null, env.id);
    const status = await remote.call('status.get');
    if (!status.result.runtimeId) throw new Error();
    return { id: env.id };
  }
  if (action === 'probe') {
    const status = (await local.call('status.get')).result;
    const metadata = JSON.parse(fs.readFileSync(path.join(profile, 'orca-runtime.json'), 'utf8'));
    const bound = metadata.transports?.find(transport => transport.kind === 'websocket');
    if (!bound || new URL(bound.endpoint).port !== '6770') return { state: 'display' };
    const caps = status.capabilities || [];
    if (!caps.includes('browser.screencast.v1') || !caps.includes('mobile.desktop-relay.v1')) {
      return { state: 'display' };
    }
    const remote = new RuntimeClient(profile, 5000, null, process.argv[3]);
    try {
      const result = (await remote.call('status.get')).result;
      const supportsRelay = result.capabilities?.includes('pairing.delegated-mobile-devices.v1');
      return { state: supportsRelay ? 'ready' : 'incompatible' };
    } catch (error) {
      return { state: error.code === 'unauthorized' ? 'revoked' : 'disconnected' };
    }
  }
  if (action === 'offer') {
    const address = process.argv[3];
    if (!address) throw new Error();
    const { result: offer } = await local.call('pairing.createOffer', {
      scope: 'mobile', address, relay: false,
    });
    const decoded = offer.available && parsePairingCode(offer.pairingUrl);
    if (offer.scope !== 'mobile' || offer.endpoint !== address ||
        decoded?.scope !== 'mobile' || decoded.endpoint !== address) {
      throw new Error();
    }
    return { pairing_url: offer.pairingUrl };
  }
  throw new Error();
}

run()
  .then(result => process.stdout.write(JSON.stringify(result)))
  .catch(() => { process.exitCode = 1; });
