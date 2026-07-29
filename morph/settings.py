"""
Morpheus CMS — Django Settings (Revised: Plugin-Native Architecture)
"""

import sys
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# True when running `python manage.py test` or pytest. Used to relax a few
# defaults (DATABASE_URL fallback, cache backend) so the suite runs without
# a real Postgres / Redis around.
_RUNNING_TESTS = 'test' in sys.argv or sys.argv[0].endswith('pytest')

DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config(
    'SECRET_KEY',
    default='dev-secret-key-change-this-in-production-abc123' if DEBUG else '',
)
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG=False')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
if not DEBUG and ALLOWED_HOSTS == ['localhost', '127.0.0.1']:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured('ALLOWED_HOSTS must be set explicitly when DEBUG=False')

# ── Plugin & Theme directories ─────────────────────────────────────────────────
MORPHEUS_PLUGINS_DIR = BASE_DIR / 'plugins' / 'installed'
MORPHEUS_THEMES_DIR = BASE_DIR / 'themes' / 'library'
MORPHEUS_ACTIVE_THEME = config('MORPHEUS_ACTIVE_THEME', default='dot_books')

# Display version next to the logo in the admin sidebar.
MORPHEUS_VERSION = config('MORPHEUS_VERSION', default='v0.34.0')

# Opt-in gate for the in-app platform self-updater (git fast-forward apply).
# OFF by default — `manage.py morph_apply_update --confirm` refuses unless this
# is on. See core/updates.py + docs/plans/updating-system-2026-06.md.
MORPHEUS_SELF_UPDATE_ENABLED = config('MORPHEUS_SELF_UPDATE_ENABLED', default=False, cast=bool)

# Optional Google Places API key — when set, checkout/address forms
# surface address autocomplete. Empty string disables the feature
# (no script tag rendered, no UI changes).
GOOGLE_PLACES_API_KEY = config('GOOGLE_PLACES_API_KEY', default='')

