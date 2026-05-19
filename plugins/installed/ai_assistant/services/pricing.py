import logging
from decimal import Decimal
from djmoney.money import Money
from plugins.installed.ai_assistant.models import DynamicPriceRule

logger = logging.getLogger('morpheus.ai.pricing')

class DynamicPricingService:
    """
    Law 0: Agentic First, but highly scalable.
    This service calculates the price of a product using cached AI multipliers.
    The actual AI evaluation happens asynchronously to prevent blocking the HTTP thread.
    """

    @classmethod
    def calculate(cls, base_money, product=None, customer=None):
        """
        Calculates the real-time dynamic price.
        Executed via the MorpheusEvents.PRODUCT_CALCULATE_PRICE hook.
        """
        if not product:
            return base_money
            
        try:
            # Extremely fast DB read (often cached by Django query cache)
            rule = DynamicPriceRule.objects.get(product=product)
            multiplier = rule.multiplier
        except DynamicPriceRule.DoesNotExist:
            multiplier = Decimal('1.0000')

        # Additional quick heuristics based on customer could be applied here
        # e.g., if customer is a VIP, apply a quick 5% discount on top
        customer_discount = Decimal('1.0000')
        if customer and getattr(customer, 'is_vip', False):
            customer_discount = Decimal('0.9500')

        from core.money import money

        # multiplier and customer_discount are Decimals, base_money is Money;
        # money() quantizes the chain so the DB never sees ``19.99750000…``
        # arithmetic noise.
        return money(
            Decimal(str(base_money.amount)) * multiplier * customer_discount,
            str(base_money.currency),
        )

    @classmethod
    def evaluate_product_price(cls, product):
        """Rule-based dynamic-pricing evaluator (runs hourly via Celery).

        Reads inventory level for the product's first variant and writes
        a DynamicPriceRule row that ``calculate()`` later reads on every
        PRODUCT_CALCULATE_PRICE hook fire. Rules:

          inventory > 100  →  multiplier 0.95  ("clear stock")
          inventory < 10   →  multiplier 1.15  ("scarcity premium")
          otherwise        →  multiplier 1.00

        The agent-driven version (which would consult competitor data
        and demand signals via an LLM) is intentionally deferred —
        the prior implementation built a prompt and threw it away
        while logging "AI Pricing Engine" messages, which misled
        merchants into thinking real reasoning was happening.
        """
        try:
            variant = product.variants.first()
            inventory_level = variant.inventory_quantity if variant else 0

            if inventory_level > 100:
                new_multiplier = Decimal('0.9500')
                reasoning = "High inventory — discount to clear stock."
            elif inventory_level < 10:
                new_multiplier = Decimal('1.1500')
                reasoning = "Low inventory — scarcity premium."
            else:
                new_multiplier = Decimal('1.0000')
                reasoning = "Normal stock — standard pricing."

            DynamicPriceRule.objects.update_or_create(
                product=product,
                defaults={'multiplier': new_multiplier, 'reasoning': reasoning},
            )
            logger.info(
                'pricing.evaluate_product_price: %s → x%s (%s)',
                product.slug, new_multiplier, reasoning,
            )
        except Exception as e:  # noqa: BLE001 — hourly cron must not stop on one bad row
            logger.warning('pricing.evaluate_product_price failed for %s: %s', product.slug, e)
