"""Auto-split from the legacy admin_dashboard/views.py monolith."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.db.models import Sum
from django.utils import timezone

from plugins.installed.admin_dashboard.forms import (
    AddressForm,
    CouponForm,
    CustomerForm,
    DraftOrderForm,
    FulfillmentForm,
    ProductForm,
    RefundForm,
    VariantForm,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    Metric, _bulk_ids, _period, _pct_delta, _since, _sparkline_points, _trend, logger,
)

def _panels_by_category() -> dict:
    """Index every active plugin's SettingsPanel by its category slug."""
    from plugins.registry import plugin_registry

    by_cat: dict[str, list] = {}
    for plugin in plugin_registry.active_plugins():
        panel = plugin_registry.settings_panel(plugin.name)
        if panel is None:
            continue
        cat = getattr(panel, 'category', '') or 'apps'
        by_cat.setdefault(cat, []).append({
            'plugin': plugin.name,
            'plugin_label': plugin.label,
            'plugin_description': plugin.description,
            'panel': panel,
        })
    for entries in by_cat.values():
        entries.sort(key=lambda e: (e['panel'].label or e['plugin_label']).lower())
    return by_cat


def _build_panel_fields(plugin_instance, schema: dict) -> list[dict]:
    """Schema → list of form-field dicts (matches plugin_settings.html shape)."""
    config = plugin_instance.get_config()
    fields = []
    for key, prop in (schema.get('properties') or {}).items():
        ptype = prop.get('type', 'string')
        kind = 'enum' if 'enum' in prop else ptype
        value = config.get(key, prop.get('default', ''))
        if kind == 'boolean':
            value = bool(value)
        fields.append({
            'key': key,
            'title': prop.get('title') or key.replace('_', ' ').title(),
            'description': prop.get('description', ''),
            'kind': kind,
            'enum': prop.get('enum') or [],
            'value': value,
        })
    return fields


@staff_member_required
def settings_view(request: HttpRequest) -> HttpResponse:
    """Settings hub — Shopify-style category index.

    Renders one card per ``SettingsCategory`` showing how many plugin
    panels live under it. Each card links to
    ``/dashboard/settings/<slug>/`` where the actual editable forms are
    grouped together. The legacy
    ``/dashboard/apps/<plugin>/settings/`` URL still works as a deep
    link for backward compat.
    """
    from django.conf import settings as dj_settings
    from plugins.installed.admin_dashboard.settings_categories import (
        SETTINGS_CATEGORIES,
    )

    by_cat = _panels_by_category()
    cards = []
    for cat in SETTINGS_CATEGORIES:
        entries = by_cat.get(cat.slug, [])
        cards.append({
            'category': cat,
            'count': len(entries),
            # Show up to 3 plugin labels as a hint of what's inside.
            'plugins': [e['panel'].label or e['plugin_label'] for e in entries[:3]],
        })

    store_summary = {
        'name': getattr(dj_settings, 'STORE_NAME', '—'),
        'currency': getattr(dj_settings, 'STORE_CURRENCY', '—'),
        'country': getattr(dj_settings, 'STORE_COUNTRY', '—'),
        'theme': getattr(dj_settings, 'MORPHEUS_ACTIVE_THEME', '—'),
    }
    return render(request, 'admin_dashboard/settings.html', {
        'cards': cards,
        'store_summary': store_summary,
        'active_nav': 'settings',
    })


_CORE_FORMS_BY_CATEGORY = {
    'general': ('StoreGeneralForm', 'Store details', 'Name, description, currency, locale.'),
    'notifications': ('StoreNotificationsForm', 'Email sender + SMTP', 'Outbound email used for transactional notifications.'),
}


def _core_form_for(category: str):
    """Return (form_class, title, description) for a category, or None."""
    entry = _CORE_FORMS_BY_CATEGORY.get(category)
    if entry is None:
        return None
    from plugins.installed.admin_dashboard import forms as dashboard_forms
    cls = getattr(dashboard_forms, entry[0])
    return cls, entry[1], entry[2]


