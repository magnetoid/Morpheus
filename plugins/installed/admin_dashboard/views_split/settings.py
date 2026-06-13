"""Auto-split from the legacy admin_dashboard/views.py monolith."""

# Legacy auto-split view module: lazy (in-function) imports are the established
# pattern here, and the dispatch views are intentionally branchy.
# ruff: noqa: PLC0415, PLR0912, PLR0915, S110
from __future__ import annotations

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    messages,
    redirect,
    render,
    staff_member_required,
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
        by_cat.setdefault(cat, []).append(
            {
                'plugin': plugin.name,
                'plugin_label': plugin.label,
                'plugin_description': plugin.description,
                'panel': panel,
            }
        )
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
        fields.append(
            {
                'key': key,
                'title': prop.get('title') or key.replace('_', ' ').title(),
                'description': prop.get('description', ''),
                'kind': kind,
                'enum': prop.get('enum') or [],
                'value': value,
            }
        )
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
        cards.append(
            {
                'category': cat,
                'count': len(entries),
                # Show up to 3 plugin labels as a hint of what's inside.
                'plugins': [e['panel'].label or e['plugin_label'] for e in entries[:3]],
            }
        )

    store_summary = {
        'name': getattr(dj_settings, 'STORE_NAME', '—'),
        'currency': getattr(dj_settings, 'STORE_CURRENCY', '—'),
        'country': getattr(dj_settings, 'STORE_COUNTRY', '—'),
        'theme': getattr(dj_settings, 'MORPHEUS_ACTIVE_THEME', '—'),
    }
    return render(
        request,
        'admin_dashboard/settings.html',
        {
            'cards': cards,
            'store_summary': store_summary,
            'active_nav': 'settings',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Settings'},
            ],
        },
    )


