# Accessibility — Morpheus OS

> **Compliance target:** WCAG 2.2 AA.
> **Why:** EU Accessibility Act enforces WCAG 2.2 AA from 28 June 2025
> for any new digital product sold into the EU; existing services
> have until 28 June 2030. Accessibility is also a measurable conversion
> lever (8-15% of customers benefit directly from a11y improvements).

## Compliance status (live snapshot)

| Surface | Status | Last audited | Notes |
|---|---|---|---|
| Storefront — home, PDP, listings | 🟡 In progress | Auto (axe-core CI) | Most violations are color-contrast on legacy templates. |
| Storefront — cart, checkout | 🟡 In progress | Auto (axe-core CI) | Form-label gaps on shipping address inputs. |
| Storefront — account pages | 🔴 Unaudited | — | Pending Phase 2 rollout. |
| Storefront — journal / CMS pages | 🟢 Compliant | Auto (axe-core CI) | Editorial templates audited. |
| Dashboard (admin) | 🟠 Best-effort | Manual | Not customer-facing; lower priority. |

## CI enforcement

Two GitHub Actions workflows gate WCAG regression:

- [`.github/workflows/lighthouse.yml`](.github/workflows/lighthouse.yml) — Lighthouse-CI's a11y category ≥ 0.92 across 5 URLs.
- [`.github/workflows/accessibility.yml`](.github/workflows/accessibility.yml) — full axe-core ruleset
  (`wcag2a wcag2aa wcag21a wcag21aa wcag22aa best-practice`) across the same URLs.

Both audit the **live** store, so they run after the `deploy-smoke`
workflow has seen production converge on a pushed version (a
`workflow_run` trigger), or by hand (`workflow_dispatch`) — never on the
push itself, when the store still serves the previous build, and never on
a PR, whose code the live store does not carry. axe waits 2 s after load
so the theme's scroll-reveal fade has settled (mid-fade text reads as a
contrast failure). Reports are uploaded as the `axe-reports` artefact for
30 days. Structural findings get a rendering guard in
`themes/test_a11y_markup.py` so they fail before a deploy, not after.

## What WCAG 2.2 AA actually requires

Highest-impact criteria for an e-commerce site:

1. **1.4.3 Contrast (Minimum) — AA.** Body text 4.5:1 vs background;
   large text 3:1. Common failure: light grey body copy on cream
   editorial themes.
2. **2.4.7 Focus Visible — AA.** Every keyboard-focusable element has
   a visible focus indicator. Common failure: `outline: none` reset
   without a replacement.
3. **3.3.2 Labels or Instructions — A.** Every form input has a label
   or aria-label. Common failure: placeholder-only inputs.
4. **4.1.2 Name, Role, Value — A.** Custom controls (dropdowns, modals,
   tabs) expose role + state to assistive tech. Common failure:
   `<div role="button">` without `tabindex`/`aria-pressed`.
5. **1.3.1 Info and Relationships — A.** Tables, lists, headings used
   semantically. Common failure: visual hierarchy implemented with
   styling-only `<div>`s.
6. **2.5.8 Target Size (Minimum) — 2.2 AA (new).** Pointer targets at
   least 24×24 CSS px. Common failure: dense icon-buttons in admin
   toolbars.

## Known violations + remediation plan

Tracked in the self-improvement engine's `code_quality` collector
(axe rules surface as `code_quality:axe:<rule>:<path>` signals). The
backlog dashboard shows them by class with a per-fix workflow.

## Manual audit cadence

- Lighthouse-CI + axe-core CI run against the live store after every
  production deploy (automated floor).
- Full WCAG 2.2 AA manual audit annually (external auditor recommended).
- Keyboard-only navigation walkthrough on every checkout-flow PR
  (manual; checklist below).

### Keyboard walkthrough checklist (checkout path)

- [ ] Land on `/`, `Tab` through to "Shop now" — first focus stop visible.
- [ ] Reach product card, `Enter` opens PDP.
- [ ] PDP — `Tab` through gallery / variant / qty / Add to Cart.
- [ ] Cart drawer / page — `Tab` reaches quantity inputs, "Remove",
      "Checkout".
- [ ] Address form — `Tab` order matches visual order; `Esc` closes
      autocomplete dropdowns.
- [ ] Payment — wallet buttons reachable; Stripe iframe focusable.
- [ ] Order-confirmation — focus moves to confirmation heading on load.

If any step fails, file a recommendation under the `accessibility`
class in the self-improvement backlog.

## References

- [WCAG 2.2 — W3C Recommendation](https://www.w3.org/TR/WCAG22/)
- [EU Accessibility Act — Directive 2019/882](https://eur-lex.europa.eu/eli/dir/2019/882/oj)
- [axe-core rules](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md)
- [Lighthouse a11y audits](https://developer.chrome.com/docs/lighthouse/accessibility)