# ── Default plugins (always in INSTALLED_APPS — they have models) ──────────────
MORPHEUS_DEFAULT_PLUGINS = [
    'plugins.installed.catalog',
    'plugins.installed.orders',
    'plugins.installed.customers',
    'plugins.installed.payments',
    'plugins.installed.inventory',
    'plugins.installed.marketing',
    'plugins.installed.newsletter',
    'plugins.installed.analytics',
    'plugins.installed.storefront',
    'plugins.installed.admin_dashboard',
    'plugins.installed.richtext',
    'plugins.installed.ai_assistant',
    'plugins.installed.ai_content',
    'plugins.installed.functions',
    'plugins.installed.importers',
    'plugins.installed.observability',
    'plugins.installed.release_notes',
    'plugins.installed.morpheus_brain',
    'plugins.installed.environments',
    'plugins.installed.affiliates',
    'plugins.installed.marketplace',
    'plugins.installed.booking_marketplace',
    'plugins.installed.cloudflare',
    'plugins.installed.flipbook',
    'plugins.installed.seo',
    'plugins.installed.advanced_ecommerce',
    'plugins.installed.advanced_payments',
    'plugins.installed.trust_signals',
    'plugins.installed.post_purchase',
    'plugins.installed.experiments',
    'plugins.installed.fraud_rules',
    'plugins.installed.personalisation',
    'plugins.installed.agent_core',
    'plugins.installed.crm',
    'plugins.installed.tax',
    'plugins.installed.shipping',
    'plugins.installed.wishlist',
    'plugins.installed.webhooks_ui',
    'plugins.installed.gift_cards',
    'plugins.installed.b2b',
    'plugins.installed.subscriptions',
    'plugins.installed.cms',
    'plugins.installed.rbac',
    'plugins.installed.promotions',
    'plugins.installed.draft_orders',
    'plugins.installed.cart_abandonment',
    'plugins.installed.backups',
    'plugins.installed.digital_products',
    'plugins.installed.dynamics',
    # Phase-1+2 plugins added later in development. Each ships its own
    # migrations; keep registered so models.* tables exist + plugin
    # manifests get discovered.
    'plugins.installed.markets',
    'plugins.installed.media',
    'plugins.installed.metafields',
    'plugins.installed.notifications_center',
    'plugins.installed.workflows',
    'plugins.installed.agent_mcp',
    'plugins.installed.reviews',
    'plugins.installed.loyalty_points',
    'plugins.installed.lumina',
    'plugins.installed.linda_generated',
    'plugins.installed.bookstore_3d',
    'plugins.installed.audiobooks',
    'plugins.installed.book_product',
    'plugins.installed.product_gallery',
    'plugins.installed.product_videos',
    'plugins.installed.tracking',
    'plugins.installed.google_shopping',
    'plugins.installed.meta_commerce',
    'plugins.installed.tiktok_commerce',
    'plugins.installed.pinterest_commerce',
    'plugins.installed.microsoft_commerce',
    'plugins.installed.amazon_ads',
    'plugins.installed.reddit_ads',
    'plugins.installed.snapchat_commerce',
    'plugins.installed.channels',
    'plugins.installed.store_bootstrap',
    'plugins.installed.localization',
    'plugins.installed.bookvault',
    'plugins.installed.pwa',
    'plugins.installed.webstories',
    'plugins.installed.consent',
    'plugins.installed.gdpr',
    # ── Vibe-coding roadmap (added 2026-06-12) ────────────────────────────
    # These plugins implement the F1-F20 vibe-coding feature roadmap in
    # docs/analysis/vibe_coding_gap_assessment.md. They all follow the
    # plugin contract: settings panel + StorefrontBlock contributions,
    # no hard-coded storefront edits, no cross-plugin model imports.
    #   F10  checkout_experience    — end-to-end checkout + express pay
    #   F1   immersive_pdp          — video hero, story blocks, sticky buybox
    #   F6   rails                  — six personalised recommendation rails
    #   F2   media_3d               — 3D / AR previews + shoppable video
    #   F7   ai_stylist             — on-site AI shopping assistant
    #   F14  ugc_reviews            — photo + video reviews + creator program
    #   F11  one_click              — one-click returning shopper
    #   F17  rich_post_purchase     — multichannel post-purchase chain
    #   F3   journal                — block-editor story-telling CMS
    #   F4   brand_kit              — brand asset library + design tokens
    #   F8   discovery_quiz         — zero-party-data quiz funnel
    #   F19  save_for_later         — save-for-later / wishlist upgrades
    #   F15  referrals              — Give-5, Get-5 customer referrals
    #   F12  smart_shipping         — live rates + carbon display
    #   F20  returns_portal         — returns as a retention surface
    #   F9   lookbook               — editorial product bundles
    #   F13  post_checkout_upsell   — single in-checkout + post-order upsell
    #   F16  drops                  — scheduled drops + waitlist
    #   F5   motion                 — micro-animations + skeleton states
    'plugins.installed.checkout_experience',
    'plugins.installed.immersive_pdp',
    'plugins.installed.product_stories',
    'plugins.installed.rails',
    'plugins.installed.media_3d',
    'plugins.installed.ai_stylist',
    'plugins.installed.ugc_reviews',
    'plugins.installed.one_click',
    'plugins.installed.rich_post_purchase',
    'plugins.installed.journal',
    'plugins.installed.brand_kit',
    'plugins.installed.discovery_quiz',
    'plugins.installed.staff_mfa',
    'plugins.installed.staff_sso',
    'plugins.installed.save_for_later',
    'plugins.installed.referrals',
    'plugins.installed.smart_shipping',
    'plugins.installed.returns_portal',
    'plugins.installed.lookbook',
    'plugins.installed.post_checkout_upsell',
    'plugins.installed.drops',
    'plugins.installed.motion',
    # Agentic Commerce Protocol (ACP 2026-04-17). Agent-driven discovery +
    # checkout backed by our Cart. Ships OFF by default — the money path
    # (Stripe Shared Payment Token) is gated until a merchant enrolls.
    'plugins.installed.agentic_checkout',
    # Per-install feature-usage aggregates + install-health score. No PII,
    # no fleet telemetry — single-install product analytics.
    'plugins.installed.feature_adoption',
    # Live shopping events MVP: scheduled event + embedded stream + pinned
    # buyable products; conversion via the existing UTM/attribution pipeline.
    'plugins.installed.live_commerce',
    # Book production-footprint badge (paper/wood/CO₂) + opt-in plant-a-tree
    # checkout offset with a merchant-fulfilled tree fund + public impact page.
    'plugins.installed.eco_impact',
]