_CORE_FORMS_BY_CATEGORY = {
    'general': ('StoreGeneralForm', 'Store details', 'Name, description, currency, locale.'),
    'notifications': (
        'StoreNotificationsForm',
        'Email sender + SMTP',
        'Outbound email used for transactional notifications.',
    ),
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
        provider — openai | anthropic | gemini | openrouter | grok | apikey | packy | ollama
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
        'slug': 'apikey',
        'label': 'apikey.fun',
        'icon': 'globe',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://apikey.fun/docs',
        'placeholder_model': 'gpt-4o-mini',
    },
    {
        'slug': 'packy',
        'label': 'Packy (packyapi.com)',
        'icon': 'globe',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://www.packyapi.com',
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
def settings_caching(request: HttpRequest) -> HttpResponse:
    """Unified caching dashboard — Django cache backend status, Redis
    stats, storefront page-cache TTL, and Cloudflare zone summary.

    POST actions:
      action=clear_default  — flush the Django default cache
      action=save_storefront — persist storefront.page_cache_ttl + asset_max_age
    """
    from django.conf import settings as dj_settings
    from django.core.cache import cache

    from plugins.installed.admin_dashboard.settings_categories import get_category
    from plugins.registry import plugin_registry

    if request.method == 'POST':
        action = request.POST.get('action') or ''
        sf = plugin_registry.get('storefront')
        if action == 'clear_default':
            try:
                cache.clear()
                messages.success(request, 'App cache cleared.')
            except Exception as e:  # noqa: BLE001
                messages.error(request, f'Cache clear failed: {e}')
        elif action == 'save_storefront' and sf is not None:
            try:
                sf.set_config(
                    'html_cache_control', (request.POST.get('html_cache_control') or '').strip()
                )
                sf.set_config(
                    'asset_max_age_seconds', int(request.POST.get('asset_max_age_seconds') or 0)
                )
                sf.set_config(
                    'graphql_edge_cache_ttl', int(request.POST.get('graphql_edge_cache_ttl') or 0)
                )
                messages.success(request, 'Cache-Control headers saved.')
            except (TypeError, ValueError):
                messages.error(request, 'TTL fields must be integers.')
        elif action == 'save_assets' and sf is not None:
            sf.set_config('lazy_load_images', request.POST.get('lazy_load_images') == 'on')
            sf.set_config('serve_webp', request.POST.get('serve_webp') == 'on')
            sf.set_config('preload_lcp', request.POST.get('preload_lcp') == 'on')
            sf.set_config('responsive_srcset', request.POST.get('responsive_srcset') == 'on')
            messages.success(request, 'Image optimization settings saved.')
        elif action == 'save_hints' and sf is not None:
            sf.set_config(
                'preconnect_origins', (request.POST.get('preconnect_origins') or '').strip()
            )
            sf.set_config(
                'dns_prefetch_origins', (request.POST.get('dns_prefetch_origins') or '').strip()
            )
            messages.success(request, 'Resource hints saved.')
        elif action == 'save_pwa' and sf is not None:
            sf.set_config(
                'service_worker_enabled', request.POST.get('service_worker_enabled') == 'on'
            )
            sf.set_config(
                'offline_page_path', (request.POST.get('offline_page_path') or '/offline/').strip()
            )
            messages.success(request, 'PWA settings saved.')
        elif action == 'save_compression' and sf is not None:
            sf.set_config('brotli_enabled', request.POST.get('brotli_enabled') == 'on')
            sf.set_config('gzip_enabled', request.POST.get('gzip_enabled') == 'on')
            sf.set_config('min_compress_bytes', int(request.POST.get('min_compress_bytes') or 1024))
            messages.success(request, 'Compression settings saved.')
        elif action == 'save_critical' and sf is not None:
            sf.set_config('inline_critical_css', request.POST.get('inline_critical_css') == 'on')
            sf.set_config(
                'defer_non_critical_js', request.POST.get('defer_non_critical_js') == 'on'
            )
            sf.set_config('font_display', (request.POST.get('font_display') or 'swap').strip())
            sf.set_config('preload_fonts', (request.POST.get('preload_fonts') or '').strip())
            messages.success(request, 'Critical-path settings saved.')
        elif action == 'save_ttls' and sf is not None:
            try:
                sf.set_config('home_cache_ttl', int(request.POST.get('home_cache_ttl') or 0))
                sf.set_config('product_cache_ttl', int(request.POST.get('product_cache_ttl') or 0))
                sf.set_config(
                    'category_cache_ttl', int(request.POST.get('category_cache_ttl') or 0)
                )
                sf.set_config('search_cache_ttl', int(request.POST.get('search_cache_ttl') or 0))
                messages.success(request, 'Per-route TTLs saved.')
            except (TypeError, ValueError):
                messages.error(request, 'TTL fields must be integers.')
        elif action == 'save_warmup' and sf is not None:
            sf.set_config('post_deploy_warmup', request.POST.get('post_deploy_warmup') == 'on')
            sf.set_config('warmup_top_n', int(request.POST.get('warmup_top_n') or 20))
            sf.set_config(
                'warmup_extra_urls', (request.POST.get('warmup_extra_urls') or '').strip()
            )
            messages.success(request, 'Cache-warmup settings saved.')
        elif action == 'optimize_images':
            # Re-warm WebP/AVIF image variants in the background. Lives here
            # (the Caching page) rather than the SEO dashboard — ADR 0005,
            # superseding ADR 0002. Fail-soft when the broker is down.
            try:
                from plugins.installed.seo.tasks import optimize_images_task

                optimize_images_task.delay(avif=bool(request.POST.get('avif')))
                messages.success(
                    request,
                    'Image optimization started — warming WebP/AVIF variants in the '
                    'background. Refresh in a minute for the result.',
                )
            except Exception as e:  # noqa: BLE001 — broker down: report, don't 500
                messages.error(request, f'Could not start image optimization: {e}')
        elif action == 'cf_patch_setting':
            # Edit one Cloudflare cache setting (cache_level, browser_cache_ttl,
            # brotli, early_hints, polish, mirage) for a zone — ADR 0005. Only
            # the curated cache subset is editable here; everything else stays
            # on the Cloudflare zone page.
            zone_id = (request.POST.get('zone_id') or '').strip()
            setting_id = (request.POST.get('setting_id') or '').strip()
            value = (request.POST.get('value') or '').strip()
            try:
                from plugins.installed.cloudflare.models import CloudflareZone
                from plugins.installed.cloudflare.services import (
                    CACHE_SETTING_IDS,
                    CloudflareError,
                    patch_zone_setting,
                )

                if setting_id not in CACHE_SETTING_IDS:
                    messages.error(request, 'Not an editable cache setting.')
                else:
                    zone = CloudflareZone.objects.get(pk=zone_id)
                    coerced = int(value) if setting_id == 'browser_cache_ttl' else value
                    patch_zone_setting(zone, setting_id, coerced)
                    messages.success(request, f'Cloudflare · {setting_id} → {value}.')
            except (ValueError, TypeError):
                messages.error(request, 'Browser cache TTL must be an integer.')
            except CloudflareError as e:
                messages.error(request, f'Cloudflare API error: {e}')
            except Exception as e:  # noqa: BLE001
                messages.error(request, f'Could not update Cloudflare setting: {e}')
        elif action == 'cf_purge_all':
            zone_id = (request.POST.get('zone_id') or '').strip()
            try:
                from plugins.installed.cloudflare.models import CloudflareZone
                from plugins.installed.cloudflare.services import (
                    CloudflareError,
                    purge_everything,
                )

                zone = CloudflareZone.objects.get(pk=zone_id)
                purge_everything(zone=zone, triggered_by=str(request.user))
                messages.success(request, f'Purged everything for {zone.domain}.')
            except CloudflareError as e:
                messages.error(request, f'Cloudflare API error: {e}')
            except Exception as e:  # noqa: BLE001
                messages.error(request, f'Could not purge Cloudflare cache: {e}')
        return HttpResponseRedirect(request.path)

    # ── Django cache backend status ────────────────────────────────────────
    default_backend = (dj_settings.CACHES.get('default') or {}).get('BACKEND', '')
    default_location = (dj_settings.CACHES.get('default') or {}).get('LOCATION', '')
    cache_alive = False
    cache_round_trip_ms = None
    cache_error = ''
    try:
        import time

        sentinel_key = '_morpheus_health_ping'
        t0 = time.monotonic()
        cache.set(sentinel_key, 'ok', 5)
        got = cache.get(sentinel_key)
        cache_round_trip_ms = int((time.monotonic() - t0) * 1000)
        cache_alive = got == 'ok'
    except Exception as e:  # noqa: BLE001
        cache_error = f'{type(e).__name__}: {e}'

    # ── Redis INFO (when backend is Redis) ─────────────────────────────────
    redis_stats: dict = {}
    if 'redis' in default_backend.lower():
        try:
            from django_redis import get_redis_connection

            conn = get_redis_connection('default')
            info = conn.info(section='stats')
            mem = conn.info(section='memory')
            keyspace = conn.info(section='keyspace')
            redis_stats = {
                'used_memory_human': mem.get('used_memory_human', '—'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'evicted_keys': info.get('evicted_keys', 0),
                'expired_keys': info.get('expired_keys', 0),
                'db0_keys': (keyspace.get('db0') or {}).get('keys', 0)
                if isinstance(keyspace.get('db0'), dict)
                else 0,
            }
            hits = redis_stats['keyspace_hits']
            misses = redis_stats['keyspace_misses']
            redis_stats['hit_ratio'] = round(100 * hits / max(hits + misses, 1), 1)
        except Exception as e:  # noqa: BLE001
            redis_stats = {'error': f'{type(e).__name__}: {e}'}

    # ── Storefront cache knobs (stored in PluginConfig) ────────────────────
    storefront_plugin = plugin_registry.get('storefront')
    sf_cfg = storefront_plugin.get_config() if storefront_plugin else {}
    storefront = {
        'asset_max_age_seconds': int(
            sf_cfg.get('asset_max_age_seconds') or 31536000
        ),  # 1 year default
        'html_cache_control': (
            sf_cfg.get('html_cache_control')
            or 'public, max-age=0, s-maxage=300, must-revalidate, stale-while-revalidate=86400, stale-if-error=86400'
        ),
        'graphql_edge_cache_ttl': int(sf_cfg.get('graphql_edge_cache_ttl') or 0),
    }
    assets = {
        'lazy_load_images': bool(sf_cfg.get('lazy_load_images', True)),
        'serve_webp': bool(sf_cfg.get('serve_webp', True)),
        'preload_lcp': bool(sf_cfg.get('preload_lcp', True)),
        'responsive_srcset': bool(sf_cfg.get('responsive_srcset', True)),
    }
    hints = {
        'preconnect_origins': sf_cfg.get('preconnect_origins') or '',
        'dns_prefetch_origins': sf_cfg.get('dns_prefetch_origins') or '',
    }
    pwa = {
        'service_worker_enabled': bool(sf_cfg.get('service_worker_enabled', False)),
        'offline_page_path': sf_cfg.get('offline_page_path') or '/offline/',
    }
    compression = {
        'brotli_enabled': bool(sf_cfg.get('brotli_enabled', True)),
        'gzip_enabled': bool(sf_cfg.get('gzip_enabled', True)),
        'min_compress_bytes': int(sf_cfg.get('min_compress_bytes') or 1024),
    }
    critical = {
        'inline_critical_css': bool(sf_cfg.get('inline_critical_css', False)),
        'defer_non_critical_js': bool(sf_cfg.get('defer_non_critical_js', True)),
        'font_display': sf_cfg.get('font_display') or 'swap',
        'preload_fonts': sf_cfg.get('preload_fonts') or '',
    }
    route_ttls = {
        'home_cache_ttl': int(sf_cfg.get('home_cache_ttl') or 600),
        'product_cache_ttl': int(sf_cfg.get('product_cache_ttl') or 300),
        'category_cache_ttl': int(sf_cfg.get('category_cache_ttl') or 180),
        'search_cache_ttl': int(sf_cfg.get('search_cache_ttl') or 0),
    }
    warmup = {
        'post_deploy_warmup': bool(sf_cfg.get('post_deploy_warmup', False)),
        'warmup_top_n': int(sf_cfg.get('warmup_top_n') or 20),
        'warmup_extra_urls': sf_cfg.get('warmup_extra_urls') or '',
    }

    # ── Recent cache activity (across all CF zones) — last 10 purges ───────
    recent_activity = []
    try:
        from plugins.installed.cloudflare.models import CacheInvalidation

        recent_activity = list(
            CacheInvalidation.objects.select_related('zone').order_by('-created_at')[:10]
        )
    except Exception:  # noqa: BLE001
        pass

    # ── Cloudflare zone summary ────────────────────────────────────────────
    cf_zones = []
    cf_account_count = 0
    try:
        from plugins.installed.cloudflare.models import (
            CacheInvalidation,
            CloudflareAccount,
            CloudflareZone,
        )

        cf_zones = list(CloudflareZone.objects.select_related('account')[:10])
        cf_account_count = CloudflareAccount.objects.count()
        recent_purges_count = CacheInvalidation.objects.count()
    except Exception:  # noqa: BLE001
        recent_purges_count = 0

    # ── Cloudflare cache controls (live per-zone read; fail-soft) ──────────
    # ADR 0005: the six curated cache settings are editable here. One CF API
    # read per zone — guarded so a bad token / disabled plugin never 500s.
    cf_cache_zones = []
    if cf_zones:
        try:
            from plugins.installed.cloudflare.services import (
                CACHE_SETTINGS,
                zone_settings_map,
            )

            for zone in cf_zones:
                row = {'zone': zone, 'settings': [], 'error': ''}
                try:
                    smap = zone_settings_map(zone)
                    row['settings'] = [
                        {'id': sid, 'label': label, 'help': help_text, 'value': smap.get(sid, '')}
                        for sid, label, help_text in CACHE_SETTINGS
                    ]
                except Exception as e:  # noqa: BLE001
                    row['error'] = f'{type(e).__name__}: {e}'
                cf_cache_zones.append(row)
        except Exception:  # noqa: BLE001
            pass

    # ── Image-optimization last-run status (SEO task; ADR 0005) ────────────
    image_optimize_status = None
    try:
        from plugins.installed.seo.tasks import last_image_optimize_status

        image_optimize_status = last_image_optimize_status()
    except Exception:  # noqa: BLE001
        pass

    return render(
        request,
        'admin_dashboard/settings_caching.html',
        {
            'category': get_category('caching'),
            'image_optimize_status': image_optimize_status,
            'default_backend': default_backend.split('.')[-1] or default_backend,
            'default_location': default_location,
            'cache_alive': cache_alive,
            'cache_round_trip_ms': cache_round_trip_ms,
            'cache_error': cache_error,
            'redis_stats': redis_stats,
            'storefront': storefront,
            'assets': assets,
            'hints': hints,
            'pwa': pwa,
            'compression': compression,
            'critical': critical,
            'route_ttls': route_ttls,
            'warmup': warmup,
            'recent_activity': recent_activity,
            'cf_zones': cf_zones,
            'cf_cache_zones': cf_cache_zones,
            'cf_account_count': cf_account_count,
            'recent_purges_count': recent_purges_count,
            'active_nav': 'settings',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': 'Caching'},
            ],
        },
    )


def settings_ai(request: HttpRequest) -> HttpResponse:
    """Custom AI providers settings page — card per provider.

    Replaces the schema-driven render path for the 'ai' category. Each
    provider gets its own form/card with Fetch / Test buttons and a
    per-provider Save. The agent_core 'Agents' panel still renders below
    as a regular schema-driven panel for runtime config.
    """
    from plugins.installed.admin_dashboard.settings_categories import get_category
    from plugins.registry import plugin_registry

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

        recent = AuditEvent.objects.filter(event_type='agents.decision').order_by('-created_at')[
            :200
        ]
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
        cards.append(
            {
                **p,
                'api_key': api_key,
                'base_url': base_url,
                'model': model,
                'configured': configured,
                'is_active': p['slug'] == active,
                'last_call': last_call_by_provider.get(p['slug']),
            }
        )

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
    features = [{'key': k, 'label': lbl, 'value': bool(cfg.get(k))} for k, lbl in feature_flags]

    return render(
        request,
        'admin_dashboard/settings_ai.html',
        {
            'category': cat,
            'cards': cards,
            'active_provider': active,
            'active_banner': active_banner,
            'features': features,
            'agent_core_card': agent_core_card,
            'active_nav': 'settings',
        },
    )


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
    if category == 'caching':
        return settings_caching(request)

    cat = get_category(category)
    if cat is None:
        # Not a category — fall back to per-plugin settings page (the
        # canonical URL pattern post-2026-05-23: every plugin with a
        # SettingsPanel is reachable at /dashboard/settings/<plugin>/).
        from plugins.registry import plugin_registry

        if plugin_registry.settings_panel(category) is not None:
            from plugins.installed.admin_dashboard.urls import plugin_settings_view

            return plugin_settings_view(request, plugin=category)
        from morpheus.views import Http404

        raise Http404('Unknown settings category or plugin')

    core_card = None
    core_entry = _core_form_for(category)
    if core_entry is not None:
        FormCls, core_title, core_description = core_entry
        from core.models import StoreSettings

        instance = StoreSettings.objects.first()

        if request.method == 'POST' and request.POST.get('_form') == 'core':
            form = FormCls(request.POST, request.FILES, instance=instance)
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
        cards.append(
            {
                'plugin': instance,
                'plugin_name': entry['plugin'],
                'panel': entry['panel'],
                'fields': _build_panel_fields(instance, entry['panel'].schema),
                # New canonical URL — post-2026-05-23. The legacy
                # /dashboard/apps/<plugin>/settings/ 301-redirects here so
                # any bookmarks keep working.
                'submit_url': f'/dashboard/settings/{entry["plugin"]}/',
            }
        )

    # The Developers hub: every section='developer' DashboardPage renders
    # here as a tool card (one sidebar entry instead of seven), plus the
    # always-reachable core tools. A disabled plugin's card vanishes with
    # its contribution.
    developer_tools = []
    if category == 'developer':
        for page in sorted(
            plugin_registry.dashboard_pages(section='developer'),
            key=lambda pg: (pg.order, pg.label),
        ):
            developer_tools.append(
                {
                    'label': page.label,
                    'url': getattr(page, 'url', '')
                    or f'/dashboard/apps/{page.plugin}/{page.slug}/',
                    'icon': page.icon or 'circle',
                    'hint': page.plugin.replace('_', ' '),
                }
            )
        developer_tools += [
            {
                'label': 'Tracking',
                'url': '/dashboard/tracking/',
                'icon': 'activity',
                'hint': 'GA4 / GTM, event log, consent',
            },
            {
                'label': 'Errors',
                'url': '/dashboard/errors/',
                'icon': 'alert-circle',
                'hint': 'server + client error log',
            },
            {
                'label': 'Updates',
                'url': '/dashboard/updates/',
                'icon': 'refresh-cw',
                'hint': 'component version inventory',
            },
            {
                'label': 'Caching',
                'url': '/dashboard/settings/caching/',
                'icon': 'zap',
                'hint': 'page cache, Redis, Cloudflare edge',
            },
        ]

    return render(
        request,
        'admin_dashboard/settings_category.html',
        {
            'category': cat,
            'core_card': core_card,
            'cards': cards,
            'developer_tools': developer_tools,
            'active_nav': 'settings',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': cat.label},
            ],
        },
    )


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
        / 'core'
        / 'emails'
        / 'templates'
        / 'emails'
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
        rows.append(
            {
                'key': key,
                'label': label,
                'subject': tpl.subject if tpl else default_subject,
                'is_active': tpl.is_active if tpl else False,
                'updated_at': tpl.updated_at if tpl else None,
                'is_customised': tpl is not None,
            }
        )
    return render(
        request,
        'admin_dashboard/email_templates_list.html',
        {
            'rows': rows,
            'active_nav': 'settings',
        },
    )


@staff_member_required
def email_template_edit(request: HttpRequest, key: str) -> HttpResponse:
    """Edit one template. Reset = delete the row → falls back to filesystem default."""
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

    return render(
        request,
        'admin_dashboard/email_template_edit.html',
        {
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
        },
    )


# ─── Returns / RMA ────────────────────────────────────────────────────────────
