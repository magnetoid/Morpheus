---
name: permission-boundary-tests
description: Given a Django view (path + URL name), generate the three mandatory permission boundary tests (anonymous blocked, authed-without-scope blocked, authed-with-scope allowed). Required for every new staff-facing or customer-scoped view.
---

# permission-boundary-tests

Trigger phrases:
- **"boundary tests for view X"**
- **"write boundary tests for `<view>`"**
- **"add permission tests for `<url_name>`"**

## Why this exists

PLUGIN_DEVELOPMENT.md §13 mandates three tests on every view that
distinguishes authenticated users by scope. Without them a view that
grew past `@login_required` into permission-aware territory can ship
silently broken — production-only auth bugs are how SaaS breaches
happen.

## Steps

1. Resolve the view: get the URL name, the underlying callable, and
   the permission decorator stack (`@login_required`, `@staff_member_required`,
   `@permission_required(...)`, custom decorators).
2. Identify the scope checked. If the view uses
   `@permission_required('foo.bar')`, the *scope* is the perm string.
   If it uses a custom decorator like `@require_staff_scope('orders.write')`,
   that string is the scope.
3. Generate three tests in the view's plugin's `tests/test_*.py`:

```python
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse


class <ViewName>BoundaryTests(TestCase):

    URL = reverse('<url_name>')

    def setUp(self):
        self.unscoped = User.objects.create_user('alice', 'a@example.com', 'pw')
        self.scoped = User.objects.create_user('bob', 'b@example.com', 'pw')
        # Grant the specific permission the view checks.
        ct = ContentType.objects.get_for_model(<RelevantModel>)
        perm = Permission.objects.get(content_type=ct, codename='<codename>')
        self.scoped.user_permissions.add(perm)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])

    def test_authed_without_scope_forbidden(self):
        self.client.force_login(self.unscoped)
        response = self.client.get(self.URL)
        self.assertIn(response.status_code, (302, 403))

    def test_authed_with_scope_allowed(self):
        self.client.force_login(self.scoped)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
```

4. Adjust the scope-grant pattern to match the view:
   - **Django permission**: `user_permissions.add(Permission.objects.get(...))`
   - **Staff flag**: `user.is_staff = True; user.save()`
   - **Custom scope on `UserProfile`**: set the scope via `assign_scope(...)`
5. Run the tests and adjust until all three pass.

## Reuse

- The view's existing permission decorator is the source of truth —
  don't add or remove decorators in pursuit of test compatibility.
- Match the test style of an existing plugin's tests (grep for
  `BoundaryTests` in `plugins/installed/*/tests/`).

## When NOT to apply

- Anonymous-only views (storefront product list, sitemap) — skip
  the second + third tests; one "200 for anonymous" assertion is
  enough.
- Webhook receivers — those use HMAC, not session auth. Test the
  signature path separately.
