# C2 — Email campaigns and the workflow "Email customer" action

Status: design, waiting for the owner's approval (2026-11-23).
Plan of record: `docs/plans/platform-gap-analysis-2026-11.md`, row 10.

## Intent

The merchant has no way to write a newsletter. There is a send engine
(`newsletter/tasks.py:send_campaign`) and a model (`marketing.EmailCampaign`),
but nothing creates a campaign, so the engine has never sent anything. A store
that wants to tell its subscribers about a new book or a sale has no way to do it.
Linda has no way either. Automations (workflows) cannot email a customer at all.

C2 makes the existing pieces usable. It does not build a second email system.

## Goals

1. **Compose a campaign** in the dashboard. A campaign has:
   - a name;
   - a subject;
   - a preheader;
   - a rich-text body;
   - an audience;
   - an optional send time.

   The merchant can save a draft, send a test copy to themselves, send now,
   schedule a send, or cancel a scheduled send.
2. **Choose the audience.** It is either every confirmed subscriber or the
   confirmed subscribers in one RFM segment (champions, loyal, potential, new,
   at_risk, lost). A segment only narrows the confirmed list. It never adds an
   address that did not opt in.
3. **Send a scheduled campaign at its time.** Today `scheduled_at` is stored and
   never read.
4. **Send in the store's own look.** The body is sanitised and wrapped in
   `emails/_layout.html`, like every other email the store sends. Today the raw
   HTML goes out, bare.
5. **Let Linda use it:**
   - `newsletter.campaign_create` writes a draft and needs approval.
   - `newsletter.campaign_send` sends now or schedules, and needs approval.
   - `newsletter.campaigns` lists campaigns and is read-only.
