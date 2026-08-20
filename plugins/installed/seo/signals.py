"""Signal wiring: redirect-cache invalidation and automatic slug history.

Two jobs, both of which have to happen on *every* write path rather than in the
dashboard view that happens to be the most common one:

* **Cache invalidation.** The redirect resolver reads a compiled ruleset out of
  the cache. A merchant who adds a rule and sees it do nothing for five minutes
  concludes the feature is broken — and a rule that was *deleted* but still
  served is worse. `post_save`/`post_delete` fire for the dashboard, CSV
  import, an assistant, the admin, and a queryset delete alike.

* **Slug history.** Renaming a product renames its URL, and every inbound link
  and every ranking pointing at the old one dies with no error anywhere. The
  `pre_save` watcher compares the stored slug against the incoming one and mints
  the 301 the merchant would otherwise have to remember to write by hand.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save, pre_save

logger = logging.getLogger('morpheus.seo')


def wire() -> None:
    """Connect every receiver.

    Idempotent by construction: every `connect` carries a `dispatch_uid`, so
    calling this twice (a re-`ready()`, a runtime plugin re-enable) registers
    each receiver once rather than doubling it.
    """
    from plugins.installed.seo.models import IndexRule, Redirect, SiteSeoSettings

    post_save.connect(_on_redirect_saved, sender=Redirect, dispatch_uid='seo.redirect_cache_save')
    post_delete.connect(
        _on_redirect_saved, sender=Redirect, dispatch_uid='seo.redirect_cache_delete'
    )
    post_save.connect(
        _on_index_policy_changed, sender=IndexRule, dispatch_uid='seo.index_rule_save'
    )
    post_delete.connect(
        _on_index_policy_changed, sender=IndexRule, dispatch_uid='seo.index_rule_delete'
    )
    # The compiled ruleset also bakes in the legacy `noindex_query_params` list,
    # so a merchant editing that field on the settings page has to see it take
    # effect now rather than whenever the cache happens to expire.
    post_save.connect(
        _on_index_policy_changed, sender=SiteSeoSettings, dispatch_uid='seo.index_rule_settings'
    )
    from plugins.installed.seo.models import SeoTemplate

    post_save.connect(_on_template_changed, sender=SeoTemplate, dispatch_uid='seo.template_save')
    post_delete.connect(
        _on_template_changed, sender=SeoTemplate, dispatch_uid='seo.template_delete'
    )
    _wire_slug_watchers()


def _on_redirect_saved(sender, instance=None, **kwargs):
    from plugins.installed.seo.services.redirects import invalidate_redirect_cache

    invalidate_redirect_cache()


def _on_index_policy_changed(sender, instance=None, **kwargs):
    from plugins.installed.seo.rules import invalidate_index_rules_cache

    invalidate_index_rules_cache()


# -- slug history ---------------------------------------------------------
def _wire_slug_watchers() -> None:
    """Watch the models whose slug IS a public URL.

    catalog is a declared dependency, so its three models are wired directly.
    cms is optional: a missing or unmigrated cms plugin costs page slug history,
    not the whole feature.
    """
    from plugins.installed.seo.services.slug_history import URL_TEMPLATES

    for label in URL_TEMPLATES:
        model = _model_for(label)
        if model is None:
            continue
        pre_save.connect(_on_slug_maybe_changed, sender=model, dispatch_uid=f'seo.slug.{label}')


def _model_for(label: str):
    from django.apps import apps

    try:
        app_label, model_name = label.split('.', 1)
        return apps.get_model(app_label, model_name)
    except Exception as e:  # noqa: BLE001 — an optional/disabled app
        logger.debug('seo: no model for slug watch %s: %s', label, e)
        return None


def _on_slug_maybe_changed(sender, instance=None, **kwargs):
    """Record the old public path when a slug changes.

    Reads the *stored* row rather than trusting an in-memory original: the save
    may come from a form, an import, an assistant, or a shell, and only the
    database knows what the URL currently is.
    """
    if instance is None or not getattr(instance, 'pk', None):
        return
    from plugins.installed.seo.services.slug_history import record_slug_change

    try:
        previous = sender.objects.filter(pk=instance.pk).values_list('slug', flat=True).first()
    except Exception:  # noqa: BLE001 — an unmigrated table during a deploy
        return
    new_slug = getattr(instance, 'slug', '') or ''
    if not previous or not new_slug or previous == new_slug:
        return
    try:
        record_slug_change(instance, old_slug=previous, new_slug=new_slug)
    except Exception as e:  # noqa: BLE001 — never fail a merchant's save over this
        logger.warning('seo: slug history failed for %s: %s', instance, e, exc_info=True)


def _on_template_changed(sender, instance=None, **kwargs):
    """A pattern edit must re-title its pages on the NEXT render, not when the
    compiled-cache TTL happens to lapse."""
    from plugins.installed.seo.services.templating import invalidate_templates

    invalidate_templates()