@staff_member_required
def settings_ai_probe(request: HttpRequest) -> HttpResponse:
    """JSON endpoint backing the "Fetch models" + "Test connection" buttons.

    POST body fields:
        provider — openai | anthropic | gemini | openrouter | grok | packy | ollama
        api_key  — optional override; falls back to saved plugin config
        base_url — optional override

    Returns ``{"ok": bool, "models": [{"id", "label"}], "error": str}``.
    """
    from morpheus.views import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    provider = (request.POST.get('provider') or '').strip()
    if not provider:
        return JsonResponse({'ok': False, 'error': 'provider is required'}, status=400)

    api_key = (request.POST.get('api_key') or '').strip()
    base_url = (request.POST.get('base_url') or '').strip()
    try:
        from plugins.registry import plugin_registry
        ai_plugin = plugin_registry.get('ai_assistant')
        if ai_plugin is not None:
            cfg = ai_plugin.get_config()
            if not api_key:
                api_key = cfg.get(f'{provider}_api_key') or ''
            if not base_url:
                base_url = cfg.get(f'{provider}_base_url') or ''
    except Exception:  # noqa: BLE001
        pass

    from plugins.installed.ai_assistant.services.probe import probe
    result = probe(provider, api_key=api_key, base_url=base_url)
    return JsonResponse(result)


_AI_PROVIDERS = [
    {
        'slug': 'openai',
        'label': 'OpenAI',
        'icon': 'sparkle',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://platform.openai.com/api-keys',
        'placeholder_model': 'gpt-4o-mini',
    },
    {
        'slug': 'anthropic',
        'label': 'Anthropic',
        'icon': 'sparkle',
        'fields': ('api_key', 'model'),
        'help_url': 'https://console.anthropic.com/settings/keys',
        'placeholder_model': 'claude-3-5-sonnet-latest',
    },
    {
        'slug': 'gemini',
        'label': 'Google Gemini',
        'icon': 'sparkle',
        'fields': ('api_key', 'model'),
        'help_url': 'https://aistudio.google.com/app/apikey',
        'placeholder_model': 'gemini-2.0-flash',
    },
    {
        'slug': 'openrouter',
        'label': 'OpenRouter',
        'icon': 'route',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://openrouter.ai/keys',
        'placeholder_model': 'anthropic/claude-3.5-sonnet',
    },
    {
        'slug': 'grok',
        'label': 'Grok (xAI)',
        'icon': 'sparkles',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://console.x.ai',
        'placeholder_model': 'grok-4',
    },
    {
        'slug': 'packy',
        'label': 'Packy (packiapi.com)',
        'icon': 'globe',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://packiapi.com',
        'placeholder_model': 'claude-3-5-sonnet-20241022',
    },
    {
        'slug': 'ollama',
        'label': 'Ollama',
        'icon': 'cpu',
        'fields': ('base_url', 'api_key', 'model'),
        'help_url': 'https://ollama.com',
        'placeholder_model': 'llama3.2',
        'api_key_optional': True,
    },
]