6. **Add a workflow action, "Email customer".** The workflow sends one email,
   with its own subject and body, to the customer of the event (the order's
   customer, or the event's customer or email). The merchant picks a purpose for
   each action:
   - **service** (about their order) goes to anyone the event names;
   - **marketing** goes only to a confirmed newsletter subscriber who has not
     refused marketing. It carries the newsletter's unsubscribe link and the
     RFC 8058 headers. When the address is not subscribed, the action is
     skipped and the reason is recorded on the run.

## Non-goals

- Open and click tracking. The `open_count` and `click_count` columns stay
  unfed, and the dashboard does not show them.
- A/B subjects, send-time optimisation, and drag-and-drop email builders.
- Audiences other than "all" or one RFM segment: no tags, no purchase history,
  no hand-made lists.
- Emailing customers who are not subscribers as marketing. `Customer.accepts_marketing`
  has no reader today, and C2 does not give it one.
- A Linda tool that creates or edits workflows. Linda has only `workflows.run`
  today, so the new action is reachable only from the workflow editor.
  Building workflow tools is its own change.
- Changes to win-back, popups or the double opt-in.

## Anti-goals

These would make C2 a failure even if it works:

- **Marketing mail to someone who never opted in.** That covers a segment that
  widens the list, a workflow marketing email to a non-subscriber, and a missing
  unsubscribe link.
- **A campaign sent twice.** The causes would be a double click, the beat and a
  manual send at once, or a retry. The existing atomic claim and the
  `CampaignSend` ledger stay the only way a campaign starts.
- **Merchant HTML that reaches inboxes unsanitised,** or a workflow placeholder
  that can read any attribute of a model (for example `customer.user.password`).
- **A staff member who can only read Marketing being able to send to the whole list**
  (today's bug).

## Constraints

- **Ownership.** `marketing` owns `EmailCampaign`, and the new `audience` field
  goes there. `newsletter` owns the audience, the sending, the composer pages
  and the Linda tools. It already reads `EmailCampaign` through `requires=['marketing']`.
- **No plugin→plugin imports beyond `requires`.** Two places need data another
  app owns:
  - **Segment emails.** newsletter fires a new filter,
    `CUSTOMER_SEGMENT_EMAILS(value=None, segment=<key>)`, and the customers app
    answers it with the set of lower-cased emails in that segment. When nothing
    answers, segment campaigns are refused with "the customers app is off".
    The audience field still offers the choice, but Send explains the refusal.
  - **Marketing recipient for workflows.** workflows fires a new filter,
    `MARKETING_EMAIL_RECIPIENT(value=None, email=<addr>)`. newsletter answers
    only for a confirmed subscriber, with `{'headers': {...}, 'unsubscribe_url': ...}`.
    When nothing answers, the marketing send is refused ("not a subscriber").
    Workflows imports no newsletter code.

  Both events are declared in `core/hooks.py` with their kwargs, like the
  existing filters.
- **Consent.** A marketing workflow email whose event carries an order also
  needs `core.consent.allowed('marketing', order=order)`, as the C1
  post-purchase emails do. A campaign's legal basis is the double opt-in itself.
  This is unchanged, and the win-back email works the same way.
- **Capabilities:**
  - composing, testing, scheduling, sending and cancelling need `marketing.write`;
  - the list page stays on `marketing.read`;
  - the "Email customer" action is edited inside workflows, which stays on
    `system.write`.
- **Linda scopes.** The new tools use `promotions.read` and `promotions.write`.
  Those are the marketing scopes that already sit in `gates.LINDA_SCOPES` and map
  to `marketing.read` and `marketing.write`. The two write tools carry
  `requires_approval=True`. They are not everyday writes: one sends mail to the
  whole list.
- **Migration.** `EmailCampaign.audience` is
  `CharField(max_length=20, blank=True, default='', db_default='')`, where an empty
  value means every confirmed subscriber. It is added with `db_default`, so the
  previous release keeps working (migration gate).
- **Body sanitising.** The body is cleaned with
  `core.utils.html.sanitize_richtext` when it is saved, whether from the
  dashboard or from Linda, and once more when it is sent, for rows written
  before C2. `text_body` is derived from the cleaned HTML
  (`strip_tags` + unescape) when the merchant leaves it blank.
- **Rendering.**
  - The campaign HTML is rendered once per send with a new template,
    `newsletter/templates/emails/newsletter_campaign.html`. It extends
    `_layout.html`, carries the preheader, and puts the clean body in the body
    block.
  - The per-recipient unsubscribe footer is added after that, as today.
  - The template is not registered as an overridable `EmailTemplateDef`,
    because each campaign carries its own content.
- **Scheduling.**
  - A new beat entry, `newsletter:send_due_campaigns`, runs every 300 s.
  - For each campaign with `status='scheduled'` and `scheduled_at <= now`, it
    calls the existing `send_campaign`. The claim inside `send_campaign` already
    stops a double start.
  - Scheduling sets `status='scheduled'`. Cancelling a scheduled campaign sets
    it back to `draft`, so it can be edited again. A campaign that is `sending`
    or `sent` cannot be edited, scheduled or cancelled.
  - The send time is entered in the store's time zone and stored in UTC.
  - A time in the past is refused.
- **Workflow placeholders.** A workflow email's subject and body may use exactly
  these placeholders:
  - `{customer_first_name}`
  - `{customer_name}`
  - `{order_number}`
  - `{order_total}`
  - `{store_name}`

  They come from a fixed map. The body is plain text, escaped, and split into
  paragraphs. It is never a Django template, and no dotted path is looked up.
  An unknown placeholder stays as typed.
- **Workflow sending.** The action calls
  `core.emails.send_templated_email('workflow_email', …)` through a new
  `workflows/templates/emails/workflow_email.{html,txt}`, so the mail has the
  store layout and goes out after commit through the same queue.
  - Action spec: `{kind: 'email_customer', purpose: 'service'|'marketing', subject, body}`.
  - The purpose is required. An action with no purpose, or an unknown one,
    fails with a message instead of guessing.
  - Missing subject, missing body or no address all fail with a message on the
    `WorkflowRun`.
- **Docs.** The newsletter and workflows `help.md` files, `CLAUDE.md` (a short
  convention entry) and the plan's status line ship in the same change, along
  with a `manage.py release --minor` entry (v0.190.0).

## Approaches

- **A. Make the existing engine usable (chosen).**
  - Add a composer and an audience field to `EmailCampaign`.
  - Reuse `send_campaign`'s claim, batching and ledger.
  - Add one beat task.
  - Make the workflow action a new handler in `ACTION_HANDLERS`.

  It is small, builds on code that already handles double sends and large lists,
  and keeps one model owner.
- **B. Send campaigns through `send_templated_email` per recipient.** This would
  give the layout and the override path for free. But it throws away the
  claim, batching and ledger, or has to rebuild them, and a per-campaign body
  does not fit the per-key override model. Rejected.
- **C. A new "Campaigns" app with its own model.** This would duplicate
  `EmailCampaign`, which is the parallel-table mistake CLAUDE.md warns about
  (one concept has one model owner). Rejected.

For the workflow email, the owner chose (2026-11-23) that the merchant picks a
purpose for each action, either service or marketing. Marketing gets the consent
check and the unsubscribe link. The alternatives were "always service" and
"always marketing".

## Decided by the owner

- C2's scope as written in the plan: a composer, the audience as all opted-in or
  an RFM segment, scheduling, sending through the store's email path,
  `newsletter.campaign_create` with approval, and a workflow email action.
- The workflow email's purpose is picked per action: service or marketing (A+B).

## My calls (the owner may overrule)

- A segment only narrows the opted-in list. It never emails a customer who did
  not subscribe.
- Cancelling a scheduled campaign returns it to draft instead of marking it
  `cancelled`, because a draft can still be edited.
- Linda gets three tools: a read-only list, a create, and a send or schedule.
  Keeping create and send apart means the merchant approves the content and the
  send separately.
- No open or click tracking, and no Linda tool for creating workflows (see
  Non-goals).
- The placeholders are a fixed list of five.
- **What "has not refused marketing" means.**
  - The confirmed newsletter subscription is the consent. A refusal is either
    `status='unsubscribed'` (the newsletter does not answer the filter for that
    address) or a consent decision that refuses marketing, recorded on the
    event's order (`order.metadata['consent']`).
  - When an event has no order, as with `customer.registered` and
    `cart.abandoned`, the subscription alone decides. Store-level
    `consent.allowed` is not consulted, because with no visitor it would refuse
    every send on a store that manages consent, even to a subscriber who
    confirmed by email.
- **Who receives a workflow email.** The first that exists wins: the payload's
  `customer.email`, then `order.customer.email`, then `order.email` (a guest
  order), then the payload's `email`. A guest gets service mail. Marketing mail
  still needs the subscription.
- **The workflow action checks before it sends.** `send_templated_email` returns
  nothing and only logs, so the action first checks for a sending address
  (`core.email.smtp_configured()` and `DEFAULT_FROM_EMAIL`) and records
  "no sending email" on the run when either is missing.
- **The preheader is the existing `preview_text` column.** No new column.
- **The existing Send button becomes the composer's send.** It needs
  `marketing.write`, honours the audience, and is refused for a campaign that is
  `sending`, `sent` or `cancelled`.
- **The test copy is rendered exactly like the real send:** the layout and the
  footer. The unsubscribe link points at a sample token that does nothing.
- **Segment emails are read in full, once per batch.** The filter returns every
  email in the segment, which fits stores of up to tens of thousands of
  customers. A customer who changes segment during a multi-batch send may or may
  not get the email. The ledger still makes sure nobody gets it twice.
- **The beat goes through `register_celery_beat`,** as post_purchase's does,
  under the task's registered `name=` (`newsletter.send_due_campaigns`).
- **A campaign more than 24 hours past its time is not sent.** That happens when
  workers were down. It goes back to `draft`, and the list shows "missed its
  send time": a sale announced days late is worse than one not sent. A campaign
  stuck in `sending` after a crash behaves as it does today, which C2 does not
  change.
- **The workflow editor stays the JSON textarea.** The action's example spec and
  the placeholders go in the editor's help text and in the workflows `help.md`.
  A form for actions is a separate change.

## Left to the builder

- The composer's layout. It follows the dashboard conventions: one page width,
  `{% richtext_field %}` for the body, `data-confirm` on Send, and the hub
  section and tab under Marketing next to the existing Campaigns page.
- The names of the views, URLs and test files.
- How the composer previews the email. A "Send test" is enough; an in-page
  preview is optional.
- How the existing campaigns list shows the audience and the scheduled time.
