# Help inside the dashboard, written next to each app

**Status:** design approved in conversation (2026-10-16 to 2026-10-18). This spec awaits the owner's review.

**Owner's request (2026-10-16):** "there should be internal help page system where it shows all about app and where is documentation always up to date"

**Owner's choices:**
- written for store staff first, with a folded technical part for developers;
- a guide for every app now, including the apps the consolidation waves will delete or merge;
- live help built from the running code, plus a guide file in each app's folder.

**Ships as:** one MINOR release.

## What is there today (checked 2026-10-16)

- **Settings → Developer → Help** frames morpheus.direct's `help.html` (`release_notes/views.py:help_page`).
  - It is written by hand once for every store and says nothing about any one app.
  - It changes only when someone edits the website.
- **The user menu hardcodes links to Help, About and Version & updates.** They sit in `admin_dashboard/base.html` behind `{% plugin_enabled "release_notes" %}`. This is the shell-to-app link the dashboard convention rules out.
- **Each of the 113 apps declares only `name`, `label`, `version` and `description`**, and 76 also declare `requires`. The descriptions are written for developers.
- **The code already knows a lot about each app:**
  - its dashboard pages and their sections (`DashboardPage`);
  - its settings pages and settings panel;
  - its landing-page cards;
  - its storefront blocks and their slots;
  - its agent tools and which of them need approval;
  - the events it listens to (handlers are tagged with their owner);
  - its URL mounts and what it requires.
- **`admin_dashboard/navigation.py:describe_app` already turns part of this into words** for the Apps catalogue. It also works for an app that is off, because it asks the app itself.
- **The shell's own pages (`CORE_TABS`)** are All orders, All products, Categories, Collections, Tags, All customers, the Marketing and Analytics overviews, and Linda's tabs. None of them records which app it belongs to.
- **No capability is held by every role** (`rbac/models.py:_DEFAULT_TEMPLATES`). `system.read`, which gates today's Help page, is admin-only. Once roles are enforced, a support agent could not open Help.

## Goal

Every staff member can find out, inside the dashboard:
- what each app is for;
- how to set it up;
- where its screens and settings are;
- what Janus can do with it.

Nothing on those pages can fall behind the code without CI noticing.

## Success criteria

1. **The Help index.** `/dashboard/help/` lists every installed app with a one-sentence summary, grouped by dashboard area, with search across every guide.
2. **Every app has a guide.** Every app folder in `plugins/installed/` has a `help.md`, and CI fails when one is missing.
3. **No dead links.** A guide never links a screen, setting, settings field or sidebar section that does not exist.
   - CI fails on an unresolved link.
   - At run time it renders as plain text, never as a dead link.
4. **Facts come from the running code.** "Where to find it", "What Janus can do" and the technical details are read from the running code on each request. None of that is written down anywhere.
5. **Help is linked from the screens.**
   - Every dashboard page or settings tool an app contributes carries a Help link to that app's help.
   - So does every shell tab in `CORE_TABS`.
   - The Apps catalogue shows the same summary as the help.
6. **Janus reads the same help** (`help.apps`, `help.read`), for every role and in every mode.
7. **It disables cleanly.** With `release_notes` off, `/dashboard/help/` answers 404, no Help link renders anywhere, and the help tools are gone.
8. **Every staff member can read help,** whatever their role.

## Behaviour

### The index: `/dashboard/help/`

- **Search box at the top.** `?q=` searches labels, summaries, headings and guide text, and shows each hit as the app's name, summary and a snippet.
  - An empty query shows the index.
  - A query with no hits says so and keeps the index below.
- **Apps that are on**, grouped by the area they live in: the same areas and labels as the Apps catalogue (`describe_app`). Each row shows the app's label and summary and links to its page.
- **"Not switched on"** lists the apps that are installed but off, in the same row format.
- **An opening line** links the dashboard's own guide (`admin_dashboard`'s `help.md`), which explains how the dashboard is laid out.

### An app's page: `/dashboard/help/<app>/`

Top to bottom:

