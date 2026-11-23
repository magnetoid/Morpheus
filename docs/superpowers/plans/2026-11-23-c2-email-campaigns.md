# C2 Email Campaigns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the merchant and Linda compose, schedule and send newsletter campaigns to all confirmed subscribers or to one RFM segment. Add a workflow action, "Email customer", that sends either a service email or a marketing email.

**Architecture:**
- The existing `send_campaign` engine is reused: its claim, its batches and its `CampaignSend` ledger.
- A new module, `plugins/installed/newsletter/campaigns.py`, holds the rules: compose, schedule, cancel, send-now, audience and rendering. The dashboard views and Linda's tools both call it.
- Two filter hooks keep the apps apart:
  - `CUSTOMER_SEGMENT_EMAILS`, which the customers app answers;
  - `MARKETING_EMAIL_RECIPIENT`, which the newsletter app answers.
- The workflow action is a new handler in `workflows/engine.py`, with its helpers in `workflows/emailing.py`.

**Tech Stack:** Django 6.1, Celery beat via `Plugin.register_celery_beat`, `core.emails.send_templated_email`, `core.utils.html.sanitize_richtext`, `{% richtext_field %}`.

**Spec:** `docs/superpowers/specs/2026-11-23-c2-email-campaigns-design.md`

## Global Constraints

- **Test command prefix:** `DEBUG=True DATABASE_URL='sqlite:///:memory:' SECRET_KEY=test-key REDIS_URL=redis://127.0.0.1:6379/15 .venv/bin/python manage.py test …`
- **Ruff:** `uvx ruff@0.15.8 check` and `uvx ruff@0.15.8 format --check` on changed files.
- **The `audience` column:** `CharField(max_length=20, blank=True, default='', db_default='')`. An empty value means every confirmed subscriber.
- **Segment keys** (from `CustomerSegment.SEGMENTS`): `champions`, `loyal`, `potential`, `new`, `at_risk`, `lost`. A segment only narrows the confirmed list.
- **Capabilities:**
  - compose, test, schedule, send and cancel need `marketing.write`;
  - the list page needs `marketing.read`;
  - the workflows editor stays on `system.write`.
- **Linda tools:**
  - `newsletter.campaigns` uses `promotions.read`;
  - `newsletter.campaign_create` and `newsletter.campaign_send` use `promotions.write` with `requires_approval=True`.
- **Beat:** the key is `newsletter:send_due_campaigns`, the task is `newsletter.send_due_campaigns` (explicit `name=`), and the schedule is 300 s.
- **Scheduling:**
  - a campaign more than 24 hours past its time (`MISSED_AFTER = timedelta(hours=24)`) goes back to `draft` with `scheduled_at` kept, and the list shows "missed its send time";
  - cancelling a scheduled campaign sets `draft` and `scheduled_at=None`;
  - a time in the past is refused;
  - times are entered in `core.utils.site.store_timezone()` and stored in UTC.
- **Workflow placeholders, exactly these:** `{customer_first_name}`, `{customer_name}`, `{order_number}`, `{order_total}`, `{store_name}`. An unknown placeholder stays as typed. The body is plain text, escaped and split into paragraphs on blank lines.
- **Workflow recipient order:** `payload['customer'].email`, then `order.customer.email`, then `order.email`, then `payload['email']`.
- **Marketing workflow email:**
  - it needs a confirmed subscriber (`MARKETING_EMAIL_RECIPIENT` answered);
  - it is refused when the event's order carries `metadata['consent']` refusing marketing (checked with `core.consent.allowed('marketing', order=order)` only when that stamp exists);
  - it has no store-level check when no order exists.
- **Release:** v0.190.0 via `manage.py release --minor`. Never cut a release while a suite runs.

## Review Focus

