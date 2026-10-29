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

console.log('worker: OK');