1. **Header.** The app's label and summary, with an "On" or "Off" badge. When the app is off, a line says where to switch it on and links to Settings → Apps.
2. **Guide.** The app's `help.md`, rendered.
3. **Where to find it.** Generated from the app's contributions, each line a link to the place it names:
   - each dashboard page: "Products → Reviews";
   - each settings page or panel: "Settings → Catalog → Reviews";
   - each landing-page card: "a card on the Orders overview";
   - each storefront block, in plain words: "under the product page's buy form".

   For an app that is off, the same lines show as text without links, since those screens exist only while it is on.
4. **What Janus can do here.** Each of the app's agent tools, by its description. A tool that writes is marked "asks you first".
5. **Technical details** (a folded `<details>`):
   - the app's name and version;
   - what it requires, and what requires it;
   - the events it listens to;
   - its storefront slots and URL prefixes;
   - its manifest description.

An unknown app answers 404.

### Help links elsewhere

- **Page header.** Every dashboard page carries a "Help" link to the help of the app that page belongs to:
  - an app's own tab or settings tool links to that app;
  - a shell page links to the app named on its `CoreTab` (below).
- **User menu.** Help, About Morpheus OS and Version & updates are contributed by `release_notes` through `DASHBOARD_USER_MENU`. They replace the three hardcoded links in `base.html`.
- **Apps catalogue.** Each app shows its help summary, or its manifest description when it has no guide, plus a Help link.
- **Old address.** `/dashboard/apps/release_notes/help/` redirects to `/dashboard/help/`, and the Settings → Developer → Help card points there.
- **About is unchanged.** It stays the framed morpheus.direct page.

### Janus

- **`help.apps()`** returns every installed app: its name, label, summary, area and whether it is on.
- **`help.read(app)`** returns one app's help as plain text:
  - the summary;
  - the guide, with markers resolved to labels and paths;
  - "where to find it";
  - the tools Janus has there.

  An unknown name returns an error listing the closest app names.
- **One line is added to Janus's standing instructions:** read the help first when the merchant asks how to do something in the dashboard.

## Design

### The guide file: `plugins/installed/<app>/help.md`

```markdown
---
summary: Shoppers rate and review products; you approve or hide reviews.
---

## What it's for
…

## Set it up
…

## Common tasks
…

## Good to know
…
```

- **Front matter** holds exactly one key, `summary`: one plain sentence, at most 140 characters.
  - It is the merchant-facing sentence about the app, shown in the help, the Apps catalogue and Janus.
  - The manifest `description` stays as the developer note, shown in the technical details.
- **Headings** come from a fixed set, in this order:
  - "What it's for" (required);
  - "Set it up";
  - "Common tasks";
  - "Good to know".

  A section with nothing to say is left out.
- **Body length** is 60 to 400 words.
- **Plain words only.** Store staff read it, so the body never uses plugin, hook, slot, GraphQL, Celery, queryset, migration, endpoint, manifest or middleware. Those belong in the generated technical details. A test enforces the list, matching whole words, so "webhook" is allowed.
- **Links go through markers, never URLs** to the store's own pages. Links to outside sites (Stripe, Google Merchant Center) are written as plain `https://` links.

### Markers

| Marker | Example | Renders as | Resolves when |
|---|---|---|---|
| `page:<slug>`, or `page:<app>/<slug>` for another app's page | `[the Reviews tab](page:reviews)` | a link to that dashboard page | the app contributes a `DashboardPage` with that slug |
| `settings:<app>` | `[its settings](settings:reviews)` | a link to the app's settings page or panel | the app has a settings page or a settings panel |
| `field:<app>.<key>` | `[](field:reviews.auto_publish)` | the field's live label, linked to its settings | the key is in the app's settings schema |
| `section:<key>` | `[](section:orders)` | the sidebar section's live label, linked to its landing | the key is in `navigation.SECTIONS` |
| `app:<name>` | `[Orders](app:orders)` | a link to that app's help | that app folder has a `help.md` |