# ── Extra plugins installed by merchant via .env ───────────────────────────────
MORPHEUS_EXTRA_PLUGINS = config('MORPHEUS_EXTRA_PLUGINS', default='', cast=Csv())

ALL_MORPHEUS_PLUGINS = MORPHEUS_DEFAULT_PLUGINS + list(MORPHEUS_EXTRA_PLUGINS)

# ── Installed Apps ─────────────────────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'mptt',
    'taggit',
    'djmoney',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # OIDC provider machinery for staff_sso. Always loaded (Django's app
    # registry is frozen after settings import, so it can't be added from a
    # plugin's ready()), but inert without a configured SocialApp — the
    # staff_sso plugin (OFF by default) creates that row only when an IdP is
    # set up, so no provider button renders and email-OTP is unaffected.
    'allauth.socialaccount.providers.openid_connect',
    # SAML 2.0 provider machinery for staff_sso (Phase 4b), alongside OIDC.
    # Same posture: loaded at settings-import (the app registry is frozen after,
    # so a plugin's ready() can't add it), inert without a configured SocialApp.
    # staff_sso (OFF by default) creates the SAML SocialApp only when an IdP is
    # wired up. Hard-imports python3-saml (onelogin.saml2) at app load.
    'allauth.socialaccount.providers.saml',
]

# Engine apps (no business logic — just infrastructure)
MORPHEUS_ENGINE_APPS = [
    'core',
    'core.assistant',  # Hard-coded Linda AI Assistant
    'core.auth',  # Passwordless email-OTP login (parallel to allauth)
    'core.i18n',  # Translation kernel — generic-FK Translation rows
    'core.audit',  # Security-grade audit log
    'core.errors',  # Deep error log — 5xx + client JS errors → ErrorEvent
    'core.self_improvement',  # Autonomic loop + code review + drift tracking
    'plugins',
    'themes',
    'api',
]

INSTALLED_APPS = (
    DJANGO_APPS
    + THIRD_PARTY_APPS
    + MORPHEUS_ENGINE_APPS
    + ALL_MORPHEUS_PLUGINS  # ← All plugins as Django apps
)

# Discover plugins so they are available in the registry
from plugins.registry import plugin_registry  # noqa: E402 — must follow INSTALLED_APPS build

plugin_registry.discover(ALL_MORPHEUS_PLUGINS)

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.security_headers.SecurityHeadersMiddleware',
    'core.storefront_cache.StorefrontCacheMiddleware',
    # Gzip-compresses responses > 200 bytes. Cloudflare also compresses
    # at the edge but origin compression saves bytes on the CF↔origin
    # hop AND for clients that bypass CF (Bearer-token agents, direct
    # origin probes). Toggle-gated via storefront PluginConfig
    # gzip_enabled — when off, GZipMiddleware sees an env var hint and
    # skips. Brotli is not in Django's stdlib; CF handles br at the edge.
    'django.middleware.gzip.GZipMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # i18n: activate the request language from the URL prefix (/fr/, /sr/ …) for
    # storefront pages. Must sit after SessionMiddleware and before
    # CommonMiddleware. The core language (LANGUAGE_CODE) is served unprefixed.
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'plugins.middleware.PluginMiddleware',
    'themes.middleware.ThemeMiddleware',
    'plugins.installed.markets.middleware.MarketMiddleware',
    'plugins.installed.agent_mcp.middleware.TrustedAgentMiddleware',
    'plugins.installed.ai_assistant.middleware.AIContextMiddleware',
    'api.permissions.AgentAuthMiddleware',
    'api.middleware.GraphQLCacheMiddleware',  # Enterprise: GraphQL Query Caching
    'api.rate_limit.RateLimitMiddleware',
    'core.ratelimit.RateLimitMiddleware',
    'plugins.installed.environments.middleware.EnvironmentMiddleware',
    'plugins.installed.seo.middleware.SeoRedirectMiddleware',
    'plugins.installed.storefront.middleware.StorefrontCacheControlMiddleware',
    'plugins.installed.analytics.middleware.AnalyticsMiddleware',
    # request_id MUST come before error-capture: process_exception runs in
    # reverse MIDDLEWARE order, so error-capture (which reads request.request_id)
    # has to be registered AFTER request_id. With the previous ordering every
    # captured server ErrorEvent had request_id=''.
    'core.request_id.RequestIdMiddleware',
    # N+1 detector — DEBUG-only, zero overhead in prod (the middleware
    # short-circuits when settings.DEBUG is False). Threshold tunable
    # via MORPHEUS_N_PLUS_ONE_THRESHOLD env var.
    'core.query_count_middleware.QueryCountMiddleware',
    'core.errors.middleware.ErrorCaptureMiddleware',
]