1. **Case mismatch.** A subscriber stored as `Reader@Example.com` while the customer is `reader@example.com` must still be in the segment audience. The comparison is case-insensitive; Task 2 pins it.
2. **Script in the body.** A body with `<script>` or `<img onerror=…>` must arrive without them, including a row written before C2 (sanitised again at send time). Task 2 pins it.
3. **Beat and manual send together.** `send_due_campaigns` running twice, or alongside Send, must deliver one copy per subscriber. Task 3 pins it.
4. **Unsubscribed address.** A workflow marketing email to an unsubscribed address is skipped, and the run message names the reason. Task 6 pins it.
5. **Time zone.** A Belgrade store entering 2099-12-01 10:00 stores 09:00 UTC. Task 4 pins it.

---

### Task 1: Hook contracts, the audience column, and the customers answer

**Files:**
- Modify: `core/hooks.py`. Add two filter constants beside `CONSENT_MARKETING_CUSTOMERS`, each with a comment block in the existing style.
- Modify: `plugins/installed/marketing/models.py`. Add `EmailCampaign.audience`.
- Create: `plugins/installed/marketing/migrations/00NN_emailcampaign_audience.py`, with `makemigrations marketing`; check the `db_default` is in it.
- Modify: `plugins/installed/customers/app.py`. Register the handler in `ready()`.
- Create: `plugins/installed/customers/segment_emails.py`.
- Test: `plugins/installed/customers/tests/test_segment_emails.py`.

**Interfaces:**
- Produces `MorpheusEvents.CUSTOMER_SEGMENT_EMAILS = 'customer.segment_emails'`, a filter with `value=None` and kwargs `segment: str`. Its answer is `set[str]`: the lower-cased emails of customers whose `rfm_segment.segment == segment`. An unknown segment answers `set()`.
- Produces `MorpheusEvents.MARKETING_EMAIL_RECIPIENT = 'marketing.email_recipient'`, a filter with `value=None` and kwargs `email: str`. Its answer is `{'headers': dict, 'unsubscribe_url': str}` for a confirmed subscriber; otherwise `value` is passed through. The newsletter answers it in Task 6.
- Produces `customers.segment_emails.on_segment_emails(value, segment='', **kwargs) -> set[str] | None`.

- [ ] **Step 1: Write the failing tests** in `test_segment_emails.py`:
  - `test_answers_lowercased_emails_of_the_segment`: two customers, one `at_risk` with email `Ann@Example.com` and one `loyal`. `hook_registry.filter(MorpheusEvents.CUSTOMER_SEGMENT_EMAILS, None, segment='at_risk') == {'ann@example.com'}`.
  - `test_unknown_segment_answers_empty_set`: the filter with `segment='nope'` returns `set()`.
  - `test_campaign_audience_defaults_to_everyone`: `EmailCampaign.objects.create(name='x', subject='y', html_body='<p>z</p>').audience == ''`.
- [ ] **Step 2: Run** `… manage.py test plugins.installed.customers.tests.test_segment_emails`. Expected: FAIL with `AttributeError` on `CUSTOMER_SEGMENT_EMAILS`.
- [ ] **Step 3: Implement** the two constants, the field, the migration, `on_segment_emails`, and `self.register_hook(events.CUSTOMER_SEGMENT_EMAILS, on_segment_emails, priority=50)`. The handler reads `CustomerSegment.objects.filter(segment=segment).values_list('customer__email', flat=True)`, drops blanks and lower-cases the rest.
- [ ] **Step 4: Run** the same test and `… manage.py makemigrations --check --dry-run`. Expected: OK, and "No changes detected".
- [ ] **Step 5: Commit** with `feat: segment-email and marketing-recipient hooks, campaign audience field`.

### Task 2: Rendering and audience in the send path

**Files:**
- Create: `plugins/installed/newsletter/campaigns.py`, the rendering and audience part.
- Create: `plugins/installed/newsletter/templates/emails/newsletter_campaign.html`, which extends `emails/_layout.html`:
  - the `title` block is the subject;
  - the `preheader` block is `preview_text`;
  - the `body` block is `{{ body|safe }}`;
  - the `footer` block is `{{ store_name }}. You get this because you subscribed. <a href="{{ unsubscribe_url }}">Unsubscribe</a>`.
