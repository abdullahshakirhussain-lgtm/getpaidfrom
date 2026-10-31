// Get Paid From: Cloudflare Worker in front of the static site (site/dist).
// - /api/subscribe, /api/unsubscribe: email alerts per country, stored in KV (binding SIGNUPS).
// - /api/pack: opens a paid Country Pack after checking the buyer's Gumroad license key. Pack text lives only in KV
//   (binding PACKS), never in the static site or the public repo.
// - Page views: counted per page and visitor country in Analytics Engine (binding VIEWS). No cookies, no IP addresses.
// - Unknown pages under /<lang>/ get that language's not-found page (status 404).
// - Security headers on everything the Worker returns.
// Everything else is served from the static assets unchanged.

const EMAIL = /^[^\s@]{1,64}@[^\s@]+\.[^\s@]{2,}$/;
const COUNTRY = /^[A-Z]{2}$/;
const LANG_PATH = /^\/(es|fr|pt|ar|ur|bn|id|vi)\//;
// Pages use no inline scripts or third-party resources; logos set their brand colour with a style attribute.
const SECURITY = {
  'content-security-policy': "default-src 'self'; img-src 'self' data:; style-src 'self'; style-src-attr 'unsafe-inline'; script-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'",
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'strict-origin-when-cross-origin',
  'permissions-policy': 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
  'strict-transport-security': 'max-age=31536000',
};

function secured(response) {
  const r = new Response(response.body, response);
  for (const [k, v] of Object.entries(SECURITY)) r.headers.set(k, v);
  return r;
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
}

async function readBody(request) {
  const type = request.headers.get('content-type') || '';
  if (type.includes('application/json')) return await request.json().catch(() => ({}));
  const form = await request.formData().catch(() => null);
  return form ? Object.fromEntries(form) : {};
}

function backTo(request, query) {
  // no-JS form posts: send the reader back to the page they came from
  const ref = request.headers.get('referer');
  const url = new URL(ref && new URL(ref).host === new URL(request.url).host ? ref : '/', request.url);
  url.search = query;
  url.hash = 'alerts';
  return Response.redirect(url.toString(), 303);
}

async function handleApi(request, env, path) {
  if (request.method !== 'POST') return json({ ok: false, error: 'Use POST.' }, 405);
  const wantsJson = (request.headers.get('content-type') || '').includes('application/json');
  const body = await readBody(request);
  if (body.website) return wantsJson ? json({ ok: true }) : backTo(request, 'subscribed=1'); // honeypot: pretend it worked
  const email = String(body.email || '').trim().toLowerCase();
  if (email.length > 254 || !EMAIL.test(email)) return wantsJson ? json({ ok: false, error: 'That email address doesn’t look right.' }, 400) : backTo(request, 'error=email');
  const key = 'sub:' + email;

  if (path === '/api/unsubscribe') {
    await env.SIGNUPS.delete(key);
    return wantsJson ? json({ ok: true }) : backTo(request, 'unsubscribed=1');
  }

  const country = String(body.country || '').toUpperCase();
  if (!COUNTRY.test(country)) return wantsJson ? json({ ok: false, error: 'Missing country.' }, 400) : backTo(request, 'error=country');
  const now = new Date().toISOString();
  const existing = await env.SIGNUPS.get(key, 'json');
  const record = existing || { email, countries: [], created: now };
  if (!record.countries.includes(country)) record.countries.push(country);
  record.updated = now;
  await env.SIGNUPS.put(key, JSON.stringify(record));
  return wantsJson ? json({ ok: true }) : backTo(request, 'subscribed=1');
}

const VERIFY_URL = 'https://api.gumroad.com/v2/licenses/verify'; // no access token needed for this call
const LICENSE_KEY = /^[A-Za-z0-9-]{8,64}$/;
const MAX_UNLOCKS = 10; // Gumroad counts uses; the owner can reset a buyer's count from the Sales dashboard
const CHECK_CACHE_SECONDS = 86400; // a refund stops access within a day

async function sha256(text) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

