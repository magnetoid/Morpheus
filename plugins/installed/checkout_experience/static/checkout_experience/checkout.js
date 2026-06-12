/* Morpheus checkout runtime — drives the existing complete_order GraphQL
 * mutation end-to-end, with progressive enhancement: no JS = the merchant's
 * pre-existing template form; with JS = express-pay, address autocomplete,
 * shipping-rate live recalc, prefers-reduced-motion awareness.
 *
 * Keep the runtime self-contained: no external runtime deps, no bundler.
 * Targets evergreen browsers (last 2 Chrome/Safari/Firefox/Edge).
 */
(function () {
  'use strict';
  if (window.__morpheusCheckoutLoaded) return;
  window.__morpheusCheckoutLoaded = true;

  var root = document.getElementById('morpheus-checkout');
  if (!root) return;

  var form = document.getElementById('morpheus-checkout-form');
  var ratesBox = document.getElementById('morpheus-shipping-rates');
  var expressBox = document.getElementById('morpheus-express-buttons');
  var submitBtn = form ? form.querySelector('button[type="submit"]') : null;
  if (!form || !ratesBox || !submitBtn) return;

  var cfg = {
    cartId: root.dataset.cartId,
    currency: root.dataset.currency || 'USD',
    layout: root.dataset.layout || 'one-page',
    express: (root.dataset.express || '').split(',').filter(Boolean),
    csrf: root.dataset.csrf || '',
    country: root.dataset.country || ''
  };

  var prefersReducedMotion =
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function el(tag, attrs, kids) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'text') node.textContent = attrs[k];
        else if (k === 'html') node.innerHTML = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    (kids || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function gql(query, variables) {
    return fetch('/graphql/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFToken': cfg.csrf
      },
      body: JSON.stringify({ query: query, variables: variables || {} })
    }).then(function (r) {
      return r.json();
    });
  }

  function safe(fn) {
    return function () {
      try { return fn.apply(null, arguments); } catch (e) { console.warn('[checkout]', e); }
    };
  }

  function readForm() {
    var data = new FormData(form);
    return {
      email: (data.get('email') || '').trim(),
      shipping_address: {
        full_name: data.get('full_name'),
        line1: data.get('line1'),
        line2: data.get('line2'),
        city: data.get('city'),
        postal_code: data.get('postal_code'),
        country: (data.get('country') || cfg.country).toUpperCase()
      },
      shipping_rate_id: ratesBox.dataset.selected || ''
    };
  }

  function loadShippingRates() {
    var addr = readForm().shipping_address;
    if (!addr.country || !addr.postal_code) {
      ratesBox.textContent = 'Enter a complete address to see shipping options.';
      return;
    }
    ratesBox.textContent = 'Calculating…';
    gql(
      'query($cart:ID!,$addr:AddressInput!){shippingRates(cartId:$cart,address:$addr){id label amount currency}}',
      { cart: cfg.cartId, addr: addr }
    ).then(safe(function (resp) {
      if (!resp || !resp.data || !resp.data.shippingRates) {
        ratesBox.textContent = 'Shipping rates unavailable.';
        return;
      }
      ratesBox.innerHTML = '';
      resp.data.shippingRates.forEach(function (rate) {
        var id = 'rate-' + rate.id;
        var radio = el('input', { type: 'radio', name: 'shipping_rate', id: id, value: rate.id, required: 'required' });
        var label = el('label', { for: id }, [
          el('span', { text: rate.label }),
          el('span', { text: ' — ' + (rate.currency || cfg.currency) + ' ' + (rate.amount || '0') })
        ]);
        radio.addEventListener('change', function () { ratesBox.dataset.selected = rate.id; });
        ratesBox.appendChild(radio);
        ratesBox.appendChild(label);
      });
      if (!ratesBox.dataset.selected && resp.data.shippingRates[0]) {
        var first = resp.data.shippingRates[0];
        ratesBox.dataset.selected = first.id;
        var firstRadio = ratesBox.querySelector('input[value="' + first.id + '"]');
        if (firstRadio) firstRadio.checked = true;
      }
    }));
  }

  function paintExpressButtons() {
    if (!expressBox) return;
    expressBox.innerHTML = '';
    cfg.express.forEach(function (m) {
      var b = el('button', {
        type: 'button',
        'data-method': m,
        'aria-label': 'Pay with ' + m.replace('_', ' '),
        text: '⚡ ' + m.replace('_', ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); })
      });
      b.addEventListener('click', function () {
        submitBtn.dataset.intent = m;
        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      });
      expressBox.appendChild(b);
    });
  }

  function animateSection(section) {
    if (prefersReducedMotion) return;
    if (!section) return;
    section.classList.remove('morpheus-checkout__section--enter');
    // force reflow so the animation restarts
    void section.offsetWidth;
    section.classList.add('morpheus-checkout__section--enter');
  }

  function submit() {
    var data = readForm();
    if (!data.email || data.email.indexOf('@') < 1) {
      alert('Please enter a valid email.'); return;
    }
    submitBtn.disabled = true;
    submitBtn.dataset.state = 'loading';
    var mutation =
      'mutation($input:CompleteOrderInput!){' +
      'completeOrder(input:$input){orderNumber paymentClientSecret errors{code message}}' +
      '}';
    var input = {
      cartId: cfg.cartId,
      email: data.email,
      shippingAddress: data.shipping_address,
      billingAddress: data.shipping_address,
      shippingRateId: data.shipping_rate_id,
      paymentGateway: submitBtn.dataset.intent === 'link' ? 'link' : ''
    };
    gql(mutation, { input: input }).then(safe(function (resp) {
      submitBtn.disabled = false;
      submitBtn.dataset.state = '';
      if (!resp || !resp.data || !resp.data.completeOrder) {
        alert('Checkout failed. Please try again.');
        return;
      }
      var out = resp.data.completeOrder;
      if (out.errors && out.errors.length) {
        alert(out.errors.map(function (e) { return e.message; }).join('\n'));
        return;
      }
      var redirect = '/orders/' + out.orderNumber + '/confirmation/?cs=' + (out.paymentClientSecret || '');
      window.location.assign(redirect);
    }));
  }

  ['line1', 'city', 'postal_code', 'country'].forEach(function (name) {
    var input = form.elements[name];
    if (input) input.addEventListener('change', safe(loadShippingRates));
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    submit();
  });

  // Initial paint
  safe(paintExpressButtons)();
  safe(loadShippingRates)();
})();