- Modify: `plugins/installed/newsletter/tasks.py`. `_run_campaign_batch` and `send_campaign_test` use the new rendering and the audience. `_base_bodies` and `_with_footer` are removed if nothing else uses them.
- Test: `plugins/installed/newsletter/tests/test_campaign_render.py`. Update `test_campaign_send.py` only where it asserted the old bare footer text.

**Interfaces:**
- Produces `class CampaignError(ValueError)`. Its message is shown to the merchant and to Linda.
- Produces `AUDIENCES: list[tuple[str, str]]`: `('', 'All confirmed subscribers')`, then the six segments with their labels (`'Champions'`, `'Loyal'`, `'Potential'`, `'New'`, `'At risk'`, `'Lost'`).
- Produces `UNSUBSCRIBE_SENTINEL = '__morpheus_unsubscribe_url__'`.
- Produces `render_campaign(campaign) -> tuple[str, str]` → `(text, html)`:
  - the HTML is sanitised with `sanitize_richtext` and rendered with the layout;
  - the text is `campaign.text_body` or the plain text of the clean HTML (`strip_tags` + `html.unescape`), followed by `\n\n—\nUnsubscribe: <sentinel>\n`;
  - both carry `UNSUBSCRIBE_SENTINEL` wherever the per-recipient URL goes.
- Produces `personalise(text: str, html: str, unsubscribe_url: str) -> tuple[str, str]`, which replaces the sentinel.
- Produces `audience_emails(audience: str) -> set[str] | None`:
  - `None` means everyone;
  - a segment means the filter's lower-cased set;
  - it raises `CampaignError('The customers app is off, so a segment cannot be used.')` when nothing answers (the filter returns `None`);
  - it raises `CampaignError('Unknown audience.')` for a key not in `AUDIENCES`.

- [ ] **Step 1: Write the failing tests** in `test_campaign_render.py`, with locmem email and `DEFAULT_FROM_EMAIL` set as in `test_campaign_send.py`:
  - `test_body_is_sanitised_and_wrapped_in_the_store_layout`: the body is `<p>Hi</p><script>x()</script><img src=x onerror=y()>`. After `send_campaign`, the HTML alternative has no `<script` and no `onerror`, contains `<p>Hi</p>`, and contains a marker from `_layout.html`. Read `core/emails/templates/emails/_layout.html` to pick that marker.
  - `test_each_recipient_gets_their_own_unsubscribe_link`: two confirmed subscribers; each message's HTML and body contain that subscriber's `confirm_token` and not the other's, and nothing contains `UNSUBSCRIBE_SENTINEL`.
  - `test_segment_audience_narrows_the_confirmed_list`:
    - setup: confirmed subscribers `a@x.com` and `b@x.com`, plus pending `c@x.com`; a customer `A@X.com` and a customer `c@x.com`, both in segment `loyal`;
    - a campaign with `audience='loyal'` sends to `['a@x.com']` only;
    - `recipient_count == 1`.
  - `test_segment_audience_refused_when_nobody_answers`: inside a test, patch `hook_registry.filter` for that event to return `None`. Save and restore `_handlers`, per CLAUDE.md; never call `clear()`. `audience_emails('loyal')` then raises `CampaignError`.
  - `test_test_copy_uses_the_layout_and_a_sample_link`: `send_campaign_test` sends one message whose subject starts with `[test] `, whose HTML has the layout marker, and with no `List-Unsubscribe` header.