@staff_member_required
def settings_ai(request: HttpRequest) -> HttpResponse:
    """Custom AI providers settings page — card per provider.

    Replaces the schema-driven render path for the 'ai' category. Each
    provider gets its own form/card with Fetch / Test buttons and a
    per-provider Save. The agent_core 'Agents' panel still renders below
    as a regular schema-driven panel for runtime config.
    """
    from plugins.registry import plugin_registry
    from plugins.installed.admin_dashboard.settings_categories import get_category

    cat = get_category('ai')
    ai_plugin = plugin_registry.get('ai_assistant')
    cfg = ai_plugin.get_config() if ai_plugin else {}
    active = cfg.get('ai_provider') or 'openai'

    # Last AI call per provider (success / error + timestamp) for the per-
    # card "Used N min ago" pill. Source: agents.decision rows the audit
    # log captures on every Linda + agent tool call.
    last_call_by_provider: dict[str, dict] = {}
    try:
        from core.audit.models import AuditEvent
        recent = (
            AuditEvent.objects
            .filter(event_type='agents.decision')
            .order_by('-created_at')[:200]
        )
        for ev in recent:
            slug = (ev.metadata or {}).get('provider') or ''
            if not slug or slug in last_call_by_provider:
                continue
            last_call_by_provider[slug] = {
                'at': ev.created_at,
                'ok': not (ev.metadata or {}).get('error'),
                'error': (ev.metadata or {}).get('error') or '',
            }
    except Exception:  # noqa: BLE001 — audit table may be empty / pre-migration
        pass

    # Per-provider card data with current values + status.
    cards = []
    for p in _AI_PROVIDERS:
        api_key = cfg.get(f'{p["slug"]}_api_key', '') or ''
        base_url = cfg.get(f'{p["slug"]}_base_url', '') or ''
        model = cfg.get(f'{p["slug"]}_model', '') or p.get('placeholder_model', '')
        configured = bool(api_key) or p.get('api_key_optional')
        cards.append({
            **p,
            'api_key': api_key,
            'base_url': base_url,
            'model': model,
            'configured': configured,
            'is_active': p['slug'] == active,
            'last_call': last_call_by_provider.get(p['slug']),
        })

    # Active-provider banner data — resolved model + status, the only
    # answer to "which provider is Linda actually using right now?".
    active_card = next((c for c in cards if c['is_active']), None)
    resolved_model = ''
    if active_card:
        try:
            from core.agents.llm import get_llm_provider
            resolved_model = getattr(get_llm_provider(), 'model', '') or ''
        except Exception:  # noqa: BLE001
            resolved_model = active_card.get('model', '')
    active_banner = {
        'card': active_card,
        'resolved_model': resolved_model,
        'last_call': (active_card or {}).get('last_call'),
    }

    # The agent_core panel — render it as a secondary schema-driven card
    # below the providers (existing template fields helper handles it).
    agent_core_card = None
    ac_plugin = plugin_registry.get('agent_core')
    if ac_plugin is not None and plugin_registry.settings_panel('agent_core') is not None:
        panel = plugin_registry.settings_panel('agent_core')
        agent_core_card = {
            'plugin_name': 'agent_core',
            'plugin': ac_plugin,
            'panel': panel,
            'fields': _build_panel_fields(ac_plugin, panel.schema),
            'submit_url': '/dashboard/apps/agent_core/settings/',
        }

    feature_flags = [
        ('enable_intent_engine', 'Intent engine'),
        ('enable_semantic_search', 'Semantic search'),
        ('enable_dynamic_pricing', 'Dynamic pricing'),
        ('enable_zero_shot_catalog', 'Zero-shot catalog'),
        ('enable_autonomous_operator', 'Autonomous operator'),
        ('enable_synthetic_testing', 'Synthetic testing'),
        ('agent_purchase_requires_approval', 'Agent purchases require approval'),
    ]
    features = [
        {'key': k, 'label': lbl, 'value': bool(cfg.get(k))}
        for k, lbl in feature_flags
    ]

    return render(request, 'admin_dashboard/settings_ai.html', {
        'category': cat,
        'cards': cards,
        'active_provider': active,
        'active_banner': active_banner,
        'features': features,
        'agent_core_card': agent_core_card,
        'active_nav': 'settings',
    })


@staff_member_required
def settings_category(request: HttpRequest, category: str) -> HttpResponse:
    """Render every plugin SettingsPanel that belongs to one category.

    The 'ai' category is handled by a dedicated rich view (per-provider
    cards). Everything else falls through to the schema-driven render.

    For categories that map to core ``StoreSettings`` fields ('general',
    'notifications') we additionally render an editable core form at the
    top of the page. POSTs land in this same view and are dispatched by
    the hidden ``_form`` field so we can host both core and plugin
    submissions on one URL.

    Each plugin panel becomes a card with an inline form posting to the
    existing plugin-settings handler at
    ``/dashboard/apps/<plugin>/settings/``.
    """
    from plugins.installed.admin_dashboard.settings_categories import get_category
    from plugins.registry import plugin_registry

    # AI gets a custom render — per-provider cards with Fetch / Test
    # buttons rather than a single schema-driven form.
    if category == 'ai':
        return settings_ai(request)

    cat = get_category(category)
    if cat is None:
        from morpheus.views import Http404
        raise Http404('Unknown settings category')

    core_card = None
    core_entry = _core_form_for(category)
    if core_entry is not None:
        FormCls, core_title, core_description = core_entry
        from core.models import StoreSettings
        instance = StoreSettings.objects.first()

        if request.method == 'POST' and request.POST.get('_form') == 'core':
            form = FormCls(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, f'{core_title} saved.')
                return redirect('admin_dashboard:settings_category', category=category)
        else:
            form = FormCls(instance=instance)

        core_card = {
            'title': core_title,
            'description': core_description,
            'form': form,
        }

    by_cat = _panels_by_category()
    entries = by_cat.get(category, [])
    cards = []
    for entry in entries:
        instance = plugin_registry.get(entry['plugin'])
        if instance is None:
            continue
        cards.append({
            'plugin': instance,
            'plugin_name': entry['plugin'],
            'panel': entry['panel'],
            'fields': _build_panel_fields(instance, entry['panel'].schema),
            'submit_url': f'/dashboard/apps/{entry["plugin"]}/settings/',
        })

    return render(request, 'admin_dashboard/settings_category.html', {
        'category': cat,
        'core_card': core_card,
        'cards': cards,
        'active_nav': 'settings',
    })


