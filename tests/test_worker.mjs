// Test worker/index.js against a stand-in for Cloudflare's asset store and KV (run: node tests/test_worker.mjs).
import assert from 'node:assert/strict';
import worker from '../worker/index.js';

const pages = {
  '/': '<html lang="en">home</html>',
  '/kenya/': '<html lang="en">kenya</html>',
  '/404.html': '<html lang="en">not found</html>',
  '/es/404/': '<html lang="es">no encontrado</html>',
  '/static/app.js': 'js',
};
const ASSETS = {
  async fetch(req) {
    const path = new URL(req.url).pathname;
    if (pages[path]) return new Response(pages[path], { status: 200, headers: { 'content-type': path.endsWith('.js') ? 'text/javascript' : 'text/html; charset=utf-8' } });
    return new Response(pages['/404.html'], { status: 404, headers: { 'content-type': 'text/html; charset=utf-8' } });
  },
};
const store = new Map();
const SIGNUPS = {
  async get(k, type) { const v = store.get(k); return v && type === 'json' ? JSON.parse(v) : v ?? null; },
  async put(k, v) { store.set(k, v); },
  async delete(k) { store.delete(k); },
};
const env = { ASSETS, SIGNUPS };
const get = (path, init) => worker.fetch(new Request('https://example.test' + path, init), env);
const post = (path, body) => get(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });

let r = await get('/kenya/');
assert.equal(r.status, 200);
assert.match(r.headers.get('content-security-policy'), /default-src 'self'/);
assert.equal(r.headers.get('x-content-type-options'), 'nosniff');
assert.match(await r.text(), /kenya/);

r = await get('/es/no-existe/');
assert.equal(r.status, 404, 'unknown Spanish page is a 404');
assert.match(await r.text(), /no encontrado/, 'and it is the Spanish not-found page');

r = await get('/nowhere/');
assert.equal(r.status, 404);
assert.match(await r.text(), /not found/);

r = await post('/api/subscribe', { email: 'Reader@Example.com', country: 'ke' });
assert.equal(r.status, 200);
assert.deepEqual(JSON.parse(store.get('sub:reader@example.com')).countries, ['KE']);
r = await post('/api/subscribe', { email: 'reader@example.com', country: 'NG' });
assert.deepEqual(JSON.parse(store.get('sub:reader@example.com')).countries, ['KE', 'NG'], 'countries accumulate');

r = await post('/api/subscribe', { email: 'not-an-email', country: 'KE' });
assert.equal(r.status, 400);
r = await post('/api/subscribe', { email: 'a@b.co', country: 'Kenya' });
assert.equal(r.status, 400);
r = await post('/api/subscribe', { email: 'bot@spam.test', country: 'KE', website: 'http://spam' });
assert.equal(r.status, 200, 'honeypot pretends to work');
assert.equal(store.has('sub:bot@spam.test'), false, 'but stores nothing');

r = await post('/api/unsubscribe', { email: 'reader@example.com' });
assert.equal(r.status, 200);
assert.equal(store.has('sub:reader@example.com'), false);

r = await get('/api/subscribe');
assert.equal(r.status, 405);
r = await get('/api/other', { method: 'POST' });
assert.equal(r.status, 404);