- [ ] **Step 2: Run** `… manage.py test plugins.installed.newsletter.tests.test_campaign_render`. Expected: FAIL with an `ImportError` for `campaigns`.
- [ ] **Step 3: Implement** `campaigns.py` (the render and audience parts) and the template.
  - In `_run_campaign_batch`, render once per batch. Compute `allowed = audience_emails(campaign.audience)` once per batch, and skip a subscriber with `allowed is not None and sub.email.lower() not in allowed`.
  - A `CampaignError` there marks the campaign back to `draft` and returns `{'ok': False, 'error': str(e)}`.
  - The test copy uses `personalise(text, html, '#')`.
- [ ] **Step 4: Run** `… manage.py test plugins.installed.newsletter`. Expected: OK. Older tests asserting `Unsubscribe:` in the text body still pass.
- [ ] **Step 5: Commit** with `feat: campaigns render in the store layout, sanitised, per audience`.

### Task 3: Scheduled sends

**Files:**
- Modify: `plugins/installed/newsletter/campaigns.py`. Add the scheduling rules.
- Modify: `plugins/installed/newsletter/tasks.py`. Add `send_due_campaigns`.
- Modify: `plugins/installed/newsletter/app.py`, in `ready()`: `self.register_celery_beat('newsletter:send_due_campaigns', {'task': 'newsletter.send_due_campaigns', 'schedule': 300})`.
- Test: `plugins/installed/newsletter/tests/test_campaign_schedule.py`.

**Interfaces:**
- Produces `MISSED_AFTER = timedelta(hours=24)`.
- Produces `schedule_campaign(campaign, when: datetime) -> None`:
  - it needs an aware `when` later than now;
  - the status must be `draft` or `scheduled`;
  - it sets `status='scheduled'` and `scheduled_at=when`;
  - otherwise it raises `CampaignError` with one of these messages: `'Pick a time in the future.'`, or `'"<name>" is <status> and cannot be scheduled.'`.
- Produces `cancel_campaign(campaign) -> None`. It works only from `scheduled`, sets `status='draft'` and `scheduled_at=None`, and otherwise raises `CampaignError`.
- Produces `is_missed(campaign) -> bool`, true when `status == 'draft'` and `scheduled_at` is set and in the past.
- Produces task `send_due_campaigns() -> dict`, with `@shared_task(name='newsletter.send_due_campaigns')`:
  - for a scheduled campaign with `scheduled_at <= now - MISSED_AFTER`, it sets `status='draft'` and keeps `scheduled_at`;
  - for one with `scheduled_at <= now`, it calls `send_campaign.delay(str(pk))`;
  - it returns `{'started': n, 'missed': m}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_due_campaign_starts`: scheduled 1 minute ago, one confirmed subscriber; after `send_due_campaigns()`, `status == 'sent'` and `len(mail.outbox) == 1`.
  - `test_future_campaign_waits`: scheduled 1 hour ahead; it stays `scheduled` and nothing is sent.
  - `test_more_than_a_day_late_goes_back_to_draft`: scheduled 25 hours ago; it becomes `draft`, `scheduled_at` is unchanged, `is_missed` is True, and nothing is sent.
  - `test_running_twice_sends_once`: call `send_due_campaigns()` twice, then `send_campaign.delay(id)`; `len(mail.outbox) == 1`.
  - `test_schedule_refuses_the_past` and `test_schedule_refuses_a_sent_campaign`, both raising `CampaignError`.
  - `test_cancel_returns_to_editable_draft`: `status == 'draft'` and `scheduled_at is None`.
  - `test_beat_entry_names_the_registered_task`: the beat schedule built from settings has the key `newsletter:send_due_campaigns`, and its task is in `celery_app.tasks`. Mirror the assertion style of `core/tests/test_beat_schedule.py`.
- [ ] **Step 2: Run** `… manage.py test plugins.installed.newsletter.tests.test_campaign_schedule`. Expected: FAIL with an `ImportError`.
- [ ] **Step 3: Implement** the functions, the task and the beat registration.
- [ ] **Step 4: Run** the same test. Expected: OK.
- [ ] **Step 5: Commit** with `feat: scheduled campaigns send at their time; late ones go back to draft`.

### Task 4: The composer in the dashboard

