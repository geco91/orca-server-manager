// Run inside the optional bridge container. Reads credentials without logging them.
import { readFileSync } from 'node:fs';

const token = readFileSync('/run/secrets/bridge_token', 'utf8').trim();
const endpoint = `http://127.0.0.1:8787/t/${token}/mcp`;
async function rpc(method, params, id) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream' },
    body: JSON.stringify({ jsonrpc: '2.0', ...(id === undefined ? {} : { id }), method, params }),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`MCP HTTP ${response.status}`);
  if (id === undefined) return;
  const text = await response.text();
  const body = response.headers.get('content-type')?.includes('text/event-stream')
    ? text.split(/\r?\n/).filter(line => line.startsWith('data:'))
        .map(line => JSON.parse(line.slice(5).trim())).find(message => message.id === id)
    : JSON.parse(text);
  if (!body) throw new Error('Missing JSON-RPC response');
  if (body.error) throw new Error('MCP JSON-RPC error');
  return body.result;
}
const init = await rpc('initialize', {
  protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'osm-smoke', version: '0.1.0' },
}, 1);
if (!init.protocolVersion) throw new Error('Missing protocol version');
await rpc('notifications/initialized', {});
const inventory = await rpc('tools/list', {}, 2);
if (!inventory.tools.some(tool => tool.name === 'orca')) throw new Error('Orca tool missing');
const health = await rpc('tools/call', { name: 'orca', arguments: { action: 'health', verbose: true } }, 3);
if (health.isError) throw new Error('Bridge health call failed');
const payload = health.structuredContent ?? JSON.parse(health.content.find(item => item.type === 'text').text);
if (payload.statusProbe?.ok !== true) throw new Error('Bridge cannot reach the real Orca runtime');
console.log('PASS: MCP initialize, tools/list and real Orca health; no agent dispatched');
