from django.contrib import admin

from plugins.installed.product_videos.models import ProductVideo


@admin.register(ProductVideo)
class ProductVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'is_active', 'sort_order', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'url', 'product__name', 'product__sku')
    raw_id_fields = ('product',)
    ordering = ('product', 'sort_order')
    fieldsets = (
        (
            None,
            {
                'fields': ('product', 'title', 'sort_order', 'is_active'),
            },
        ),
        (
            'Source',
            {
                'fields': ('url', 'embed_html', 'poster_url'),
                'description': 'Set <em>url</em> (YouTube/Vimeo auto-detected) '
                'OR paste raw iframe markup into <em>embed_html</em>.',
            },
        ),
    )