**Files:**
- Modify: `plugins/installed/newsletter/campaigns.py`. Add `save_campaign`, `send_campaign_now` and `parse_local_datetime`.
- Modify: `plugins/installed/newsletter/dashboard.py`:
  - new `campaign_edit_view(request, campaign_id=None)` (GET shows the form; POST saves), `campaign_schedule_view` and `campaign_cancel_view`;
  - `campaign_send_view` and `campaign_test_view` move to `@require_capability('marketing.write')`;
  - Send calls `send_campaign_now`.
- Modify: `plugins/installed/newsletter/urls_dashboard.py`. Add `campaigns/new/` (`campaign_new`), `campaigns/<uuid:campaign_id>/` (`campaign_edit`), `…/schedule/` (`campaign_schedule`) and `…/cancel/` (`campaign_cancel`). Literal paths go before the converter path.
- Create: `plugins/installed/newsletter/templates/newsletter/dashboard/campaign_edit.html`:
  - a name field;
  - a subject field;
  - a preheader field, named `preview_text`;
  - `{% richtext_field name="html_body" … allow_headings=True allow_images=False aria_label="Campaign body" %}`;
  - an audience `<select>` built from `AUDIENCES`, which shows the confirmed count of the current choice;
  - a `datetime-local` input named `send_at`;
  - buttons: Save draft, Send test, Schedule, and Send now (with `data-confirm`), plus Cancel schedule when the campaign is scheduled.

  The template uses no page-width cap and whole Tailwind classes. Run the Tailwind build if new classes appear (`admin_dashboard/frontend`: `npm ci && npm run build`), and commit `tailwind.css`.
- Modify: `campaigns.html`:
  - a "New campaign" link;
  - each row links to the edit page and shows the audience label, the scheduled time in the store zone, and "missed its send time" when `is_missed`;
  - Send buttons appear only for drafts.
- Test: `plugins/installed/newsletter/tests/test_campaign_composer.py`.

**Interfaces:**
- Produces `save_campaign(*, campaign=None, name: str, subject: str, preview_text: str = '', html_body: str, audience: str = '') -> EmailCampaign`:
  - it strips the fields and sanitises `html_body`;
  - name, subject and a body with visible text are required (`CampaignError('Name, subject and body are required.')`);
  - the audience must be in `AUDIENCES`;
  - an existing campaign must be `draft` (`CampaignError('"<name>" is <status> and cannot be edited.')`);
  - `text_body` is set to `''`, so it is derived at send time.
- Produces `send_campaign_now(campaign) -> None`:
  - the status must be `draft`;
  - it calls `audience_emails(campaign.audience)` so a refusal is raised now and not in the worker;
  - then it calls `send_campaign.delay(str(campaign.pk))`.
- Produces `parse_local_datetime(raw: str) -> datetime | None`. It parses `YYYY-MM-DDTHH:MM` in `store_timezone()` and returns an aware UTC datetime. Blank or invalid input gives `None`.

- [ ] **Step 1: Write the failing tests** (superuser client unless the test says otherwise):
  - `test_new_campaign_page_renders`: GET `/dashboard/newsletter/campaigns/new/` returns 200, contains `name="html_body"`, and compiles.
  - `test_saving_creates_a_sanitised_draft`: POST `name`, `subject`, `preview_text` and `html_body='<p>Hi</p><script>x</script>'`, `audience='loyal'`, `action='save'` → one campaign with `status='draft'`, `audience='loyal'`, and no `<script` in `html_body`.
  - `test_schedule_in_store_time_zone`: with `set_app_settings` or `StoreSettings` timezone set to `Europe/Belgrade`, POST `send_at='2099-12-01T10:00'`, `action='schedule'` → `scheduled_at == datetime(2099,12,1,9,0,tzinfo=UTC)` and `status='scheduled'`. The far-future date keeps the test valid forever; December is outside summer time, so the offset is +1.
  - `test_editing_a_sent_campaign_is_refused`: POST to a `sent` campaign's edit URL → the row is unchanged and an error message appears.
  - `test_cancel_schedule`: POST cancel → `draft`.
  - `test_list_shows_missed_campaigns`: a draft with a past `scheduled_at` → the list contains `missed its send time`.
  - `test_staff_without_marketing_write_cannot_send_or_compose`: follow `admin_dashboard/tests/test_return_close_form.py:176-200`, with rbac set to `enforce` and restored with `addCleanup`. A no-role staff member POSTing to the send, test, new, schedule and cancel URLs is refused (not 2xx/302 to success, and nothing changes). Anonymous POSTs redirect to sign-in.
