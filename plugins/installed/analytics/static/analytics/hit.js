/* One pageview per page a browser shows (analytics). The server adds this
   script to every storefront page it answers with 200, so a page Cloudflare
   serves from its cache is counted too, and a redirect or a 404 is not. */
(function () {
  try {
    var body = JSON.stringify({
      name: 'pageview',
      kind: 'pageview',
      url: location.pathname + location.search,
      referrer: document.referrer || ''
    });
    var url = '/api/analytics/track/';
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
    } else {
      fetch(url, {
        method: 'POST',
        body: body,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        keepalive: true
      });
    }
  } catch (e) {}
})();
