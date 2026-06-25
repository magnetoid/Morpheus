from morph.settings import *  # noqa

# Pre-existing breakage in 11 sibling plugins (literal 'auth.User' FKs after
# AUTH_USER_MODEL swap; ugc_reviews/returns_portal reference non-existent
# reviews.Review / orders.OrderLine) poisons the system check AND the test-DB
# migration graph. They are unrelated to the inventory StockoutAlert task.
# Drop them for this isolated model test only.
_BROKEN = {
    'plugins.installed.ai_stylist',
    'plugins.installed.discovery_quiz',
    'plugins.installed.drops',
    'plugins.installed.journal',
    'plugins.installed.one_click',
    'plugins.installed.referrals',
    'plugins.installed.returns_portal',
    'plugins.installed.rich_post_purchase',
    'plugins.installed.save_for_later',
    'plugins.installed.subscriptions_plus',
    'plugins.installed.ugc_reviews',
}
INSTALLED_APPS = [a for a in INSTALLED_APPS if a not in _BROKEN]  # noqa: F405
SILENCED_SYSTEM_CHECKS = ['fields.E300', 'fields.E301', 'fields.E307']