# ── AI insights (kept for back-compat with old URL) ──────────────────────────


# Master list of transactional email keys + labels + default subjects.
# Drives both the list page (rows) and the edit page (label / default
# subject lookup). When adding a new transactional email, register it
# here AND ship a default body at core/emails/templates/emails/<key>.txt.
_EMAIL_TEMPLATE_KEYS = [
    ('order_placed', 'Order placed', 'Order #{{ order.order_number }} received'),
    ('order_paid', 'Order paid', 'Payment confirmed for order #{{ order.order_number }}'),
    ('order_fulfilled', 'Order fulfilled', 'Order #{{ order.order_number }} is on its way'),
    ('order_cancelled', 'Order cancelled', 'Order #{{ order.order_number }} cancelled'),
    ('refund_issued', 'Refund issued', 'Refund issued for order #{{ order.order_number }}'),
    ('digital_download', 'Digital downloads', 'Your downloads — order #{{ order.order_number }}'),
    ('cart_abandoned', 'Cart abandoned', 'You left items in your cart'),
    ('welcome', 'Welcome', 'Welcome'),
]


def _filesystem_default(key: str) -> str:
    """Read the shipped default body so the editor can show / restore it.

    Path traversal: this file lives at
    ``plugins/installed/admin_dashboard/views_split/settings.py`` — five
    `.parent` hops to reach the project root, then `core/emails/...`
    """
    from pathlib import Path
    base = (
        Path(__file__).resolve().parent.parent.parent.parent.parent
        / 'core' / 'emails' / 'templates' / 'emails'
    )
    fp = base / f'{key}.txt'
    try:
        return fp.read_text(encoding='utf-8')
    except OSError:
        return ''


@staff_member_required
def email_templates_list(request: HttpRequest) -> HttpResponse:
    """Show every transactional email template, edited or not."""
    from plugins.installed.cms.models import EmailTemplate

    existing = {t.key: t for t in EmailTemplate.objects.all()}
    rows = []
    for key, label, default_subject in _EMAIL_TEMPLATE_KEYS:
        tpl = existing.get(key)
        rows.append({
            'key': key,
            'label': label,
            'subject': tpl.subject if tpl else default_subject,
            'is_active': tpl.is_active if tpl else False,
            'updated_at': tpl.updated_at if tpl else None,
            'is_customised': tpl is not None,
        })
    return render(request, 'admin_dashboard/email_templates_list.html', {
        'rows': rows,
        'active_nav': 'settings',
    })


@staff_member_required
def email_template_edit(request: HttpRequest, key: str) -> HttpResponse:
    """Edit one template. Reset = delete the row → falls back to filesystem default."""
    from morpheus.views import HttpResponseRedirect

    from plugins.installed.cms.models import EmailTemplate

    label_map = {k: lbl for k, lbl, _ in _EMAIL_TEMPLATE_KEYS}
    default_subject_map = {k: subj for k, _, subj in _EMAIL_TEMPLATE_KEYS}
    if key not in label_map:
        from django.http import Http404
        raise Http404('Unknown template.')

    tpl = EmailTemplate.objects.filter(key=key).first()

    if request.method == 'POST':
        action = request.POST.get('action') or 'save'
        if action == 'reset':
            if tpl:
                tpl.delete()
            return HttpResponseRedirect(request.path)
        subject = (request.POST.get('subject') or '').strip()
        body_text = request.POST.get('body_text') or ''
        body_html = request.POST.get('body_html') or ''
        is_active = request.POST.get('is_active') == 'on'
        EmailTemplate.objects.update_or_create(
            key=key,
            defaults={
                'label': label_map[key],
                'subject': subject or default_subject_map[key],
                'body_text': body_text,
                'body_html': body_html,
                'is_active': is_active,
                'updated_by': request.user if request.user.is_authenticated else None,
            },
        )
        return HttpResponseRedirect('/dashboard/settings/email-templates/')

    return render(request, 'admin_dashboard/email_template_edit.html', {
        'key': key,
        'label': label_map[key],
        'subject': tpl.subject if tpl else default_subject_map[key],
        'body_text': tpl.body_text if tpl else _filesystem_default(key),
        'body_html': tpl.body_html if tpl else '',
        'is_active': tpl.is_active if tpl else True,
        'is_customised': tpl is not None,
        'default_subject': default_subject_map[key],
        'default_body_text': _filesystem_default(key),
        'active_nav': 'settings',
    })


# ─── Returns / RMA ────────────────────────────────────────────────────────────


