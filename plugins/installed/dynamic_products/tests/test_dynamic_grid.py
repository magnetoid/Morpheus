from decimal import Decimal
from django.test import TestCase, RequestFactory
from plugins.installed.catalog.models import Product, Category
from plugins.installed.dynamic_products.models import DynamicBlock, DynamicGridItem
from plugins.installed.dynamic_products.services import calculate_grid_probabilities, recommend

class DynamicGridTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.category = Category.objects.create(name='Test Category', slug='test-cat')
        
        # Create test products
        self.product_high = Product.objects.create(
            name='High Prob Book',
            slug='high-prob',
            price=Decimal('19.99'),
            category=self.category,
            status='active'
        )
        self.product_low = Product.objects.create(
            name='Low Prob Book',
            slug='low-prob',
            price=Decimal('9.99'),
            category=self.category,
            status='active'
        )
        
        # Set mock attributes to influence probability calculation
        # High prob product: good sales, high popularity, high trend
        setattr(self.product_high, 'recent_sales_score', 0.9)
        setattr(self.product_high, 'view_count_score', 0.8)
        setattr(self.product_high, 'trend_velocity', 0.9)
        
        # Low prob product: low sales, low popularity, low trend
        setattr(self.product_low, 'recent_sales_score', 0.1)
        setattr(self.product_low, 'view_count_score', 0.2)
        setattr(self.product_low, 'trend_velocity', 0.1)

    def test_calculate_grid_probabilities(self):
        """Test the algorithm calculates and assigns probabilities correctly."""
        # Calculate probabilities
        result = calculate_grid_probabilities()
        self.assertEqual(result['updated'], 2)
        
        # Verify DynamicGridItems were created
        self.assertEqual(DynamicGridItem.objects.count(), 2)
        
        item_high = DynamicGridItem.objects.get(product=self.product_high)
        item_low = DynamicGridItem.objects.get(product=self.product_low)
        
        # Verify high product got higher probability
        self.assertGreater(item_high.purchase_probability, item_low.purchase_probability)
        
        # Verify metadata is copied
        self.assertEqual(item_high.title, 'High Prob Book')
        self.assertEqual(item_high.genre, 'Test Category')

    def test_probability_grid_strategy(self):
        """Test the probability_grid strategy returns correctly sorted products."""
        # Force specific probabilities
        DynamicGridItem.objects.create(
            product=self.product_high,
            title='High',
            purchase_probability=0.85
        )
        DynamicGridItem.objects.create(
            product=self.product_low,
            title='Low',
            purchase_probability=0.25
        )
        
        block = DynamicBlock.objects.create(
            name='Test Grid',
            slot='home_below_grid',
            strategy='probability_grid',
            limit=4
        )
        
        request = self.factory.get('/')
        products = recommend(block, request=request)
        
        # Should return both products, high probability first
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].id, self.product_high.id)
        self.assertEqual(products[1].id, self.product_low.id)
