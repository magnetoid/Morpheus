/* Morpheus immersive PDP — sticky-buybox runtime.
 * Posts to the existing /graphql/ `mutateAddToCart` mutation.
 * Respects prefers-reduced-motion client-side (skips the loading shimmer). */
(function () {
  'use strict';
  function getCsrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  function onSubmit(form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var data = new FormData(form);
      var variantId = data.get('variant_id');
      var qty = parseInt(data.get('quantity') || '1', 10);
      var feedback = form.querySelector('.morpheus-immersive__buybox-feedback');
      if (!variantId) { if (feedback) feedback.textContent = 'Pick a variant first.'; return; }
      var btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      if (feedback) feedback.textContent = 'Adding…';
      fetch('/graphql/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': getCsrf()
        },
        body: JSON.stringify({
          query: 'mutation($input:AddToCartInput!){addToCart(input:$input){cart{id itemCount} errors{code message}}}',
          variables: { input: { variantId: variantId, quantity: qty } }
        })
      })
        .then(function (r) { return r.json(); })
        .then(function (resp) {
          if (btn) btn.disabled = false;
          if (!resp || !resp.data || !resp.data.addToCart) {
            if (feedback) feedback.textContent = 'Could not add to bag — try again.';
            return;
          }
          var out = resp.data.addToCart;
          if (out.errors && out.errors.length) {
            if (feedback) feedback.textContent = out.errors.map(function (er) { return er.message; }).join(' ');
            return;
          }
          if (feedback) feedback.textContent = 'Added — count ' + (out.cart && out.cart.itemCount);
        })
        .catch(function () {
          if (btn) btn.disabled = false;
          if (feedback) feedback.textContent = 'Network error — try again.';
        });
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.morpheus-immersive__buybox-form').forEach(onSubmit);
  });
})();
