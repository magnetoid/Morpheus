/* Morpheus immersive PDP — sticky-buybox runtime.
 * Posts to the GraphQL `addToCart` mutation (AddToCartInput needs productId +
 * quantity, variantId optional). */
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
      var productId = data.get('product_id');
      var variantId = data.get('variant_id') || null;
      var qty = parseInt(data.get('quantity') || '1', 10);
      var feedback = form.querySelector('.immersive-buybox__feedback');
      if (!productId) { if (feedback) feedback.textContent = 'Could not identify the product.'; return; }
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
          variables: { input: { productId: productId, variantId: variantId, quantity: qty } }
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
          var n = out.cart && out.cart.itemCount;
          if (feedback) feedback.textContent = 'Added to bag' + (n ? ' (' + n + ')' : '') + '.';
          document.dispatchEvent(new CustomEvent('morpheus:cart-updated', { detail: { itemCount: n } }));
        })
        .catch(function () {
          if (btn) btn.disabled = false;
          if (feedback) feedback.textContent = 'Network error — try again.';
        });
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.immersive-buybox__form').forEach(onSubmit);
  });
})();