ROOT_URLCONF = 'morph.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.store_settings',
                # cart_context moved to the orders plugin (register_context_processor);
                # merged at request time by plugins.context_processors.plugin_context.
                'core.context_processors.display_currency',
                'core.context_processors.channel_context',
                'plugins.installed.catalog.context_processors.nav_categories',
                'plugins.installed.catalog.context_processors.nav_authors',
                'plugins.installed.catalog.context_processors.nav_featured_books',
                'plugins.installed.book_product.context_processors.nav_genres',
                'plugins.installed.book_product.context_processors.nav_topics',
                'plugins.installed.cms.context_processors.nav_menus',
                'plugins.installed.admin_dashboard.context_processors.dashboard_breadcrumbs',
                'themes.context_processors.theme_context',
                'plugins.context_processors.plugin_context',
                'plugins.installed.markets.services.market_context',
            ],
            'loaders': [
                'themes.loaders.ThemeLoader',
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

WSGI_APPLICATION = 'morph.wsgi.application'

# ── Database (Supabase / Postgres) ─────────────────────────────────────────────
# Production: DATABASE_URL must be a Postgres URL (Supabase recommended).
# Tests: a SQLite in-memory DB is used automatically — see _RUNNING_TESTS.
_default_db_url = config(
    'DATABASE_URL',
    default='sqlite:///:memory:' if _RUNNING_TESTS else '',
)
if not _default_db_url:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        'DATABASE_URL must be set. Use a Postgres URL (Supabase recommended). '
        'See .env.example for the exact format.'
    )

DATABASES = {
    'default': dj_database_url.config(default=_default_db_url, conn_max_age=600),
}

# Optional: Add read-replica for enterprise scaling
REPLICA_DB_URL = config('REPLICA_DATABASE_URL', default='')
if REPLICA_DB_URL:
    DATABASES['replica'] = dj_database_url.config(
        default=REPLICA_DB_URL,
        conn_max_age=600,
    )

DATABASE_ROUTERS = ['core.db_router.PrimaryReplicaRouter']

# Postgres SSL mode is operator-controlled. Defaults to 'require' so the
# common Supabase / managed-PG case is safe. Set DATABASE_SSL_MODE=disable
# (or 'prefer') for internal Docker Postgres without SSL certs. Honours the
# `?sslmode=…` query string in DATABASE_URL when present.
_DEFAULT_SSL_MODE = config('DATABASE_SSL_MODE', default='require')
for db_config in DATABASES.values():
    if db_config.get('ENGINE') == 'django.db.backends.postgresql':
        db_config.setdefault('OPTIONS', {})
        db_config['OPTIONS'].setdefault('sslmode', _DEFAULT_SSL_MODE)
    elif db_config.get('ENGINE') == 'django.db.backends.sqlite3':
        # File-backed sqlite (CI runs sqlite:///db.sqlite3) locks coarsely,
        # so a concurrent writer — e.g. the eager outbox publisher writing
        # back an event's retry status while a test holds its transaction —
        # can raise "database table is locked" with the 5s default. A 30s
        # busy_timeout makes the writer wait instead of erroring. Harmless
        # for the in-memory test DB.
        db_config.setdefault('OPTIONS', {})
        db_config['OPTIONS'].setdefault('timeout', 30)

