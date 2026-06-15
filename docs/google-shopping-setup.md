# Google Shopping — merchant setup guide

How to connect the `google_shopping` plugin to Google Merchant Center + Google
Ads. The plugin is fully built; this is the one-time credential setup. Everything
is entered in **Dashboard → Settings → Channels → Google Shopping feed** and
stored in PluginConfig (never in `settings.py` or the repo).

## What you get once connected

- **Product feed** at `https://<your-domain>/feeds/google-merchant.xml` — submit
  it in Merchant Center, or let the **Content API** push products directly.
- **Merchant diagnostics** — live disapproval/issue breakdown on the dashboard.
- **Google Ads** — create Shopping campaigns, report (cost/clicks/conv/ROAS),
  pause/enable/budget, and a dynamic remarketing tag.

The feed works with **no credentials at all** — only the API push, diagnostics
and Ads features need the Google connection below.

---

## 1. Create an OAuth client (Google Cloud Console)

1. Go to <https://console.cloud.google.com/> → create/select a project.
2. Enable the **Content API for Shopping** and the **Google Ads API**.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   → application type **Web application**.
4. Under **Authorized redirect URIs** add exactly:
   `https://<your-domain>/dashboard/apps/google_shopping/oauth-callback/`
5. Copy the **client ID** and **client secret**.

Paste those two into the settings panel (`OAuth client ID` / `OAuth client
secret`) and save.

## 2. Connect with Google (one click)

On **Dashboard → Google Shopping**, the connection card now shows
**“Connect with Google.”** Click it → grant access on Google’s consent screen
(this authorises both Merchant **and** Ads in one go) → you’re redirected back
and the refresh token is captured automatically. The card flips to
**✅ Connected**.

> Behind the scenes this uses `access_type=offline` + `prompt=consent` so Google
> returns a refresh token, and an anti-CSRF `state` token is verified on return.

## 3. Merchant Center ID

In <https://merchants.google.com/> copy your **Merchant Center ID** (top right)
into the `Merchant Center ID` field. Required for the Content API push and the
diagnostics panel.

## 4. Google Ads (optional — only for the Ads dashboard)

1. In your Google Ads account: **Tools → API Center** → copy the **developer
   token** → `Google Ads developer token`.
2. Copy your **customer ID** (top right, `123-456-7890`) → `Google Ads customer
   ID` (dashes are fine).
3. If you access the account through a manager (MCC) account, put the manager’s
   ID in `Google Ads login customer ID (MCC)`.

The **Google Ads** dashboard page then shows campaign reporting and the
create/manage controls. (Conversion tracking itself is owned by the separate
**tracking** plugin — set your `AW-…` conversion id there.)

## 5. Per-product overrides (optional)

Any product can override feed attributes via the `google.*` metafield namespace:
`google.condition`, `google.google_product_category`, `google.brand`,
`google.custom_label_0…4`, `google.gender`, `google.age_group`, and
`google.excluded` (set truthy to keep a product out of the feed). Defaults come
from the settings panel.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Feed URL returns 404 | The feed is disabled — enable it in settings. |
| “Connect” bounces to settings | OAuth client ID/secret not saved yet. |
| Connected but “no refresh token” | Re-run Connect — Google only returns one with `prompt=consent` (the plugin forces this). |
| Content push says “not connected” | Set the Merchant Center ID + complete the OAuth connect. |
| Ads page shows “connect” after OAuth | Add the developer token + customer ID. |
| Feed served stale after a deploy | Redis cache survives deploys — hit **Rebuild feed**. |

## Architecture

See `docs/plans/google-shopping.md` for the full design, API surfaces, and the
boundary with the `tracking` plugin.
