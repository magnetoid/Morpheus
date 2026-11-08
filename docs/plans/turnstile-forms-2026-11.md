# Turnstile on every public form (owner, 2026-11-08)

Owner's choice for dotbooks: protect the contact forms (contact, newsletter in the footer,
section and popup, CMS forms, Do not sell) and the sign-in pages (sign-in, sign-up, password
reset, the emailed sign-in code). Not the checkout. No page-level challenge. Each group is a
switch on the Cloudflare app's settings.

## Shape

- Core seam `core/bot_check.py`: `passes(request, form)` fires the `BOT_CHECK_PASSES` filter
  (value `True`), `widget(context, form)` fires `BOT_CHECK_WIDGET` (value `''`); the tag
  `{% bot_check "<form>" %}` in `core/templatetags/morph.py`. Nothing answers → no widget, every
  form passes (a store without the Cloudflare app keeps working).
- The Cloudflare app answers both: a form is protected when Turnstile is on, both keys are set and
  the form's switch is on (`turnstile_contact`, `turnstile_newsletter`, `turnstile_sign_in`,
  `turnstile_affiliates`). While protected, a missing or invalid token fails (closed).
- Views: storefront contact + do-not-sell, newsletter subscribe (JSON), cms form submit, core OTP
  request, allauth login/signup/password reset (wrapped in `morph/urls.py`, same names), affiliates
  apply (moved off its direct cloudflare import).
- Every template that posts one of those forms, in every theme, carries the tag (guard test);
  scripts that post with fetch reset the widget after each answer (a token is single-use).
- The footer newsletter puts Turnstile's script on payment pages too: its origin joins
  `PAYMENT_PAGE_SCRIPT_ORIGINS` and `docs/CHECKOUT_SCRIPTS.md`.