- [ ] **Step 2: Run** `… manage.py test plugins.installed.newsletter.tests.test_campaign_composer`. Expected: FAIL with a 404 on `/campaigns/new/`.
- [ ] **Step 3: Implement** the views, URLs, templates and `campaigns.py` functions. Every `CampaignError` becomes `messages.error`, and the edit form re-renders with the posted values.
- [ ] **Step 4: Run** `… manage.py test plugins.installed.newsletter plugins.installed.admin_dashboard.tests.test_navigation plugins.installed.admin_dashboard.tests.test_tailwind_build`. Also call `get_template()` on both templates. Expected: OK.
- [ ] **Step 5: Commit** with `feat: compose, schedule and cancel campaigns; sending needs marketing.write`.

### Task 5: Linda's campaign tools

**Files:**
- Modify: `plugins/installed/newsletter/agent_tools.py`. Add three tools.
- Modify: `plugins/installed/newsletter/app.py`. Add them to `contribute_agent_tools`.
- Test: `plugins/installed/newsletter/tests/test_campaign_tools.py`.

**Interfaces:**
- Consumes `save_campaign`, `schedule_campaign`, `send_campaign_now`, `AUDIENCES`, `CampaignError` and `is_missed` from Tasks 2–4.
- Produces the tool `newsletter.campaigns`:
  - scopes `['promotions.read']`, schema `{limit: integer 1–50, default 20}`;
  - output `{'campaigns': [{'id', 'name', 'subject', 'status', 'audience', 'scheduled_at' (ISO or None), 'missed', 'recipient_count'}]}`.
- Produces the tool `newsletter.campaign_create`:
  - scopes `['promotions.write']`, `requires_approval=True`;
  - schema: required `name`, `subject` and `body_html`, plus optional `preview_text` and `audience` (an enum of the `AUDIENCES` keys);
  - it creates a draft and returns `{'id', 'status': 'draft'}`;
  - a `CampaignError` gives `ToolResult(error=str(e))`. Match how the existing tools in this file report errors.
