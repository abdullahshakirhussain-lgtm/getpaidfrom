// Get Paid From: Cloudflare Worker in front of the static site (site/dist).
// - /api/subscribe, /api/unsubscribe: email alerts per country, stored in KV (binding SIGNUPS).
// - Page views: counted per page and visitor country in Analytics Engine (binding VIEWS). No cookies, no IP addresses.
// Everything else is served from the static assets unchanged.

const EMAIL = /^[^\s@]{1,64}@[^\s@]+\.[^\s@]{2,}$/;
const COUNTRY = /^[A-Z]{2}$/;

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
      if (url.pathname === '/api/subscribe' || url.pathname === '/api/unsubscribe') return handleApi(request, env, url.pathname);
      return json({ ok: false, error: 'Not found.' }, 404);
    }
    const response = await env.ASSETS.fetch(request);
    if (response.status === 200 && (response.headers.get('content-type') || '').includes('text/html')) countView(request, env, url);
    return response;
  },
};
