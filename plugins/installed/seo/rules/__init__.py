"""Indexability policy: which URLs of a listing deserve to exist in an index.

A storefront category is not one URL. It is the category, times every sort
order, times every facet value, times every combination of facets, times every
page of results, times whatever a campaign link appended — and each of those is
a page a crawler can fetch and an index can hold. Deciding which ones count is
the single highest-leverage lever a store has over how its crawl budget is
spent, and until now Morpheus had one global switch for it.

Two modules, because there are two mechanisms:

* `params` — the per-parameter rules (`IndexRule`) and the canonical they
  produce.
* `pagination` — `?page=N`, which is not a facet: page 2 is different content
  and must stay indexable, so it has its own policy rather than a rule row.
"""

from plugins.installed.seo.rules.pagination import (
    page_number,
    page_one_redirect_target,
    page_value,
    paginated_title,
)
from plugins.installed.seo.rules.params import (
    ParamDecision,
    blocked_param_patterns,
    decide_params,
    invalidate_index_rules_cache,
)

__all__ = [
    'ParamDecision',
    'blocked_param_patterns',
    'decide_params',
    'invalidate_index_rules_cache',
    'page_number',
    'page_one_redirect_target',
    'page_value',
    'paginated_title',
]
