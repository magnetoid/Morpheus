# Supernatural Shop

Dark storefront theme for [supernatural-shop.com](https://supernatural-shop.com).

Morpheus theme names are snake_case: **`supernatural_shop`**. The public label is **Supernatural Shop**.

## Activate

```bash
export MORPHEUS_ACTIVE_THEME=supernatural_shop
python manage.py runserver
```

Do not set this on the DotBooks Coolify app (`ghtnqf6lw2bg5229lv1sf4h9`). That instance stays `dot_books`.

## Files

- `theme.py` — manifest
- `templates/storefront/` — storefront overrides
- `sections/` — CMS section bundle
- `static/supernatural_shop/` — assets

See `docs/THEME_DEVELOPMENT.md`.