r = await get('/api/subscribe', { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded', referer: 'https://example.test/kenya/' }, body: 'email=c%40d.co&country=KE' });
assert.equal(r.status, 303, 'no-JS form posts redirect back');
assert.equal(r.headers.get('location'), 'https://example.test/kenya/?subscribed=1#alerts');

// --- paid packs
const packStore = new Map([['pack:PK', JSON.stringify({ product_id: 'prod-1', updated: '2026-10-31', html: '<h2>Secret steps</h2>' })]]);
const puts = [];
const PACKS = {
  async get(k, type) { const v = packStore.get(k); return v && type === 'json' ? JSON.parse(v) : v ?? null; },
  async put(k, v, opts) { packStore.set(k, v); puts.push([k, opts]); },
};
const sales = {
  'GOOD-KEY-1': { uses: 1, purchase: { product_id: 'prod-1' } },
  'REFUNDED-1': { uses: 1, purchase: { product_id: 'prod-1', refunded: true } },
  'DISPUTED-1': { uses: 1, purchase: { product_id: 'prod-1', disputed: true } },
  'WONDISPUTE': { uses: 1, purchase: { product_id: 'prod-1', disputed: true, dispute_won: true } },
  'OTHERPROD1': { uses: 1, purchase: { product_id: 'prod-2' } },
  'OVERUSED-1': { uses: 11, purchase: { product_id: 'prod-1' } },
};
const calls = [];
let gumroadDown = false;
globalThis.fetch = async (url, init) => {
  assert.equal(url, 'https://api.gumroad.com/v2/licenses/verify');
  const form = new URLSearchParams(init.body);
  calls.push(Object.fromEntries(form));
  if (gumroadDown) return new Response('oops', { status: 500 });
  const sale = sales[form.get('license_key')];
  if (!sale) return new Response(JSON.stringify({ success: false, message: 'That license does not exist.' }), { status: 404 });
  return new Response(JSON.stringify({ success: true, ...sale }), { status: 200 });
};
const penv = { ASSETS, SIGNUPS, PACKS };
const pack = async (body) => {
  const res = await worker.fetch(new Request('https://example.test/api/pack', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }), penv);
  return [res.status, await res.json(), res];
};

let [st, d, res] = await pack({ country: 'PK', key: 'GOOD-KEY-1', fresh: true });
assert.equal(st, 200);
assert.match(d.html, /Secret steps/, 'a valid key opens the pack');
assert.equal(res.headers.get('cache-control'), 'no-store', 'pack text is never cached');
assert.match(res.headers.get('content-security-policy'), /default-src/);
assert.equal(calls.at(-1).increment_uses_count, 'true', 'typing a key counts as an unlock');
assert.equal(calls.at(-1).product_id, 'prod-1');
assert.equal(puts.at(-1)[1].expirationTtl, 86400, 'the check is remembered for a day only');
assert.ok(![...packStore.keys(), ...packStore.values()].some((v) => v.includes('GOOD-KEY-1')), 'the key itself is never stored');

let before = calls.length;
[st, d] = await pack({ country: 'pk', key: 'GOOD-KEY-1' });
assert.equal(st, 200, 'quiet re-open works');
assert.equal(calls.length, before, 'and uses the remembered check, not another Gumroad call');

for (const [key, code] of [['NOSUCHKEY1', 'invalid'], ['REFUNDED-1', 'refunded'], ['DISPUTED-1', 'refunded'], ['OTHERPROD1', 'invalid'], ['OVERUSED-1', 'too_many']]) {
  [st, d] = await pack({ country: 'PK', key, fresh: true });
  assert.equal(st, 403, key);
  assert.equal(d.code, code, key);
  assert.equal(d.html, undefined, `${key} must not get the pack`);
}
[st] = await pack({ country: 'PK', key: 'WONDISPUTE', fresh: true });
assert.equal(st, 200, 'a dispute the seller won keeps access');
[st] = await pack({ country: 'PK', key: 'OVERUSED-1' });
assert.equal(st, 200, 'the device limit only applies to typed keys');

[st, d] = await pack({ country: 'PK', key: 'bad key!', fresh: true });
assert.equal(st, 400, 'malformed key never reaches Gumroad');
[st] = await pack({ country: 'NG', key: 'GOOD-KEY-1', fresh: true });
assert.equal(st, 404, 'no pack for this country');
[st] = await pack({ country: 'P', key: 'GOOD-KEY-1', fresh: true });
assert.equal(st, 404);

gumroadDown = true;
[st, d] = await pack({ country: 'PK', key: 'FRESHKEY-9', fresh: true });
assert.equal(st, 503, 'fails closed when Gumroad is down');
assert.equal(d.code, 'unavailable');
assert.equal(d.html, undefined);
[st, d] = await pack({ country: 'PK', key: 'GOOD-KEY-1' });
assert.equal(st, 200, 'a buyer already checked today still gets in during an outage');
gumroadDown = false;

r = await worker.fetch(new Request('https://example.test/api/pack'), penv);
assert.equal(r.status, 405);
r = await worker.fetch(new Request('https://example.test/api/pack', { method: 'POST', body: '{}' }), env);
assert.equal(r.status, 404, 'no PACKS binding: nothing to sell');

console.log('worker: OK');
