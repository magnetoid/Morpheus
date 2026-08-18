"""Machine-facing endpoints: sitemaps, robots, feeds, discovery files.

These are mounted with ``surface='chrome'`` (see ``app.py``), which keeps them
OUT of ``i18n_patterns``. They used to be mounted as storefront routes, so a
multi-language store published a second copy of every one of them under each
language prefix — ``/fr/robots.txt``, ``/fr/sitemap.xml``, ``/fr/llms.txt`` — none
of which any crawler should ever see. A sitemap is not a page; it has no
translation.
"""

from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt

from plugins.installed.seo import views

app_name = 'seo'

urlpatterns = [
    path('.well-known/security.txt', views.security_txt, name='security_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap'),
    path('sitemap-index.xml', views.sitemap_index_xml, name='sitemap_index'),
    path('sitemap-images.xml', views.image_sitemap_xml, name='image_sitemap'),
    path('sitemap-news.xml', views.news_sitemap_xml, name='news_sitemap'),
    path('robots.txt', views.robots_txt, name='robots'),
    path('llms.txt', views.llms_txt, name='llms_txt'),
    path('llms-full.txt', views.llms_full_txt, name='llms_full_txt'),
    path('agents.md', views.agents_md, name='agents_md'),
    path('ai/products.json', views.ai_products_feed, name='ai_feed'),
    path('md/products/<slug:slug>', views.product_markdown, name='product_md'),
    # web-vitals beacon: browser-initiated POST, no CSRF token available.
    # Body is validated (metric name allow-list) and writes to audit log only.
    path('web-vitals/', csrf_exempt(views.web_vitals_beacon), name='web_vitals'),
    path('opensearch.xml', views.opensearch_xml, name='opensearch'),
    path('journal/feed.xml', views.journal_rss, name='journal_rss'),
    path('journal/atom.xml', views.journal_atom, name='journal_atom'),
    path('img/<str:fmt>/<int:width>/<path:path>', views.image_variant, name='image_variant'),
    # The IndexNow ownership key. Constrained to the hex shape the protocol
    # specifies: as a bare `<str:key>.txt` this was a root-level catch-all that
    # shadowed every other top-level `.txt` route the platform might add.
    re_path(r'^(?P<key>[A-Fa-f0-9]{8,128})\.txt$', views.indexnow_keyfile, name='indexnow_key'),
]