# ── Auth ───────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'customers.Customer'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
# Point @login_required / @staff_member_required at allauth, not Django admin.
# When DEBUG=False the admin URL conf isn't mounted, so the default
# 'admin:login' reverse blows up with NoReverseMatch on unauthenticated hits.
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Cache & Celery ─────────────────────────────────────────────────────────────
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

if _RUNNING_TESTS:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'morpheus-tests',
        }
    }
    # Tests create lots of users; PBKDF2 with 200k iterations dominates the
    # suite runtime. Drop to MD5 in tests only — never reachable in prod
    # because this branch is gated by `_RUNNING_TESTS`.
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
else:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
            },
        }
    }
    DJANGO_REDIS_IGNORE_EXCEPTIONS = True

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TIME_LIMIT = 300  # hard kill after 5 min
CELERY_TASK_SOFT_TIME_LIMIT = 240  # raise SoftTimeLimitExceeded after 4 min
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_BEAT_SCHEDULE = {}  # populated by plugins via plugin.ready()

if _RUNNING_TESTS:
    # Run tasks inline and never dial the (unreachable, in tests) Redis broker /
    # result backend. Without this, any test that creates an object firing a
    # product.*/order.* hook spent minutes retrying the result-backend connection
    # on each .delay(). Eager + no eager-result-store = no broker/backend I/O.
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False
    CELERY_TASK_STORE_EAGER_RESULT = False
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'cache+memory://'

# ── Static & Media ─────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    d
    for d in [
        BASE_DIR / 'static',
        BASE_DIR / 'themes' / 'library' / MORPHEUS_ACTIVE_THEME / 'static',
    ]
    if d.exists()
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_S3 = config('USE_S3', default=False, cast=bool)
if USE_S3:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# ── Internationalization ───────────────────────────────────────────────────────
# Core (default) storefront language — served UNPREFIXED via
# i18n_patterns(prefix_default_language=False). It mirrors StoreSettings.
# core_language (Settings → General); because LANGUAGE_CODE is read at settings
# import (before the DB), a non-'en' core language must also be set here via env.
LANGUAGE_CODE = config('MORPHEUS_CORE_LANGUAGE', default='en')
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Native display name per supported language code (for the switcher + LANGUAGES).
_SUPPORTED_LANGUAGE_NAMES = {
    'en': 'English',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
    'it': 'Italiano',
    'pt': 'Português',
    'nl': 'Nederlands',
    'sr': 'Српски',
    'ru': 'Русский',
    'pl': 'Polski',
    'tr': 'Türkçe',
    'ar': 'العربية',
    'zh-hans': '简体中文',
    'ja': '日本語',
}

# Languages that get URL routing (i18n_patterns) + Accept-Language handling.
# Driven by env so it's opt-in: default is the core language ALONE → no
# prefixes, no redirects, zero behaviour change. Set e.g.
# MORPHEUS_LANGUAGES="en,fr,sr" to activate /fr/ + /sr/ once translated.
# RTL scripts get direction handling in the theme.
_lang_codes = [
    c.strip().lower()
    for c in config('MORPHEUS_LANGUAGES', default=LANGUAGE_CODE).split(',')
    if c.strip()
] or [LANGUAGE_CODE]
if LANGUAGE_CODE not in _lang_codes:  # core language is always routable
    _lang_codes.insert(0, LANGUAGE_CODE)
LANGUAGES = [(c, _SUPPORTED_LANGUAGE_NAMES.get(c, c)) for c in dict.fromkeys(_lang_codes)]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── GraphQL ────────────────────────────────────────────────────────────────────
STRAWBERRY_DJANGO = {
    'FIELD_DESCRIPTION_FROM_HELP_TEXT': True,
    'TYPE_DESCRIPTION_FROM_MODEL_DOCSTRING': True,
}

