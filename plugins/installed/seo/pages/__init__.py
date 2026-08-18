"""What page is this? — the question every SEO decision starts from.

`resolve_page()` turns a request (plus, when available, the template context)
into a `SeoPage`: the kind of page, the object it is about, its clean title, and
whether it should be indexed. The head builder, the sitemap, the audit and the
dashboard inspector all read that one object, so "the PDP is indexable but the
cart is not" is decided once rather than in each template.

Apps that own a URL shape answer `SEO_RESOLVE_PAGE` instead of being imported
here — that is how book_product's author landings and cms's journal pages get
first-class SEO without seo depending on them.
"""

from .resolve import resolve_page
from .types import SeoPage

__all__ = ['SeoPage', 'resolve_page']
