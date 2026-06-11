"""
Morpheus CMS — REST API v1
Versioned, filterable, channel-scoped storefront REST layer.
"""

from __future__ import annotations

from typing import Any

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, serializers, viewsets

from plugins.installed.catalog.models import Category, Product
from plugins.installed.orders.models import Order

# ── Serializers ───────────────────────────────────────────────────────────────


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'is_active']


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'short_description',
            'price',
            'category',
            'status',
            'is_featured',
            'created_at',
        ]

    def get_price(self, obj: Product) -> dict[str, str]:
        if obj.price:
            return {'amount': str(obj.price.amount), 'currency': obj.price.currency.code}
        return {'amount': '0.00', 'currency': 'USD'}


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'status', 'payment_status', 'placed_at']


# ── ViewSets ─────────────────────────────────────────────────────────────────


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Public storefront: anyone can list/read active products."""

    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'status': ['exact'],
        'is_featured': ['exact'],
        'category__slug': ['exact'],
    }
    search_fields = ['name', 'short_description', 'description']
    ordering_fields = ['name', 'price', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self) -> Any:
        qs = (
            Product.objects.filter(status='active')
            .select_related('category', 'vendor')
            .prefetch_related('variants', 'images', 'tags')
        )

        api_key = getattr(self.request, '_morpheus_api_key', None)
        if api_key and api_key.channel_id:
            qs = qs.filter(channels=api_key.channel)
        return qs


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Public storefront: anyone can list/read active categories."""

    queryset = Category.objects.filter(is_active=True).select_related('parent')
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Authenticated customers see only their own orders.
    API keys with the `read:orders` scope (admin) see everything within their channel.
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> Any:
        request = self.request
        qs = Order.objects.select_related('customer', 'channel').prefetch_related('items')

        api_key = getattr(request, '_morpheus_api_key', None)
        if api_key is not None:
            if not api_key.has_scope('read:orders'):
                return Order.objects.none()
            if api_key.channel_id:
                qs = qs.filter(channel=api_key.channel)
            return qs

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return Order.objects.none()
        if user.is_staff or user.is_superuser:
            return qs
        return qs.filter(customer=user)
