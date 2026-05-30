import logging
from celery import shared_task
from plugins.installed.ai_assistant.services.operator import AgentOperator

logger = logging.getLogger('morpheus.ai.tasks')


@shared_task
def update_recommendations_after_order(order_id):
    logger.info(f'AI Task: Updating recommendations for order {order_id}')
    operator = AgentOperator()
    operator.run_workflow(
        f'Order {order_id} placed. Analyze the purchased products and update the semantic recommendation clusters.'
    )


@shared_task
def initialize_customer_memory(customer_id):
    logger.info(f'AI Task: Initializing memory vector space for customer {customer_id}')
    operator = AgentOperator()
    operator.run_workflow(
        f'Customer {customer_id} just registered. Create an initial preference graph based on their registration domain and first session data.'
    )


@shared_task
def generate_cart_recovery(cart_id):
    logger.info(f'AI Task: Generating personalized cart recovery for cart {cart_id}')
    operator = AgentOperator()
    # Autonomous agent generates a highly specific, high-conversion email snippet
    operator.run_workflow(
        f"Cart {cart_id} abandoned. Review the items and generate a hyper-personalized 2-sentence recovery message focusing on the main product's primary benefit. Do not use generic discount language."
    )


@shared_task
def generate_product_description(product_id):
    logger.info(f'AI Task: Autonomously generating product description for {product_id}')
    operator = AgentOperator()
    operator.run_workflow(
        f'Product {product_id} was just created but lacks a description. Retrieve its name, category, and metadata, and autonomously write a compelling, SEO-optimized 3-paragraph product description.'
    )


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


@shared_task(bind=True, time_limit=600, soft_time_limit=540)
def refresh_product_embeddings_bulk(self, product_ids):
    """Compute embeddings for a list of products in a single task.

    Use this when bulk-importing or re-embedding the whole catalog
    after switching providers — sending 1000 individual
    `refresh_product_embedding.delay()` calls floods the queue and
    burns worker slots on overhead. This batches the work so the
    Celery worker handles N products on one connection.

    Idempotent: `upsert_product_embedding` skips products whose source
    text hash already matches the stored embedding.

    Args:
        product_ids: list[str|UUID] — up to 200 ids per call. Split
            larger sets across multiple invocations.
    """
    from plugins.installed.catalog.models import Product
    from plugins.installed.ai_assistant.services.search import upsert_product_embedding

    ids = list(product_ids or [])[:200]
    if not ids:
        return {'processed': 0, 'skipped': 0, 'errored': 0}

    qs = Product.objects.select_related('category').filter(pk__in=ids)
    processed = 0
    errored = 0
    for product in qs.iterator():
        try:
            upsert_product_embedding(product)
            processed += 1
        except Exception as e:  # noqa: BLE001 — one bad product mustn't stop the batch
            errored += 1
            logger.warning(
                'bulk embed: product=%s failed: %s',
                product.pk,
                e,
                exc_info=True,
            )
    logger.info(
        'bulk embed: processed=%d errored=%d (batch_size=%d)',
        processed,
        errored,
        len(ids),
    )
    return {'processed': processed, 'skipped': len(ids) - processed - errored, 'errored': errored}


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def run_completion_task(self, task_id, prompt, system='', max_tokens=1000, temperature=0.6):
    """Run an LLM completion off the request thread, write result to cache.

    Pairs with `/api/llm-tasks/` polling endpoint (api/llm_tasks.py).
    Always writes a final terminal status (done | failed) so the
    poller doesn't hang on an abandoned task. TTL is 1 hour.
    """
    from django.core.cache import cache

    key = f'llm-task:{task_id}'
    # Preserve the owner_id stamped by the creator endpoint — the
    # status poller checks it for ownership.
    prior = cache.get(key) or {}
    owner_id = prior.get('owner_id')
    try:
        from plugins.installed.ai_assistant.services.llm import get_llm

        gateway = get_llm()
        text = gateway.complete(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        cache.set(
            key,
            {'status': 'done', 'result': text or '', 'owner_id': owner_id},
            timeout=3600,
        )
    except Exception as e:  # noqa: BLE001 — any failure becomes a terminal error
        logger.warning('run_completion_task %s failed: %s', task_id, e, exc_info=True)
        cache.set(
            key,
            {'status': 'failed', 'error': str(e)[:500], 'owner_id': owner_id},
            timeout=3600,
        )


@shared_task
def reembed_all_products(batch_size: int = 50):
    """Queue a series of bulk-embed tasks covering every active
    product. Use after switching embedding providers or when adopting
    semantic search for the first time. Idempotent — re-running has
    no effect on products whose source text didn't change.

    Splits work into chunks of `batch_size` and dispatches each as its
    own `refresh_product_embeddings_bulk` task so the queue stays fluid
    and one slow chunk doesn't block the rest.
    """
    from plugins.installed.catalog.models import Product

    ids = list(Product.objects.filter(status='active').values_list('id', flat=True))
    if not ids:
        return {'dispatched_chunks': 0, 'total_products': 0}
    chunks = [ids[i : i + batch_size] for i in range(0, len(ids), batch_size)]
    for chunk in chunks:
        refresh_product_embeddings_bulk.delay([str(i) for i in chunk])
    logger.info(
        'reembed_all_products: dispatched %d chunk(s) covering %d product(s)',
        len(chunks),
        len(ids),
    )
    return {'dispatched_chunks': len(chunks), 'total_products': len(ids)}


@shared_task
def pulse_daily_refresh():
    """Linda's Pulse — refresh proactive insight cards on the dashboard.

    Runs once a day (06:00 server TZ) plus on event triggers
    (low_stock, return.requested, cart_abandoned). Each pass evaluates
    six signals and upserts the resulting MerchantInsight rows; the
    dashboard panel renders the top-5 unread cards.
    """
    logger.info("AI Task: refreshing Linda's Pulse insights")
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
    logger.info('AI Task: Starting global dynamic price evaluation...')
    from plugins.installed.catalog.models import Product
    from plugins.installed.ai_assistant.services.pricing import DynamicPricingService

    products = Product.objects.filter(status='active')
    for product in products:
        DynamicPricingService.evaluate_product_price(product)
