# Morpheus OS — Release Notes

Detailed, user-facing updates to the **Morpheus OS core** and its modules,
surfaced in **Dashboard → Settings → Version & updates**.

> **House rule (enforced):** merging to `main` is a production deploy, so
> **every deploy MUST bump `MORPHEUS_VERSION` and add a matching dated
> `## vX.Y.Z — YYYY-MM-DD` entry** here describing the change. Don't hand-edit —
> run **`python manage.py release --minor "Headline" -m "bullet"`** (it writes
> both atomically); `release --check` is a blocking CI gate. This file is the
> single source of truth for the in-dashboard changelog, and the `release`
> GitHub workflow mirrors each version to a git tag + GitHub Release. See
> [`CLAUDE.md`](../CLAUDE.md) and torsor ADRs "Versioned release notes" + **0032**
> + **0033** (every production deploy bumps the version; app *and* theme code).

---

## v0.75.12 — 2026-09-24

**Linda chat: composer stays put when the sidebar nav is expanded**

- The desktop sidebar (lg:static, inside a min-h-screen flex body) had no height bound, so expanding a nav group grew it past the viewport, stretched the content column, and pushed the Linda chat composer — an absolute inset:0 child of #main-content — below the fold.
- Pin the desktop rail to the viewport (position:sticky; height:100dvh) so its own nav scrolls internally instead of growing the page. The composer stays fixed at the bottom on every page.

## v0.75.11 — 2026-09-24

**Product editor: saving works again (un-nested variant forms)**

- The variant delete/add/edit forms were nested inside the product form, which is invalid HTML — the browser adopted the add-variant modal's empty required name/SKU into the product form, so native validation aborted every save ('An invalid form control is not focusable') before it could run.
- Un-nested them: delete buttons now target their form via form=, and the add/edit modals are dialogs outside the product form. Saving now succeeds and runs through the interactive AJAX path — a button spinner ('Saving' → 'Saved'), no full-page reload.

## v0.75.10 — 2026-09-23

**Deeper, unique hotel pages: data-grounded 'Staying in' intro + 'Best for' profile**

- Hotel detail pages were thin and shared one boilerplate 'Staying in…' paragraph across all 68 (SEO audit). New stay_content composes a unique intro from each property's own type, star rating, region and the real nearby-place names, plus a 'Best for' audience profile derived from its type/stars/amenities. No invented facts, no LLM — pure and unit-tested.

## v0.75.9 — 2026-09-23

**Fix montenegro header hiding under the admin bar + dashboard icon baseline alignment**

