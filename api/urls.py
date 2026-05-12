"""
Morpheus CMS — API URLs (versioned).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api import views
from api.rest import CategoryViewSet, OrderViewSet, ProductViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'orders', OrderViewSet, basename='order')


def graphql_view(agent_only: bool = False):
    from api.graphql_view import morpheus_graphql_view
    return morpheus_graphql_view(agent_only=agent_only)


urlpatterns = [
    path('healthz', views.healthz, name='healthz'),
    path('healthz/', views.healthz),  # tolerate trailing slash from naive probes
    path('healthz/deep', views.healthz_deep, name='healthz_deep'),
    path('readyz', views.readyz, name='readyz'),
    path('readyz/', views.readyz),
    path('graphql/', graphql_view(), name='graphql'),
    path('graphql/agent/', graphql_view(agent_only=True), name='graphql_agent'),
    path('v1/', include(router.urls)),
]