- **Empty link text** (`[](…)`) renders the live label, so a renamed page or field renames itself in every guide.
- **A marker that does not resolve** renders its text without a link, and the marker test fails in CI.
- **A marker to a page of an app that is off** renders as text, followed by "(when the app is on)".

### Reading the guides: `plugins/app_help.py`

This is shared plugin infrastructure at the `plugins/` package root: code that two apps need and core does not.
- It reads an app's `help.md` from the app's own folder, which works for an app in `MORPHEUS_APPS_DIR` too, and parses the front matter and sections.
- It caches per process, keyed on `MORPHEUS_VERSION`, and skips the cache under `DEBUG`.
- **`release_notes`** reads it for the Help area and the tools; **`admin_dashboard`** reads it for the catalogue summary.
- An app with no guide reads as `None`. The help page then shows the generated facts and the manifest description, and says the guide is missing.

### Generated facts: `release_notes/help_facts.py`

- **Source.** Built per request from the app's manifest instance. Contributions are asked of the app itself, so an app that is off still answers, as `describe_app` already does. Added to that:
  - `agent_registry` (tools and their owners);
  - `hook_registry` (events, by handler owner);
  - `app_registry` (on or off, requires, required by).
- **Labels and links.** Section labels, settings categories and page URLs come from `admin_dashboard.navigation`, so `release_notes` declares `requires = ['admin_dashboard']`. That is an allowed, declared dependency, and `admin_dashboard` is protected.
- **Slot words.** Storefront slots are put in plain words through one map in `release_notes` (`SLOT_WORDS`). A slot missing from the map shows its raw name, and a test fails.

### Built-in tabs name their app

`CoreTab` gains `app: str`, the app a shell page belongs to for help. The Help link uses it.

| Tab | Its app |
|---|---|
| All orders | `orders` |
| Returns | `orders` |
| All products, Categories, Collections, Tags, Content audit | `catalog` |
| All customers | `customers` |
| Marketing overview | `marketing` |
| Analytics overview | `analytics` |
| Linda's tabs | `agent_core` |

A test checks that every `CoreTab.app` names an app folder with a `help.md`.

### The Help link: `DASHBOARD_PAGE_HELP`

- **A new core filter**, declared in `core/hooks.py` with its contract. Value `None`; kwargs `app` and `request`.
- **The shell fires it** in two places:
  - in the page header, with the app the current location belongs to: `Location.tab.plugin`, else `Location.tool.plugin`, else the tab's `CoreTab.app`;
  - on each Apps catalogue card, with that card's app.
- **`release_notes` answers** `{'url', 'label'}` when the app's folder exists. With no answer, no link renders, so a disabled `release_notes` takes every Help link with it.

### Rendering

`release_notes`'s existing Markdown renderer is extended, and no dependency is added. It handles:
- `##` and `###` headings;
- paragraphs;
- bullet and numbered lists;
- bold and inline code;
- `https://` links (`rel="noopener"`);
- markers.

Every other character is escaped. A `<script>` in a guide renders as text.

### Search

- **The index** holds each app's label, summary, headings and body. It is built once per process, keyed on `MORPHEUS_VERSION`. Under `DEBUG` it is rebuilt on every request, so a guide edited locally shows without a restart.
- **Matching** folds case and accents. Hits rank label, then summary, then heading, then body.
- **Snippets** show about 160 characters around the first hit in the body.
- **No search service.** 113 short files fit in memory.

### Janus tools

- **Owner and registration.** `help.apps` and `help.read` are owned by `release_notes` and registered through `contribute_agent_tools`. Both are reads.
- **`scopes=[]`**, like `platform.capabilities`. A tool with no scopes is inside every role's profile (`linda_turn.catalogue`) and passes every mode (`filter_tools_by_mode`), so every staff member's Janus can read help.
- **Not public.** The storefront, cart, checkout and legacy `/mcp/v1/` doors each list their tools explicitly, so help is not exposed there. On `/mcp/admin/v1/` an external agent's token can read it. Help holds no store data, only documentation and which apps are on.
- **Removed with the app.** With `release_notes` off, both tools leave the catalogue.

