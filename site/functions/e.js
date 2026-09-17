// Cloudflare Pages Function: first-party analytics collector endpoint.
// Path: /e  (same origin as the site, so ad-blockers do not drop it)
// Enriches the browser payload with Cloudflare edge intelligence — crucially
// cf.asOrganization, the organisation that owns the visitor's IP — and forwards
// to the lbtrack collector on Box B.

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return new Response('{"ok":false}', { status: 400, headers: json() });
  }
  const cf = request.cf || {};
  const h = request.headers;

  const payload = {
    edge: {
      ip: h.get('CF-Connecting-IP') || '',
      asn: cf.asn || 0,
      asOrganization: cf.asOrganization || '',
      country: cf.country || h.get('CF-IPCountry') || '',
      region: cf.region || '',
      city: cf.city || '',
      postalCode: cf.postalCode || '',
      latitude: cf.latitude || '',
      longitude: cf.longitude || '',
      colo: cf.colo || '',
      timezone: cf.timezone || '',
      httpProtocol: cf.httpProtocol || '',
      tlsVersion: cf.tlsVersion || '',
      verifiedBotCategory: cf.verifiedBotCategory || '',
      ua: h.get('User-Agent') || '',
      acceptLanguage: h.get('Accept-Language') || '',
      host: new URL(request.url).hostname,
    },
    events: Array.isArray(body.events) ? body.events.slice(0, 50) : [],
  };

  // Fire and forget — never make the visitor wait on our collector.
  context.waitUntil(
    fetch(env.LBTRACK_URL || 'https://a.levelbrook.com/i', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-LB-Key': env.LBTRACK_KEY || '' },
      body: JSON.stringify(payload),
    }).catch(() => {})
  );

  return new Response('{"ok":true}', { headers: json() });
}

// Some browsers preflight; keep it cheap.
export async function onRequestOptions() {
  return new Response(null, {
    headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST,OPTIONS' },
  });
}

function json() {
  return { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
}
