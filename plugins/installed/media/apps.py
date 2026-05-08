"""
media — central asset library for the platform.

Until now every model that wanted to attach a file declared its own
`ImageField` / `FileField` (vendor logo, category image, OG image,
digital_file, ProductImage, …). That works but produces siloed
uploads — one file per upload site, no cross-resource reuse, no
search across the library, no way to know whether deleting a record
orphans a useful asset.

This plugin introduces a single `MediaAsset` model that any other
plugin or template can reference. Once an asset is uploaded it can
be reused everywhere — products, CMS pages, email templates, theme
sections, metafields. A delete-when-orphaned policy is left to the
referencing surface; MediaAsset itself is opt-in cleanup so brief
unreferenced periods don't lose work in progress.

Why this matters: it's the foundation for both the metafields plugin
(file-typed metafields point at MediaAsset.id) and the future theme
builder (drop assets into sections without re-uploading).
"""
