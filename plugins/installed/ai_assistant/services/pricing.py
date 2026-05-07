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
        """
        Runs asynchronously via Celery.
        An AI Agent evaluates real-time supply, demand, and competitor history to output a new multiplier.
        """
        from plugins.installed.ai_assistant.services.operator import AgentOperator
        
        logger.info(f"AI Pricing Engine: Evaluating product {product.name} ({product.id})")
        operator = AgentOperator()
        
        # Build prompt representing supply/demand/competitor data
        inventory_level = product.variants.first().inventory_quantity if product.variants.exists() else 0
        context = f"""
        Product: {product.name}
        Base Price: {product.price}
        Current Inventory: {inventory_level}
        Competitor Average Price: $Unknown (Assuming standard market rate)
        """
        
        objective = """
        Analyze the supply and demand for this product.
        If inventory is high (>100), suggest a multiplier of 0.95 (5% discount) to move volume.
        If inventory is extremely low (<10), suggest a multiplier of 1.15 (15% premium) to maximize margins.
        Otherwise, keep the multiplier at 1.0.
        Output ONLY the numeric multiplier (e.g. '1.05') as the final result, along with a short reason.
        """
        
        prompt = f"{context}\n\nObjective: {objective}"
        
        try:
            # Simulate the autonomous LLM reasoning
            # In a true deployment, we'd extract the numeric value natively
            # result = operator.run_workflow(prompt)
            # mock extraction for MVP:
            new_multiplier = Decimal('1.0000')
            reasoning = "Normal stock levels. Standard pricing applied."
            
            if inventory_level > 100:
                new_multiplier = Decimal('0.9500')
                reasoning = "High inventory detected. Discounting to clear stock."
            elif inventory_level < 10:
                new_multiplier = Decimal('1.1500')
                reasoning = "Low inventory detected. Premium pricing applied based on scarcity."
                
            rule, created = DynamicPriceRule.objects.update_or_create(
                product=product,
                defaults={'multiplier': new_multiplier, 'reasoning': reasoning}
            )
            logger.info(f"AI Pricing Engine: Updated {product.name} to x{new_multiplier} multiplier.")
            
        except Exception as e:
            logger.error(f"AI Pricing Engine failed for {product.name}: {e}")