// 'ok' | 'invalid' | 'refunded' | 'too_many' | 'unavailable'
async function checkLicense(env, productId, key, fresh) {
  const cacheKey = 'lic:' + await sha256(productId + ':' + key); // the key itself is never stored
  if (!fresh && await env.PACKS.get(cacheKey)) return 'ok';
  let res, data;
  try {
    res = await fetch(env.GUMROAD_VERIFY_URL || VERIFY_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      // a key typed into the form counts as one unlock; the browser quietly re-opening a pack doesn't
      body: new URLSearchParams({ product_id: productId, license_key: key, increment_uses_count: fresh ? 'true' : 'false' }),
    });
    if (res.status === 404) return 'invalid';
    if (!res.ok) return 'unavailable';
    data = await res.json();
  } catch (e) {
    return 'unavailable';
  }
  const purchase = data.purchase || {};
  if (!data.success || purchase.product_id !== productId) return 'invalid';
  if (purchase.refunded || purchase.chargebacked || (purchase.disputed && !purchase.dispute_won)) return 'refunded';
  if (fresh && data.uses > MAX_UNLOCKS) return 'too_many';
  await env.PACKS.put(cacheKey, '1', { expirationTtl: CHECK_CACHE_SECONDS });
  return 'ok';
}

const PACK_ERRORS = {
  invalid: [403, 'That key doesn’t match this pack. Copy it from your Gumroad receipt, with the dashes.'],
  refunded: [403, 'This purchase was refunded or disputed, so the key no longer opens the pack.'],
  too_many: [403, 'This key has been used too many times. Email the support address on your Gumroad receipt and we’ll reset it.'],
  unavailable: [503, 'We couldn’t check your key just now. Please try again in a few minutes.'],
};

async function handlePack(request, env) {
  if (request.method !== 'POST') return json({ ok: false, error: 'Use POST.' }, 405);
  const body = await request.json().catch(() => ({}));
  const country = String(body.country || '').toUpperCase();
  const key = String(body.key || '').trim();
  if (!COUNTRY.test(country) || !env.PACKS) return json({ ok: false, error: 'This pack isn’t available.' }, 404);
  if (!LICENSE_KEY.test(key)) return json({ ok: false, code: 'invalid', error: PACK_ERRORS.invalid[1] }, 400);
  const pack = await env.PACKS.get('pack:' + country, 'json');
  if (!pack) return json({ ok: false, error: 'This pack isn’t available.' }, 404);
  const result = await checkLicense(env, pack.product_id, key, body.fresh === true);
  if (result !== 'ok') return json({ ok: false, code: result, error: PACK_ERRORS[result][1] }, PACK_ERRORS[result][0]);
  return json({ ok: true, html: pack.html, updated: pack.updated });
}

function countView(request, env, url) {
  if (!env.VIEWS || request.method !== 'GET') return;
  const ref = request.headers.get('referer');
  let refHost = '';
  try { refHost = ref ? new URL(ref).hostname : ''; } catch (e) { refHost = ''; }
  if (refHost === url.hostname) refHost = '(internal)';
  env.VIEWS.writeDataPoint({
    blobs: [url.pathname, (request.cf && request.cf.country) || '', refHost],
    doubles: [1],
    indexes: [url.pathname.slice(0, 96)],
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) {
      if (url.pathname === '/api/subscribe' || url.pathname === '/api/unsubscribe') return secured(await handleApi(request, env, url.pathname));
      if (url.pathname === '/api/pack') return secured(await handlePack(request, env));
      return secured(json({ ok: false, error: 'Not found.' }, 404));
    }
    let response = await env.ASSETS.fetch(request);
    const lang = url.pathname.match(LANG_PATH);
    if (response.status === 404 && lang && request.method === 'GET') {
      const page = await env.ASSETS.fetch(new Request(new URL(`/${lang[1]}/404/`, url), request));
      if (page.status === 200) response = new Response(page.body, { status: 404, headers: page.headers });
    }
    if (response.status === 200 && (response.headers.get('content-type') || '').includes('text/html')) countView(request, env, url);
    return secured(response);
  },
};
