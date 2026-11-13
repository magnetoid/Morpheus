/* Offer the page in the visitor's language. The page is cached and the same for
   every visitor, so the decision is made here, not on the server. */
(function () {
  var COOKIE = 'morpheus_lang_choice';
  var node = document.getElementById('morpheus-language-bar');
  if (!node || !document.body) return;
  var data;
  try { data = JSON.parse(node.textContent); } catch (e) { return; }
  var languages = (data && data.languages) || {};

  function primary(tag) { return String(tag || '').toLowerCase().split('-')[0]; }
  function readChoice() {
    var m = document.cookie.match(new RegExp('(?:^|; )' + COOKIE + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
  }
  function setChoice(code) {
    document.cookie = COOKIE + '=' + encodeURIComponent(code) +
      '; max-age=31536000; path=/; SameSite=Lax';
  }

  if (readChoice()) return;
  // A crawler that runs scripts must not index the bar as page text.
  if (/bot|crawl|spider|slurp|lighthouse|headless|facebookexternalhit/i.test(navigator.userAgent)) return;
  var pageLang = primary(document.documentElement.lang);
  var wanted = '';
  var prefs = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language];
  for (var i = 0; i < prefs.length; i++) {
    var code = primary(prefs[i]);
    if (languages[code]) { wanted = code; break; }
  }
  if (!wanted || wanted === pageLang) return;

  var href = '';
  var links = document.querySelectorAll('link[rel="alternate"][hreflang]');
  for (var j = 0; j < links.length; j++) {
    var lang = links[j].getAttribute('hreflang');
    if (lang && lang !== 'x-default' && primary(lang) === wanted) { href = links[j].href; break; }
  }
  if (!href) return;

  var strings = languages[wanted];
  var bar = document.createElement('div');
  bar.className = 'morpheus-language-bar';
  bar.setAttribute('role', 'region');
  bar.setAttribute('aria-label', strings.name);
  bar.lang = wanted;
  bar.setAttribute('data-nosnippet', '');
  var text = document.createElement('span');
  text.textContent = strings.also_in.replace('{name}', strings.name);
  var sw = document.createElement('button');
  sw.type = 'button';
  sw.setAttribute('data-action', 'switch');
  sw.textContent = strings.switch;
  var stay = document.createElement('button');
  stay.type = 'button';
  stay.setAttribute('data-action', 'stay');
  stay.textContent = strings.stay;
  sw.addEventListener('click', function () { setChoice(wanted); window.location.href = href; });
  stay.addEventListener('click', function () { setChoice(pageLang); bar.remove(); });
  bar.appendChild(text);
  bar.appendChild(sw);
  bar.appendChild(stay);
  document.body.insertBefore(bar, document.body.firstChild);
})();