# ── REST Framework (admin API only) ───────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.MorpheusAPIKeyAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    # ViewSets that expose public-readable resources (e.g. catalog) opt out
    # explicitly with `permission_classes = [AllowAny]`. Everything else
    # requires authentication by default.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 24,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('DRF_THROTTLE_ANON', default='100/hour'),
        'user': config('DRF_THROTTLE_USER', default='1000/hour'),
    },
    'EXCEPTION_HANDLER': 'api.exception_handler.morpheus_exception_handler',
}

# ── CORS ───────────────────────────────────────────────────────────────────────
_default_cors = 'http://localhost:3000,http://127.0.0.1:3000' if DEBUG else ''
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default=_default_cors, cast=Csv())
if not DEBUG and not CORS_ALLOWED_ORIGINS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured('CORS_ALLOWED_ORIGINS must be set when DEBUG=False')
CORS_ALLOW_CREDENTIALS = True

# ── GraphQL hardening ─────────────────────────────────────────────────────────
GRAPHQL_MAX_QUERY_DEPTH = config('GRAPHQL_MAX_QUERY_DEPTH', default=10, cast=int)
GRAPHQL_MAX_ALIASES = config('GRAPHQL_MAX_ALIASES', default=15, cast=int)
# Block `__schema` / `__type` discovery in prod. Override only if you need
# to ship a public IDE.
GRAPHQL_DISABLE_INTROSPECTION_IN_PROD = config(
    'GRAPHQL_DISABLE_INTROSPECTION_IN_PROD',
    default=True,
    cast=bool,
)

# ── Crispy Forms ───────────────────────────────────────────────────────────────

# ── Payments ───────────────────────────────────────────────────────────────────
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# ── Store Settings ─────────────────────────────────────────────────────────────
STORE_NAME = config('STORE_NAME', default='Morpheus Store')
STORE_CURRENCY = config('STORE_CURRENCY', default='USD')
STORE_COUNTRY = config('STORE_COUNTRY', default='US')
STORE_TAX_RATE = config('STORE_TAX_RATE', default=0.0, cast=float)

# ── AI / LLM ───────────────────────────────────────────────────────────────────
AI_PROVIDER = config('AI_PROVIDER', default='openai')  # openai | anthropic | ollama
AI_MODEL = config('AI_MODEL', default='gpt-4o-mini')
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
OLLAMA_BASE_URL = config('OLLAMA_BASE_URL', default='http://localhost:11434')
AI_EMBEDDING_MODEL = config('AI_EMBEDDING_MODEL', default='text-embedding-3-small')

# Tests must NEVER hit a real LLM/embeddings API. A developer's `.env` usually
# has a real OPENAI_API_KEY, and AI tasks run eagerly (CELERY_TASK_ALWAYS_EAGER)
# from product/order hooks during tests — without this they'd POST to
# api.openai.com (slow, flaky, and it polluted OpenAIArgParsingTests). Blanking
# the provider + keys forces every provider factory to the offline mock.
if _RUNNING_TESTS:
    AI_PROVIDER = ''
    OPENAI_API_KEY = ''
    ANTHROPIC_API_KEY = ''

# ── Email ──────────────────────────────────────────────────────────────────────
# Always use the Morpheus Custom backend so admins can configure via dashboard
EMAIL_BACKEND = 'core.email.MorpheusEmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@morpheusstore.io')
EMAIL_USE_TLS = True

