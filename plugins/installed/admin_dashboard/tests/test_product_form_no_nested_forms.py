"""The product edit page must contain no nested ``<form>`` elements.

Regression for the 2026-09 "can't save product" bug. The variant delete form
and the add/edit variant ``<dialog>`` modals were rendered *inside*
``<form id="product-form">``. Nested forms are invalid HTML: the browser drops
the inner ``<form>`` tags and adopts their inputs — including the add-variant
modal's empty ``required`` name/sku — into the product form, so native
constraint validation aborted every save with "An invalid form control with
name='name' is not focusable" before the ``data-ajax`` submit handler could run.
Saving silently did nothing.

The fix moves all variant forms out of ``#product-form`` (delete buttons reach
their form via the ``form=`` attribute; the modals are overlays). These tests
GET the real edit page and assert the invariant on the rendered HTML.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class ProductFormNoNestedFormsTests(TestCase):
    def setUp(self):
        self.client = Client()
        staff = get_user_model().objects.create_user(
            username='formstaff', email='formstaff@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        from plugins.installed.catalog.models import Product, ProductVariant

        self.product = Product.objects.create(
            name='Nested Form Guard', product_type='variable', status='draft', price=0
        )
        # A variant makes the edit modal + delete form render — the exact markup
        # that used to nest inside #product-form.
        ProductVariant.objects.create(product=self.product, name='Red', sku='NFG-RED')

    def _html(self) -> str:
        resp = self.client.get(
            reverse('admin_dashboard:product_edit', kwargs={'product_id': self.product.id})
        )
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_no_form_is_nested_inside_the_product_form(self):
        """No ``<form>`` opens between #product-form's open and its close.

        Scoped to #product-form on purpose: the dashboard shell renders its own
        standalone forms (confirm modal, save bar, AI-assist), so a whole-page
        form-depth walk would measure unrelated markup. The invariant that fixes
        the save bug is local to the product form.
        """
        html = self._html()
        start = html.index('id="product-form"')
        end = html.index('</form>', start)  # product-form's own close (nothing valid nests now)
        self.assertNotIn('<form', html[start:end], 'a <form> is nested inside #product-form')

    def test_variant_forms_live_after_the_product_form_closes(self):
        """The delete form and the add-variant modal must sit outside #product-form."""
        html = self._html()
        open_idx = html.index('id="product-form"')
        # The product form's own close is the first </form> after its open,
        # because nothing valid nests inside it any more.
        close_idx = html.index('</form>', open_idx)
        self.assertNotIn('<form', html[open_idx:close_idx], 'a form opens inside #product-form')
        # The actual variant-management ELEMENTS live after the close. (The
        # in-table Add-variant button legitimately keeps an onclick reference to
        # the modal id, and the delete button a form= reference — assert on the
        # markup that defines the form/dialog, not on those bare id references.)
        self.assertIn('<form id="variant-del-', html[close_idx:])
        self.assertIn('<dialog id="variant-new-modal"', html[close_idx:])
        self.assertNotIn('<dialog id="variant-new-modal"', html[:close_idx])
        self.assertNotIn('<form id="variant-del-', html[:close_idx])
