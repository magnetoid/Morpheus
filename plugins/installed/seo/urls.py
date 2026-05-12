from django.urls import path

from plugins.installed.seo import views

app_name = 'seo'

urlpatterns = [
    path('sitemap.xml', views.sitemap_xml, name='sitemap'),
    path('sitemap-images.xml', views.image_sitemap_xml, name='image_sitemap'),
    path('robots.txt', views.robots_txt, name='robots'),
    path('llms.txt', views.llms_txt, name='llms_txt'),
    path('llms-full.txt', views.llms_full_txt, name='llms_full_txt'),
    path('ai/products.json', views.ai_products_feed, name='ai_feed'),
    path('md/products/<slug:slug>', views.product_markdown, name='product_md'),
    path('web-vitals/', views.web_vitals_beacon, name='web_vitals'),
]
