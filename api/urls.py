"""
Morpheus CMS — API URLs (versioned).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api import views
from api.llm_tasks import llm_task_create, llm_task_status
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
    # Long-running LLM completions — polling pattern. The POST returns
    # a task_id immediately; the LLM call runs on a Celery worker so
    # the gunicorn pool isn't held. (docs/plans/concurrency-roadmap.md)
    path('api/llm-tasks/', llm_task_create, name='llm_task_create'),
    path('api/llm-tasks/<str:task_id>/', llm_task_status, name='llm_task_status'),
    # CSP report-only sink (see core/security_headers.py). Logs every
    # violation; we'll mine the log to tighten the policy before flipping
    # to enforcing.
    path('api/csp-report/', views.csp_report, name='csp_report'),
]