### Access

The Help area requires a signed-in staff member (`@staff_member_required`) and checks no capability: no single capability is held by every role, and help shows documentation, not store data. The screens it links to still check access themselves.

## Writing the guides

- **All 113 apps get a guide in this release.** That includes the apps Wave 1 will delete and those Wave 2 will fold into others.
  - A Wave 1 app's guide says plainly what it does today, including when that is nothing.
  - A Wave 2 app's guide describes it as it is now.
- **Each guide is written from the app's own code:**
  - its manifest and contributions;
  - its views and templates;
  - its settings schema;
  - its agent tools;
  - its tests.

  It describes only what the code does today. A broken or dead feature is never described as working.
- **Defects found while writing are reported, not fixed.** They go to the owner as a list.
- **Process.** Guides are drafted in parallel batches by dashboard area, then reviewed one at a time against the code and the generated facts that sit beside them on the page.
- **Later waves:**
  - deleting an app deletes its guide with its folder;
  - a merge folds the absorbed app's guide into the target app's guide in the same release.

## Keeping it current

- **What tests catch:** a missing guide, a link to a screen, setting, field or section that no longer exists, a missing summary, a heading outside the set, developer jargon in the body, and a storefront slot with no plain words.
- **What the code generates:** "where to find it", the Janus tools and the technical details, so they cannot drift.
- **The limit:** whether a guide's sentences still describe what the app does is a review rule, not a test. `CLAUDE.md` and `docs/PLUGIN_DEVELOPMENT.md` gain the rule that a change to what a merchant sees or does in an app updates that app's `help.md` in the same commit, and that a new app ships with its `help.md`.

## Left out

- per-app "what's new" taken from the release notes;
- editing help from the dashboard;
- translated help (the dashboard is English);
- help for shoppers on the storefront;
- a search service.

## Testing

All in `plugins/installed/release_notes/tests/` unless named otherwise.

- **`test_help_files.py`**
  - every `plugins/installed/*/app.py` folder has a `help.md`;
  - the front matter has a one-sentence summary of at most 140 characters with no markup;
  - headings come from the set, with "What it's for" first;
  - the body is 60 to 400 words;
  - the jargon list is matched as whole words.
- **`test_help_markers.py`**
  - every marker in every guide resolves against the app manifests (installed or not) and the sidebar sections;
  - every `CoreTab.app` has a guide;
  - every slot any contribution names, read from the runtime registry, has plain words.
- **`test_help_pages.py`**
  - the index and every installed app's page answer 200, with the app both on and off;
  - an unknown app answers 404;
  - a signed-out visitor is sent to sign in;
  - a staff member with no role reads help;
  - search finds an app by a word that appears only in its guide body;
  - a `<script>` in a guide renders escaped;
  - the old address redirects.
- **`test_help_links.py`**
  - an app's page, a settings tool and a shell page (All orders) each carry the right Help link;
  - the Apps catalogue shows the summary and the link;
  - the user menu carries Help, About and Version from the contribution, and `base.html` no longer names `release_notes`.
- **`test_help_disable.py`.** With `release_notes` off:
  - `/dashboard/help/` answers 404;
  - no Help link renders in the header, the user menu or the catalogue;
  - `help.apps` and `help.read` are not in Janus's catalogue.
- **`test_help_tools.py`**
  - `help.apps` lists every installed app with its on/off state;
  - `help.read` returns the guide with markers resolved and no raw `page:` text;
  - an unknown app returns the closest names;
  - both tools are in every mode's catalogue for a staff member with no role.
- **Existing guards still pass:**
  - `admin_dashboard/tests/test_navigation.py`;
  - `test_disable_guards.py`;
  - `agent_mcp/tests/test_linda_turn.py::LindaCatalogueTests`;
  - `agent_mcp/tests/test_scopes.py`;
  - the plugin-boundary ratchet, with the new `release_notes → admin_dashboard` import declared in `requires`.