- Produces the tool `newsletter.campaign_send`:
  - scopes `['promotions.write']`, `requires_approval=True`;
  - schema: required `campaign_id`, optional `send_at` (an ISO 8601 string with an offset);
  - with no `send_at` it calls `send_campaign_now`; with one it calls `schedule_campaign`;
  - it returns `{'id', 'status'}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_tools_are_registered_with_approval_on_writes`: `agent_registry.get_tool(...)` for each tool. `requires_approval` is True on create and send and False on the list. The scopes are exactly as above.
  - `test_create_makes_a_sanitised_draft` (invoked through the tool's `invoke`, as `test_agent_tools.py` does).
  - `test_send_with_time_schedules`, and `test_send_without_time_sends`: locmem email, one confirmed subscriber, then `len(mail.outbox) == 1`.
  - `test_send_refuses_a_sent_campaign_with_a_message`.
  - `test_tools_are_in_lindas_catalogue`: follow `agent_mcp/tests/test_linda_turn.py::LindaCatalogueTests`; the three names appear in the store-mode catalogue.
- [ ] **Step 2: Run** `… manage.py test plugins.installed.newsletter.tests.test_campaign_tools`. Expected: FAIL because the tool is not found.
- [ ] **Step 3: Implement** the three tools.
- [ ] **Step 4: Run** `… manage.py test plugins.installed.newsletter plugins.installed.agent_mcp core.agents.tests.test_registry_collisions core.assistant`. Expected: OK.
- [ ] **Step 5: Commit** with `feat: Linda lists, drafts and sends campaigns (approval on writes)`.

### Task 6: The workflow "Email customer" action

**Files:**
- Create: `plugins/installed/workflows/emailing.py`.
- Create: `plugins/installed/workflows/templates/emails/workflow_email.html` and `.txt`.
  - The HTML extends `_layout.html`. The `body` block holds the escaped paragraphs as `<p>`.
  - The footer says `{{ store_name }}. You get this about your order.` for service. For marketing it says `{{ store_name }}. You get this because you subscribed. <a href="{{ unsubscribe_url }}">Unsubscribe</a>`.
  - The text version has the same content.
- Modify: `plugins/installed/workflows/engine.py`. Add `_action_email_customer` and register it in `ACTION_HANDLERS` as `'email_customer'`.
- Modify: `plugins/installed/workflows/models.py`. Append `('email_customer', 'Email customer')` to `ACTION_KINDS`. It is a plain list, so no migration; check with `makemigrations --check`.
- Modify: `plugins/installed/workflows/templates/workflows/edit.html`. Add the example spec and the five placeholders to the actions help.
- Modify: `plugins/installed/newsletter/app.py`. Add `ready()` registration and the handler that answers `MARKETING_EMAIL_RECIPIENT`.
- Test: `plugins/installed/workflows/tests/test_email_customer.py`.

**Interfaces:**
- Consumes `MorpheusEvents.MARKETING_EMAIL_RECIPIENT` (Task 1).
- Produces `emailing.PLACEHOLDERS: tuple[str, ...]`, the five names.
- Produces `emailing.recipient(payload: dict) -> tuple[str, object | None]`, returning `(email, order)` in the Global Constraints order.
- Produces `emailing.fill(text: str, payload: dict) -> str`:
  - `customer_first_name` is the customer's `first_name`, else `''`;
  - `customer_name` is the full name, else the email's local part;
  - `order_number` is `order.order_number`;
  - `order_total` is `str(order.total)`;
  - `store_name` is `core.utils.site.store_name()`;
  - substitution is plain `str.replace` per name, with no `format()` and no attribute lookup.
- Produces `emailing.paragraphs(text: str) -> list[str]`, split on blank lines and stripped. Escaping happens in the template (autoescape).
- Produces `_action_email_customer(spec, payload) -> tuple[bool, str]`:
  - spec `{kind:'email_customer', purpose:'service'|'marketing', subject, body}`;
  - the failure messages are `'purpose must be service or marketing'`, `'no subject or body'`, `'no email address in the event'`, `'no sending email'` (when `not smtp_configured()` or no `DEFAULT_FROM_EMAIL`), `'not a newsletter subscriber'` and `'the order refused marketing'`;
  - on success it returns `(True, f'emailed {email} ({purpose})')`.
- Produces `NewsletterPlugin.on_marketing_email_recipient(value, email='', **kwargs)`. For a confirmed subscriber (case-insensitive) it returns `{'headers': _unsubscribe_headers(token), 'unsubscribe_url': _unsubscribe_url(token)}`; otherwise it returns `value`.

- [ ] **Step 1: Write the failing tests** with `override_settings(EMAIL_BACKEND=locmem, DEFAULT_FROM_EMAIL='shop@example.com', EMAIL_HOST='smtp.test')`, calling `run_workflow(wf, payload)` with real `Workflow` rows:
  - `test_service_email_reaches_a_guest_order`: an order with no customer and `email='g@x.com'`, `order_number='1001'`. The body is `'Hi {customer_name},\n\nOrder {order_number} is late.'`. One message goes to `g@x.com`; its HTML contains `Order 1001 is late.` and the layout marker; it has no `List-Unsubscribe` header; the run is `state='succeeded'`. Use the state value the engine writes, read from `run_workflow`.
  - `test_placeholders_never_read_attributes`: the body `'{customer.user.password} {order.customer} {unknown}'` arrives unchanged, escaped.
  - `test_body_html_is_escaped`: the body `'<script>x</script>'` arrives as `&lt;script&gt;`.
  - `test_marketing_email_needs_a_confirmed_subscriber`: no subscriber → no mail, and the action message is `'not a newsletter subscriber'`. An `unsubscribed` subscriber gets the same result.
  - `test_marketing_email_to_subscriber_carries_unsubscribe`: a confirmed subscriber `Sub@X.com` and a customer `sub@x.com` → one message with `List-Unsubscribe` containing their token.
  - `test_marketing_refused_when_the_order_refused_marketing`: `order.metadata = {'consent': {...marketing False...}}`, shaped like the stamp `core.consent._permits` reads → the message is `'the order refused marketing'`.
  - `test_missing_purpose_fails_with_a_message` and `test_no_sending_email_fails_with_a_message` (with `EMAIL_HOST=''` and no `StoreSettings.smtp_host`).
- [ ] **Step 2: Run** `… manage.py test plugins.installed.workflows`. Expected: FAIL with "unknown action kind: email_customer".
- [ ] **Step 3: Implement** `emailing.py`, the templates, the handler (which calls `send_templated_email('workflow_email', to=email, subject=fill(subject), ctx=…, headers=answer['headers'] if marketing)`), the `ACTION_KINDS` entry, the editor help and the newsletter answer.
- [ ] **Step 4: Run** `… manage.py test plugins.installed.workflows plugins.installed.newsletter` and `get_template('emails/workflow_email.html')`. Expected: OK.
- [ ] **Step 5: Commit** with `feat: workflows can email the customer, as service or as marketing`.

### Task 7: Docs, gates and release

**Files:**
- Modify: `plugins/installed/newsletter/help.md` (composing, audiences, scheduling, the missed rule, Linda's tools) and `plugins/installed/workflows/help.md` (the action, the two purposes, the placeholders). Use only the allowed headings and markers; `release_notes/tests/test_help_*.py` guards them.
- Modify: `CLAUDE.md`. Add one convention paragraph, "a campaign reaches only the opted-in list (v0.190.0)". It covers:
  - the segment narrows the list;
  - marketing workflow email only to a confirmed subscriber;
  - the sentinel render;
  - the beat and the 24 h missed rule;
  - the guard files.
- Modify: `docs/plans/platform-gap-analysis-2026-11.md`. Mark the C2 row done with the version.
- Release: `manage.py release --minor "Email campaigns" -m …`, with one bullet each for the composer, audience, scheduling, the send-capability fix, Linda and workflows.

- [ ] **Step 1: Run the gates:**
  - `uvx ruff@0.15.8 check . && uvx ruff@0.15.8 format --check .`
  - `manage.py check`
  - `makemigrations --check --dry-run`
  - `scripts/check_core_boundary.py`, `scripts/check_plugin_boundary.py` and `scripts/check_plugin_standard.py`
  - `… manage.py test plugins.installed.release_notes core.tests.test_settings_keys_have_readers core.tests.test_authz`

  Expected: all pass. The plugin boundary has no new pairs, because no new cross-app imports were added.
- [ ] **Step 2: Run the full suite serially in the background with the opt-in apps** (`MORPHEUS_EXTRA_APPS=…` from CLAUDE.md), redirecting output to the scratchpad. Expected: OK. The only known noise is the two beat and celery-wiring tests when run without the opt-in apps.
- [ ] **Step 3: Release** with `manage.py release --minor …`, then run `manage.py release --check`. Expected: v0.190.0, and the check passes.
- [ ] **Step 4: Commit** the docs and the release, with `chore: release v0.190.0 — email campaigns`.
