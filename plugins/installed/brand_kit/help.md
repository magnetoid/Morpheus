---
summary: Turns a saved set of brand colors, fonts, spacing and corner rounding into values the storefront theme can use.
---

## What it's for

This app holds a brand "look" — colors, fonts, spacing and corner rounding — plus a library of brand assets such as images, fonts and icons. When one set of these values is marked active, the storefront reads them instead of its own built-in defaults, so the whole theme can share one set of brand values.

## Good to know

There is no dashboard screen today for creating a set of values, marking one active, or adding a brand asset — that has to happen outside the dashboard. The one entry under [](settings:brand_kit) does not currently change which set is used. Either way, every storefront page still renders correctly: with the brand's own colors and type when a set is marked active, or with sensible built-in values when none is. Turning this app off removes the brand's values from the storefront and brings back the built-in look.
