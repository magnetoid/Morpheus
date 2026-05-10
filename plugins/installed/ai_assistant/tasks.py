import logging
from celery import shared_task
from plugins.installed.ai_assistant.services.operator import AgentOperator

logger = logging.getLogger('morpheus.ai.tasks')

@shared_task
def update_recommendations_after_order(order_id):
    logger.info(f"AI Task: Updating recommendations for order {order_id}")
    operator = AgentOperator()
    operator.run_workflow(f"Order {order_id} placed. Analyze the purchased products and update the semantic recommendation clusters.")

@shared_task
def record_product_view(product_id, customer_id=None, session_key=None):
    logger.info(f"AI Task: Recorded product view {product_id} for user {customer_id}")

@shared_task
def initialize_customer_memory(customer_id):
    logger.info(f"AI Task: Initializing memory vector space for customer {customer_id}")
    operator = AgentOperator()
    operator.run_workflow(f"Customer {customer_id} just registered. Create an initial preference graph based on their registration domain and first session data.")

@shared_task
def log_search_event(query, results_count, customer_id=None):
    logger.info(f"AI Task: Logging search intent for query: '{query}'")

@shared_task
def generate_cart_recovery(cart_id):
    logger.info(f"AI Task: Generating personalized cart recovery for cart {cart_id}")
    operator = AgentOperator()
    # Autonomous agent generates a highly specific, high-conversion email snippet
    operator.run_workflow(f"Cart {cart_id} abandoned. Review the items and generate a hyper-personalized 2-sentence recovery message focusing on the main product's primary benefit. Do not use generic discount language.")

@shared_task
def generate_product_description(product_id):
    logger.info(f"AI Task: Autonomously generating product description for {product_id}")
    operator = AgentOperator()
    operator.run_workflow(f"Product {product_id} was just created but lacks a description. Retrieve its name, category, and metadata, and autonomously write a compelling, SEO-optimized 3-paragraph product description.")

@shared_task(bind=True, time_limit=60, soft_time_limit=45)
def refresh_product_embedding(self, product_id):
    """Compute and persist the embedding for a product (idempotent on text hash)."""
    from plugins.installed.catalog.models import Product
    from plugins.installed.ai_assistant.services.search import upsert_product_embedding
    try:
        product = Product.objects.select_related('category').get(pk=product_id)
    except Product.DoesNotExist:
        return
    upsert_product_embedding(product)


@shared_task
def pulse_daily_refresh():
    """Linda's Pulse — refresh proactive insight cards on the dashboard.

    Runs once a day (06:00 server TZ) plus on event triggers
    (low_stock, return.requested, cart_abandoned). Each pass evaluates
    six signals and upserts the resulting MerchantInsight rows; the
    dashboard panel renders the top-5 unread cards.
    """
    logger.info('AI Task: refreshing Linda\'s Pulse insights')
    try:
        from plugins.installed.ai_assistant.services.pulse import generate_pulse_insights
        out = generate_pulse_insights()
        logger.info('Pulse: %d insight(s) emitted', len(out))
    except Exception as e:  # noqa: BLE001
        logger.warning('Pulse: refresh failed: %s', e, exc_info=True)


@shared_task
def evaluate_all_product_prices():
    """
    Periodic task (e.g., hourly) to re-evaluate prices for all active products
    using the Dynamic Pricing Engine. No-ops when dynamic pricing is
    disabled in plugin config so scheduling is safe by default.
    """
    try:
        from plugins.registry import plugin_registry
        plugin = plugin_registry.get('ai_assistant')
        if plugin is None or not plugin.get_config_value('enable_dynamic_pricing', False):
            return
    except Exception:  # noqa: BLE001
        return
    logger.info("AI Task: Starting global dynamic price evaluation...")
    from plugins.installed.catalog.models import Product
    from plugins.installed.ai_assistant.services.pricing import DynamicPricingService

    products = Product.objects.filter(status='active')
    for product in products:
        DynamicPricingService.evaluate_product_price(product)

