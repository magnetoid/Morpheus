# Theme settings page and Dawnchild's Christmas look: design

Approved by the owner on 2026-11-21 ("Approve design"). This is a short design: it records what was agreed
in the conversation.

## Intent

The owner wants a Christmas look on Dawnchild (beta.dawnchildbooks.com) before 1 December 2026. A throwaway
spike on the live page showed it, and the owner approved that look. The pieces are:

- **Hero:** snow in three depths with gusts, a garland of twinkling lights, frost feathers in the corners, a
  snow cap growing on the plaque and a drift along the bottom. The picture itself is untouched. Everything
  sits on the bordeaux background.
- **Header:** a snow ledge with icicles, holly on the wordmark, and a burst of flakes when the basket count
  rises.
- **Footer:** pines and a cottage standing on the line above Privacy Policy. The cottage window flickers
  and smoke rises from the chimney. The footer also gets falling snow, a cap on its wordmark and a sealed
  letter beside the newsletter that flies off when the form is sent.

The owner's rule (2026-11-18) is that everything ships inside Morpheus as an option any store can switch
on. Each choice is a setting, with the code that reads it and a Linda tool, all in the same change. Theme
settings fail that rule today, because nobody can change them: there is no dashboard screen and no Linda
tool, only a database write. So the Christmas look needs a theme settings page first.

## Goals

**Release 1: a settings page for the active theme, in any store.**
- It sits under Settings → Storefront, as a card named "Theme: <label>", at `/dashboard/settings/theme/`.
- Its fields come from the active theme's `get_config_schema()` and render exactly like an app's settings
  card: text, switch and choice list. It saves the same way.
- It is gated like the other settings pages.
- Linda gets two tools:
  - `theme.describe` reads the active theme and each of its settings: title, type, allowed values,
    default and current value.
  - `theme.set` changes one setting. It has `requires_approval=True`, so it waits for the merchant's own
    yes. It uses the same type checks as `settings.set`.
- The page is found by the dashboard search (Cmd+K). The storefront app's `help.md` gains a section on
  it.
- **Freshness.** `MorpheusTheme.get_config()` caches per process and is never invalidated, so a save
  would show on one worker until a restart. Theme config is re-read at most 10 s after it was last read,
  the same as `Plugin.config_fresh_s` for storefront. A save also clears the cache in the process that
  saved.

**Release 2: Dawnchild's "Christmas look".**
- Three new Dawnchild settings:
  - `christmas_look`: `off` (the default), `dates` or `on`. `on` lets the owner preview the look before
    the season.
  - `christmas_from`: day and month written `DD-MM`, default `01-12` (1 December).
  - `christmas_until`: `DD-MM`, default `06-01` (6 January).
  - The dates apply every year, on the store's clock, and the range may cross New Year.
- When the look is on, the theme's own templates render the pieces above, from one theme stylesheet and
  one theme script. The script carries the CSP nonce and attaches behaviour with `addEventListener`.
- One pause button stops all the motion, both in the hero and in the footer. The choice is remembered in
  `localStorage`, wrapped in try/except.
- `prefers-reduced-motion` gets a still version: the final states, no motion.
- The snow never delays the hero image (LCP). It starts after the image loads, and it pauses when the
  hero is off screen or the tab is hidden.
- The same release fixes two things in Dawnchild's footer:
  - The newsletter field and its "Send me the letter" button are black text on black today, so neither
    can be read.
  - On phones the pines get room above the last footer link.

## Non-goals

- A generic "seasonal decorations" app for every theme (approach B).
- Switching themes from the dashboard. Linda's `theme.activate` already does it.
- Editing design tokens (colours, fonts).
- Editing an inactive theme's settings.
- Any other season.

## Anti-goals

- **A switch that does nothing on some workers** (see Freshness above).
- **Motion with no way to stop it.** WCAG 2.2.2 requires a pause for motion that lasts longer than 5 s.
- **A slower hero image.**
- **Inline handlers or scripts without the nonce.** They would break on the payment pages.
- **A setting no code reads.** `core/tests/test_settings_keys_have_readers.py` covers app schemas. The
  theme keys need readers in the same change.

## Approaches

- **A, chosen: two releases.** Release 1 is the theme settings page and the Linda tools, for any theme.
  Release 2 is the Christmas look as a Dawnchild theme setting.
  - It meets the owner's rule.
  - It lets the owner set `hero_link_url` today.
  - The creative pieces stay with the markup they decorate.
- **B: a "seasonal decorations" app for all themes.** It is much more work for little gain, because the
  best pieces are tied to Dawnchild's markup: the plaque, the footer line, the newsletter. Rejected.
- **C: switch by dates in code, with no setting.** It is the fastest, but it breaks the owner's rule: a
  store could not turn it off, and neither could Linda. Rejected.

## Decided

- No new app.
  - The page is contributed by the storefront app, because the theme layer is the storefront's. It is
    filed under the existing Storefront settings category.
  - The Christmas settings live in `themes/library/dawnchild/theme.py`.
- Linda's tools follow the shape of `settings.describe` / `settings.set` (`system.read` /
  `system.write`). The page is gated on the same capability as other settings pages (`system.write`).
- The defaults leave every store as it is today. Christmas is off until someone switches it on.

## Left to the builder

- The exact form markup of the day-and-month fields. A text field that takes `DD-MM` (the order the owner approved) is acceptable if the
  schema renderer has no date kind.
- Whether `theme.describe` and `theme.set` live with `theme.activate` in
  `core/assistant/tools/admin_ops.py` or in the storefront app.
- How the Christmas templates are split into includes.