# ── Security ───────────────────────────────────────────────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    # The Docker healthcheck hits `http://localhost:8000/healthz` from
    # inside the container; without this exemption Django responds 301
    # → https://localhost:8000 which has no TLS listener. curl returns
    # exit-0 on the 301 anyway, so the container is marked "healthy"
    # before Django has finished warming plugins — Coolify swaps
    # traffic, users see 503 for 10-30s. Exempting /healthz lets the
    # healthcheck verify real readiness.
    SECURE_REDIRECT_EXEMPT = [r'^healthz/?$', r'^api/health/?$', r'^api/ready/?$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# ── Logging ────────────────────────────────────────────────────────────────────
# Pretty text formatter in DEBUG, single-line JSON in production. Every record
# carries `request_id` via the RequestIdFilter so logs correlate end-to-end.
_LOG_FORMAT = 'pretty' if DEBUG else 'json'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {
            '()': 'core.request_id.RequestIdFilter',
        },
    },
    'formatters': {
        'pretty': {
            'format': '[MORPHEUS] {levelname} {asctime} [{request_id}] {module}: {message}',
            'style': '{',
        },
        'json': {
            '()': 'core.log_formatters.JsonFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': _LOG_FORMAT,
            'filters': ['request_id'],
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'morph': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
            'filters': ['request_id'],
        },
        'morpheus': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
            'filters': ['request_id'],
        },
        # Comprehensive error + warning capture so the self-improvement
        # error-log collector (and Morpheus Brain) sees the full picture:
        # request 5xx/4xx, DB issues, security events, deprecations, task
        # failures — all at WARNING so nothing important is silently dropped.
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
            'filters': ['request_id'],
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
            'filters': ['request_id'],
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
            'filters': ['request_id'],
        },
        'celery': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
            'filters': ['request_id'],
        },
        # Surface Python deprecation/runtime warnings through logging too.
        'py.warnings': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
            'filters': ['request_id'],
        },
    },
}

# Route Python's warnings module through logging (py.warnings logger above),
# so deprecations + runtime warnings land in the same stream the error-log
# collector + Morpheus Brain read.
import logging as _logging  # noqa: E402

_logging.captureWarnings(True)

# Bridge ERROR-level app logs into the Morpheus Brain's signal pipeline
# (core.errors.ErrorEvent → error_log collector → SiSignal → Brain). Skipped
# under tests (no DB writes from log lines in the suite). The handler is
# fail-soft + loop-safe; see core/brain/log_handler.py. Attached to the app +
# request/security/celery loggers, NOT db.backends (its own writes log there)
# nor py.warnings (deprecations aren't errors).
if not _RUNNING_TESTS:
    LOGGING['handlers']['error_event'] = {
        'class': 'core.brain.log_handler.ErrorEventLogHandler',
        'level': 'ERROR',
        'filters': ['request_id'],
    }
    for _brain_logger in ('morph', 'morpheus', 'django.request', 'django.security', 'celery'):
        LOGGING['loggers'][_brain_logger]['handlers'].append('error_event')

# ── Self-improvement engine ────────────────────────────────────────────────────
# Configure the autonomic loop. None of these settings are required —
# defaults in core.self_improvement.policy ship sensible thresholds.
SELF_IMPROVEMENT = {
    # Maximum daily token budget across all engine LLM calls. Hard cap;
    # exceeded → analyzer aborts the remainder of the run and logs to Sentry.
    'daily_token_budget': config('SELF_IMPROVEMENT_TOKEN_BUDGET', default=500_000, cast=int),
    # Override per-class policy here, e.g.:
    #   'policy': {'seo_gap': {'auto': 0.95}},
    'policy': {},
    # Where canonical Morpheus lives. Read by the upstream_drift collector
    # when core/customizations.yml doesn't declare an upstream ref.
    'upstream_ref': config('SELF_IMPROVEMENT_UPSTREAM_REF', default=''),
    # Paths the engine treats as protected in addition to core/safety.py's
    # PROTECTED_PATHS. Always a superset, never a relax.
    'extra_protected_paths': [],
    # Weekly digest email recipients.
    'digest_recipients': config('SELF_IMPROVEMENT_DIGEST_RECIPIENTS', default='', cast=Csv()),
}

# ── Sentry ─────────────────────────────────────────────────────────────────────
# init_sentry() is a no-op when SENTRY_DSN is not set. It scrubs Authorization,
# X-Agent-Token, Cookie, and any *password*/*secret*/*token*/*card* keys from
# every event before sending.
try:
    from core.sentry import init_sentry

    init_sentry()
except Exception:  # noqa: BLE001, S110 — observability must never block app boot
    pass
