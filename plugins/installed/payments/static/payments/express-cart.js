/* Wallet buttons on the cart page: Apple Pay, Google Pay and Link through Stripe's
 * Express Checkout Element.
 *
 * The wallet sheet shows an amount, and Stripe charges the order's PaymentIntent, so
 * every amount comes from the server for the address the wallet shares
 * (/payments/express/quote/), and the server places the order only while the amount
 * the sheet showed still holds (/payments/express/order/). A refusal names the new
 * amount, which the next tap shows.
 */
(function () {
  'use strict';

  var box = document.querySelector('[data-express-checkout]');
  var configEl = document.getElementById('express-checkout-config');
  if (!box || !configEl || typeof Stripe === 'undefined') return;

  var cfg;
  try {
    cfg = JSON.parse(configEl.textContent);
  } catch (e) {
    return;
  }
  var message = box.querySelector('[data-express-message]');

  // What the sheet shows now: the amount on the Elements instance, the delivery
  // choice it is for, and the last address the wallet shared.
  var base = cfg.amount;
  var state = { amount: cfg.amount, rateId: cfg.rateId, address: null };

  function csrfToken() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (m) return decodeURIComponent(m[1]);
    var input = box.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        data.ok = r.ok;
        return data;
      });
    });
  }

  function say(text, payUrl) {
    message.textContent = text || '';
    if (text && payUrl) {
      var link = document.createElement('a');
      link.href = payUrl;
      link.textContent = cfg.text.payAnotherWay;
      link.style.marginLeft = '.4rem';
      link.style.textDecoration = 'underline';
      message.appendChild(link);
    }
    message.hidden = !text;
  }

  var stripe = Stripe(cfg.key);
  var elements = stripe.elements({
    mode: 'payment',
    amount: cfg.amount,
    currency: cfg.currency,
    captureMethod: cfg.captureMethod || 'automatic',
  });

  function setAmount(amount) {
    state.amount = amount;
    elements.update({ amount: amount });
  }

  var express = elements.create('expressCheckout', {
    buttonType: { applePay: 'check-out', googlePay: 'checkout' },
  });

  express.on('ready', function (event) {
    if (!event.availablePaymentMethods) return;
    box.style.visibility = 'visible';
    box.style.maxHeight = 'none';
    box.style.overflow = 'visible';
  });

  express.on('click', function (event) {
    say('');
    var options = { emailRequired: true };
    if (cfg.ships) {
      options.shippingAddressRequired = true;
      options.shippingRates = cfg.shippingRates;
      state.rateId = cfg.rateId;
    }
    event.resolve(options);
  });

  express.on('shippingaddresschange', function (event) {
    state.address = event.address;
    post(cfg.quoteUrl, { address: event.address }).then(function (quote) {
      if (!quote.ok || !quote.shippingRates || !quote.shippingRates.length) {
        event.reject();
        return;
      }
      setAmount(quote.amount);
      state.rateId = quote.rateId;
      event.resolve({ shippingRates: quote.shippingRates });
    }).catch(function () { event.reject(); });
  });

  express.on('shippingratechange', function (event) {
    post(cfg.quoteUrl, { address: state.address, rateId: event.shippingRate.id }).then(function (quote) {
      if (!quote.ok) {
        event.reject();
        return;
      }
      setAmount(quote.amount);
      state.rateId = quote.rateId;
      event.resolve();
    }).catch(function () { event.reject(); });
  });

  express.on('cancel', function () {
    setAmount(base);
    state.rateId = cfg.rateId;
  });

  express.on('confirm', function (event) {
    elements.submit().then(function (submitted) {
      if (submitted.error) {
        event.paymentFailed({ reason: 'fail' });
        say(submitted.error.message || cfg.text.failed);
        return null;
      }
      return post(cfg.orderUrl, {
        billingDetails: event.billingDetails || {},
        shippingAddress: event.shippingAddress || {},
        rateId: event.shippingRate ? event.shippingRate.id : '',
        amount: state.amount,
      }).then(function (placed) {
        if (!placed.ok || !placed.clientSecret) {
          if (typeof placed.amount === 'number') {
            base = placed.amount;
            setAmount(placed.amount);
          }
          event.paymentFailed({ reason: 'fail' });
          say(placed.message || cfg.text.failed);
          return null;
        }
        // The order exists now and the cart is empty, so a decline carries on at
        // the checkout's payment step.
        return stripe.confirmPayment({
          elements: elements,
          clientSecret: placed.clientSecret,
          confirmParams: { return_url: placed.returnUrl },
        }).then(function (result) {
          if (result.error) say(result.error.message || cfg.text.failed, cfg.payUrl);
        });
      });
    }).catch(function () {
      event.paymentFailed({ reason: 'fail' });
      say(cfg.text.failed);
    });
  });

  express.mount(box.querySelector('[data-express-mount]'));
})();