- Montenegro: the admin-bar offset targeted .topbar (which this theme doesn't use), so with the admin bar now correctly pinned the header slid under it — offset the real <header> and the home categories rail by 32px instead.
- Dashboard: Remix icon-font glyphs render low on the baseline; flex-center every icon glyph in its box (not just on .btn/.nav-link surfaces) so the top-bar search field and other icon+element pairs align.

## v0.75.8 — 2026-09-23

**Montenegro SEO: hotels hub meta description + trimmed over-long hub metas**

- The /hotels/ hub had 1,700+ words but no meta description (stay_detail set one, stays_index didn't) — added a 154-char description. Trimmed the /events/ (167) and /places/ (172) hub meta descriptions to a SERP-friendly ~154 chars.

## v0.75.7 — 2026-09-23

**Fix the admin bar scrolling away and leaving a gap above the sticky header**

- The motion plugin's page-enter animation ran on <html> with a transform keyframe, which makes the root a containing block for position:fixed — so the staff admin bar scrolled away with the page instead of staying pinned, leaving a ~32px hole above the sticky store header on every theme (visible only when signed in). The entrance is now an opacity-only fade.

## v0.75.6 — 2026-09-22

**Self-heal the legal pages if their seed was ever swallowed**

- gdpr now re-runs its idempotent legal-page seed on post_migrate, so a seed that failed once (e.g. mid store-cutover) and left the 0002 migration marked applied with zero pages — 404ing every footer legal link — recovers on the next deploy instead of staying broken forever.

## v0.75.5 — 2026-09-22

**Fix product pages crashing on any tagged product**

- PDP 500'd for every product carrying a tag (180 of 684 on the supernatural store) — the tag-chip link used {{ tag.slug|default:tag.name }}, but GraphQL returns tags as plain strings, so the eager filter argument raised VariableDoesNotExist. Now uses {% firstof %} across all three themes; renders string and object tags alike.

## v0.75.4 — 2026-09-22

**Bigger, left-aligned product image on the Supernatural Shop PDP**

- The product-detail image was capped at ~412px and centred in a narrow 2fr/3fr column, inset ~48px from the page's left edge. Both were sized for portrait book covers: the column comment literally says a cover "doesn't need half the page", and the product_gallery plugin caps the hero by (100svh − reserve)/1.5 — the 1.5 being a 2/3 cover ratio that under-sizes this store's square images.
- The PDP now uses a 50/50 split; the image fills its column (~640px, +55%) and its left edge lines up with the breadcrumb. Scoped to the supernatural_shop theme (overrides the shared plugin with !important) — dotbooks and montenegro keep their book-cover layout. Mobile (<900px, single column) is unchanged.

## v0.75.3 — 2026-09-22

**Supernatural Shop copy drops leftover book-shop vocabulary**

- The Supernatural Shop theme is a clone of the book theme, so an essential-oils store showed book vocabulary in its copy: the PDP said "About this book", "Reader questions", "Reader letters" and "Readers who picked this also reached for"; the cart column read "Book" and its empty state said "pick a book or two"; checkout said "Browse books"; the privacy page said "ship you a book"; account pages said "book reviews" and "for other readers". All 12 are now product-neutral ("About this product", "Common questions", "Customer reviews", "Item", "Browse the shop", "ship your order", …).
- The shop's deliberate apothecary voice is untouched: the "Made for the workbench, not the bookshelf" tagline and the "shelf / bench" metaphor stay, because they are the brand, not a leak.
- Book-taxonomy nav panels (authors/genres/topics) and the /authors/ page are book_product-driven and off on this store, so they don't render — left as-is rather than editing dead templates.

## v0.75.2 — 2026-09-22

**Product cards show clean text, and survive the book vertical being off**

- Supernatural Shop product cards rendered raw HTML entities — "bring it back&#8230; It&#8217;s been…" — because the card used |striptags, which removes tags but leaves entities to escape into literal text. It now uses first_sentence, which decodes entities and strips markup into clean prose (matching the other themes).
- That filter, first_sentence, lived in book_product's book_extras — but every theme's shared product card uses it, and montenegro + supernatural just disabled the book vertical. Their cards `{% load book_extras %}`, which fails to parse once book_product is uninstalled: a latent 500 that only stayed hidden because those stores have no catalog products to render a card for. first_sentence moved to core's morph (always loaded); the three cards no longer load book_extras.
- Guarded both ways: core/tests/test_first_sentence.py (entities/markup never leak) and a scan that fails if any theme's shared _product_card.html loads book_extras again.

## v0.75.1 — 2026-09-22

**Supernatural Shop product images are no longer tiny squares**

- The Supernatural Shop product grid packed up to 6 columns on desktop, rendering every product an ~208px square — bookshelf density inherited from the book theme, wrong for a boutique shop of essential oils, hydrosols and ritual goods. It now shows 2 columns on phones, 3 on tablets and 4 on desktop, so each product image is ~318px — about 50% larger.
- Scoped to the supernatural_shop theme's own base.html; dotbooks (dot_books) and Montenegro keep their own layouts untouched. The horizontal --rail carousels set their own flex layout and are unaffected.

## v0.75.0 — 2026-09-21

**A non-book store can switch off the book vertical**

- book_product ships as a default app (the first Morpheus store sold books), so the Montenegro travel marketplace served live /genres/, /authors/, /series/ pages and a "Book taxonomies" dashboard page it can never fill. A new MORPHEUS_DISABLED_APPS env lets a deployment subtract a default app; montenegro + supernatural switch off the book vertical (book_product, audiobooks, and the entirely book-gated eco_impact) in their own Coolify env.
- This deploy changes nothing on its own: a store that sets no MORPHEUS_DISABLED_APPS — dotbooks — is completely unaffected and keeps its whole book vertical. The switch is opt-out, per deployment, no code fork.
- book_product's Genres/Topics nav context processors moved from settings.TEMPLATES to register_context_processor, so a store with the vertical disabled runs none of that code instead of querying unloaded models on every request. INSTALLED_APPS also now dedupes, so listing an app in both the default and extra lists can't double-register it.

## v0.74.1 — 2026-09-21

**Hotel stay policies are data-driven, not hardcoded in the theme**

- The stay-policies block added in v0.74.0 hardcoded the four policy keys and their labels in the montenegro theme. The theme no longer knows the shape of a hotel's policies dict: POLICY_LABELS (the plugin's models) owns the labels and their order, a _policies view helper resolves them, and the template just loops what it is given — the same arrangement amenities already use.
- A policy key the theme has never heard of now renders, humanised, with no theme edit — so adding a policy is a data change, not a template change. Existing hotels render exactly as before.

## v0.74.0 — 2026-09-21

**Hotel pages now link out to the region around them**

- A montenegro hotel page ended at its room list with two generic links. It now carries three internal-linking blocks: the destination guides in the hotel's region (/places/), other hotels in the same town and region (/hotels/), and the stay's own cancellation, children, pets and payment policies — a field that was stored on every hotel but never rendered.
- The related-hotels rail is ordered by star class, a real attribute, and shows ★ — never the guest rating this store stopped publishing. Same-town hotels rank ahead of the wider region; a hotel never links to itself, and an inactive hotel or vendor never appears.
- This is the audit's §4.2 hub<->spoke: a stay now points at the region pages that rank for its area, and they point back, so crawlers (and readers) can move between them. Every block is hidden when it has no data, so a hotel with no region or policies degrades cleanly.

## v0.73.3 — 2026-09-21

**Every hotel got its own meta description**

- montenegro's hotel pages drew their meta description from a string built out of star rating, type and town alone, so nine 4-star Podgorica hotels all published "An upscale hotel in Podgorica." — 18 such groups, 52 hotels, the site audit's top warning.
- Each hotel's meta description now leads with its own name and names its real amenities ("… in Podgorica, Montenegro, with a pool, a restaurant and a gym"). Across all 100 live hotels: 100 distinct descriptions where there were 66, every one inside the 70–160 character window, and none naming an amenity the hotel does not have.
- The generator was fixed and a `refresh_hotel_blurbs` command rewrites the already-seeded hotels in place. It only touches a description still holding the old generated string, so a hotel a host has since written up keeps its own words.
- Nothing a shopper sees changes: the hotel page's on-page description was already unique and is untouched.

## v0.73.2 — 2026-09-21

**The AI feed stopped claiming reviews nobody wrote**

- `/ai/products.json` put an `aggregateRating` on 225 of the Montenegro store's 242 listings — 40,733 reviews in all — read from the denormalised `rating`/`review_count` columns. The database held 559 reviews, every one written by `seed_reviews` with no booking behind it, and the 100 hotel ratings were computed from a hash of each hotel's slug: hotels have no review model at all.
- A rating is now claimed only from reviews carrying the evidence `create_review` demands — a confirmed or completed booking (`booking_marketplace/services.py:verified_reviews`). The experience page's `aggregateRating` and its `Review` nodes come from that one set; the page had claimed "4.8 from 3 reviews" whenever the columns said so, whatever it showed.
- Hotels never carry a guest rating in the feed now, matching the hotel page, which already omitted it for exactly this reason. The hotel's star class is a fact about the hotel and stays.
- Nothing changes on the page a shopper sees: which reviews a merchant displays is their content. What the platform asserts to Google and AI crawlers is not.
- The feed computes the verified rating for every listing in one query, guarded by a test that fails if it ever becomes one query per row.

## v0.73.1 — 2026-09-21

**404 pages were titled Error**

- The shared 404 passes title='Page not found' to storefront_head, but _title_from_object only reads the page's OBJECT and an error render has none — so _fallback_title Title-Cased the subtype and every 404 shipped as 'Error — <store>'. The resolver now names the error page explicitly, and a title the template supplies still wins.

## v0.73.0 — 2026-09-21

**One store's brand was published on every other store**

- The storefront shell hardcoded dot books inside SEO descriptions, so two other live businesses introduced themselves to Google as a bookshop. supernatural-shop.com About read 'dot books is an independent bookshop, run by readers, for readers'; montenegro-experience.me Shipping read 'How dot books ships your order — tracked, signed-for, free over 40 dollars'. Verified live on both before the fix.
- The shipping line is the serious one: a rate and a threshold published on stores whose checkout has no such rule — the same shape as the invented shippingDetails in the offer-claims landmine, a promise checkout will break. It now describes delivery generically and names no rate the shipping app did not supply.
- Worse still, the CCPA opt-out page asserted 'DotBooks does not sell personal data' — a privacy claim, under another company's name, on every store. It now describes the RIGHT rather than any store's data practices, which the shell has no way to verify.
- Descriptions come from the merchant's own StoreSettings (store_name, store_description / meta_description), and fall back to nothing rather than to invented copy. 'All books' was hardcoded in six places for titles and breadcrumbs, so an oils shop's listing was titled All books; the book vertical owns that word now and every other store gets the neutral one.
- templates/404.html overrode the whole seo block with its own title and robots meta, so error pages on every theme without their own 404 shipped one store's brand, no canonical, no Open Graph — and the v0.70.3 error-page noindex rule could never reach them. It calls storefront_head now. templates/500.html renders with an empty context so its brand is simply gone.
- Guarded by storefront/tests/test_store_identity.py (no brand and no 'All books' anywhere in the shell) and the head-contract guard extended to the shared error templates.

## v0.72.2 — 2026-09-21

**The sitemap dashboard and the SEO audit saw a fraction of the real sitemap**

- Both read iter_sitemap_entries(), which yields only the URLs seo builds itself. A vertical's routes arrive through the SITEMAP_URLS filter and were invisible to both: on the Montenegro marketplace the Sitemap page reported 59 URLs while /sitemap.xml served 343, and the new site audit checked the same 59 — every booking, stay, place and event, i.e. the entire commercial catalogue, was skipped by the two screens that exist to cover it.
- Both now read the merged corpus. Contributed URLs get their own count rather than being absorbed into manual_count, which means a hand-written SitemapEntry row and would have misreported both. Guarded by a test asserting the dashboard total equals what /sitemap.xml actually serves.

## v0.72.1 — 2026-09-21

**Site audit reported every page as a redirect on production**

- SECURE_SSL_REDIRECT is on in production and off in dev, so the in-process request the audit makes was 301ed to https by SecurityMiddleware before it reached a view. The first production run reported 59 of 59 sitemap URLs as critical Sitemap lists URLs that redirect — the dashboard lying at maximum volume, and invisible to every local test because dev does not set the flag. The audit now makes a secure request, and a test pins SECURE_SSL_REDIRECT on so this cannot regress.

## v0.72.0 — 2026-09-21

**The SEO page shows what is wrong, not how many of things there are**

- The page led with five counters — meta complete, redirects, 404s, keywords, audits. None of them is a problem you can act on: '12 redirects' is a fact, not a finding. And none could surface the three defects a paid audit of a live Morpheus store actually found in Sep 2026, because all three exist only BETWEEN pages and all three render as valid markup: two URLs sharing a title, a sitemap inviting crawlers to a URL that redirects, and a bilingual store emitting no hreflang.
- New site-wide scan (seo/services/site_audit.py) renders every URL in the sitemap through the real stack and reports twelve classes of finding, each with the reason it costs traffic, up to five real example URLs, and a link to where it is fixed. Ordered worst-first by severity then page count, with a health score and head-coverage bars measured from what the page RENDERED rather than whether a column is non-empty (the seo_gap landmine).
- It never runs in a request: a full render per URL inside a live request would re-enter the middleware stack and hold a worker for the length of the catalogue. It runs nightly at 03:10 via a new beat task, on demand from `manage.py seo_site_audit`, or from the page's Scan button which dispatches to a worker — and says so plainly when no broker is reachable rather than reporting 'queued' for work that never ran.
- Results are cached, not stored in a table: this is derived data that is recomputable at any time, so a migration would buy history nobody needs. The cache outlives a daily run by two hours, so a failed night shows the previous report instead of an empty page.

## v0.71.0 — 2026-09-21

**Product image shape is a setting, not a book cover**

- Every image frame on the platform was hardcoded 2/3 — a book cover — because the first store here sold books. Six in the dashboard alone (the product list's h-10 w-7 = 28x40, the media library tile and modal, the cover slot, the variant modal) plus every theme card. A store selling soap, tours or wine showed square photographs letterboxed into portrait slots in the merchant's own product list.
- Nothing could change it: the Images panel's grid_image_width/height and og_image_width/height had ZERO consumers in the tree — the 'a settings field with no consumer is a lie' landmine, four keys over. grid_* was superseded by the on-demand /img/<fmt>/<w>/ resizer; nothing on this platform generates an og:image at all (SeoMeta.og_image is a URL the merchant supplies). Both pairs are removed.
- New Settings → General → Images: image shape (square / portrait / tall / landscape / wide / original), how images fill the frame (cover / contain), image quality (40-100, was hardcoded 82/60/85 per format), and an off-by-default crop that bakes the shape into the stored variant.
- One resolver, core/images.py, read by the dashboard, all three themes and the variant pipeline, so they cannot drift on what shape an image is. It reads the catalog plugin's config by name — the same inversion core/agents/guardrails.py uses — so neither shell imports the other's plugin.
- The {% image_frame_style %} tag emits nothing until a merchant actually chooses, so an existing storefront is never reshaped on deploy: dot_books keeps its portrait frames, and the dashboard falls back to square, which is the fix.

## v0.70.3 — 2026-09-21

**Error pages asked to be indexed**

- The 404 template resolved as an ordinary static page, so the head document emitted 'index, follow' on every error page of every theme. Removing montenegro's hand-written noindex in v0.70.2 exposed it: what had looked like a duplicate-directive bug was a theme papering over a resolver gap. resolve_page now recognises Django's documented 404 context ({request_path, exception}) and returns a private page with 'noindex, follow' — noindex because the page is not worth indexing, follow because its nav is the same nav as everywhere else.

## v0.70.2 — 2026-09-21

**404 emitted two robots directives; the contract guard now checks every theme that signs it**

- The montenegro 404 carried its own <meta name="robots" content="noindex"> next to the one the head document emits for a KIND_PRIVATE page — two directives for one URL, which is precisely what head_contract = 1 exists to prevent.
- It survived because HeadContractTests renders only the ACTIVE theme, and CI runs with dot_books. A second theme could sign the contract and never be looked at. themes/test_head_contract.py now also scans every theme declaring head_contract for tags the head document owns, with no request cycle — Django comments are stripped first (a comment may legitimately quote the markup it warns about) and AMP templates are exempt, since the AMP spec requires each to carry its own canonical.

## v0.70.1 — 2026-09-21

**FAQPage reads the article's own labelled FAQ section**

- The H2-only reader found FAQ content on 1 of 34 live journal articles — while 33 of them end in a literal 'Frequently Asked Questions' H2 whose H3s are the questions and the paragraphs beneath are the answers. That section is the article declaring its own FAQ, which is also exactly what Google requires (the Q&A must be visible on the page in that form). Serbian headings recognised too. The question-shaped-H2 reader stays as the fallback; neither ever converts a noun-phrase heading into a Question.

## v0.70.0 — 2026-09-21

**Montenegro SEO/AEO audit: hreflang, /categories/, llms.txt and journal markup**

- hreflang x-default named whichever page emitted it, so / declared / the default and /sr/ declared /sr/ — two contradictory claims per cluster, which is the same as none. It now names the LANGUAGE_CODE tree.
- /categories/ 301'd unconditionally to /genres/, a route only the optional book_product app mounts, while the sitemap advertised it — so every store published a sitemap URL that redirects, and a non-book store redirected into a 404. The shell's own category index is restored (both themes already shipped the orphaned template), and the sitemap entry moved to its owner.
- llms.txt emitted 45 double-slash URLs (a missing rstrip the agents.md renderer already had) and opened a '## Products' heading before checking for rows — telling AI crawlers the shop had no catalogue. New SEO_LLMS_SECTIONS filter: booking_marketplace now publishes its experiences and stays.
- Journal bodies authored as full documents repeat the title as their own <h1> plus a byline, both of which the template already renders; 19 live articles shipped two <h1> elements. Stripped at the journal_dict seam, so existing content is fixed without a re-seed.
- author.sameAs, citations and wordCount reached no live page: every theme passes them to {% seo_article_jsonld %}, which the head contract shims to ''. They are now read from the entry by the graph builder.
- FAQPage for journal articles, built only from H2 headings that are genuinely questions — converting every H2 would assert questions the page never asks.
- booking_marketplace stopped seeding placeholder Privacy/Terms pages that duplicated gdpr's; seed_cms_pages retires the existing rows to draft and seed_seo_redirects 301s their paths.

## v0.69.1 — 2026-09-21

**Broken product images now fall back cleanly, including the homepage hero**

- A product whose image file is missing now shows its title card everywhere, including the homepage hero — that one slipped through the previous release because it loads earlier than the rest of the page.

## v0.69.0 — 2026-09-21

**Product photos fill their frames, and Montenegro pages tell search engines the truth**

- Supernatural Shop: product images now fill their card instead of sitting at a third of the width with empty space beside them, and the fake book-spine shadow that was drawn over every photograph is gone.
- A product whose image file has gone missing now shows its title card rather than a broken-image icon.
- Montenegro: every page's title, canonical, robots and social-share tags now come from one place, so the shop finally publishes language alternates for its Serbian pages — search engines could not tell the two languages apart before.
- Montenegro: the homepage has a destinations strip; the code for it existed but no page had ever shown it.

## v0.68.7 — 2026-09-20

**CI is green again, and the Montenegro store's live SEO and Serbian defects are fixed**

- Fixed three different Montenegro pages sharing one browser-tab title and one search-result title: the experiences list, a category-filtered list and the Shop each have their own again.
- The Serbian listing heading and the Highlights section on an experience page now actually appear in Serbian; the heading's translation had been stranded by an English copy change.
- The journal seeding command no longer deletes store pages it was only ever meant to retire — it unpublishes them, so nothing a merchant wrote is destroyed.
- Developer-facing: the build's lint and test gates pass again after the Montenegro fold, and the booking app's 180 tests run in CI instead of erroring.

## v0.68.6 — 2026-09-18

**Your store's name, not ours**

- Every document an AI shopping agent reads to identify your store — the UCP, Trusted-Agent, MCP and plugin manifests — now carries your store name and contact address instead of the platform's. They previously introduced every shop as 'Morpheus' with a support address that does not exist and a terms link that 404s; the contact and logo are now omitted entirely when you have not set them.
- Apps whose inventory is not a catalog product (bookings, stays, tickets) can now add their own entries to the sitemap and the AI shopping feed, so a store built on them no longer advertises an empty catalogue to crawlers.
- Fixed the referral block on the account page, which could fail to render and take the whole block with it.

## v0.68.5 — 2026-09-17

**Real covers in the shop window**

- The homepage slider now features only books with real cover artwork. The 752 classics carrying an auto-generated typographic cover keep it on their product cards and still sell normally — they just no longer lead the front page.
- Bigger type in the slider's left column, so the copy reaches across the page instead of leaving a channel of empty paper beside it.
- Slightly wider page margins throughout.

## v0.68.4 — 2026-09-17

**The book fills the shop window**

- The featured book now runs the full height of the homepage slider, flush to the right margin, with a proper drop shadow — it used to float mid-page at a third of the height.
- The slider is half as tall (1334px to 663px), so the shelf below it is visible on landing. A single 120-character book title had been setting the height for all four books.
- Long titles now step down the type scale instead of running to nine lines; the copy and the book share the same top and bottom edge.

## v0.68.3 — 2026-09-16

**The nightly SEO scan runs again**

- The daily SEO scan has failed on every run since 1 June: it looked for a description column that content pages have never had, so the scan died before it could check a single page. It now completes and finds 8 pages that need a description.
- Products are no longer reported as missing an Open Graph title — a blank one renders from the page title, so there was nothing to fix. That rule alone was 648 of 861 products of phantom SEO debt.
- A description saved in the SEO panel now counts: a product or page described there is no longer reported as missing one.

## v0.68.2 — 2026-09-15

**Linda follows orders to their products**

- Fixed: when Linda looked at the products in an order, she often could not find them, because order lines use each variant's SKU. She now finds the product from either SKU, and order details include each line's product.

## v0.68.1 — 2026-09-15

**Linda's longer answers are no longer lost**

- Fixed: after about ten steps of work, or every tenth message in a conversation, Linda could finish her answer but show "I couldn't put an answer together" instead. Her answer now always arrives.

## v0.68.0 — 2026-09-15

**See Linda work**

- While Linda works you now see what she is doing: each store lookup or change appears in the chat as it happens, with a running "Linda is working" timer.
- Linda can take up to two minutes on a message by default (up to about three, in Settings → AI → Janus), so bigger questions finish instead of timing out.
- Long conversations stay quick and affordable: Linda no longer re-reads the whole history twice, and starts a fresh working session after a long pause or many messages, with a short recap.
- Each reply now records the AI tokens it used, so the conversation cost panel shows Linda's spend and the daily spend cap in Agent guardrails includes it.
- Sales summaries now state the currency instead of guessing it.

## v0.67.0 — 2026-09-15

**Linda can do the job**

- Linda can now reach the store tools merchants actually ask about — stock and restocking, SEO checks, order fulfilment and shipping, product edits, returns, promotions, reviews, apps and more — in every mode. Sales, Support and Operations modes were limited to a single tool before.
- Every change Linda makes now waits for your own yes in the chat, including changes that previously ran without asking. Saying yes once is enough; she no longer asks twice.
- Linda answers faster: she thinks at a quicker level by default (Settings → AI → Janus → How hard Linda thinks), no longer carries dozens of unrelated built-in skills, and no longer browses platform internals looking for tools.
- Clearer answers: Linda leads with the answer, stops naming internal tools, and says plainly when something took too long instead of reporting an AI provider error.
- Fixed: store settings and app descriptions could not be read; tool discovery failed while the cache was down; external MCP clients were refused by a security check since v0.64.0.

## v0.66.1 — 2026-09-15

**Deleted notes are fully forgotten**

- Deleting a note on Settings → AI → Janus now also removes it from Linda's memory journal, so she can no longer recall it.
- Linda's notes about one team member are no longer written to the store-wide memory journal, where colleagues' conversations could find them.

## v0.66.0 — 2026-09-15

**Linda keeps what she learns**

- What Linda learns while she works — notes about the store, notes about each team member, skills she writes and lessons from past work — is now kept in the store's database and used in every conversation. It survives redeploys on any host, with no disk volume or Coolify storage needed.
- Settings → AI → Janus has a new switch, "Linda keeps what she learns", and a "What Linda has learned" card where you can review and delete any note, skill or lessons. Each team member sees only Linda's notes about themselves. Deletions are recorded in the audit log.
- Learned notes can guide Linda but never approve anything: every store change still needs your own yes in the chat. Skills she writes are scanned before they are saved.
- Linda saves memories only through her engine's own memory now; the separate memory.remember and memory.forget tools are no longer offered to her. Existing remembered facts still reach her.
- The Janus settings page no longer shows its breadcrumb twice.

## v0.65.0 — 2026-09-14

**Janus settings page, and Linda runs only on Janus**

- New page: Settings → AI → Janus. Turn Linda on or off, use the store's AI provider or pin one just for Linda, cap tool steps and the time per message, add standing instructions, switch the built-in store skills on or off, and run a connection test. Changes are recorded in the audit log.
- Linda now runs only on Janus. The old built-in assistant loop is gone, along with its fallback and the LINDA_ENGINE and LINDA_MCP_TOKEN settings.
- Removed Linda's self-coding features: the Self-development page, code proposals and their review, and the weekly tool-drafting job. The staged-changes inbox is unchanged.
- Removed old API endpoints: /api/agent-tools/openai.json, /api/agent-tools/anthropic.json, /api/mcp/tools/list, /api/mcp/tools/call, and /dashboard/assistant/invoke/. Use the MCP servers under /mcp/ instead; see MIGRATING.md.

## v0.64.1 — 2026-09-14

**Linda answers again**

- Fixed: every Linda message failed with a permission error since v0.63.0. Linda kept her working files inside the app folder, which the server can't write to. They now live in a private temporary folder, or wherever LINDA_JANUS_HOME points.
- Linda now stops after 8 tool steps per message and answers, instead of exploring until the 55-second limit cut her off.

## v0.64.0 — 2026-09-14

**Linda can use the store's tools again, with your approval on every change**

- Linda's Janus engine can now read and act on the store. Each chat turn carries a short-lived signed identity for the staff member and conversation, so the store's tool server knows who is asking.
- Every change Linda proposes still needs your own yes in the chat. Approval is bound to the exact change, works once, and 'no' or 'but not that one' always wins.
- Fixed: a request that already contained an approving word, such as 'set the price to 20, ok?', could approve its own retry before you ever saw the proposal. Approval now only counts from a message you send after Linda asks.
- The Sales, Support and Operations modes now run on Janus too, and still limit which tools Linda can see and use.
- Every change Linda attempts, allowed or refused, is recorded in the audit log under your name.
- Linda stops starting new turns once the daily run or spend limit in Agent guardrails is reached.
- Removed the static Linda MCP token setting; nothing replaces it and nothing needs configuring.
- Linda's first reply no longer starts with a Janus security-scanner warning, and Janus reaches the store's tools inside the server instead of through the public internet.

## v0.63.1 — 2026-09-13

**Linda on Janus: store-only tools, working follow-ups, correct provider**

- Janus turns are restricted to the store's tools and skills. Before this, every turn loaded Janus's default toolset — shell, file writes, code execution, browser — running as the user that owns the app.
- Follow-up messages work. Janus's continue flag only resumed sessions tagged for its own CLI, so every second message in a conversation failed; turns now resume by stored session id and start fresh if that session is gone.
- Janus uses the store's configured AI provider and model. It previously guessed from environment keys, sent turns to OpenRouter with the wrong key, and never saw a key saved in the dashboard.
- Janus is installed with its MCP client, without which it had no store tools at all; the image build now fails if that client is missing.
- Replies are clean text (quiet mode), and Janus always runs in the conversation's own home so it never picks up an engine checkout's developer instructions.

## v0.63.0 — 2026-09-13

**Janus is the store agent; Linda is brand**

- Janus Agent is always installed from magnetoid/janus@main and is the default store engine. Linda remains the merchant-facing name.
- Each conversation home loads bundled daily-ops skills: orders, catalog, content/SEO, and store operator.
- Tests still force the in-process loop. Restricted modes and YOLO stay fenced.

## v0.62.0 — 2026-09-11

**Linda's Janus subprocess engine, gated and opt-in**

- Linda can run her turn on an out-of-process Janus engine (LINDA_ENGINE=janus). Default stays 'legacy': a subprocess reaches its tools over MCP, so it bypasses the in-process scope/budget/deadline/consent stack and the write audit.
- The engine subprocess no longer inherits the platform environment — it gets an allowlist, so DATABASE_URL, SECRET_KEY and payment keys stay in the parent.
- Auto-approve (Janus yolo mode) is off unless LINDA_JANUS_AUTO_APPROVE is set; on, it would make core/safety.py's FORBIDDEN_PATHS unenforceable for that process.
- A scope-restricted conversation mode (sales/support/ops) falls back to the in-process loop instead of silently receiving the wildcard tool palette.
- Fixed: inverted trailing-slash handling that broke every MCP tool call, a write-once config that pinned a rotated token, a hardcoded loopback port, discarded conversation history, a crash-after-partial-output reported as success, and a JSON envelope parsed from only the first 200 characters.
- Turn timeout now defaults to 55s (under GUNICORN_TIMEOUT) and failures emit a self-improvement signal. Janus image build pinned to a commit instead of @main.

## v0.61.3 — 2026-09-04

**Homepage hero: the book sits closer to its title**

- the gap between the copy and the cover is tightened, and both columns are content-sized so a short title no longer leaves a gulf across to a right-pinned cover
- on a phone the book leads again — v0.61.2's DOM reorder had pushed the cover below the dots

## v0.61.2 — 2026-09-03

**Homepage hero: the remembered editorial composition**

- copy on the left, one large cover on the right, dot navigation under the copy — the small-cover rail is gone
- the book title returns to display-xl as the dominant line (the "two big texts" arrangement), with "The book that moved this month." leading above it
- still no autoplay, no decode effect, no JS measurement — the constant-geometry panel stage is unchanged

## v0.61.1 — 2026-09-03

**Homepage hero: the original editorial opening returns**

- "The book that moved this month." — the shop's first hero headline — leads the bookshop window again as its single display headline
- the selected book's title is demoted to the first hero's serif italic line, so two headlines never compete in one column
- the four-cover shelf, no-autoplay behaviour and geometry-not-measurement layout of v0.51.0 are unchanged

## v0.61.0 — 2026-09-03

**Outbound SSRF gate for server-initiated fetches**

- SECURITY: webhook delivery POSTed to a stored endpoint URL with no SSRF guard and no validation at creation. A staff user — or any agent holding system.write — could register a webhook pointing at http://169.254.169.254/ (cloud instance credentials) or an internal admin port, and Morpheus would POST event payloads to it from inside the network, with retries. Both sinks (webhooks_ui delivery and core.tasks) are now gated.
- The SSRF check is promoted to core/net.py as a reusable seam and catalog now delegates to it instead of keeping its own copy — two copies of a security check drift, and the looser copy becomes the hole. It resolves the host and requires EVERY returned address to be public; literal metadata IPs are blocked belt-and-braces.
- A transient DNS failure is deliberately distinguished from an unsafe host (UnresolvableHostError, a subclass so plain catches still work). Conflating them would let a brief resolver outage permanently fail every queued webhook instead of retrying it; allowing the retry concedes nothing, since an unresolvable host cannot be connected to and the full check reruns if it starts resolving. The catalog download path stays strict via a non-raising wrapper — a one-shot synchronous agent fetch should fail fast, not retry.
- Known limit, stated in the module: getaddrinfo resolves, then requests resolves again on connect, so DNS rebinding (TOCTOU) remains theoretically open — closing it needs a pinned-IP transport adapter. What is guaranteed is that a host resolving unsafe at check time is refused.

## v0.60.0 — 2026-09-02

**GraphQL wired to the RBAC capability seam**

- has_scope() granted on is_staff alone, so a role revoked in the dashboard still had full GraphQL access — the surface consulted core/authz.py nowhere. Session-authenticated staff now route through a scope-to-capability map (admin:seo -> seo.write, read:orders -> orders.read, ...), which is what finally makes a dashboard role change reach the API. This closes the deferred 'eight divergent GraphQL auth patterns' item from the API audit.
- Three deliberate safety properties. check() is used, never has_capability(): check() is mode-aware, so under the default 'log' mode a failed check still returns True while recording the would-be denial — this changes NO behaviour today and starts denying only when a merchant flips enforcement (has_capability would have denied immediately, i.e. a lockout). An unmapped scope keeps the previous is_staff fallback, so adding a resolver can never accidentally deny. Bearer tokens are untouched — a token is judged by its own scopes; vendor:self is deliberately unmapped because it describes a customer-owned relation, not a staff capability.

## v0.59.0 — 2026-09-02

**System-wide RBAC capability coverage (roadmap Milestone 1.2)**

- Capability coverage expands from 43 to 250 gated views (~13% to ~77% of the staff surface) across 64 files — the roadmap's Phase 1 milestone, and the prerequisite its own risk-mitigation section names for scoping external AI access. NOTHING DENIES YET: enforcement_mode stays 'log', which records what would be denied without denying it, and is what makes a sweep this size safe to land at once.
- marketing.read / marketing.write added to the admin + marketing_manager role templates in the SAME change as the views that demand them. This is mandatory, not cosmetic: a capability no role can hold denies EVERYONE once enforcement flips. Guarded by core/tests/test_authz.py::CapabilityVocabularyTests, which passes on all 250.
- Two corrections made mid-sweep. (1) Classifying read-vs-write by view NAME under-gated 65 mutating views behind a .read capability — e.g. tax/dashboard.py:regions, a POST-handling dispatch view; re-scanned by actual POST handling and upgraded 54 to .write. (2) seo/views.py already uses a BETTER pattern — page gated on .read, enforce(request, '<domain>.write') inside the POST branch, so a reader can open the page but not mutate it. Those 13 views were detected and deliberately left alone rather than flattened into the cruder page-level gate.
- Before flipping enforcement_mode to 'enforce' (a separate, deliberate decision): superusers bypass and the seam falls back to is_staff when rbac is absent, so exposure is narrow but real — staff who are not superusers and hold no RoleBinding would be denied. Provision bindings, then confirm a week of 'would deny (log-only)' warnings is empty.

## v0.58.0 — 2026-08-21

**GraphQL cache correctness + agent scope semantics**

- Response-cache correctness: the cache key now folds in the per-visitor vary axes (market, display currency, language) — an anonymous EUR or /fr/ visitor's response could previously be replayed to the next USD/en guest for the full 5-minute TTL. The 'cart' substring guard is replaced by a parse-based, deny-by-default allowlist of public catalog root fields, which inherently excludes mutations, introspection, the cart family, scope-gated CMS/SEO fields, and anything added later.
- The GraphQL cache middleware now runs BELOW the rate limiters, so a cache HIT is still metered (it previously short-circuited the limiter). Invalidation binds PRODUCT_CREATED / COLLECTION_UPDATED / PRODUCT_OUT_OF_STOCK / PRODUCT_LOW_STOCK in addition to the original two, so a new product, a collection edit, or a stock-out no longer leaves a stale list until the TTL lapses.
- SECURITY — agent scope semantics are now ALL, not any. A tool declaring two scopes means both; the MCP edge passed on ONE match, so a token holding just system.write could invoke the self-coding tools (code.apply_proposal, scopes=['system.write','selfdev']) WITHOUT the selfdev scope that gates them. Now aligned with the in-process runtime and Tool's own docstring.
- semanticSearch cost guard: the field is public storefront search and each miss computes an embedding, so an unauthenticated caller could drive provider spend at request rate. The expensive path is now budgeted per client and degrades to keyword search — no embed call, no spend, no error.

## v0.57.0 — 2026-08-21

**MCP + GraphQL robustness (arg validation, discovery metering, product-list N+1)**

- MCP tool-argument validation: a dependency-free JSON-Schema-subset check (required/type/enum/min-max/length) now runs before Tool.invoke and returns -32602. Invoke silently drops args the handler doesn't name, so an out-of-range or wrong-typed value used to reach the ORM as a default-valued 'success'.
- MCP discovery metering: initialize/tools/list/resources/list/ping now go through a per-token-or-IP rate limit (240/min) — they previously ran a DB query on every call with no cap (free admin-tool enumeration + DB-amplification).
- Product-list N+1: ProductType.collections/price/priceStartsFrom filtered already-prefetched relations with .filter()/.count(), discarding the prefetch cache and re-querying per product. Now Python-filter over .all() (identical semantics). Guarded by an assertNumQueries-style flat-count test.

## v0.56.0 — 2026-08-21

**Cart-mutation IDOR fix + GraphQL query hardening**

- SECURITY (cart IDOR): every cart mutation looked a cart/item up by caller-supplied id and mutated it with NO ownership check — any anonymous caller could empty, re-price, strip the gift card off, or check out any cart whose id they named. One ownership seam (orders/graphql/_ownership.py) now gates all eight mutations, the cart query, and shipping's shippingRates: a non-owning session gets the same NOT_FOUND as a missing cart (no enumeration oracle) and the cart is left untouched; read:carts tokens remain the agent escape hatch.
- addToCart now IGNORES the caller-supplied session_key (it let anyone add to — and read back — another visitor's cart); the session is derived from the request cookie, minting one when absent so anonymous carts get a real owner. CartType.sessionKey returns '' (was the session-hijack primitive). Both fields kept for API stability, deprecated.
- orders(order_by:) whitelists the sort key (a raw string reached .order_by() → FieldError 500 / relation-span leak); journalEntries(limit:) capped at 100 (was uncapped).

## v0.55.0 — 2026-08-21

**MCP + GraphQL authorization hardening**

- Agent-tool ownership: deleted duplicate agent_core tools that let plugin load order decide the winner — inventory.adjust_stock resolved to an UNGATED twin, so the approval gate silently never fired on stock writes. register_tool is now first-owner-wins and refuses cross-plugin duplicates. Orders owns analytics.summary/top_products; the analytics rollup pair renamed to analytics.traffic_summary/top_viewed_products. inventory.set_stock gained approval parity.
- MCP scopes fail closed: the token dashboard no longer wipes other tokens' scopes/approvals on save (a create/revoke used to silently promote every token to wildcard); a malformed scope value denies instead of reading as wildcard; bearer resolution stashes deny-first. 22 tool scopes missing from the vocabulary (incl. system.write → plugins.enable/disable) are added so tokens can actually be scoped. The merchant kill switch now reaches the MCP write path.
- GraphQL authorization: a Bearer token resolved to a shared is_staff service user, so any valid token passed EVERY scope (admin:seo, read:orders, …); has_scope now authorizes a token against its own scope set. Fixed vendor-financials IDOR on myVendorOrders/myVendorPayouts and a metricSeries filter that leaked all channels.
- Cache + price: the invalidation guard tested dead code (api/cache.py, never wired) instead of the real writer — repointed and deleted the dead file. Variant price and the agent product feed now pass through the price seam like the PDP + checkout (displayed=charged).
- Repo is public; pre-existing bandit B310 false-positives in the update system marked (https already enforced).

## v0.54.1 — 2026-08-21

**SEO title patterns now actually apply on live product pages**

- Fix: the SeoTemplate token reader read model fields unguarded; on the PDP (loaded with .only()) a deferred djmoney column raises KeyError through getattr's default, and the fail-soft wrapper turned that into 'pattern silently absent' on every live product page — the v0.46/v0.49 deferred-field landmine, third bite.
- Token reads now skip deferred columns outright and guard each read; a broken column costs one empty token, never the render. Regression test loads the product with .only() the way the live view does.
- The apply_templates fail-soft now logs (debug) instead of swallowing silently.

## v0.54.0 — 2026-08-20

**SEO templates: one pattern titles every page of a kind**

- New Dashboard -> SEO -> Templates: write one pattern - {name} - buy online | {site_name} - and it titles every product (or category page, journal post, CMS page) at render time. Nothing is written onto rows, so editing the pattern re-titles everything it covers on the next page load, and deleting it puts the old titles straight back. That render-time design also made a 'bulk apply' step unnecessary.
- Precedence keeps the v0.47 lesson honest: a title the merchant typed always beats a fill-empty-fields pattern - and a pattern beats the autofill guess the platform mints for every product, which is exactly the class of value the lesson says must lose to a human decision. 'Override everything' mode is the deliberate inversion, for re-branding titles typed before the pattern existed.
- Grammar, kept small: {tokens} from the page's fields and metafields plus {site_name}/{sep}; alternatives {author|"Anonymous"}; filters truncate:N/title/lower/upper; and bracket blocks [ by {author}] that vanish whole when nothing inside resolves, so separators never dangle. A pattern in which no token resolves declines entirely rather than publishing boilerplate. Patterns can be scoped to one category by slug; scoped beats global.
- The engine resolves the PDP's GraphQL dict as well as ORM objects (the surface that matters most), fires SEO_TEMPLATE_TOKENS so apps can contribute their own vocabulary (the event finally has its producer), and compiles to a cache invalidated on save - including the dashboard's own edit path, which uses update() and therefore drops the cache by hand.

## v0.53.0 — 2026-08-20

**Full-screen feedback capture with console log; plugin routes resolve before discovery**

- Feedback reports now tell the whole story: the screen-capture picker preselects the entire screen instead of the current tab (you can still choose a window or tab), and each ticket carries the last 50 console lines alongside the JS errors, server errors, page, browser and version. The console buffer lives in core's error-capture script, which runs in the page head - so a ticket includes chatter from before the feedback modal ever loaded.
- Plugin URL mounts now resolve most-specific-prefix first, making the dashboard's app-discovery router the fallback it was meant to be. Before this, anything a plugin mounted one segment deep under dashboard/apps/<name>/ was silently swallowed by the discovery route - bookvault's Connect and Disconnect buttons have been dead since they shipped, with every test green. They work again. One intended flip: a plugin's own settings/ route now beats the legacy plugin-settings redirect that shadowed it.
- Also: the README says plainly that the repository is private and how to ask for access, so its opening git clone no longer fails silently for readers; and the bookvault contribution tests no longer assert exclusive ownership of the shared product-list-columns accumulator (they broke the day seo's score column shipped and CI's billing outage hid it).

## v0.52.4 — 2026-08-20

**Refactor pass over v0.51-v0.52.3: one owner per mechanism**

- Four-angle review (reuse / simplification / efficiency / altitude) of everything shipped since v0.51.0, applied: 17 mechanisms consolidated.
- One owner of recent client errors: core's error-capture.js now retains its shipped payloads in window.morphClientErrors (same dedup, same cap), and the feedback modal reads that instead of running a second listener pipeline - tickets now also include errors fired before the modal's own script loaded, and their entries match what /api/errors/client/ ingested.
- Feedback queue uses the shared dashboard machinery it sat next to: paginate_and_sort (page links keep an active ?status= filter, the per-page selector works, the footer hides on single pages), the index_tabs strip with per-status counts, dashboard_trail (restores the root crumb and fixes a detail-page crumb that pointed at a URL that does not exist), Morph.csrf, core_version, and {% url %} instead of a hardcoded path.
- Dashboard sticky bars are one .dash-sticky-bar class instead of three inline copies, and the pinned header now consumes --dash-topbar-h - the token and the bar height can no longer drift apart.
- Theme geometry moved to the theme: dot_books declares its measured 158px PDP chrome on its own :root; product_gallery only reads the variable. The old escape hatch was unusable - the plugin's element-scoped declaration would have beaten any theme override. Also: .sr-only is a theme-base utility now, hero thumbnails stop requesting an image width the pipeline never serves, and a handful of dead CSS/guards from the hero rewrite are gone.

## v0.52.3 — 2026-08-20

**Sticky offset only where the scrollport is the window**

- Fixes a regression from v0.52.2: dashboard table rows were invisible. Table headers live inside .card.overflow-hidden, which :has(table.morph-table) gives overflow-x:auto - that makes the CARD the sticky scrollport, not the window, so offsetting them by the topbar height pushed each header 48px down inside its own card and straight over the first row (measured: card top 219, row top 258, header top 267). The Feedback queue showed 'Showing 1-1 of 1' with no visible row.
- The rule: only sticky elements whose scrollport is the window take the topbar offset. Table headers and the variant modal's media column are back to top:0; the page-level filter bars on products, orders and customers keep var(--dash-topbar-h), verified by walking each element's ancestors to find its real scrollport.

## v0.52.2 — 2026-08-20

**Dashboard top bar stays put; sticky elements work again**

- The dashboard top bar no longer scrolls away. <body> is min-h-screen flex, so nothing bounds <main>'s height and the window is the real scroller - the sidebar is fixed and stayed put while the header had no positioning at all and scrolled off, taking search, notifications and the account menu with it.
- Every position:sticky element inside the dashboard content was silently dead. <main> carried overflow-y-auto but never actually scrolled (measured scrollHeight == clientHeight), which made it the scrollport for its sticky descendants - a scrollport that never moves. Table headers and the products/orders/customers/product-form filter bars therefore stuck to nothing. Removing that one class makes all five work.
- Sticky offsets now key off a shared --dash-topbar-h token instead of each hardcoding top:0, so they park under the pinned bar rather than sliding beneath it.

## v0.52.1 — 2026-08-20

**Product gallery: reserve the real chrome above it**

- Follow-up to v0.52.0: the gallery cap reserved only the sticky topbar (65px), but the gallery actually starts 158px down the page (topbar + section padding + breadcrumb), so it still overflowed by 77px and the thumbnail strip stayed clipped. Reserving the measured offset fits it: 412x726, thumbnails visible, 16px clear at 1440x900.

## v0.52.0 — 2026-08-20

**Feedback tickets, and the product gallery fits the screen**

- New Feedback app: a 'Send feedback' entry in the dashboard account menu opens a modal that takes your message, offers to capture the screen, and attaches the JavaScript errors the page already logged. Each report becomes a ticket under Settings -> Feedback with the page, viewport, browser, version and request id alongside it.
- Screen capture uses the browser's native getDisplayMedia, so it adds no dependencies. It is best-effort by design and the ticket records WHY an image is missing (declined / unsupported / too large / failed) - a report that quietly lost its screenshot would otherwise look identical to one where sharing was refused.
- Two new shell contribution points: DASHBOARD_USER_MENU (account-dropdown entries) and DASHBOARD_BODY_END (templates at the end of the dashboard body - the shell's equivalent of the storefront's global_below_body slot). Both are hook-gated, so a contributed entry or modal disappears when its app is disabled.
- Product page: the gallery no longer runs off the bottom of the screen. The slide is aspect-ratio 2/3, so its height came entirely from the column width and nothing bounded it against the viewport - at 1440x900 the cover rendered 763px tall and the thumbnail strip fell below the fold. The width is now capped so the cover plus its thumbnails fit one screen (871px -> 819px at that size).

## v0.51.0 — 2026-08-20

**Homepage hero rebuilt as the bookshop window**

- The homepage hero is rebuilt: one book stands face-out and still, and the other editor's picks stand beside it on a hairline shelf as real covers instead of four anonymous dots — every featured book is now visible on landing and one click away.
- Removed the per-letter decode scramble. It rendered the hero's headline AND the book title as coloured gibberish for about a second on load and again on every 5.6s auto-advance, so the shop's front page was illegible a meaningful share of the time.
- Removed the auto-advance timer and the second competing display headline. Motion is now one crossfade plus a short staggered rise; the slider only moves when a shopper asks it to.
- The hero no longer fills the viewport: 835px to 733px at a 900px viewport, so 102px of the shelf below is visible on landing instead of nothing.
- Deleted the machinery the scramble needed to look stable: the JS title fitter, the reserved tallest-title box, contain:layout, the top-anchored grid and the :has() sale-row collapse. The copy is a constant-height stage with centred panels, so the shelf never moves between books and no JS measures anything. Hero section 774 lines to 403; its script 250 lines to 45.
- The homepage now has an h1. It had none at all — the marketing sentence that was removed had been the page's top heading.
- Hero covers are wired into the theme's shared spine/edge-light and missing-cover title-page treatments rather than carrying their own copies.

## v0.50.0 — 2026-08-19

**You decide which URLs of your shop belong in search**

- Page numbers that do not exist now say so. /products/?page=999 answered with your first page of products while telling Google it WAS page 999 — so every number anyone appended became another copy of your shop, competing with itself and spending the crawl budget meant for your products. Out-of-range page numbers now return 'not found', and ?page=1 sends visitors to the clean address instead of serving a second copy of page one.
- Every page of a listing used to carry the same title. Page 2 onwards now has its own, so a search result can tell them apart — and so can a shopper reading the tab.
- New: Index rules, under SEO. One rule per link parameter — sorting, filters, campaign tags — saying whether it makes a real page, a page to keep out of search, a landing page for the values you choose, or an address crawlers should not visit at all. Paste any URL to see exactly what your store publishes for it and which rule decided.
- Filter pages no longer send search engines two contradictory instructions. A page you kept out of search also named your category page as its 'real' address, and the documented consequence is that the exclusion can carry across and take the category with it. A page you hold back is now its own address, and nothing else's.
- robots.txt is assembled from the apps that own each address. Your cart, checkout and sign-in pages are kept out of search by the storefront itself rather than by a list hardcoded in the SEO app, so an app you install can protect its own private pages without anyone editing another one.

## v0.49.1 — 2026-08-19

**Books sold in several editions keep their group markup**

- Fixes a v0.49.0 slip. A book listed in more than one edition carried its variant markup but described itself as a single product, because removing the duplicate book claim from the page erased the group type along with it. Google ignores variant properties on a plain product, so the editions were published and then discarded.

## v0.49.0 — 2026-08-19

**Products with variants are described as one item**

- A product sold in several versions — print and ebook, hardcover and paperback, several sizes — is now described to Google as one item with choices, each carrying its own price and its own real stock, instead of a single entry that mentioned none of them. This has been written and switched off since v0.30: the code was reachable only from a path your product pages never take.
- Products on sale now show their previous price, so search results can display the saving. It appears only when the compare-at price is genuinely higher than what you charge — a leftover compare-at price equal to the current one is not a sale and is not advertised as one.
- Fixed: a product page could lose its entire product markup. Reading a price field that the page had not loaded raised an error the markup builder swallowed, leaving the page valid but with nothing in it describing the product. Money fields are read defensively now, and there is a test for it.

## v0.48.1 — 2026-08-19

**Availability: untracked stock is not zero stock**

- Fixes a regression in v0.48.0. A shop that does not track inventory has no stock records at all, and the new availability check read that emptiness as 'none left' — so every product page declared the item out of stock while its add-to-cart button worked normally. A product is only out of stock when its stock is actually counted and has run out; products with inventory tracking switched off, and variants nobody counts, are purchasable as before.

## v0.48.0 — 2026-08-19

**Product markup states only what is true**

- Every product page was advertising free shipping. The shipping and return policy in your product markup was assembled by the SEO app from settings that no screen ever wrote — so every store published the same invented policy, and because the free-shipping threshold defaulted to a value that read as 'yes', every product claimed free delivery whatever your shipping rates said. Both now come from the apps that hold the data, and are simply left out when you have not configured them.
- Out-of-stock products were telling Google they were in stock. The stock check ran on a code path the product page never took, so the markup said 'in stock' for the whole catalogue. Availability now comes from your real inventory — including backorders — and matches what your channel feeds send.
- Star ratings counted reviews the page does not show. The rating aggregate included unapproved reviews while the review snippets filtered them out, so a product could advertise a rating built partly from reviews nobody can read.
- Product pages carry their full markup again. The page renders through GraphQL, and the markup builder skipped everything only the database can supply — so ISBN/GTIN identifiers, the image gallery, ratings, reviews and the book details were missing from every product page, and the SKU was published empty.
- The product form now shows your real domain and edits the URL in place: one line reading https://your-store.com/products/your-slug, click the slug to change it. The separate slug box and the duplicated URL beneath it are gone.
- 'Include in the sitemap' works. The per-page control shipped last release without being connected to anything; the sitemap now honours it, and pages you have set to noindex are kept out automatically rather than being submitted for crawling and then discarded.

## v0.47.0 — 2026-08-19

**Per-entity SEO has one owner and one editor; redirects that actually hold**

- One SEO editor everywhere. Products, categories, collections and journal pages now share the same panel — live Google and social previews, character counters, canonical, indexing, snippet controls — contributed into each form by the SEO app, so it disappears cleanly when the app is off. The product form's separate 13-field SEO block is retired.
- What you type is what ships. A meta title typed into the product form used to be saved and then ignored: the platform autofills an SEO record from the product's name, and that outranked the field you filled in. A value a human typed now wins over one the platform guessed.
- Product pages finally say they are products. Every product page declared og:type=website, so Facebook, LinkedIn and Pinterest rendered share cards for a generic page instead of an item with a price. Run 'manage.py seo_backfill_meta' to correct existing records.
- Redirects grew up: prefix rules that move a whole branch, pattern rules, 410 Gone for pages removed for good, CSV import and export, automatic chain collapsing, and a cached resolver. Renaming a product now keeps its old URL alive with a 301 automatically, so a rename stops costing you the page.
- Three redirect bugs fixed: a rule could point off-site (an open redirect), a rule stored as /old/ never fired for visitors browsing in another language, and the query string was dropped on the way through — breaking campaign attribution for every link ever shared.
- Cloudflare was purging URLs this platform does not serve, so product and category pages had effectively never been dropped from the edge. Meta edits, redirects and sitemap regenerations now request a purge too.
- The SEO dashboard checks permissions. Every page needs 'seo.read' and every change needs 'seo.write' (enforcement stays off until you turn it on). The 404 monitor no longer writes to the database when you merely look at it, and Redirects finally has a sidebar entry.
- The 'auto-noindex thin product pages' setting works again — it had had no effect since v0.46 — and each page can now set its own snippet and image-preview limits, which is what governs how much of it AI Overviews may reproduce.

## v0.46.0 — 2026-08-18

**SEO 3.0 phase 1 — the storefront head is a core contract**

- The <head> is now built by core and filled in by the SEO app, not by the theme: a theme calls {% storefront_head %} once and gets title, description, canonical, robots, Open Graph, Twitter, hreflang (language and market), pagination links, verification metas, discovery links and one JSON-LD @graph — on any page, in any theme (ADR 0036).
- Fixes found by diffing the old output against the new: /search/ rendered with NO <title> at all; the product page emitted og:type twice; WebSite and CollectionPage JSON-LD were emitted twice on most pages; category, collection and journal titles carried the shop name twice; the sitelinks SearchAction and Book ReadAction Google retired were still being emitted.
- The shop name is out of the templates and views (20 hardcoded suffixes removed) — it comes from settings, so two merchants can run the same theme. The bundled fallback storefront, which previously emitted a hardcoded title and no SEO at all, now gets the same head as a designed theme.
- robots.txt, sitemaps, llms.txt, agents.md, the feeds and /.well-known/security.txt are no longer language-prefixed (a multi-language store was publishing a second copy of every discovery file per language), and the IndexNow key route no longer shadows every other root-level .txt URL.
- Apps now contribute SEO instead of being imported by it: new STOREFRONT_HEAD, SEO_RESOLVE_PAGE, SEO_JSONLD_GRAPH, SEO_ENTITY_ADAPTERS, SEO_SITEMAP_SOURCES, SEO_ROBOTS_RULES, SEO_TEMPLATE_TOKENS and SEO_STRUCTURED_DATA_FOR_OBJECT events; catalog -> seo and seo -> catalog leave the boundary baseline (120 pairs).
- Guarded by a recorded head profile of 15 page types (seo/tests/test_head_parity.py) and a theme head-contract test (themes/test_head_contract.py), both mutation-tested; legacy {% seo_* %} tags still work and go silent on a migrated page — see docs/MIGRATING.md.

## v0.45.0 — 2026-08-16

**Paid memberships collect a card; every shell surface now vanishes with its plugin**

- feat(subscriptions): P4a part 2 — a paid **Stripe** plan is sold online at last. `/membership/subscribe/<plan>/` mounts a Stripe Payment Element on a SetupIntent (`usage=off_session`, the same flow the account 'saved cards' page runs live); Stripe returns to `…/confirm/`, which **verifies the caller-supplied SetupIntent** against Stripe (`succeeded` and *this* customer's vault — `StripeSubscriptionAdapter.payment_method_from_setup_intent`), creates the subscription, calls `start_subscription`, and **deletes the row if Stripe refuses** so a failed attempt never greets the shopper as a member. `invoice.paid`/`payment_failed` reconcile from there (existing subscribers, now with a producer). Free plans unchanged; a paid plan on any other provider is still refused honestly. 27 tests, four guards mutation-tested. **Not yet exercised against Stripe test mode** (no test keys here) — before enabling a paid plan for real, run one signup with a test card and confirm the webhook lands. No paid Stripe plan exists on dotbooks.store, so nothing changes there until one is created.
- fix(disable-safety): P6 interim — every remaining shell→optional-plugin read is gated on `app_registry.is_active()` (ADR 0013), so the surface disappears when the merchant toggles the plugin off instead of surviving behind a `try/except` that only ever guarded absence: storefront `catalog/content/home/vendor` (book_product ×9, metafields ×6, cms ×5, product_videos, crm, consent, marketplace) and dashboard `views_split/*` + `forms/*` (cloudflare ×7, cms ×8, marketing ×5, seo ×4, product_videos ×4, ai_assistant ×3, metafields ×3, draft_orders ×2, ai_content, analytics). Views that exist only for a plugin — coupons, theme builder, video CRUD, `orders/new`, email-template edit — return 404 while it is off. Two unguarded imports that would have 500'd if the plugin were uninstalled (`content.py` crm, `theme_builder.py` cms) are gated too. New `storefront/tests/test_disable_safety.py` + `admin_dashboard/tests/test_disable_safety.py` toggle each plugin, GET every shell page, and assert three surfaces per shell actually vanish; gates mutation-tested.
- fix(admin_dashboard): the email-template editor (`/dashboard/settings/email-templates/<key>/`) had 500'd since 2026-06-13 — its placeholder help wrote literal `{{ "{{ order.order_number }}" }}`, which the template lexer cuts at the first `}}` (TemplateSyntaxError). Now `{% verbatim %}`; the page is asserted 200.
- docs: CLAUDE.md — the interim disable-safety rule and a literal-braces landmine; boundary-debt plan marked interim; open-core plan P4a part 2 status + Stripe test-mode caveat.

## v0.44.0 — 2026-08-16

**Per-app / per-theme update channel; runtime toggles reach the live URL resolver**

- feat(updates): apps and themes installed on their own now update one at a time from the signed manifest (`core/component_updates.py`). Chain, fail-closed at every link: signed `sha256` required → artifact streamed + hashed over HTTPS with a size cap → every tar member inspected (no absolute paths, `..`, links, devices; exactly one top-level dir) → `tarfile` data filter → `app.py`/`theme.py` marker → app `migrations/__init__.py` present → rename swap → fresh-interpreter boot probe → migrate → check → rename-back on any failure; `restart_required` reported. Refuses anything that ships with core (`MORPHEUS_DEFAULT_APPS` / git-tracked) and `core/safety.py` protected paths; `min_core` gate; same `MORPHEUS_SELF_UPDATE_ENABLED` opt-in and dry-run default.
- feat(updates): `morph_check_updates` lists app/theme updates; `morph_apply_update --app NAME | --theme NAME`; `morph_sign_manifest --components FILE` signs `apps`/`themes` entries (validated: version, https artifact, 64-hex sha256). Dashboard Updates page: 'App & theme updates' card populated by the daily check / Check button, one-click apply. `SignedManifestSource.components()`; the GitHub source deliberately publishes none (transport-authenticated only). Every guard mutation-tested; verified end-to-end with a real fresh-interpreter boot probe.
- fix(plugins): runtime enable/disable never reached the live URL resolver — `_refresh_urlconf` rebuilt `plugins.urls`, which nothing has included since the ADR 0022 split into `plugins.chrome_urls` + `plugins.storefront_urls`; and `activate()` refreshed only on first wiring, *before* `_active.add`, so an enable never mounted URLs and a re-enable never remounted them. A disabled app's endpoints kept serving until restart; an enabled one 404'd. Now rebuilds the included modules in place after the active set changes, on every toggle. Guarded by `LiveResolverDisableTests` (asserts on the live resolver, not `get_urlpatterns()`).
- fix(seo,theme): dot_books' `<head>` hard-reversed `seo:journal_rss`/`journal_atom` — with seo disabled and the process restarted, that NoReverseMatch 500'd every storefront page. Feed autodiscovery is now a seo-owned `global_head` block that vanishes with the plugin. New `storefront/tests/test_disable_safety.py` toggles each optional plugin and asserts the storefront still answers.
- fix(versioning): `theme_versions()` called `theme_registry.active` — a property — so it raised inside its fail-soft guard and returned `[]` on every deployment: the Updates page said 'No themes discovered' and `morph_versions --json` (the stable contract) never listed a theme. The old test excused the empty list; it now asserts `dot_books` is present and exactly one theme is active. Theme discovery also skips dot-dirs so a mid-swap crash cannot register a phantom duplicate.
- rbac: `updates_apply` and `updates_apply_component` gated on `system.write`.
- docs: UPDATING.md rewritten to state precisely what is built and what is not (hosting still open); CLAUDE.md +2 landmines (URL-refresh-on-the-wrong-module, verify-the-bytes-not-just-the-manifest); PLUGIN_DEVELOPMENT 'shipping updates to installed copies'; roadmap reconciliation updated.

## v0.43.3 — 2026-08-12

**Signed release manifests (Ed25519)**

- core/signing.py adds Ed25519 signing and verification over a canonical JSON form, SignedManifestSource fetches and verifies a manifest before trusting a word of it, and manage.py morph_sign_manifest generates keys and signs releases on the publisher side. A signed manifest takes precedence over the GitHub source, because it proves the publisher produced the bytes — HTTPS only proves you reached a server.
- Verification fails CLOSED, deliberately the opposite of the authorization seam. An unsigned manifest, a bad signature, a wrong key, a missing public key or a non-HTTPS URL all cause the source to be ignored entirely. Running unverified code is worse than not updating; locking a merchant out of their dashboard is worse than a missed permission check. The two postures are opposite on purpose.
- cryptography is now a direct requirement rather than a pyjwt[crypto] transitive, since core imports it. The same keypair will serve the commercial edition's licence checks.
- Not built, and labelled as such in docs/UPDATING.md: hosting the manifest, verifying an artifact during apply, and per-app/theme channels. The apps and themes keys are emitted empty and clients read core only, so filling them later is backwards-compatible.

## v0.43.2 — 2026-08-12

**Update checks work without git; TLS verified against certifi**

- A deployment built as a container image has no .git, so the updater could not even ask whether an update existed — it reported 'unavailable' and stopped. core/update_sources.py adds a pluggable UpdateSource with a GitHub Releases implementation, and platform_update_status() falls back to it. Configure with MORPHEUS_UPDATE_REPO (owner/repo) and, while the repository is private, MORPHEUS_UPDATE_TOKEN. Check only — applying is unchanged and still gated by MORPHEUS_SELF_UPDATE_ENABLED.
- A private repository answers 404 to an anonymous client, which is indistinguishable from 'no releases yet'. That is reported as unknown with a reason, never as 'up to date' — telling a merchant they are current when we cannot see the releases is the worst thing an updater can do.
- TLS is verified against certifi's bundle when present. urllib uses the interpreter's default trust store, which is empty on a python.org macOS build, so every request failed with CERTIFICATE_VERIFY_FAILED and the source merely looked unreachable. Found by contract-testing against the live GitHub API; every mocked test had passed. Verification is never disabled.

## v0.43.1 — 2026-08-12

**Every test passes; a production cache bug fixed**

- The GraphQL response cache was never actually invalidated. api/cache.py keys entries graphql:query:<hash>, the invalidator deleted gql:*product*, and nothing has ever written that prefix — so a product edit invalidated zero keys and the API kept serving the old price and title until the TTL lapsed. Production only: dev and tests use LocMem, which has no delete_pattern and falls through to clearing everything, so development always looked correct.
- Fixed the six long-standing test failures. Four came from one test registering a real agent tool under a fake owner and then dropping that owner, which deleted the real catalog tool from the process-global registry for every later test. One posted a page slug that gdpr.0002 already seeds during migrate, so it asserted on collision handling while claiming to test creation. One asserted product ordering with body.index('One'), which matched the theme's own marketing copy 26,000 characters before the product grid — the ordering had always been correct.
- The full suite now runs clean: 2,621 tests, zero failures.

## v0.43.0 — 2026-08-11

**RBAC enforcement, phase 1 — capabilities are finally checked**

- Roles and capabilities have shipped since v0.x but nothing ever called has_capability(): all 83 dashboard views were gated on is_staff alone, so a support agent or content editor held the same power as the owner. Roles were labels with no effect.
- Adds the authorization seam core/authz.py. Core asks (AUTHZ_CAPABILITY_CHECK), the rbac app answers from role bindings — a direct dashboard->rbac import would be the plugin-to-plugin coupling the boundary ratchet blocks. Same inversion as the pricing seam.
- Enforcement is OPT-IN and defaults to log-only: every check runs and records what it WOULD have denied, then allows it. Settings -> Other apps -> Roles & permissions switches between off / log / enforce. Installing this changes nobody's access.
- The seam fails OPEN on absence: if rbac is missing or cannot answer, the check falls back to the historical is_staff behaviour. An authorization layer that failed closed when its own answerer is missing would lock every merchant out of their dashboard.
- Gated in this phase: order refunds and state changes, product/variant/image/video writes and deletes, customer/address/collection deletes (21 views). Read-only views and remaining settings surfaces still behave exactly as before.
- Superusers always pass, so you cannot lock yourself out. Staff with no role hold nothing — assign roles before switching to enforce.

## v0.42.0 — 2026-08-11

**Apps, not plugins: one vocabulary, one surface, one protected-app gate**

- BREAKING for out-of-tree app authors: the manifest file is now app.py (was plugin.py), the SDK door is morpheus.app (was morpheus.plugin), the registry singleton is app_registry (was plugin_registry), and the settings lists are MORPHEUS_DEFAULT_APPS / MORPHEUS_EXTRA_APPS. The MORPHEUS_EXTRA_PLUGINS env var is still read as a fallback, so existing deployments keep their extra apps.
- The merchant-facing word is Apps everywhere — page titles, subtitles, the settings category, empty states. plugins/installed/ and the MorpheusPlugin base class deliberately keep their names; moving the directory would rewrite ~2,000 imports and both CI boundary baselines.
- Fixed: a fresh Postgres install could not finish migrate. Reading plugin config swallowed a DatabaseError, which on Postgres leaves the whole transaction aborted, so Django's own write to django_migrations failed and the deploy stopped partway with 51 apps unmigrated. sqlite never reproduced it.
- Fixed: the AI could disable apps the merchant dashboard refuses. PROTECTED_PLUGINS existed twice with different contents — Linda's disable tools allowed catalog, orders, payments and morpheus_brain while the dashboard blocked them. One gate now; an app manifest can add protection but never remove it.
- Version & updates no longer repeats the whole app list as a second table; Installed and Browse are now two tabs on one Apps surface.

## v0.41.1 — 2026-08-11

**Five plugins' database tables were never created**

- brand_kit, lookbook, media_3d, rails and smart_shipping each shipped a migrations/ folder with no __init__.py, so Django never recognised it as a package and reported "no migrations" — their tables were never created on any real deployment. Local tests passed throughout because Django creates tables directly for apps it thinks have no migrations, so the gap only ever existed in production.
- Consequence: the design-token set a merchant configures had nowhere to be stored, and the new look page returned a server error instead of "not found". Adding the missing package markers makes all five sets of tables get created on the next deploy.
- The five initial migrations were regenerated rather than patched: since Django had never seen them, no installation had ever applied them, so a clean regeneration avoids a risky primary-key alteration on tables that do not exist. Verified against real PostgreSQL — all ten tables create cleanly.

## v0.41.0 — 2026-08-10

**Backend settings now reach the storefront; dead customer links fixed (P-wiring)**

- SECURITY-ADJACENT: maintenance mode did nothing. The Storefront settings panel has offered a maintenance switch with no consumer at all — a merchant could flip it and the shop stayed wide open. It now returns 503 with the merchant's message, while staff keep browsing and the dashboard, APIs, payment webhooks and health probes are never gated.
- Brand-kit design tokens never reached the browser. The token block shipped reading values nothing supplied, so every palette and typeface a merchant configured rendered as a hardcoded default on every page. A contributed context processor now feeds the active token set — and it vanishes cleanly when the plugin is disabled.
- Store identity is read from the row the merchant edits, not from environment variables: store name, logo and favicon now show on the storefront instead of being silently ignored. An unconfigured install is unchanged.
- Shelf prices could disagree with the product page. Dynamic and rule-based pricing was applied on the product page and at checkout but not on listing cards or the home page, so an active pricing rule quoted one price on the shelf and another at the till. All three now go through the same seam.
- Every customer who rated an order saw "link expired": the NPS thank-you route was shadowed by the token route, so the post-survey redirect resolved back into the survey view and failed signature verification.
- Fixed dead customer-facing links: the lookbook "See the full look" link 404'd because the page it advertised was never routed (now built), two collection links used a plural path that does not exist, and the theme's newsletter section posted to a non-existent URL.
- Newsletter signups become CRM leads again. The capture lived in a storefront view that a plugin route shadowed, so it never ran; it now travels on the event bus, where it works regardless of routing and stops cleanly when CRM is disabled.

## v0.40.0 — 2026-08-10

**Membership entitlement requires proof of payment (P4a part 1)**

- SECURITY/REVENUE: any logged-in customer could POST /membership/subscribe/ and become a member of a PAID plan without paying — the view created the subscription in an active state and never touched payment — then take that plan's member discount off every order, forever. Reported by the completeness audit; the endpoint was live.
- Entitlement no longer trusts the subscription's state string. A member perk now requires evidence the plan was actually paid for: the plan is free, a payment-provider subscription exists, or a paid invoice is on file. This also de-entitles any row already created the old way, with no data migration, and means the next code path that writes 'active' cannot silently reopen the hole.
- The signup view now refuses a paid plan outright instead of minting a membership that entitles nobody. Free plans still activate immediately. Online sign-up for paid plans returns with the Stripe billing flow.

## v0.39.0 — 2026-08-10

**Stranded stock reservations released (P3)**

- An order that was created but never paid held its stock reservation forever. A failed card only marks the payment transaction FAILED and an abandoned redirect leaves the order pending, so ORDER_CANCELLED — which is what releases the reservation — never fired. Available stock shrank with every abandoned checkout until a merchant looked oversold on stock they still had. orders/tasks.py was an empty file.
- A beat task now cancels unpaid pending orders past an expiry window, which fires ORDER_CANCELLED and lets the existing subscribers release the reservation and restore any gift-card or loyalty tender. The window is a merchant setting (Orders settings, default 60 minutes); 0 disables it.
- A paid-in-the-meantime order is re-checked under a row lock before cancelling, because the gap between selecting and cancelling is exactly where a late payment webhook lands.
- Web checkout now releases its Redis cart-hold once the database reservation takes over. Only the agent checkout path did this, so every completed web order double-held its stock until the hold's TTL lapsed.

## v0.38.0 — 2026-08-10

**Dead hooks wired: pricing seam, workflow triggers, payment.captured (P2)**

- PRODUCT_CALCULATE_PRICE now actually fires. It had two subscribers (AI dynamic pricing, merchant pricing Functions) and zero callers, so every pricing rule a merchant configured was silently inert. Fired on both the displayed price and the charged price through one guarded core helper, so the two cannot drift — a shopper can never be quoted one price and billed another.
- A broken, hostile, or careless pricing rule cannot break a product page or a cart-add: a non-Money return, a negative price, or a currency swap is logged and ignored, and the original price stands.
- Two workflow triggers pointed at events that do not exist (customer.created, agent.run_failed), so any workflow built on them was bound to a listener nothing ever fired. Renamed to customer.registered / agent.run.failed with a data migration that repoints existing workflows, and inventory.overstock_detected is now selectable.
- payment.captured is fired at capture by both Stripe and PayPal. It had subscribers — the merchant webhook fan-out and analytics — but no producer, so a merchant who configured a payment.captured webhook never received one.
- Removed the orders subscriber for payment.captured: the gateways already confirm the order directly, so it would have re-run a pending-only transition and raised on every already-confirmed order the moment the event started firing.

## v0.37.0 — 2026-08-10

**Storefront slot-render repair (P1)**

- Four contributed storefront slots had no render point anywhere, so eleven plugins' surfaces were invisible to customers: brand_kit's design tokens and motion's animation CSS never reached <head>; six plugins' checkout surfaces, media_3d's 3D/AR viewer, ugc_reviews' photo strip, and the referrals/returns_portal account panels all silently dropped.
- global_head now renders last in <head> (so tokens override theme defaults), checkout_extra renders in both the multi-step and one-page checkout, pdp_below_gallery renders with the product gallery, and account_summary_extra renders below the account tiles.
- Autopilot no longer provisions blocks into a slot the theme does not render: it defaulted to home_above_grid, which dot_books deliberately dropped, so every new store got an invisible merchandising block.
- New slot-render parity test reads the runtime registry (a source grep misses dynamics, which registers slots in a loop) and fails the build if any contributed slot has nowhere to render. Intentional exceptions are allow-listed with a stated reason and checked for staleness.

## v0.36.0 — 2026-08-10

**Agent-safety + money-correctness (P0)**

- Linda now runs the same enforcement stack as the Worker: scope, token budget, deadline, and a fail-closed approval gate. Her dangerous tools previously trusted an LLM-supplied confirmed=True argument, so content she merely read could induce a write; consent is now kernel-verified against the human's own reply, single-use and bound to the exact tool+arguments.
- Linda holds an explicit scope profile — a plugin-contributed tool demanding a scope she does not hold is refused instead of silently callable.
- Refused write attempts are audited, so a blocked injection leaves a trace outside the chat transcript.
- Gift-card and loyalty-point tender is re-credited on refunds and returns, prorated to the refund and idempotent per refund. Previously only a full order cancel restored it, so shoppers forfeited the tender on every partial refund.
- Stock reservation fails closed: a DatabaseError during reserve now aborts the order instead of being swallowed, which had let checkout proceed believing stock was held (silent oversell).
- The production model is priced, so the merchant's daily USD spend cap actually trips — it previously estimated $0.00 and could never fire.

## v0.35.1 — 2026-08-09

**Fix /shop/ 500 — reconcile booking_marketplace prod schema**

- booking_marketplace: 0002_reconcile_prod_schema idempotently adds the schema prod never got when the 0001..0007 chain was squashed into one 0001 (Django skips a same-named migration): the addon + pricingtier tables and 12 columns incl. bookableservice.listing_kind that /shop/ filters on. RunPython + introspection (no IF NOT EXISTS — sqlite-safe); state_operations=[]. Verified on real Postgres incl. a populated simulated-prod divergence + idempotent re-run
- docs: README gains a 'Project memory: torsor-helper' section (how the .torsor knowledge base + MCP server are used in AI-assisted development)
- docs: CLAUDE.md documents the new plugin-boundary ratchet; reconciliation plan at docs/plans/booking-marketplace-schema-reconcile-2026-08.md

## v0.35.0 — 2026-08-09

**MCP hardening + plugin-boundary ratchet + new README**

- agent_mcp: resources/read now runs the same scope + rate-limit + audit gate as tools/call (closes an authz + AI-Act-audit bypass); a write tool can't be mapped as a readable resource
- agent_mcp: trusted-agent X-Verified-Agent-* headers are honored only from a verified Cloudflare origin (shared-secret, fail-closed); /.well-known/agent.json advertises the capability honestly
- agents: register_tool surfaces cross-plugin tool-name collisions (warning + collisions()); agent_core's slug cart tool renamed cart.add_by_slug to stop colliding with the ACP cart.add_item
- orders/catalog: orders.search reports the real match total (not page size); orders.get/products.get cap nested collections; carts reject mixing currencies
- agentic_checkout: in-flight completion 409 now reports status=in_progress
- ci: new plugin-boundary ratchet (scripts/check_plugin_boundary.py) blocks NEW undeclared plugin->plugin imports (122-pair baseline)
- docs: brand-new comprehensive README + kernel-hardening evaluation (docs/plans/kernel-hardening-eval-2026-08.md)

## v0.34.2 — 2026-08-09

**Hotfix: revert booking_marketplace 0002 (503) — restore v0.34.0 migration state**

- booking_marketplace: the generated 0002 collided with prod's pre-existing tables (prod kept the historical 0001-0007 history; codebase had squashed them into 0001). 0002 CreateModel(Enquiry) hit an existing table and crash-looped the web container. Reverted to the v0.34.0 migration state (edited 0001, no 0002), which boots. The real /shop/ schema gap (missing addon/pricingtier tables) will be fixed with a prod-aware delta separately.

## v0.34.1 — 2026-08-09

**Moonshot provider probe + booking_marketplace migration fix**

- ai_assistant: add moonshot (Kimi) probe so its Test/Fetch-models buttons work
- booking_marketplace: split the edited 0001 into a proper 0002 delta (restores prod-applied 0001; adds the 6 new models + fields the /shop/ 500 needed)

## v0.34.0 — 2026-07-29

**Adopt the three-SDK doors across all 108 plugins (morpheus.{plugin,core})**

- Big-bang step of the SDK restructure (ADR 0035): migrated all 108 plugins — 383 files — off 'from morpheus import …' and 'from core.{hooks,agents,audit.services,money,utils.site} import …' onto the SDK doors morpheus.app (Plugin/contributions/views/models/forms) and morpheus.core (events/hooks/MorpheusEvents/tool+ToolResult+ToolError+agent_registry/record_ai_decision/Money/money_str/site_base_url/absolutize).
- Expanded morpheus.core to re-export MorpheusEvents + absolutize so the two dominant core imports (hook_registry 90x, MorpheusEvents 86x) are clean identity-preserving swaps. Deep/rare core internals (core.assistant.*, core.brain, core.agents submodules, core.emails, …) intentionally stay direct — the SDK is the curated common door, not a wrapper for every internal.
- Non-breaking: the re-exports are identity-preserving (morpheus.core.tool IS core.agents.tool). Verified: manage.py check clean (prod-boot over all 383 files); static audit clean (every symbol imported from a morpheus.{plugin,core} door is in its __all__); 951-test behavioral suite green (the single failure — moonshot provider missing a probe — is pre-existing, orthogonal drift already live on v0.33.0).

## v0.33.0 — 2026-07-28

**Three-SDK foundation — morpheus.{plugin,theme,core} (non-breaking)**

- New morpheus.app / morpheus.core / morpheus.theme subpackages — the three project SDKs (torsor ADR 0035): plugin authoring, the core-kernel API (hooks/events, agents tool/ToolResult/registry, audit, money, site utils), and storefront-theme authoring. Additive facades that re-export the real implementations.
- Non-breaking: every existing 'from morpheus import Plugin' / 'from core.hooks import …' keeps working and returns the same objects; the subpackages are the canonical doors going forward, adopted incrementally as we touch each plugin (per ADR 0035).
- The big-bang migration of ~60 plugins + themes onto the new imports is scoped in docs/plans/sdk-restructure-2026-07.md (a prod-boot-critical fan-out, run as its own effort). Verified: Django boots, all three doors import, back-compat identity holds.

## v0.32.0 — 2026-07-23

**Merchant agent guardrails — kill switch, daily run/spend caps, per-action price & refund ceilings**

- New Settings → Agent guardrails panel (agent_core): a global kill switch, a daily agent-run cap, a daily estimated-spend (USD) cap, a max price-change % per action, and a max refund value per action. All OFF by default (caps 0 = unlimited), so an unconfigured store is unchanged.
- Enforced at the real seams — the kill switch aborts a delegated run (re-checked each step, so flipping it halts an in-flight run) and makes Linda decline gracefully; the daily caps refuse a new run before any model call; the price/refund caps refuse the catalog/orders money tools before any write or charge.
- All reads funnel through one core accessor (core/agents/guardrails.py), read cross-process fresh so a celery worker sees a switch flipped from the dashboard — enforcement is plugin→core, never plugin→plugin. The AI-Act evidence report's guardrails section reflects the same live config.
- Honesty note: the USD spend cap is best-effort — it estimates $0 for unpriced/self-hosted models (incl. the current prod model), so the model-independent daily run cap is the hard backstop.

## v0.31.0 — 2026-07-22

**EU AI Act evidence export (agent-decision + approval trail)**

- New Dashboard → Linda → AI Act evidence page (/dashboard/apps/agent_core/compliance/, staff-only) + a scriptable export_ai_act_report management command (--days, --format csv|json). Both render the trail of automated AI decisions (agents.decision audit rows, art. 12/13 provenance) + the human-approval history (AgentApprovalRequest) + a per-tool/per-model summary + the active guardrail config, with a date window.
- One shared builder (agent_core/compliance.py:build_ai_act_report) backs the page + the command so they never drift. Read-only over the existing audit/agent tables — no new storage, no migration. Lives in agent_core (a PROTECTED plugin, so the compliance surface can't be disabled); the data is all core/agent-owned (audit-overlap: gdpr is customer-rights, not agent-audit).
- Scope note: this is Phase 4's compliance-export half. The guardrail ENFORCEMENT knobs (spend cap, price-change %, refund cap, kill switch) touch the safety-critical core agent loop and ship as their own focused change; the export already surfaces a guardrails section that fills in when they land.

## v0.30.0 — 2026-07-22

**Real MCP cart/checkout tools + honest UCP manifest capabilities**

- Fill the previously-empty MCP cart/checkout clusters: cart.create/add_item/get + checkout.get_session/set_buyer, in a new agentic_checkout/agent_tools.py. They REUSE the ACP cart-session helpers verbatim (_get_cart IDOR+TTL resolver, _add_line_items eligibility + CartService.add_item stock reservation + pricing, _apply_buyer/_apply_fulfillment, _serialize) — zero duplicated money logic, no drift from the REST path.
- Payment COMPLETION is deliberately NOT an MCP tool — the charge stays on the /acp/ REST endpoint behind all six money-path gates (payments_enabled default-off, quote-drift, select_for_update, Stripe-after-lock). Agents build+quote over MCP, complete on the merchant checkout.
- agent_mcp: _public_tools() resolves cluster tool names from the agent registry (so buyer-cart tools surface to their clusters without polluting Linda's operator catalog); CART_TOOLS/CHECKOUT_TOOLS populated. Disable agentic_checkout → clusters shrink to storefront-only, disable-safe.
- UCP manifest honesty: /.well-known/ucp.json cart/checkout capabilities are COMPUTED from whether the tools resolve (never advertises a dead capability), and auth.required_for lists cart/checkout (tools/call needs a Bearer token; discovery is open).
- Native Web Bot Auth (RFC 9421) split to its own focused change — a security signature-verification feature warrants dedicated attention + test matrix. docs/AGENT_PROTOCOLS.md + MCP_SERVER.md updated.

## v0.29.1 — 2026-07-22

**Settings saves are in-place AJAX (no redirect to a single-panel page)**

- Both the core StoreSettings form and every plugin SettingsPanel form on the settings-category page are now data-ajax: clicking Save shows a spinner on the button and the page never navigates or reloads (fixes the redirect to a bare single-panel page).
- settings_category core-form handler now returns JSON on AJAX (200 {ok:true} / 400 {ok:false,errors}) so the JS never shows a false 'Saved' on a validation failure (dashboard AJAX JSON-contract landmine).
- Morph.reinit (run after every boosted sidebar swap) now rebinds data-ajax forms too — previously they only bound on a full page load, so AJAX saves silently fell back to a full POST after in-app navigation. Fixes it for ALL data-ajax forms, not just settings.

## v0.29.0 — 2026-07-21

**/agents.md agent-onboarding manifest + AGENT_READINESS_SECTIONS filter**

- New /agents.md at the site root (owned by seo, same crawler-file family as llms.txt): tells AI agents what the store is, how to discover it (llms.txt/feed/sitemap), and how to transact.
- New AGENT_READINESS_SECTIONS hook filter — plugins contribute their own agent-facing section; agent_mcp contributes the MCP/UCP/well-known endpoints + auth. Disable an owner → its section (and endpoints) vanish, so the manifest never advertises a dead endpoint.
- Gated by the same expose-to-AI toggle as llms.txt; served as text/markdown. docs/AGENT_PROTOCOLS.md §6 documents the discovery surface.
- Scope note: llms.txt, dense Product/Offer/FAQPage JSON-LD, and AI-referral analytics were found already shipped in seo/analytics — not duplicated (one-concept-one-owner).

## v0.28.0 — 2026-07-21

**EU AI Act Art. 50 AI-disclosure for conversational surfaces**

- Add the `{% ai_disclosure %}` core tag + AI_SURFACE_DISCLOSURE filter — a mandatory 'you are talking to an AI' label with a core legal-floor default (never removed by disabling a plugin), wording customizable via gdpr.
- Wire the disclosure into the ai_stylist chat widget header (compliance-by-construction; the dormant block is untouched).
- COMPLIANCE.md: document the Art. 50 posture (chatbot disclosure mechanism live; per-object AI-content marking assessed and deferred — agent-mediated writes are already record_ai_decision-logged).
- Fix a pre-existing gdpr seed test that assumed an empty DB + the old 3-page set (sqlite migration-seed divergence; now deletes slugs first and asserts the real count of 6).

## v0.27.5 — 2026-07-20

**Internal: agent run-state models move into core — boundary ratchet reaches 0**

- Refactor (no behavior change, zero-SQL migrations): AgentRun/AgentStep/AgentApprovalRequest moved from the agent_core plugin into core (ADR 0034) — the runtime that persists them is permanently core, and this closes the LAST core→plugin import. The database tables are unchanged (state-only SeparateDatabaseAndState migrations, verified no-op SQL); agent_core re-exports the classes so every existing surface keeps working. The core→plugin boundary ratchet is now 0 and enforced empty by CI. Phase 4 (final) of docs/plans/architecture-debt-refactor-2026-07.md.

## v0.27.4 — 2026-07-20

**Internal: brand voice decoupled via the AGENT_SYSTEM_PROMPT filter**

- Refactor (no behavior change): core no longer imports ai_content for brand voice — prompt assembly fires the new AGENT_SYSTEM_PROMPT filter and ai_content's subscriber prepends the voice, so disabling the plugin cleanly yields the plain prompt. Core→plugin boundary ratchet 3 → 1 (only the agent_core run-state coupling remains). Phase 3 of docs/plans/architecture-debt-refactor-2026-07.md.

## v0.27.3 — 2026-07-20

**Internal: catalog agent-tools decoupled to the catalog plugin**

- Refactor (no behavior change): products.update_status and products.update_price moved out of core into the catalog plugin, driving the core→plugin boundary ratchet from 4 to 3. Tool names, approval gating, staged-mode, and the pricing_change staging blocklist (autonomous runs cannot propose price edits) are all preserved. Phase 2 of docs/plans/architecture-debt-refactor-2026-07.md.

## v0.27.2 — 2026-07-20

**Internal: orders agent-tools decoupled to the orders plugin**

- Refactor (no behavior change): the orders write tools (orders.update_status/cancel/add_note/refund) and db.recent_orders moved out of core into the orders plugin, driving the core→plugin boundary ratchet from 8 to 4. Linda and the Worker resolve the same tool names from the registry; the refund hard-gate + audit and staged-mode gating are preserved, and agent_core's duplicate orders.cancel was retired (single canonical owner). Phase 1 of docs/plans/architecture-debt-refactor-2026-07.md.

## v0.27.1 — 2026-07-19

**Loyalty redemption cap correctness (odd rates)**

- The loyalty points redemption cap now floors instead of rounding up, so a point worth more than a small order can never be over-redeemed against it. At a non-default redemption rate this previously let a shopper spend a whole point on a sub-point order and lose the unused value (the recorded discount could exceed the order total). Money-safety adversarially verified across many rates/totals; the default rate is byte-for-byte unchanged (#23).

## v0.27.0 — 2026-07-19

**Correctness & deliverability — the deferred deep-debug batch**

- Gift cards and loyalty points now apply as tenders AFTER tax and shipping, so a card or points balance covers the whole order — previously they capped against the item subtotal only, leaving the shopper to pay tax and delivery out of pocket and stranding balance on the card (#7).
- Cart-recovery emails now carry a one-click unsubscribe (RFC 8058 List-Unsubscribe header + a visible footer) and honour opt-outs, keeping them out of spam (#11).
- Large email campaigns send in resumable batches that continue automatically, so a big list can no longer stall a campaign mid-send (#20).
- A timed-out AI assistant run now stops cleanly at its next checkpoint instead of continuing to drive the model and execute tools in the background (#6).

## v0.26.2 — 2026-07-19

**Refund idempotency — distinct equal-value refunds no longer collide**

- RefundService.process now includes notes in its dedup key, so two genuinely-distinct equal-value refunds (e.g. two RMAs for equal-priced items, each stamped a unique 'RMA <n>') resolve to two refunds instead of the second silently reusing the first and moving no money. A true retry (identical args) still resumes the same row (deep-debug #8).

## v0.26.1 — 2026-07-19

**Deferred deep-debug fixes — plugin disable-safety + auto-heal backoff**

- register_urls routes now unmount on plugin disable — get_urlpatterns skips inactive owners and deactivate() rebuilds the URLconf, so a disabled plugin's endpoints (e.g. digital_products downloads) stop resolving (deep-debug #13, disable litmus).
- Self-improvement: a chronically-failing auto-heal stands down after 3 failures/fingerprint within 7 days instead of re-proposing a fresh recommendation every nightly run (unbounded backlog/audit-log leak; deep-debug #18).

## v0.26.0 — 2026-07-19

**Reliability & hardening — 14 source-verified bug fixes from an adversarial self-audit**

- Security: staged-execution approval exemption now scoped to tools that actually stage (supports_staging) — a destructive tool can no longer bypass approval under a staged routine; fs.search_files no longer leaks protected paths (secret-content oracle); protected-path check is case-insensitive; fs read_file/search honor the safety boundary; hard-gated actions now write a real audit row.
- Money: return refunds prorate order-level discounts and clamp to the order total (no more over-issued store credit / blocked refunds on discounted orders); gift-card balance is re-credited when an order is cancelled (idempotent), mirroring loyalty.
- Self-improvement: error_log collector watermark no longer collapses to the last ~10 min (was dropping ~83% of errors); a stuck-AgentRun reaper closes runs orphaned by a deploy/OOM.
- Email: campaign dedupe/counts filter kind='campaign', ok=True so failed recipients are retryable and a test-send can't suppress a real subscriber; newsletter confirm() no longer resurrects an unsubscribed (terminal) subscriber via a stale link.
- Agents: LLM fallback cascade bounded by a 50s wall-clock budget (was stacking to 60-80s past the 60s worker/proxy limit); embeddings client timeout 10s + no retries on the request path; llm.py worker-timeout comment corrected to 60s.
- Plugins: a second AppRegistry no longer rebinds the global hook active-check (test-isolation footgun); contributed skills are unregistered on plugin disable (were leaking past a disable). Core→plugin boundary debt shrank 9→8.

## v0.25.0 — 2026-07-19

**Default images, self-healing repair & one-command releases**

- **Default images (Settings → General).** Set a fallback product cover *and* a default social/share image; the product fallback now shows everywhere it was missing — home, product pages, cart, and recently-viewed — not just product grids.
- **The self-improvement engine is healthy again.** Its error + zero-result-search collectors now actually feed the backlog, a fixed auto-apply no longer re-runs forever, and rejecting or snoozing a suggestion finally sticks (with nightly duplicates deduped).
- **Versioning is one command.** `manage.py release` bumps the version and writes this changelog atomically; a CI guard blocks a deploy that forgot to bump, and every version is now mirrored to a GitHub tag + Release.

## v0.24.0 — 2026-07-19

**Agent security hardening — AI actions now need a real human sign-off.**

- **The AI agent can no longer run a sensitive action on its own.** Tools that
  change money, roles, or store config (issue a gift card, grant a staff role,
  set a tax rate, change net terms, …) are now **fail-closed**: instead of
  executing silently, the agent records a pending approval and pauses; a person
  approves it from the dashboard and the run resumes. Approvals are single-use,
  expire after 5 minutes, and are bound to the exact action requested — an
  approval for one change can't be reused for another. Scheduled "staged"
  routines are unaffected: they already propose changes for review.
- **The assistant respects who's asking.** The assistant's access "mode" is now
  decided on the server from the signed-in user, not the browser request — so
  the developer/diagnostics mode is limited to engineers, and a malformed mode
  can no longer fall back to full access.

## v0.23.0 — 2026-07-19

**Eco impact, Kimi AI provider, more legal pages, and a dashboard polish pass.**

- **Plant a tree at checkout + book footprint on every product page.** A new
  *Eco impact* plugin estimates each book's production footprint — paper, wood,
  and CO₂ — from its weight and dimensions, and shows it under the price. At
  checkout, shoppers can opt in to a flat "plant a tree" offset; the
  contributions are pooled as a tracked fund you fulfil, with a public
  **/save-the-planet/** page showing the running total and how it's calculated.
  Turn the badge on/off and set the offset amount in Settings → Eco impact.
- **Moonshot (Kimi) is now a selectable AI provider.** Pick it in
  Settings → AI providers and paste your Moonshot key — long-context, strong
  agentic reasoning, OpenAI-compatible (China endpoint supported).
- **Cookie Policy, Accessibility Statement, and FAQ pages** now ship as editable
  content pages, and the footer's FAQ link (previously a dead 404) works. Edit
  the copy any time under Dashboard → Pages.
- **Dashboard consistency pass.** Stat tiles, card headers, empty states, and the
  Users filter tabs now share one visual system across every admin page.

## v0.22.2 — 2026-07-18

**Agent tool-surface hardening** (the isolated, verified findings from the
core-kernel audit — the deeper agent-authorization work is tracked separately).

- **The AI file-read tool can no longer read secrets.** `fs.read_file` now
  refuses any path on the safety boundary (`.env`, keys, credentials, and the
  financial/auth source) — closing a path where an injected agent turn could
  exfiltrate secrets into transcripts. The resolve-then-check order means `../`
  can't dodge it.
- **The AI plugin-disable tool honours the protected-plugin list.** Disabling
  `admin_dashboard`/`orders`/`rbac`/`customers` soft-bricks the platform; the
  tool now refuses them (before even prompting for confirmation), same guard the
  registry and CLI use.
- **OTP issuance is now rate-limited.** `/auth/otp/` was missing from the auth
  rate rules — since issuance sends an email, that was an email-bombing relay.
  Now throttled per IP like login/signup.

Guarded by 6 new regression tests.

---

## v0.22.1 — 2026-07-18

**Storefront visual consistency** (batch B of the UI/UX pass — pure polish).

- **De-duplicated conflicting design tokens.** The display type scale
  (`.display-xl/-l/-m`) and `.eyebrow` were each defined twice with different
  values; consolidated to a single source of truth so headings render
  predictably.
- **The on-sale badge now uses the house red.** The product-card discount ribbon
  was paper-on-grey (invisible) and the PDP sale pill used an off-palette red
  (`#b91c1c`); both now use the brand accent — the one place a card *should* draw
  the eye.
- **Refined product-card hierarchy.** The title is a touch smaller and lighter,
  and the author is set in italic serif so it reads distinctly from the sans
  excerpt instead of blurring together.
- **Empty product listings** now use the theme's proper `.empty-shelf` treatment
  (fleuron + heading + actions) instead of an ad-hoc dashed box.

---

## v0.22.0 — 2026-07-18

**Storefront accessibility & feedback** (batch A of a UI/UX pass, from a
three-track design analysis of the theme).

- **Both slide-out drawers are now proper dialogs.** The mobile navigation and
  the cart drawer gained `role="dialog"`/`aria-modal`, correct `aria-hidden`/
  `aria-expanded` toggling, focus moved in on open and **restored to the trigger
  on close**, a **focus trap**, and Escape-to-close — so keyboard and screen-
  reader users can actually use them and never get lost behind the overlay.
- **Search is a real combobox.** The quick-search input now exposes
  `role="combobox"`, `aria-expanded`, and `aria-activedescendant`, and each
  suggestion is a labelled option with `aria-selected`, so arrowing through
  results is announced.
- **One global feedback toast.** A polite `aria-live` region now surfaces
  post-action notices (cart, coupon, subscribe) and replaces the jarring native
  `alert()` on an add-to-cart failure.
- **Bigger tap targets** — the header icon buttons meet the 44px minimum.
- **Fix:** the order-history page showed the total unformatted (`10.00` instead
  of `$10.00`).

No visual redesign — these are correctness + usability. (Batch B: visual
consistency + polish, next.)

---

## v0.21.3 — 2026-07-18

**Code-quality pass** (consistency + consolidation; no behaviour change). A
four-angle review of the recent releases surfaced repeated patterns worth
unifying:

- **One fail-soft plugin-config accessor.** The "read a plugin's config value,
  never crash the caller" try/except was hand-rolled in six places (a seventh
  that forgot the guard is how a config read takes down checkout). Collapsed to
  `app_registry.config_value(name, key, default)`.
- **One order-email helper.** Three call sites re-derived an order's contact
  email by hand — the exact drift that caused last release's `customer_email`
  bugs. Now a single `core.utils.orders.order_email(order)`.
- **Checkout cart-checks share one loader.** The shipping and digital-item
  checks each re-loaded + re-prefetched the same cart; they now load it once via
  a shared helper, with consistent iteration.
- **Campaign send hoists constant work out of the per-recipient loop** (the body
  `strip_tags` is computed once, not per subscriber), and the loyalty cart widget
  drops a duplicate balance query.

All guarded by the existing test suites (no behaviour change).

---

## v0.21.2 — 2026-07-18

**Deep-debug pass — seven real bugs fixed** (found by auditing production logs +
adversarially reviewing the recent releases):

- **Security (critical): guest cart cache leak.** The GraphQL query cache still
  cached anonymous `cart` queries, which resolve from the session — so one
  guest's cart (items *and* applied gift-card codes) could be served to the next
  guest. Cart/shipping (session-scoped) queries are now never cached; catalog
  queries still are.
- **Win-back emails were dead in production.** The nightly segment rescore fired
  `CUSTOMER_SEGMENT_CHANGED` with the wrong argument shape, so the win-back flow
  (shipped in v0.19.0) never actually ran. Fixed to the documented contract.
- **Campaign double-send race.** A double-clicked "Send" (or a task retry) could
  blast the whole list twice; sending is now claimed atomically so only one run
  proceeds.
- **Gift-card double-issue race.** A double-fired payment could mint duplicate
  real-money gift cards; issuance now locks the order so it can't.
- **"Recently viewed" rail was broken** on the homepage (a template loaded the
  wrong tag library) — it silently rendered nothing on every visit. Fixed.
- **Fraud velocity check was dead** — it queried a non-existent Order field and
  errored every time, and also missed guest-order emails. Fixed to the real
  field.
- **Guest orders sent no email to the print-on-demand vendor** (same wrong-field
  bug). Fixed.

All guarded by new/strengthened regression tests.

---

## v0.21.1 — 2026-07-18

**Faster product listings** (performance). Every product card reads its cover
image via `product.primary_image`; that property used a filtered query that
bypassed the page's prefetch, so a 60-item listing fired dozens of extra
per-card image queries (flagged in the July audit). The property now resolves
covers from the prefetched set in memory, and the listing/collection/author/
search-suggestion queries prefetch images — so the product grid renders in a
constant number of image queries instead of one (or more) per card. No visible
change; pure speed. Guarded by an `assertNumQueries` regression test.

---

## v0.21.0 — 2026-07-18

**EU digital-goods withdrawal waiver at checkout.** Selling downloadable books
(ebooks, audiobooks) in the EU requires the buyer's express consent to
immediate access *and* their acknowledgement that this waives the 14-day right
of withdrawal (Directive 2011/83/EU art. 16(m)) — otherwise a customer can
download the file and still demand a refund. Now:

- When a cart contains any digital/downloadable item, a **required
  acknowledgement checkbox** appears at checkout (both the one-page and
  multi-step flows). The order can't be placed until it's ticked.
- The exact wording is **merchant-editable** (Settings → Checkout & cart) —
  ships with a common default, which you should review with your own counsel.
- The accepted acknowledgement (the exact text shown + a timestamp) is
  **recorded on the order** as the compliance artifact.
- Physical-only carts are never gated.

**Ships disabled by default** — enable it under Settings → Checkout & cart once
you've finalised the wording. The mechanism is in place; no checkbox appears at
checkout until you switch it on.

---

## v0.20.0 — 2026-07-18

**Sales surfaces: sellable gift cards + the receipt-page upsell.**

- **Gift cards are now sellable.** Create a virtual product with the SKU
  `GIFT-CARD` (configurable under Settings → Gift cards) and every paid unit
  auto-issues a real gift card worth its price, emailed to the buyer with the
  code (merchant-editable template). Idempotent against webhook replays —
  one card per unit, never doubles. Books are gift-native; now the shop is too.
- **"You might also like" on the order confirmation page.** The receipt now
  renders the post-order upsell: the merchant-configured pick (Settings →
  Post-checkout upsell), falling back to the newest arrival the customer
  didn't just buy. Renders through the `order_receipt_extra` block slot —
  previously contributed but never rendered by the theme — so any plugin can
  now add receipt-page surfaces, and disabling the upsell plugin removes it.

---

## v0.19.0 — 2026-07-18

**The email marketing engine is live.** Morpheus could capture subscribers and
send transactional email, but campaigns had no send path — the biggest missing
marketing primitive. This release completes it:

- **Send campaigns.** New dashboard page (Marketing → Send campaigns) targets
  any Email Campaign at your confirmed, double-opt-in subscriber list — with a
  **test-send to yourself** first. Sending is queued, idempotent (a re-run or
  double-click never double-mails anyone), counts recipients, and marks the
  campaign sent.
- **Inbox-compliant by construction.** Every bulk send carries the RFC 8058
  one-click-unsubscribe headers Gmail/Yahoo require, plus a visible
  unsubscribe footer; the unsubscribe endpoint now honours the one-click POST.
  The core email sender gained a `headers` passthrough for this.
- **Win-back flow.** When a customer slips into the at-risk RFM segment
  (nightly rescore), confirmed subscribers get a warm "we saved some books for
  you" email — consent-gated (no subscription, no email), max one per address
  per 30 days, with an optional configured coupon code (Newsletter settings).

Owned by the newsletter plugin end-to-end (disable it and the send page,
routes, win-back, and emails all vanish). Covered by 8 new tests including
header assertions and dedupe windows.

**Security fixes** (from the July application audit, verified then patched):

- **GraphQL cache isolation.** The query cache keyed on query+variables only,
  so an authenticated caller's response could be served to other users for up
  to 5 minutes. Authenticated sessions and Bearer-token callers now bypass the
  cache entirely (read and write); anonymous storefront traffic keeps it.
  Regression-guarded by cross-user isolation tests.
- **Bulk customer delete now respects the staff guard.** Single-record delete
  always refused staff/superuser accounts; the bulk action didn't — a sweep
  selection could hard-delete an admin. Bulk delete now skips staff accounts
  with a warning, exactly like the single-record path.

---

## v0.18.0 — 2026-07-18

**Spend your reader points at checkout.** Loyalty points have been earnable
for a while, but there was no way to *spend* them — the discount math existed,
the checkout wiring didn't. This completes the money path:

- **Cart control** — a "You have N reader points (worth $X)" panel in the cart
  lets a signed-in shopper apply points toward their order (capped to their
  balance), or remove them. Self-hides for guests and zero-balance customers.
- **Ledger debit at checkout** — when an order is placed, the redeemed points
  are actually debited from the balance (a single `spend_order` ledger row),
  inside the same atomic block as gift-card redemption. Idempotent: a retried
  checkout never double-spends.
- **Automatic reversal on cancel** — cancel an order that spent points and the
  points come straight back (a shopper is never out points for an order that
  didn't ship). Idempotent against a paid cancel firing both cancel + refund.

The whole flow is disable-safe (the control, routes, debit, and reversal all
vanish if the loyalty plugin is turned off) and covered by 13 tests, including
the real `create_from_cart` and `order.cancel()` paths.

---

## v0.17.1 — 2026-07-18

**Fix: the mood-search landing is now reachable.** In v0.17.0 the natural-language
"describe what you're in the mood for" panel lived on the `/search/` empty state,
but a query-less `/search/` was 302-redirecting straight to `/products/` — so no
one clicking **Search** ever saw it. `/search/` now renders the mood-search
landing; a keyword search (`/search/?q=…`) still bounces to the rich product-list
page as before. Regression-guarded by `storefront/tests/test_search_landing.py`.

---

## v0.17.0 — 2026-07-18

**Book-native quick wins** — first batch from the ideas roadmap (research-backed:
Baymard AOV data, review-conversion studies, book-discovery patterns).

- **"Add €X for free shipping" progress bar in the cart.** When a free-shipping
  threshold is configured, the cart now shows how close the order is with a
  progress bar — the cheapest proven lever for average order value (shoppers add
  items to qualify), and it kills the "unexpected shipping cost" surprise that's
  the #1 cart-abandonment driver. Self-hides when no free-shipping rule is set.
- **The review-request email now links straight to each book's review form.**
  The post-purchase "how was your order?" email (sent ~2 weeks after delivery)
  used to be a generic nudge; it now lists every book on the order with a
  one-click link to write that review. Reviews are the single biggest
  conversion asset for books.
- **Mood search — "just describe what you're in the mood for."** The search
  page now invites natural-language queries ("a short novel that feels big",
  "like Normal People but hopeful") with example prompts, routed through the
  existing AI/semantic search. A genuinely indie-bookshop way to discover, and
  something the big retailers' keyword filters can't do.

*Ops (no code):* recovered from a disk-full production outage — freed 37GB,
deleted the compromised crawl4ai container permanently, and added automated
disk pruning + a disk-space alert so it can't recur silently.

## v0.16.0 — 2026-07-17

**Cancel an order (right of withdrawal)** — Batch 2 of the professionalism
roadmap, EU consumer-law compliance.

- Customers can now **cancel an order themselves before it's dispatched**, from
  the order page in their account — the pre-shipment right of withdrawal that EU
  consumer law requires. A cancelled order that was already paid is **refunded
  in full automatically**, through the same safe, idempotent refund path the
  dashboard uses (the payment provider can't be double-charged); the refund
  confirmation arrives by email as usual.
- The button only appears while the order can still be cancelled — once it has
  shipped, the customer uses "Request a return" instead. The confirmation step
  is a plain expand-to-confirm control (no accidental one-click cancels, and no
  JavaScript required).

**Fixed**

- **A broken chat widget in the storefront's bottom-left corner is gone.** The
  unfinished "AI stylist" assistant was contributing a storefront widget that
  shipped without any styling or behaviour, so it rendered as raw stray text
  ("Aria / Ask me anything…") stacked in the page corner. It's withheld until
  the feature is actually built — the working "Chat with us" widget is
  unaffected.

*Still ahead in Batch 2 (needs your input):* a product-safety panel on book
pages (GPSR — requires appointing an EU Responsible Person), a digital-download
withdrawal-waiver checkbox at checkout, an accessibility (WCAG 2.1 AA) pass, and
real legal copy to replace the seeded placeholders.

## v0.15.5 — 2026-07-17

**Trust & deploy-safety quick wins** — first code batch of the July
professionalism roadmap (see `docs/plans/` research: Baymard, EAA/GDPR, CWV).

- **Branded 404 and 500 pages.** A mistyped or expired URL used to dead-end on
  Django's bare one-line "Not Found"; a crash showed a blank server error. Both
  now land on dot-books-styled pages — the 404 offers search and a way back to
  the shelf, the 500 is fully standalone so it renders even when the app can't.
- **The shop has a favicon.** Every visit requested `/favicon.ico` and got a
  404 (visible in every browser console). A dot-books mark (ink tile, red dot)
  now serves at the conventional path and is week-cached.
- **"Reject all" is as prominent as "Accept all"** in the cookie banner — same
  fill, same size. Regulators (CNIL) fine asymmetric banners; ours no longer
  visually nudges toward consent.
- **Deploys verify themselves.** `/api/readyz` now reports the running version,
  and a new `deploy-smoke` workflow polls production after every push to main
  until it converges on the pushed version and the homepage answers 200 —
  a missed webhook or wedged build queue is now a red X instead of a silent
  stale deploy. GHCR image builds also wait for CI to pass instead of
  publishing `latest` from red commits.
- **Sentry is one env var away.** The error-tracking wiring already shipped;
  `.env.coolify.example` and the operations runbook now document the
  `SENTRY_DSN` switch that turns it on.
- **Operations runbook rewritten** to match the real production topology
  (Coolify, not the aspirational k8s notes) including stuck-deploy-queue
  recovery, rollback, and backup-restore practice.
- Removed the dead synchronous order-email path (`orders/email.py` + its
  Celery wrapper) — production has long sent all order mail through the
  retrying `deliver_email` queue; the order-confirmation test now exercises
  that live path.

*Shop operations shipped alongside (no code):* the footer's Privacy / Terms /
Imprint links now resolve (pages seeded and published), outbound mail is
DKIM-signed (selector published in DNS, joining existing SPF + DMARC), and the
server no longer advertises its stack in response headers.

## v0.15.4 — 2026-07-17

**Storefront hero**

- **The book's shadow is physical now.** Each slide threw its shadow in its own
  direction — slide 4 threw it *upward*, putting the sun underneath the book —
  in its own colour (violet, green, rust), while the whole thing crawled around
  on an endless loop. One fixed light now lights every slide, so the shadow
  always falls the same way, in one neutral ink. Slides still differ, but along
  the axis that stays honest: how high the book floats — a higher float throws
  further, blurs wider and lands fainter, as a real shadow does. The shadow is
  also the book's own silhouette rather than a round smudge beside it.
- **It fades in and settles.** The shadow slides out from under the book as it
  fades, like the book rising into its float — then stops. Reduced-motion
  keeps the shadow, drops the drift.
- **The copy no longer jumps between slides.** Book titles run one to three
  lines and the sale badge only exists on discounted books, so the price and
  buttons landed at a different height on every slide. Every slide now reserves
  the same space, so the staggered fade-in reads as choreography instead of the
  page reflowing under you.

**Fixes found by an adversarial review of this batch**

- **Filtered book lists showed the wrong intro.** `/products/?genre=…`,
  `?topic=…`, `?collection=…` and price filters were treated as unfiltered, so
  a genre's results carried the sitewide "everything we shelve" intro — and
  shipped it as that page's search-result description too.
- **"Write N missing intros" could promise work it would never do.** The button
  counted terms differently from the job it starts: a genre whose books were all
  drafts was advertised as missing an intro that the job then skipped forever,
  so the number never moved however often you clicked. Both now read from one
  definition. The same page also stopped issuing one query per row (~1,500 on
  Topics).
- **Re-clicking the button no longer double-bills.** A run now holds a lock, so
  an impatient second click can't queue an overlapping batch of paid AI calls.
- **A stunted AI answer can't auto-publish**, while the Generate button still
  shows you whatever came back — the guard belongs where nobody is reviewing.

## v0.15.3 — 2026-07-17

- **Fixed: a garbled AI reply could publish itself.** When the model returned
  broken or cut-off JSON, the copy writer fell back to using that raw text as
  the intro — which briefly put a literal `{` on the live Drama genre page. A
  reply that can't be read, or is too short to be an intro, now counts as a
  failed generation: the page keeps its existing copy and the run reports a
  skip, so re-running just picks it up. (A model that answers in plain prose
  instead of JSON is still accepted — that's what the fallback is for.) The one
  affected page has been cleared.

## v0.15.2 — 2026-07-17

- **AI copy generation: the retry now gets time to finish.** v0.15.1 taught the
  gateway to retry when a reasoning model spends its whole token budget
  thinking — but thinking that long also outruns the 20 second network timeout,
  so half the retries traded an empty answer for a timed-out one. The retry now
  carries its own 45 second budget (still inside the 60 second request limit, so
  it returns copy instead of killing the worker). Measured on the live store:
  the genre backfill went from 1-of-5 pages written to writing them properly.

## v0.15.1 — 2026-07-17

- **Fixed: AI features silently produced nothing on reasoning models.** Found
  while running the new bulk copy writer against the live store, which wrote 1
  page and skipped 4. Reasoning models (the configured `deepseek-v4-pro`,
  DeepSeek's reasoner, OpenAI's o-series) spend tokens *thinking* before they
  answer, and that thinking counts against the reply's token budget. Every
  Morpheus AI feature asks for a small budget sized for ordinary models — 400
  to 600 tokens — so the model used the entire allowance reasoning and returned
  a **successful but empty** answer. Nothing errored; the copy just never
  appeared. Any dashboard "Generate" button, product-description writer or SEO
  draft on such a model was affected. The gateway now recognises that exact
  response and retries once with room to finish (measured: ~915 tokens needed
  where 400 was offered).

## v0.15.0 — 2026-07-16

**Every listing page can have an intro now — and the AI can write the backlog.**
An audit of why category/collection/author/genre pages showed no description
found three different causes; this fixes all three.

- **Genres and Topics landing pages can hold intro copy at all.** `/genres/`
  and `/topics/` looked supported but were dead through three layers: the view
  discarded the intro, the model couldn't store one (its choices omitted both
  kinds), and the dashboard hid the "Edit landing page" button for exactly
  those two. All three are open — edit them under **Products → Book
  taxonomies → Edit landing page**, same as Authors or Publishers.
- **The /products/, /vendors/ and /journal/ intros are editable.** These pages
  own no record of their own, so their intro prose — and their search-result
  description — were hardcoded with no way in. They now read a **CMS → Blocks**
  entry (`products_intro`, `vendors_intro`, `journal_intro`); the house copy
  stands in until you write one.
- **New: write missing intros in bulk.** Products → Book taxonomies now offers
  *"Write N missing intros"* per Genres/Topics — it writes the most-stocked
  pages first (the ones shoppers actually land on), runs in the background, and
  never touches copy you wrote yourself. Batched, because each page is one AI
  call; run it again for the next batch.
- Under the hood: the per-page Generate button and the bulk backfill now share
  one prompt, so they write in the same voice.

*Why most pages looked blank:* the plumbing was mostly fine and the copy was
simply never written — 1,526 of 1,527 topics and 36 of 43 genres had no intro.
The bulk writer above is the fix for that part.

## v0.14.9 — 2026-07-16

- **Storefront hero: the per-slide 3D shadows are actually visible now.**
  v0.13.1's "strange shadow behind each featured book" shipped invisible,
  twice over: the blob's dense core sat *behind* the opaque cover (only its
  near-transparent fringe ever reached the page), and the grid-card
  "minimal cover shadow" rule silently out-ranked the hero cover's base
  shadow. Each slide's shadow mass now emerges from behind the book's edge
  into the open left flank of the hero — a different organic shape, tint,
  offset and blur per slide (compact low slump / tall violet drape / sharp
  low pool / floating rust overhang), still drifting and crossfading with
  the slides. Tuned and verified against the live storefront at every
  slide position.

## v0.14.8 — 2026-07-16

UX plan P0 batch — every item is a user-facing bug from the
`dashboard-ux-consistency-2026-07` audit:

- **Creating a product, customer, or coupon no longer fakes success.** The
  three New forms returned HTML to their AJAX submits, so invalid input
  showed "Saved" while nothing was saved. They now return the real
  validation errors, and a successful create navigates straight to the new
  record's edit page (staying on the filled-in form invited an accidental
  duplicate).
- **8 hidden settings panels are visible again.** Agentic Commerce Protocol,
  one-click checkout, post-checkout upsell, and returns portal (now under
  Payments), journal (Sales channels), fraud rules (Developer),
  post-purchase flows (Marketing), and trust signals (General) had declared
  categories that don't exist — no card, no nav entry, dead URL.
- **AI settings page shows every AI plugin's panel.** It previously
  hardcoded brand voice only; AI stylist's settings were unreachable.
- **Deleting a webhook now asks first** (proper confirm dialog with
  consequences, danger-styled button).
- **Gift cards sidebar entry links to the real page** instead of a doubled
  `/apps/gift_cards/gift_cards/` path; Bookings nav entry declared a valid
  sidebar target.
- **Tracking settings dropped two do-nothing fields** (GA4/GTM "mirror"
  inputs that were never read — the real settings live at Tracking).
- **Enforcement so this can't regress:** a new `manage.py check` rule fails
  the build when a settings panel declares an unknown category or a
  dashboard page an unknown nav target (`morpheus.E001`/`E002`), with tests
  pinning the contract.

## v0.14.7 — 2026-07-16

- **Bookvault token is now write-only in Settings.** The stored API token
  was echoed back into the settings form; it now renders masked and a blank
  submit keeps the existing secret (house `format: password` convention —
  found by the UX/settings audit).
- **Dashboard & Settings consistency audit.** A four-track audit (components,
  settings surfaces, navigation, copy/feedback) produced a ranked, phased
  polish plan at `docs/plans/dashboard-ux-consistency-2026-07.md` — P0 bug
  fixes through copy standards, each with an enforcement test so fixes stick.

## v0.14.6 — 2026-07-16

- **Fixed: cart totals API crash during checkout.** The `cartTotals` GraphQL
  query (used by the checkout page's totals refresh) crashed on every call —
  the resolver reached its sibling through `self`, which is empty for root
  queries. Found via a production log sweep during a checkout audit; the
  lookup is now a shared helper and the query executes against the real
  schema in a regression test.

## v0.14.5 — 2026-07-16

- **Fixed: "AI provider error … All AI providers degraded".** Continuing a
  conversation in which Linda had used a tool could crash every strict AI
  provider (DeepSeek et al. reject a `tool` message that doesn't directly
  follow its `tool_calls`): replayed history never carried the tool-call
  ids, and long-conversation compaction could split a tool-call pair at the
  summary boundary. Tool history now replays as assistant-visible text
  (same recall, always valid), and compaction keeps tool-call pairs
  together. Guarded by `core/assistant/tests/test_message_contract.py`.

## v0.14.4 — 2026-07-16

- **Linda's knowledge stays fresh automatically.** Her RAG knowledge index
  now rebuilds itself nightly (4:30am) — previously it had no refresh
  schedule at all, freezing at the last manual rebuild, so books, language
  editions, and descriptions added after a deploy were invisible to her.
  The rebuild is incremental (unchanged content is skipped, removed content
  is pruned). The production index was also refreshed immediately
  (174 → 183 chunks).

## v0.14.3 — 2026-07-16

- **One subscription system.** Two parallel, incompatible `Subscription`
  models had shipped (the billing one in `subscriptions`, and a never-wired
  replenish/curated skeleton in `subscriptions_plus`). Merged: the
  Subscriptions app now owns delivery subscriptions too — a `kind` on every
  subscription (plan / replenish / curated box), box contents
  (`SubscriptionLine`), a shipment schedule, and a pause/skip/swap audit log,
  plus the "Subscribe & save" PDP block and the cadence/swap-window settings.
  The `subscriptions_plus` plugin is deleted. *(Post-deploy one-off: its four
  empty tables can be dropped — `subscriptions_plus_subscription`, `_line`,
  `_shipment`, `_event` — plus their `django_migrations`/`content_types`
  rows; they held zero rows.)*
- **Guest purchases now count in experiments.** Checkout stamps the anonymous
  visitor id onto the order (`Order.metadata['visitor_id']`, new `metadata`
  field), so A/B-test conversions from customers who never log in are finally
  attributed — the loop the merchandising autopilot learns from. Previously
  only signed-in conversions counted.
- **"Bought together" counts every real purchase.** The co-purchase job
  filtered on two order statuses that don't exist and missed
  processing/shipped/delivered orders; it now uses the canonical paid-status
  set, so recommendations learn from every actual sale.

## v0.14.2 — 2026-07-16

- **Mega-menu covers load ~100× lighter.** The Featured-books thumbnails in
  the Authors/Genres/Topics dropdown menus were the last images on the
  storefront still loading raw multi-MB `/media/` PNGs. They now go through
  the responsive-image proxy like the product cards (AVIF/WebP, 200/400px
  renditions sized for the ~120px tiles).

## v0.14.1 — 2026-07-16

Internal hardening release — plugin-boundary debt repayment. No new features,
nothing to reconfigure.

- **Apps now unplug cleanly from the Products screen.** The product list's
  Bookvault column, its "Send to Bookvault" bulk action, and the fulfilment
  panel on the product form are contributed through the plugin bus (new
  `PRODUCT_LIST_COLUMNS` extension point + the existing product-form cards)
  instead of being hard-coded into the dashboard. Disabling the Bookvault app
  now removes every trace of it — and this fixes a lurking crash where the
  whole Products page could error out if the app was disabled while still
  configured.
- **One breadcrumb builder.** Eight apps carried their own copy of the
  dashboard breadcrumb helper; it's now a single SDK function
  (`morpheus.dashboard_trail`). No visual change.
- **Linda's `workflows.run` tool moved into the Workflows app** — owned by the
  app it drives, like the earlier metafields tool move. The core→plugin import
  baseline shrank from 11 to 9 entries.

## v0.14.0 — 2026-07-16

- **Language editions — customers can buy books in their own language.** A
  translated edition is a full product (its own page, own-language copy, and
  its own **print / e-book / audiobook** variants), linked to the original via
  the new **"Translation of"** field on the book card (enter the original's
  slug; linking to a translation resolves to the original automatically).
  Linked editions get:
  - a **"Read it in your language"** switcher on the product page (edition
    chips with native language names — *français*, *deutsch*, …), contributed
    by the book_product plugin so it disappears if the plugin is disabled;
  - **`hreflang` alternate links** between all editions of the work — the SEO
    item deferred since the 2026-07 audit now ships where it's real.
- **Product page — variant badges.** Audiobook variants now show an
  **Audiobook** badge (they wrongly showed "Physical"); physical editions now
  read **Print**. (book_product plugin 0.2.0 → 0.3.0.)

## v0.13.4 — 2026-07-15

**Storefront design deep-dive — bugs found on the live site, fixed at the root.**

- **Card excerpts no longer show raw code.** Product cards across the home
  rails, author pages and facet pages displayed literal `&lt;p&gt;` /
  `&#x27;` fragments. Three-layer fix: the `first_sentence` filter now
  normalises stored copy to plain text (unescape entities twice + strip
  markup), the card template avoids the `{% firstof … as %}` double-escape,
  and 13 catalog rows storing pre-escaped HTML in `short_description` were
  cleaned in place.
- **Card covers load ~30× lighter.** Cards fed by GraphQL dicts (home rails,
  hero shelf) rendered the raw `/media/` originals — multi-megabyte PNGs
  (Moby-Dick: 2.9 MB) that painted as blank cream boxes while downloading.
  They now go through the same AVIF/WebP responsive proxy as everything else
  (~65 KB at grid size).
- **Add-to-cart buttons align** across a card row regardless of title/excerpt
  length (card body flexes, actions pin to the bottom).
- **Shelf pages standardized** — categories, collections, genres, topics,
  authors, publishers, series and tags now share one hero pattern: breadcrumb,
  kind eyebrow (Category / Genre / Author / Tag / …), display title with the
  accent dot, and the **dashboard-editable description** as the lede. Filtered
  shelf views (`/products/?author=…`, `?publisher=…`) now show the same
  editable copy as the term's own landing page instead of generic filler.
  Every kind was already editable in the dashboard (Categories, Collections,
  Book taxonomies, Tag descriptions) — the storefront just never showed some
  of it.
- **Home "Browse the shelves" fixed** — it linked top-level *categories* to
  `/genre/…` URLs (wrong page) and showed a single lonely chip; it now renders
  the curated genre index (same source as the mega-menu) and hides below 3
  entries.

## v0.13.3 — 2026-07-15

- **Footer rebuilt.** Removed the duplicate **Imprint / Imprints** link and split
  the overloaded "The press" column into clean **Explore** and **Sell** columns
  (Shop · Explore · Sell · Help). Legal links (Privacy, Terms, Imprint, Cookie
  preferences) moved out of the nav columns into the **bottom bar** where they
  belong — contributed via a new `footer_legal` slot (still disable-safe: turning
  off GDPR removes them). This also fixes the `Imprint`/`Imprints` collision.
- **Product page — "Recommended for you" aligns left.** It no longer indents/
  centres inside the details column: contributed PDP blocks now sit flush-left
  with the rest of the column.
- **Product page — "Recently viewed" is now a carousel of up to 20.** The
  recently-viewed rail switched from a fixed grid of 8 to a horizontal,
  scroll-snap **carousel** remembering the visitor's last **20** books.

## v0.13.2 — 2026-07-15

- **Fix — audiobook sample player never appeared on the storefront.** The PDP
  passes `product` as a GraphQL dict, but the `audiobook_for` tag filtered the
  variant FK by that dict — which raised and was silently swallowed, so the
  "🎧 Listen to a sample" block rendered nothing even for a ready audiobook. The
  tag now resolves the id from either a dict or a model.
- **Audiobook editions are their own variant type.** An audiobook edition is no
  longer created as a generic **Digital** variant — it's now `variant_type =
  'audiobook'`, so it reads as an audiobook everywhere (dashboard, agent tools,
  API). It still behaves as a downloadable, no-shipping edition: checkout skips
  inventory reservation and the download is delivered exactly as for digital
  variants. (Metadata-only migration; existing digital audiobook variants keep
  working — re-save or run the backfill to re-type them.)

## v0.13.1 — 2026-07-15

- **Storefront — book shadows.** The hero slider now casts a **different strange
  3D shadow behind each slide** — every featured cover gets its own organic
  blob shape, tint, offset and drift, so the shadow visibly morphs as the slider
  advances (crossfades with the active slide; disabled under
  `prefers-reduced-motion`). Book covers in the grids now carry a **minimal**
  resting shadow that grows **slightly** on hover, replacing the heavier lift.

## v0.13.0 — 2026-07-15

- **Linda gets a knowledge base (RAG, phase 1).** Linda can now retrieve
  **unstructured** knowledge — the platform docs (Architecture, Plugin
  Development, Release Notes, API, Quick Start) and any plugin-contributed
  sources — and cite it in-chat, complementing her existing live tool-calls
  (structured data like orders/inventory stays on exact tool-calls; RAG only
  adds what she otherwise can't see). Architecture per ADR 0017: the retriever
  **seam lives in core** (`core/assistant/knowledge.py`) and the ai_assistant
  plugin registers the actual retriever in its `ready()` — so core imports no
  plugin, and disabling ai_assistant cleanly removes the knowledge block from
  the prompt. Plugins contribute their own documents through the new
  `KNOWLEDGE_SOURCES` filter (same pattern as `BRAIN_SIGNALS`). Build/refresh the
  index with `python manage.py rebuild_knowledge`. Embeddings are stored as JSON
  (Python cosine) at current scale; a pgvector index is the planned phase 2
  (`docs/plans/rag-knowledge-base.md`).

## v0.12.7 — 2026-07-15

- **Fix — book pages with no category no longer 500.** The PDP eyebrow used
  `{{ genre.name|default:product.category.name|default:… }}`; Django resolves
  every `|default:` argument eagerly, so `product.category.name` was evaluated
  even when a genre existed — and any book with **no category** (`category` is
  `None`) crashed with `VariableDoesNotExist`. Rewritten with `{% firstof %}`,
  which resolves each candidate with `ignore_failures=True` and tolerates a
  `None` category. (Only `giants-bread` was affected today, but it was a latent
  crash for every category-less book.)
- **Storefront grid — capped at 5 across + roomier edges.** The book grid
  (`.grid-books`, all listing pages) no longer expands to 6/7 columns on very
  wide screens — it holds at **5 per row** from 1280px up, so covers stay a
  legible size. Page gutters widen on large desktops (3.25rem ≥1280px, 4.5rem
  ≥1600px) for more breathing room at the edges; mobile/tablet unchanged.
- **Footer — capped width, no empty gap.** The footer columns and sign-off no
  longer stretch edge-to-edge on wide screens; content is capped at 1400px and
  centered. The newsletter confirmation line no longer reserves a blank gap
  under the Subscribe form when empty (its `aria-live` announcement still fires
  on success).
- **Dashboard — micro-animation polish.** Sub-nav **tabs** now grow their
  underline from the left (faint on hover, full on active) instead of snapping;
  the **confirm dialog** backdrop fades in with the card's pop; **KPI stat
  tiles** deepen their shadow on hover so they feel alive. All interaction-only
  (no new page-load animations) and neutralised under `prefers-reduced-motion`.

## v0.12.6 — 2026-07-14

### Product page: cleaner recommendations + full-height cover

- **Dynamic product blocks can now hide titles** (new "Show title" toggle in
  Merchandising, alongside "Show price"). Turn both off for a clean
  image-only recommendation grid.
- **Product cover shows in full.** The main image on the product page now fits
  the whole cover at full height instead of cropping it to fill.

---

## v0.12.5 — 2026-07-13

### Accessibility: wordmark link name matches its visible text

The header logo link advertised the accessible name "Home" while showing the
"dot books" wordmark, so voice-control users saying "click dot books" couldn't
activate it (Lighthouse `label-content-name-mismatch`). Its accessible name is
now the visible wordmark — the storefront PDP now passes Lighthouse at 100 for
Accessibility, Best Practices, and SEO.

---

## v0.12.4 — 2026-07-13

### SEO: real return policy in product structured data + sitemap cleanup

- **Return policy now appears in Product structured data.** Google's 2026
  merchant listings expect a return policy; product markup now carries the
  store's actual return window (read from the Returns plugin's configured
  window — never a fabricated value, and it disappears if that plugin is
  disabled). Previously it was omitted unless a separate SEO field was set.
- **Image sitemap trimmed to what Google still uses.** Dropped the
  `<image:caption>` and `<image:title>` tags Google deprecated (only
  `<image:loc>` carries meaning now).

---

## v0.12.3 — 2026-07-13

### Dashboard sidebar: submenus stay open across navigation

Opening a sidebar submenu no longer collapses when you move to a page in a
different section. The section (and hardcoded parents like Orders/Products) you
were browsing stays expanded as you navigate; collapsing one still sticks until
you reopen it.

---

## v0.12.2 — 2026-07-13

### Fix: Subscriptions dashboard page returned a 500

The **Subscriptions** dashboard page (`/dashboard/apps/subscriptions/`) crashed
with a server error: the view sorted subscriptions by a `created_at` field the
model doesn't have. Now sorted by `started_at` (the subscription's actual
creation timestamp). No data change.

---

## v0.12.1 — 2026-07-13

### Verified external references on book pages (SEO)

New `apply_external_links` tool adds a "Sources and references" section to book
descriptions, linking out to authoritative sources — Open Library, WorldCat, and
(when confirmed to exist) the author's Wikipedia page. Every link is built from
identifiers we already store or verified live before it's written, so there are
no broken/invented outbound links. Available to the dashboard AI as
`seo.apply_external_links` (approval-gated) and preserved across description
regenerations.

---

## v0.12.0 — 2026-07-13

### Storefront hero: full-height, auto-fitting titles, a floating book

The home hero now fills the viewport, and each featured title **auto-fits** —
long or short book names both settle into a tidy, professional block instead of
overflowing or shrinking to nothing. A soft 3D shadow drifts slowly behind the
cover so the book reads as floating (respects reduced-motion).

### Book form: searchable Genre & Topic pickers

In the dashboard product form, **Genres** and **Topics** are now searchable
multi-select dropdowns — type to filter, tick several — instead of long checkbox
walls.

### SEO fixes

- **Filtered listing pages now get a real title.** Tag, author, publisher, and
  search result pages were all titled "All books"; they now reflect the actual
  filter (and so do the page's structured-data name, breadcrumb, and social
  preview). Tag pages also use their editorial copy as the meta description.
- **Pagination no longer hides deep products.** Page 2+ of a listing used to
  canonicalise back to page 1 (which can de-index later products); each page now
  self-canonicalises, per current Google guidance.

### DeepSeek AI provider

Selecting **DeepSeek** in Settings → AI now works. The provider was offered in
the picker but had no driver wired up, so it errored with "Unknown AI provider";
it's now a first-class OpenAI-compatible provider (deepseek-chat /
deepseek-reasoner).

---

## v0.11.1 — 2026-07-13

### Fix: tag pages returned a 500 on production

The v0.11.0 tag landing pages (`/products/?tag=…`) crashed with a server error
on the live site. Root cause: products use a UUID primary key, but the tag
system (taggit) was wired through its default table whose object-id column is an
integer — so every tag lookup asked Postgres to compare a UUID against an
integer and failed. (Local SQLite is loosely typed and silently accepted it, so
tests passed while production broke — the classic "SQLite hid a Postgres bug".)

Tags now route through a UUID-typed join, so tag pages load and products can
actually be tagged. No action needed; existing data is unaffected.

---

## v0.11.0 — 2026-07-13

### Tag pages get a proper title + description

Every browse taxonomy — categories, collections, genres, topics — already showed
an editorial description below its title. **Tags** were the exception: a tag page
(`/products/?tag=<tag>`) had only a generic header. Now each tag can have its own
attractive title + description, written under **Products → Tag descriptions** in
the dashboard and shown below the title on the tag page. Tag links also resolve
more reliably (matched by slug or name).

## v0.10.0 — 2026-07-12

### Storefront polish + a round of fulfilment fixes

**Storefront.** The homepage no longer opens with a "Recommended for you" block
above the hero — the editor's-picks hero leads the page again. The "New &
notable" and "Staff picks" rows are now horizontal **carousel sliders** (swipe on
touch, arrow buttons on desktop) instead of tall grids.

**Order fulfilment (fixes).**

- **Manual "mark paid" now actually delivers.** Marking an order paid from the
  dashboard (for COD, bank transfer, or any out-of-band payment) used to only
  flip a flag — it never ran the fulfilment steps, so digital downloads weren't
  sent, loyalty points weren't awarded, and the payment-confirmed email never
  went out. Now it completes the order properly, once.
- **Bulk cancel works.** Cancelling several orders at once was silently doing
  nothing (and still reporting success); it now cancels them and releases their
  stock.
- **No more duplicate download emails** if an order's payment is confirmed twice.
- **Fixed runaway abandoned-cart processing** that was re-notifying and re-running
  recovery on every stale cart every half hour.

**Under the hood.** Consolidated duplicated internal helpers (conversions-API
payload builders, dashboard breadcrumbs) — no behaviour change.

## v0.9.0 — 2026-07-12

### Your shop now protects money, data, and shoppers' rights

A platform-wide correctness and compliance pass. The headline items are things
that could quietly lose money or data before this release.

**Money is safe at checkout and in refunds.**

- **No more overselling.** Two shoppers can no longer both buy the last copy.
  Stock is now reserved inside the order transaction with a hard gate — a
  short-stock order is refused and rolled back instead of being created and
  charged.
- **Refunds actually move money.** Refunds issued from the returns portal or by
  the AI assistant used to email the customer "refunded" while nothing happened
  at the payment provider. They now route through the real gateway, exactly like
  the dashboard refund button, and only send the "refunded" email once the money
  has genuinely moved.
- **No over-refunds.** A refund can never exceed what was actually paid, on any
  path (returns, assistant, or dashboard).
- **Gift cards can't be given away free.** If a gift card fails to apply at
  checkout (expired, disabled, already spent), the order is refused rather than
  charging the discounted total and eating the card.
- **Coupon limits hold under load.** A limit-one coupon can no longer be used
  twice by two simultaneous checkouts.
- Refund amounts now use the correct minor-unit conversion for every currency
  (yen, dinar, …), and each refund has its own idempotency key.

**Security.** Closed two stored-cross-site-scripting holes: product rich text is
now sanitised on save, and structured-data (SEO) output is properly escaped, so
a malicious product name or description can't run scripts on shoppers.

**GDPR / privacy (new `gdpr` module).** A self-service privacy hub in the account
area: shoppers can **download all their data** and **delete their account**, and
the storefront footer now carries **Privacy, Terms, and cookie-preference**
links (seeded legal pages included). Every request is logged for your records.
Cookie consent is now honoured correctly end-to-end — "Accept all" actually
enables analytics and personalisation (three mismatched consent signals were
unified into one). Turn the whole surface on or off under Settings → General.

**Order emails & account.** Order-confirmation emails are no longer sent two or
three times, and are sent reliably in the background with retries instead of
holding up checkout. Order status now shows correctly on the account pages
(it was blank).

**Operations.** Database backups are fixed: the image now ships `pg_dump`,
backups are written to a persistent volume that survives redeploys, and a failed
backup is now loud (logged + surfaced) instead of silently reporting success.
An internal event table that grew forever on every page view is now bounded.

## v0.8.1 — 2026-07-12

### Linda fails gracefully — and her actions are on the record

- **No more raw error dumps in chat.** When every AI provider is down, Linda
  now says what's wrong and what to do ("The active AI provider has no API
  key configured — open Settings → AI…") instead of printing
  `[All AI providers degraded …]` with a stack trace. The failure also
  reports the *configured* provider's real error — previously an
  unconfigured fallback's noise masked the actual cause.
- **Fallback only uses providers you've configured.** Providers without an
  API key no longer join the failover chain (each one used to burn a full
  timeout before failing).
- **Everything the AI writes is auditable.** Linda's write-tool calls,
  background Workers' actions, and their real outputs now land in the audit
  log — previously chat transcripts were the only record.
- **Sandbox locked down.** Linda's script sandbox is read-only for real:
  three tools that could quietly write or delete rows from inside scripts
  are now correctly gated. The legacy `/api/mcp/tools/*` endpoint (which
  accepted unauthenticated requests) now requires a staff session.
- **Settings tell the truth.** Two switches that were connected to nothing
  ("Agent purchases require approval", "Memory confidence decay") have been
  removed until the code behind them exists.

### The self-improvement loop actually heals now

- **Fixed an inert pipeline.** The engine's analyzer and its healers used
  two different naming schemes, so every approved fix ended in "no healer
  found" — the loop scanned, planned, and then did nothing. SEO gaps now
  route to the alt-text and meta-description healers, zero-result searches
  to the synonym healer, dead links to the redirect healer.
- **The safety boundary reaches your commits.** A new pre-commit gate blocks
  hardcoded secrets, raw destructive SQL, and `os.system` from ever being
  committed — and `extra_protected_paths` in settings now genuinely extends
  the AI-write protection boundary.

## v0.8.0 — 2026-07-11

### The storefront feels alive — microanimations everywhere

- **Covers morph into the product page.** Click any book on the shelf and its
  cover glides into place as the product page opens (cross-document view
  transitions), instead of a hard cut.
- **The brand period stamps itself.** Every big heading ends in the red
  dot-books period — it now presses into the page as the heading scrolls into
  view, like a type slug hitting paper.
- **The page responds as you read.** Product grids cascade in with a gentle
  stagger, a 2px red *reading ribbon* under the top bar tracks your progress
  down the page, and the top bar lifts and goes translucent once you scroll.
- **Adding to cart finally confirms.** The button flips to **“✓ Added”** while
  the cover flies to the bag, the drawer springs open with items cascading in,
  and the subtotal pops when its value changes.
- **Dozens of small touches** — prices tick when you switch editions, FAQ
  answers unfold, footer links nudge, ghost buttons invert to ink, search
  results and the mobile menu cascade in. Everything honours
  *prefers-reduced-motion* and works without JavaScript.

### The storefront feels printed — visual craft + real content

- **Paper with tooth.** The warm background now carries a faint print-stock
  grain; covers get a **spine crease and edge light** so books read as
  physical objects.
- **Missing covers become title pages.** Products without an image render a
  set title page — hairline frame, the title in Fraunces, the red period
  beneath — instead of an apologetic “No image yet”.
- **Bookish typography.** Drop caps open the product description and journal
  entries, prices are set in the serif, every section eyebrow carries a short
  red tick, and the footer signs off with a colophon.
- **Real content on the home page.** The journal teaser now shows your actual
  latest journal entries (with correct links and dates), and a new **“Browse
  the shelves”** genre index renders your top-level categories as a
  contents page.

## v0.7.0 — 2026-07-11

### A real account page

- **Settings → Your account** is now editable. Set your **first and last name,
  phone, and company** — saving your name means the top-right menu finally
  shows it instead of your email. The page also shows your account details, a
  **two-factor authentication** shortcut, and **your recent activity**.

### Unsaved-changes save bar

- Editing a product (or other forms) now shows a sticky **"Unsaved changes —
  Save / Discard"** bar, and warns before you navigate away with unsaved edits.
  **⌘S / Ctrl+S** saves. Previously the bar only worked on a full page load;
  now it works when you open a form from the sidebar too.

### Skip the setup checklist

- The **"Set up your store"** first-run checklist now has a **Skip** button, so
  stores that don't need it can hide it for good (you can still reach each step
  from Settings).

### Sidebar polish

- The left menu now has **uniform row heights and spacing**, a **consistent
  hover highlight and micro-animation across every item** (top-level, sections,
  and sub-items alike), and tighter **icon-to-label alignment**.

---

## v0.6.0 — 2026-07-11

### Pick your AI model from a permanent dropdown

- On the **Settings → AI** page, clicking **Fetch models** for a provider now
  **saves that model list**, so the "Pick from fetched models" dropdown is
  filled in every time you open the page — on any browser or device, not just
  the one you fetched from. Your currently-selected model is pre-highlighted.
- Previously the list was only remembered in the current browser and expired
  after a week; now it's stored with the provider, permanently.

---

## v0.5.2 — 2026-07-11

### Tidier left navigation

- Hovering an item in the left menu now looks the same everywhere. Sub-menu
  links (e.g. Categories, Collections under Products) used to only change
  text colour on hover while top-level items got a highlight — now every row
  gets the same subtle highlight.
- Even, consistent spacing between all navigation rows, and matching row
  heights so the hover highlight is uniform top to bottom.

---

## v0.5.1 — 2026-07-11

### Linda's tool-calling fixed (was failing on Anthropic)

- A provider mismatch made every AI action that used a tool fail with a
  cryptic *"All AI providers degraded"* error when the active provider was
  Claude (Anthropic) — and likely other strict providers. Internal tool
  names contained dots (`orders.update_status`), which those providers
  reject. Tool names are now sent in a provider-safe form, so Linda can run
  order updates, catalog edits, and every other tool again. If Linda felt
  "offline" despite a configured key, this was why.

### A calmer, sharper dashboard

- The dashboard now loads its intended typeface (Inter) everywhere — it was
  silently falling back to the system font, so text is crisper and more
  consistent across every page.
- KPI labels and table headers switched from ALL-CAPS to sentence case, and
  numeric columns align with even, tabular figures — easier to scan.
- One consistent focus outline on inputs, one accent colour across tabs,
  badges, and callouts (previously two slightly different blues), and several
  spots that ignored dark mode (status dots, "update available" tags, image
  "cover" labels) now theme correctly.

---

## v0.5.0 — 2026-07-10

### Search that spans the whole platform

- **Cmd/Ctrl + K** now opens a wide search across all of Morpheus OS. It finds
  **every dashboard page** (pulled live from the plugin registry, so new pages
  are searchable the moment they ship), plus live matches across **orders**
  (by number or customer email), **products** (name or SKU), **customers**,
  **categories**, **collections**, and **content pages** — grouped into tidy
  sections.
- Every search always offers a **"Search the shop for …"** action that jumps
  straight to the storefront results.

### A cleaner dashboard header

- Removed the redundant "Ask Linda" button from the header — Linda is always a
  keystroke away from the command bar.
- The account cluster (settings, notifications, your menu) now sits flush to
  the right edge.

### Easier AI provider setup

- Each AI provider now shows a **one-line description** in the "Add AI" picker
  so it's clear what each one is for (which are OpenAI-compatible, which run
  locally, relative cost/strengths).
- The **default model** field offers **curated model suggestions** as a
  dropdown, so you can pick a sensible model instantly — before you've even
  pasted a key. **DeepSeek** and **Hermes** are fully selectable.

### Reliability & security hardening (core)

A pass over the platform kernel fixed a batch of verified defects, each covered
by a new automated test:

- **Staff two-factor now fails *closed*.** If the second-factor check ever
  errored mid-sign-in, an enrolled staffer could previously slip through on the
  first factor alone — that gap is closed.
- **AI review panels are genuinely independent again** (a degraded provider no
  longer silently collapses several reviewers into one opinion).
- **Order status changes from the assistant** now follow the proper order
  lifecycle (and log each transition) instead of failing.
- Fixes to embeddings/semantic-search accuracy, AI provider failover, the
  DeepSeek/Hermes "configured" indicator, merchant email overrides, and the
  Packy provider endpoint.

---

## v0.4.4 — 2026-07-10

### A friendlier account menu

- The top-right account menu now shows **your name** instead of your email
  address (it falls back to email if you haven't set a name).
- Added **About Morpheus OS** and **Version & updates** shortcuts right in
  that menu, with the version you're running shown at a glance — one click
  to the full, explained changelog.

## v0.4.3 — 2026-07-10

### Consistent icons in the ad-channel dashboards

- The Google, Meta, TikTok, Pinterest, Microsoft, Snapchat and Reddit
  dashboards now use the same crisp icon set as the rest of the admin
  instead of emoji, so status markers render consistently everywhere.

## v0.4.2 — 2026-07-10

### Security hardening, order emails that actually send, and cleaner breadcrumbs

**Security**
- Closed four access holes: draft-order pages (including converting a draft
  into a real order), the promotions dashboard, a payment-intent lookup, and
  the agent GraphQL endpoint were reachable more broadly than intended —
  all now properly staff-/owner-scoped. Newsletter signup and support chat
  got rate limits.

**Order notifications that were silently broken**
- The **"your order shipped"** and **order-cancelled** emails, the
  **stock-reservation release on cancel**, and the **refund confirmation /
  affiliate clawback** all had templates and handlers but were never actually
  triggered — the underlying events weren't firing. They fire now, so those
  emails and side-effects work for the first time. (Reminder: there's still
  no dedicated "shipped with tracking" email — tracked as a follow-up.)

**Dashboard breadcrumbs**
- Breadcrumbs now follow where a page sits in the sidebar (e.g.
  "Dashboard › Multivendor › Vendors") instead of exposing internal routing
  ("Dashboard › Apps › Marketplace › Vendors").

**Under the hood**
- Restored the security-lint CI gate, fixed a flaky test, pinned a
  previously-transitive dependency, removed three unused ones, and
  de-branded a few generic-layer defaults so the platform reads neutrally
  for non-dot-books operators. Full suite 2,016 tests green.

## v0.4.1 — 2026-07-10

### Shipping rates now actually show at checkout, plus a deep decoupling pass

- **Fixed: configured shipping rates never appeared at checkout.** A broken
  internal call meant every checkout silently fell back to free "Standard
  delivery" regardless of the zones and rates you set up. Your configured
  rates (including live carrier quotes) now show; stores without matching
  zones keep the free-standard fallback.
- **Cleaner module boundaries across the platform** (invisible today,
  faster and safer changes tomorrow): checkout's payment picker, search
  ranking, "you might also like", per-visitor product ordering, the GDPR
  data export/erasure, and the login cart hand-off all flow through the
  platform event bus — so disabling a module now genuinely removes its
  behaviour everywhere.
- **One feed engine for all ad channels** — Google, Meta, Pinterest,
  Snapchat, TikTok and Microsoft product feeds now share a single
  resolver (verified byte-identical output), so feed fixes land once,
  for every channel.
- 28 new tests; full suite 2,008 green.

## v0.4.0 — 2026-07-10

### PayPal, a merchandising brain for every shelf, and a platform-wide quality pass

**Payments**

- **PayPal** — shoppers can now pay with PayPal at checkout. Enable it in
  Settings → Payments with your client ID + secret; checkout redirects to
  PayPal for approval and returns to the order confirmation. Refunds issued
  from the dashboard flow back through PayPal automatically, and webhooks
  keep order status in sync.
- **Apple Pay readiness** — the storefront now serves the Apple Pay domain
  verification file automatically, so enabling Apple Pay in Stripe "just
  works" with no file uploads.

**Dynamic merchandising (the Dynamics app, rebuilt)**

- **Take control of any shelf** — Dynamics can now control every product
  placeholder in the store (home hero, "New & notable", staff picks,
  product-list ordering, category & collection pages, page-builder
  sections) — not just its own carousels. One click per surface in
  Dashboard → Dynamics; disable the plugin and every surface reverts to
  the theme default.
- **Smart strategy** — a transparent AI blend of purchase probability
  (from your own analytics), 7-day trend, what the shopper is browsing
  right now, and freshness — with a guaranteed exploration slot so new
  products always get seen.
- **"Why is this product here?"** — every block has a live preview showing
  each product's score broken into bars (probability / trend / session /
  recency) plus Pinned and Exploring badges, and autopilot blocks can be
  previewed as any visitor segment.
- The announcement strip above the home hero is gone — the hero breathes.

**Quality & trust (platform-wide audit)**

- **Secrets are now write-only everywhere** — 14 settings fields (AI
  provider keys, Stripe secrets, Turnstile, ElevenLabs) no longer echo
  stored values back into the settings form.
- **Dashboard forms tell the truth** — invalid saves over AJAX (variants,
  coupons, customers, addresses, password) now surface the validation
  errors instead of a false "Saved".
- **Accessibility** — the home hero carousel dots meet WCAG 2.2 touch-target
  size and the shop filters are screen-reader labelled; the axe gate is
  green again.
- Under the hood: the full test suite (1,990 tests) and every CI gate is
  green; money amounts from carriers/GraphQL are precision-safe; duplicated
  helpers consolidated; 9 dead templates removed; the remaining
  architecture debt is mapped in `docs/plans/boundary-debt-2026-07.md`.

## v0.3.0 — 2026-07-10

### The analytics & intelligence wave — see what your store already knows

- **NPS dashboard** (Post-purchase → NPS) — the surveys you were already
  collecting finally add up: overall NPS with promoter/passive/detractor mix,
  response rate, a 12-week trend, per-product scores, and a recent-detractors
  feed so you can follow up while it still matters.
- **Subscription analytics** — committed MRR, recognized-MRR trend from paid
  invoices, churn rate, the trial→paid funnel, and a per-plan breakdown.
- **Customer segments (RFM)** — every customer is scored nightly on recency,
  frequency and monetary value and placed in a named segment (champions, loyal,
  at-risk, lost, new, potential). Segment changes fire an event your workflows
  can react to — e.g. a win-back campaign when someone slips to *at-risk*.
- **Marketing attribution & ROAS** — order revenue is split across the
  channels that touched the customer's journey under five attribution models
  (last-touch, first-touch, linear, time-decay, position-based), and combined
  with ad spend pulled from your connected Meta and Google accounts into a
  per-channel ROAS view.
- **Funnel drop-offs** — the conversion funnel now shows exactly where people
  leave (step-to-step drop-off table) and how this period compares to the last.
- **Overstock detection** — the stockout forecaster now also flags slow-moving
  and dead stock (90+ days of cover), lists it on the forecast page, and fires
  an event that can trigger a markdown or promo workflow.

### New app: Feature adoption
- An install-health score (0–100) on your dashboard home, plus an adoption
  matrix showing which of your installed apps are actually used (7/30/90 days)
  and which haven't been touched in 90 days — deprecation candidates. Tracking
  is aggregate-only: no per-event rows, no personal data.

### New app: Live commerce
- Schedule **live shopping events**: an embedded stream (YouTube Live or any
  HLS embed) with pinned, buyable products. Your storefront gets `/live/` and
  a per-event page that flips to a replay when you add a recording; the home
  page teases the next event automatically. Sales from an event are attributed
  through the new attribution pipeline.

## v0.2.28 — 2026-07-08

### New: an About page for your platform
- **Settings → About Morpheus** explains what Morpheus is, its three surfaces
  (storefront, dashboard, and Linda), and lists **every app installed on your
  store** — read live from the plugin registry, each with its version and on/off
  state. One clear map of everything running.

### A smoother, more consistent dashboard
- **Breadcrumbs are fixed** across the whole dashboard — pages that used to show
  the trail twice now show it once, and several edit screens gained proper page
  titles.
- **Dark-mode fixes** — the self-improvement and cohort-retention pages no longer
  render with light panels in dark mode; several tables and status badges moved to
  the standard styling.
- **Micro-animations** — dashboard cards and tiles ease in, tabs give hover
  feedback, and success moments get a subtle pop. All motion respects your
  operating system's "reduce motion" setting.
- Fixed a crash on the New / Edit workflow page.

### Storefront
- **Full-width layout** — the browse pages (home, shop, categories, search, and
  product pages) now stretch to fill the screen, and the book grid adds more
  columns on wide displays instead of enlarging the covers. Checkout and cart stay
  comfortably bounded for readability.
- Removed an empty **"Pairs with this"** section that could appear on product
  pages with nothing listed under it.

## v0.2.27 — 2026-07-03

### Linda learns (self-learning Release 1)
- **Memory recall is now semantic and question-aware.** Linda ranks her
  remembered facts against what you're asking *right now* — "where do my
  parcels leave from" surfaces "warehouse is in Berlin" even though they share
  no words. (Previously recall was recency-only, and the memory block was
  injected twice per turn — fixed, halving the token overhead.)
- **Linda now learns from her background Workers.** When a delegated job
  finishes, a short reflection pass judges the outcome, saves up to two
  durable lessons to her memory, and records the verdict on any learned skill
  the job used. A skill that keeps failing retires itself — and Linda
  remembers why, so she can tell you.
- **Tool gaps are tracked.** When a Worker clearly lacked a capability, the
  gap is remembered (`tool_gap.*`) — groundwork for Linda proposing her own
  new tools (propose-only, owner-approved) in an upcoming release.

### Linda's morning briefing (self-learning Release 2, opt-in)
- **Linda now works before you do.** Turn on Settings → General → *Linda's
  daily briefing* and every morning (06:00 UTC) a read-only agent reviews
  your last 24 hours — sales, errors, stock, reviews — and posts a short
  briefing on the dashboard home with up to three suggested actions. Each
  action is an "ask Linda" button that pre-fills the chat; nothing is ever
  executed without you. Distinct from Linda's Pulse (rule-based alert
  cards): the briefing is an open-ended, tool-grounded review.

### Linda writes her own tools — you hold the pen (self-learning Release 3)
- **Proposals queue.** Linda → Proposals (superuser only) lists every tool
  Linda drafted for herself: the source, the static safety scan, and the
  multi-model consensus verdicts side by side, with Approve / Reject / Run
  consensus review. Nothing executes and nothing touches the repo from
  drafting; approving records your decision, and code is only written — to
  a git branch, never main — when `MORPHEUS_SELF_UPDATE_ENABLED` is also
  set. Every decision is audited.
- **The flywheel.** Weekly, Linda turns capability gaps her Workers hit
  twice or more into drafted proposals in that queue — the platform now
  notices what it's missing and proposes the fix itself.
- **Evals harness.** `manage.py run_assistant_evals` scores Linda against
  20 golden tasks (tool grounding, write-gate discipline, no invented
  numbers), so every assistant change is measured against a baseline.

---

## v0.2.26 — 2026-07-02

### Privacy
- **GDPR/ePrivacy is now a single switch.** Settings → General → *GDPR / ePrivacy
  features* turns the compliance surfaces on or off in one place. When off (for
  stores outside GDPR jurisdiction — US-only, B2B), the cookie-consent banner is
  suppressed and the self-service data-export / account-erasure pages are
  disabled. Default **on**, so existing stores are unchanged.

---

## v0.2.25 — 2026-07-02

### Agent governance (enterprise Phase 1 — ADR 0027)
- **Protected agent tools now require explicit approval.** Tools that make
  sensitive writes (refunds, pricing, roles, translations…) can no longer be
  executed over the MCP admin API just because a token has the right *scope* —
  the merchant must grant that specific tool to that specific token under
  **Settings → Developer → MCP tokens → Approved protected tools**. Ungranted
  calls are refused. *(Tightening: an existing token that could previously fire
  a protected write now needs the tool ticked once.)*
- **Every agent action is audited.** Each executed MCP tool call, and every
  refusal, now writes to the core audit trail (who / what / arguments / result /
  duration) — the automated write surface is no longer invisible.
- **Per-token rate limits.** Each token has a tool-call budget per minute
  (default 120, adjustable), so a runaway or hostile agent can't exhaust the
  platform.
- **Agent order attribution now works.** When a verified shopping agent places
  an order, its id is recorded on the order (`order.metadata.agent_id`) — the
  manifest advertised this, but it was never actually wired until now.

---

## v0.2.24 — 2026-07-02

### Storefront
- **Letterpress decode, refined.** Hero titles and descriptions now animate as
  individual letters: each character "searches" in muted accent ink, then locks
  into place with a tiny settle pop — like type slugs snapping into a composing
  stick. Words wrap as units, so lines never break mid-word during the effect.
- **The hero headline is dynamic too** — it decodes once on page load. The old
  explainer paragraph under it (which described the widget rather than the
  books) is removed for a cleaner, more confident opening.
- **Friendlier micro-details.** Primary buttons lift gently on hover, and text
  selection uses the house ink-on-paper colors. All motion still honors
  `prefers-reduced-motion`.

---

## v0.2.23 — 2026-07-02

### Reliability & supply chain (enterprise Phase 0)
- **20 plugins' tests now actually run in CI.** They were pytest-style suites the
  Django test runner silently reported as "Ran 0 tests" — checkout_experience,
  subscriptions_plus, returns_portal, referrals and 16 more. A new CI step runs
  them (all 30 pass), and its glob auto-covers future plugins so the
  silently-never-run class can't recur.
- **Dependency CVE gate is now enforcing.** `pip-audit` was report-only; triaged
  clean (zero known CVEs), so any finding now blocks the merge.
- **Hash-pinned lockfile.** Dependencies floated on `>=` ranges; CI now installs
  from `requirements.lock.txt` (universal, `--require-hashes`), so CI tests the
  exact versions that would ship.
- **Webhook deliveries are idempotent.** A broker redelivery (worker
  crash/timeout after the POST) re-ran the delivery and double-POSTed the
  receiver; an already-delivered row is now skipped.

## v0.2.22 — 2026-07-02

### Storefront
- **Hero titles + descriptions "decode" on each slide.** As the home hero
  rotates through featured books, each book's title and description animate
  letter-by-letter — every character rapidly cycles through glyphs then locks
  into place (a "finding the right letter" reveal), including on first load.
  Framework-free (matches the vanilla dot_books theme), respects
  `prefers-reduced-motion` (settles instantly), is layout-contained (no shift),
  and never exposes the transient scramble to screen readers.

---

## v0.2.21 — 2026-07-02

### Observability (error logging is now one core system — ADR 0025)
- **All errors land in one place.** Celery task failures, REST + GraphQL API
  errors, and captured log records were being written to a *separate, simpler*
  `ErrorEvent` table in the observability plugin — invisible to the core error
  dashboard, the fingerprint dedup, and the self-improvement loop. They now all
  record into the core `core/errors` system, so every error is fingerprinted,
  deduped, request-correlated, and visible in one dashboard.
- **Three core→plugin boundary violations removed** (`core/brain/log_handler.py`,
  the Celery handler, and the assistant's `logs.*` tools no longer import a
  plugin for errors — boundary baseline 24 → 22). API errors now capture the
  real request (path/user/request_id) too.
- **Linda's log tools** (`logs.recent_errors`, `logs.search`) now read the
  unified core error log instead of the frozen plugin table, and surface the
  richer fields (exception class, level).
- New `core.errors.record_message()` for callers that only have a formatted
  string (no live exception). The plugin's `record_error` is now a thin
  forwarding shim into core. (Retiring the plugin's parallel table is a
  follow-up data migration.)

---

## v0.2.20 — 2026-07-02

### Reliability (enterprise-readiness Phase 1)
- **Domain events are delivered again.** The transactional-outbox publisher
  (`process_outbox`) existed but was scheduled on no Celery beat, so events
  written to the outbox accumulated undelivered and the at-least-once guarantee
  was silently broken. It now runs every minute.
- **Bounded retry on publish failure.** A transient NATS failure now keeps the
  event `PENDING` and retries on the next drain (new `attempts` counter),
  dead-lettering to `FAILED` only after 5 attempts — previously the first
  failure stranded the event permanently.

### CI hardening
- `manage.py check --deploy` is now an **enforcing** gate at ERROR level
  (was a no-op `--fail-level WARNING || true`).
- `mypy` (already configured, never run) now produces a **non-blocking baseline
  report** over the `core/` kernel in CI.

---

## v0.2.19 — 2026-07-01

### Dashboard UI
- **Help "?" tooltips now actually work.** The `context-help` component had no
  styling, so field help text rendered inline (cluttering the page). It's now a
  small **?** that reveals its text in a tidy tooltip on **hover, keyboard
  focus, or click/tap** — applied everywhere the "?" already appears (settings,
  products, orders, home, AI providers…).
- **Wider, standardised page width.** The dashboard content area was capped at
  1280px and most pages re-capped themselves *narrower* still (settings at
  896px, order detail at 1024px), leaving big empty margins. The global cap is
  now 1536px (`max-w-screen-2xl`) and the working pages (home, lists, settings,
  analytics, product/order detail) drop their own caps to fill it — one
  consistent width. Focused single-action forms (refund, fulfil, address, new
  order) intentionally stay narrow for readability.

---

## v0.2.18 — 2026-07-01

### Plugins / modularity (ADR 0023)
- **Disabling a plugin now reliably removes its dashboard/storefront surfaces.**
  Fixed a class of bug where a disabled plugin's contributed cards, KPIs, and
  feed items could keep rendering: the hook bus now skips any handler owned by a
  disabled plugin (previously `deactivate()` left `ready()`-wired hooks in
  place, so they kept firing). This makes **every** `register_hook`-based
  contribution disable-safe at once.
- **Book Product's "Book details" card** on the product editor was hard-wired
  into the dashboard (so it showed even when book_product was disabled). It now
  contributes through the `PRODUCT_FORM_CARDS` / `PRODUCT_FORM_SAVED` hooks like
  every other product-form card, so it appears only while the plugin is enabled.

---

## v0.2.17 — 2026-07-01

### Assistant
- **Linda's per-page helper is now dismissible per page.** The card's control is
  a **✕** that hides Linda *on that specific page* — it stays gone there on
  reload, but still appears on pages you haven't dismissed (replacing the old
  global Hide/Show toggle). Dismissing a page also skips its AI call entirely.
  The master on/off switch remains **Settings → General → AI-assisted tips &
  help** (`ai_page_help`).

---

## v0.2.16 — 2026-07-01

### Localization
- **Multi-language storefront URLs (opt-in).** The storefront can now serve each
  language on its own URL: the **core language** (Settings → General) stays at
  the root (`/product`), every other enabled language gets a prefix (`/fr/…`,
  `/sr/…`), with `reverse()` keeping the prefix as visitors browse. A **language
  switcher** appears in the footer once more than one language is enabled.
  Enable languages per environment with `MORPHEUS_LANGUAGES="en,fr,sr"` (default
  is the core language alone — no change until you opt in). Dashboard + API stay
  unprefixed. Per-language `hreflang` is the next step.

---

## v0.2.15 — 2026-07-01

### Localization
- **Translations are now a programmable API** — external translators and
  translation tools can read/write translations over **MCP and GraphQL**, not
  just the dashboard. New scopes `i18n.read` / `i18n.write` gate the access.
  - MCP tools: `i18n.languages`, `i18n.get_translations`, `i18n.set_translation`
    (any object, addressed by `content_type` + `object_id`).
  - GraphQL: `enabledLanguages`, `translations(...)` queries + a
    `setTranslation(...)` mutation. The same bearer token works from either.

---

## v0.2.14 — 2026-07-01

### SEO
- **Category & collection pages now advertise a price range** in their
  structured data (schema.org `AggregateOffer` — e.g. "from $5–$30, 240 items").
  Google and AI Overviews reward this on listing pages, improving how
  categories surface in rich results and AI answers. Builds on the existing
  `CollectionPage`/`ItemList` JSON-LD; a reusable `aggregate_offer()` helper is
  available for variant ProductGroups next.

---

## v0.2.13 — 2026-06-30

### Updates
- **Crash-safe one-click update.** The **Settings → Updates** page now always
  shows an **Update now** button when a version is available. Applying is
  hardened against bad updates: it **backs up**, then **boot-probes the new
  code in a fresh process before migrating** (so a non-bootable update reverts
  with the database untouched), and **refuses updates that change dependencies**
  (those need an image rebuild — avoids the "imports a package that isn't
  installed" crash). Any failure auto-rolls-back to the prior version.

---

## v0.2.12 — 2026-06-30

### Updates
- **Automatic "update available" check.** Morpheus now checks the upstream repo
  once a day and, when a newer version is available, surfaces an **Update
  available** item in the dashboard activity feed linking to **Settings →
  Updates** — so you know to update without manually checking. The check is
  cached (no per-page network cost) and fails silently if git/network is
  unavailable. Applying updates stays opt-in (`MORPHEUS_SELF_UPDATE_ENABLED`)
  and CLI/dashboard-driven as before.

---

## v0.2.11 — 2026-06-30

### AI providers
- **AI providers panel is now a connection manager.** Instead of one long form
  listing every possible provider, the panel shows **only the providers you've
  connected**. An **"Add AI"** button opens a picker of the remaining provider
  templates; connect one and it joins the list (and leaves the picker). Each
  connected provider can be **disconnected** — clearing its key and, if it was
  the active provider, reassigning the active one automatically.
- **DeepSeek is now a supported provider** (OpenAI-compatible; `deepseek-chat` /
  `deepseek-reasoner`). Connect it under Settings → AI providers.
- **Fixed: selecting apikey.fun reported "No AI provider selected."** apikey.fun
  was offered in settings but had no provider implementation; it now resolves
  and runs like any other provider.

### Dashboard
- **Icon set reverted to Remix Icon** for a consistent line-weight look across
  the dashboard.
- **Per-page Linda helper** — when *AI-assisted tips & help* is enabled
  (Settings), Linda explains each dashboard page and advises what to do next.

### Performance
- The active storefront channel is now resolved once per request, removing a
  duplicate lookup that ran on every page.

---

## v0.2.10 — 2026-06-28

### Morpheus Brain
- **New "Advisory" tab — a long-form AI briefing on your whole site.** Beyond the
  short prioritized recommendation list, the Brain now writes a comprehensive,
  readable advisory in prose: what's healthy, what needs attention, and the
  concrete improvements, patches and changes to make next — grounded in the live
  platform signals (errors, code quality, SEO/content, storefront performance,
  plugin health). It regenerates automatically once a day and on demand via
  **Regenerate briefing**, and degrades cleanly to a prompt when no AI provider
  is configured.

### Dashboard
- **Seamless navigation.** Moving between dashboard pages no longer flashes —
  the sidebar now does an in-place content swap (with a quick, intentional
  cross-fade) instead of a full reload, and a double-animation flicker on every
  page change was removed. Respects "reduce motion".

### Storefront
- **Nicer browse tiles.** The Genres / Topics / Authors index tiles got a visual
  pass — clearer hover, an affordance arrow, designed placeholders, focus rings.

### Fixes & hardening
- AI "Ask Linda" buttons now HTML-escape their values (defense-in-depth); a
  dashboard settings-load failure is now logged instead of silently masked; the
  nav cart-count is resolved in one query instead of two; and a book-product save
  error now surfaces in logs instead of being dropped under a false "Saved".

### Developer
- **Architecture guard-rails.** CI now blocks any *new* wrong-direction
  `core/ → plugins.installed` import (baseline-and-ratchet, so the debt can only
  shrink) and runs the plugin disable-test as its own gate.

## v0.2.9 — 2026-06-28

### Fixes
- **Restored the staff dashboard.** A recent change used the `get_guided_ux_mode`
  template tag in the dashboard base template without loading its library, which
  could 500 every dashboard page. Now loads `morph_dashboard`.
- **Added missing migrations** for the analytics-tracking, guided-UX, and
  dynamic-products grid models that had shipped without them (additive only —
  new columns/tables), so those features work in production and the migration
  gate is green again.
- **AI provider API keys are now write-only in settings.** The provider key shows
  as `********` and a blank/unchanged submit preserves the stored key instead of
  overwriting it — previously, saving AI settings without re-typing the key would
  have wiped it.

## v0.2.8 — 2026-06-25

### Security
- **Staff SSO (SAML 2.0 + OIDC), OFF by default.** New `staff_sso` plugin lets
  staff sign in through your identity provider (Okta, Entra/Azure AD, Google
  Workspace) via **OIDC** or **SAML**, configured at **Settings → Developer →
  Staff SSO** (issuer/client or IdP metadata, plus an email-domain allowlist and
  optional group claim). First sign-in just-in-time provisions the staff account;
  a "Sign in with SSO" button appears on the staff login page once configured.
  Crucially, **SSO does not bypass MFA** — an enrolled staffer is still required
  to pass their authenticator code, whether they came in by email-OTP, OIDC, or
  SAML. SAML assertions must be signed. Email-OTP stays as the break-glass path;
  disabling the plugin reverts sign-in to email-OTP exactly.
- **Fixed: dashboard settings panels echoed stored secrets in clear text.** The
  shared settings renderer ignored password fields, so saved secrets (API keys,
  the new SSO client secret, etc.) were rendered into the page as readable values.
  Secret fields are now **write-only** — masked, never pre-filled, and a blank
  submit preserves the stored value. Applies to every plugin's settings panel.

### Storefront
- **Admin "Edit" button on the storefront.** When you're signed in as staff, the
  top admin bar now shows an **Edit** link that deep-links to the dashboard editor
  for whatever you're viewing — product, **category** (a new category edit page),
  **collection**, **genre**, **topic**, or **CMS page**. Customers see nothing.

> **Operator note:** this release adds two native Python dependencies
> (`pyjwt[crypto]` for OIDC, `python3-saml`/`xmlsec` for SAML). They ship as
> prebuilt wheels, but the deploy image must reinstall `requirements.txt` on this
> release. Both SSO providers are inert until an IdP is configured.

---

## v0.2.7 — 2026-06-24

### Security
- **Staff two-factor authentication (MFA).** New `staff_mfa` plugin adds a TOTP
  second factor (authenticator apps — Google Authenticator, 1Password, Authy)
  on top of the existing email sign-in code for staff accounts. Self-service
  enrollment lives at **Settings → Two-factor authentication** (scan a QR,
  confirm a code, save one-time recovery codes). Lost your device? A recovery
  code gets you in; an admin can run `python manage.py reset_mfa <email>` as a
  break-glass (audited). **Enrolled** staff are always challenged at sign-in.
  Enforcement for *un*enrolled staff is **opt-in**: turn on **Require MFA for all
  staff** in **Settings → Developer → Staff two-factor** to prompt them to enroll
  at sign-in (a first-admin grace prevents locking the org out before anyone has
  enrolled; hard per-page gating lands in a follow-up). Email-OTP stays factor
  one and is unchanged; disabling the plugin reverts sign-in to single-factor
  exactly. Customers are unaffected.

### Agentic commerce
- **ACP (Agentic Commerce Protocol) — Phase 1, OFF by default.** New
  `agentic_checkout` plugin lets AI shopping agents discover products and build a
  checkout session against the platform — a discovery manifest at
  `/.well-known/acp.json`, an ACP product feed, and the `checkout_sessions`
  create/read/update/cancel endpoints (Bearer-scoped via `acp.checkout`), backed
  by the existing cart. Conformant to the real ACP `2026-04-17` spec. The payment
  path (Stripe Shared Payment Token) is **Phase 2** and intentionally returns
  "unsupported" until a merchant enrols — so nothing charges yet. Ships disabled;
  enable from Dashboard → Apps.

### Plugins
- **Abandoned-cart recovery is now one consent-checked drip — and the
  double-send is fixed.** Previously *two* recovery emails went out per abandoned
  cart (a core handler and a marketing task both fired). Consolidated into a
  single multi-step sequence owned by the `cart_abandonment` plugin: configurable
  send delays (default 1h / 24h / 72h), merchant-editable templates
  (**Settings → Notifications**), a marketing-consent check, and a guard that
  stops once the cart converts. Disabling the plugin now removes recovery email
  entirely.

### Fixes
- **Loyalty points no longer accrue to guest checkouts** (the guard compared
  against the wrong default, so guest orders could mint points with no account to
  hold them).
- **Digital downloads can't exceed their limit under a race** — the
  download-count claim is now atomic, closing a window where a rapid double-click
  could grant an extra download.
- **Webhooks dispatch only after the transaction commits** (and are suppressed on
  rollback), so a subscriber never sees an event for a change that didn't land.

### Developer
- **Supply-chain scanning:** weekly Dependabot PRs (grouped) plus a `pip-audit`
  CVE check in CI (advisory).

---

## v0.2.6 — 2026-06-21

### Plugins
- **Linda now reports the real product count.** Her `products.search` tool
  returned `count = page size` (capped at 20–50), so she'd say "there are ~40
  books" for an 859-product catalogue. It now returns `total` (the true number
  of matching products) alongside the sample, and a new **`products.count`** tool
  answers "how many products/books" exactly. Linda's prompt points at it.
- Retired the PDP **"Pairs with this / Goes well together"** recommendation block
  (cropped book covers; only rendered for the few products with co-purchase
  data). The recommendation service stays available for reuse.

---

## v0.2.5 — 2026-06-21

### Core
- **Morpheus Brain now actually sees application errors.** A fail-soft, loop-safe
  logging handler routes ERROR-level app logs into the error pipeline
  (`ErrorEvent` → error_log collector → `SiSignal`), so the Brain's **Errors tab**
  and AI analysis reflect real exceptions — completing the "analyze error logs"
  capability (previously those logs only hit the console).
- **Brain correctness fixes:** merchant insights are now fed to the AI digest
  (they were gathered + shown but never sent to the model); a transient AI-provider
  failure no longer pins a stale error banner for 24h (only successful analyses are
  cached); and the signal snapshot is cached ~90s (was ~18 DB queries on every page
  load), refreshed on demand when you click *Refresh analysis*.

---

## v0.2.4 — 2026-06-21

### Core
- **Fixed: CSP violation flood (~2,500/day).** The storefront Content-Security-
  Policy (report-only) didn't allow `cdn.ampproject.org`, which the webstories
  plugin's `<amp-story-player>` PDP embed loads (amp-story-player + amp-loader +
  v0). Added it to `script-src`/`style-src`, silencing the reports. (Report-only,
  so nothing was broken — just noise the self-improvement engine kept flagging.)
- **Fixed: false plugin-validation error on every boot.** `validate()` checked a
  plugin's `requires` only against other plugin names, so a `core.*` dependency
  (e.g. `ai_stylist` → `core.audit`) wrongly logged "not installed" even though
  the core app is always present. `core.*` deps now resolve against
  `INSTALLED_APPS`; the `ai_stylist`/`core.audit` boot error is gone.

---

## v0.2.3 — 2026-06-21

### Plugins
- **Fixed:** the *Version & updates* page rendered blank in production — it
  depended on a markdown library that isn't installed there. Replaced with a
  small built-in renderer (no external dependency), so the release notes now
  show. (If this page was empty for you, that's why.)
- Settings nav: **Morpheus Brain** and **Version & updates** are now pinned
  right under **General** instead of buried at the bottom of the settings list.

---

## v0.2.2 — 2026-06-21

### Core
- Plugin contract gains `enabled_by_default` — a plugin can ship
  **installed-but-OFF**, opting in from Dashboard → Apps (default stays on, so
  existing plugins are unchanged).

### Plugins
- **Booking marketplace** (new, **off by default**): a multivendor *services*
  marketplace alongside the product one. Vendors offer time-slot
  `BookableService`s with weekly availability; customers book a slot at
  `/bookings/`. Manage at Dashboard → Bookings. Enable it from Dashboard → Apps.

---

## v0.2.1 — 2026-06-21

### Storefront
- Author page: the author image now spans the full content width instead of a
  cramped 160px thumbnail.

---

## v0.2.0 — 2026-06-20

### Core
- **Morpheus Brain** is now a **core capability** (`core/brain/`), not an app —
  always on (the surface plugin is protected from disable). It continuously
  reads the platform's own signals (code-quality + error-log findings from the
  self-improvement immune system, plugin health, SEO/content audits, storefront
  Core Web Vitals) and uses your **configured AI provider** to synthesize a
  prioritized list of fixes, improvements, and feature ideas. Refreshes on a
  6-hour beat and on demand; degrades cleanly when no AI is configured.
- **More comprehensive error/warning logging** — `django.request`,
  `django.security`, `django.db.backends`, `celery`, and Python `warnings` now
  flow through the log stream the error-log collector + Brain read.

### Plugins
- **Morpheus Brain** surface (Settings → Morpheus Brain): tabbed console for the
  above (Overview, Plugins, Code, Errors, Content & SEO, Storefront,
  Improvements) with a one-click **Refresh analysis**.

---

## v0.1.0 — 2026-06-20

The current foundation release. Highlights since the platform came together:

### SEO & structured data (rich results)
- **One complete, valid Product** rich result per product page — offer with
  price, availability, shipping, return policy, `itemCondition`, and
  `priceValidUntil`, plus absolute `image`, `brand`, and review stars
  (`aggregateRating` + `review`) when reviews exist.
- **Google Book structured data** — Work → Edition → ReadAction, with `sameAs`
  (Open Library) + OCLC identifier so public-domain titles are reconcilable
  without fabricated ISBNs.
- **VideoObject** for product videos, and an enriched **Organization** graph
  (contact point + postal address) for the brand knowledge panel.
- **Rich-snippets editor** gained Book + enriched Article types.
- Fixed the AMP Web Story canonical error (stories are now standalone /
  self-canonical).

### Catalog & books
- **Identifier fields** (ISBN-13 / OCLC / Open Library work ID) on the product
  edit form, plus a bulk `backfill_book_identifiers` command that reconciles the
  catalog against Open Library with conservative title+author matching.

### Storefront
- Editorial homepage hero, bigger grid titles with first-sentence excerpts.

### Platform
- **Version & updates** page in Settings (this page), backed by this document.
- **Morpheus Brain** (Settings → Morpheus Brain) — a tabbed intelligence console
  that aggregates plugin health, code analysis & self-improvement, content &
  SEO, storefront Core Web Vitals, and improvement recommendations, read-only
  from the platform's own engines.
- **Book identifiers** — ISBN-13 / OCLC / Open Library fields on the product
  form, plus the `backfill_book_identifiers` bulk reconciliation command.

_Earlier engineering history (PR-level) lives in [`CHANGELOG.md`](../CHANGELOG.md)._
