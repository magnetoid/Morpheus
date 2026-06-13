from django.contrib import admin

from .models import APIKey, StoreChannel, StoreSettings, WebhookEndpoint


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            'General',
            {
                'fields': (
                    'store_name',
                    'store_description',
                    'logo',
                    'favicon',
                    'primary_currency',
                    'country',
                    'timezone',
                    'tax_rate',
                )
            },
        ),
        ('AI Configuration', {'fields': ('ai_provider',)}),
        (
            'SMTP Configuration (Overrides ENV)',
            {
                'fields': (
                    'smtp_host',
                    'smtp_port',
                    'smtp_user',
                    'smtp_password',
                    'default_from_email',
                ),
                'description': 'Leave these blank to use the server environment variables. Filling these out will override the server settings.',
            },
        ),
        ('Contact & Social', {'fields': ('contact_email', 'support_phone', 'social_links')}),
        ('SEO', {'fields': ('meta_title', 'meta_description')}),
    )

    def has_add_permission(self, request):
        # Enforce Singleton pattern
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(StoreChannel)
class StoreChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'is_active', 'created_at')
    search_fields = ('name', 'domain')


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'key_prefix', 'channel', 'is_active', 'created_at')
    readonly_fields = ('key_prefix', 'key_hash', 'created_at')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        raw = getattr(obj, '_raw_key', None)
        if raw:
            from django.contrib import messages

            messages.warning(
                request,
                f'Copy this API token now — it is stored hashed and will not be shown again: {raw}',
            )


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'created_at')
