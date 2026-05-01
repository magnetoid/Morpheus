"""
Morpheus CMS - Customer (Auth User) Model
"""
import uuid
from django.contrib.auth.models import AbstractUser
from morpheus import models


class Customer(AbstractUser):
    """
    Custom user model — replaces Django's default User.

    Serves as the unified contact record: store customers, B2B contacts,
    captured leads, manual entries, and staff all live in one table.
    The `source` field marks where each contact arrived from so the
    dashboard can filter (orders / signup / lead form / manual / …).
    """

    SOURCE_CHOICES = [
        ('order', 'Order'),
        ('signup', 'Signup'),
        ('lead_form', 'Lead form'),
        ('newsletter', 'Newsletter'),
        ('import', 'Import'),
        ('manual', 'Manual entry'),
        ('agent', 'Agent-captured'),
        ('referral', 'Referral'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to='customers/avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    accepts_marketing = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='other', db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Override username to be optional (email-first auth)
    username = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def default_address(self):
        return self.addresses.filter(is_default=True).first()


class Address(models.Model):
    ADDRESS_TYPES = [
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='shipping')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=200, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='US')
    phone = models.CharField(max_length=30, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.address_line1}, {self.city}, {self.country}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Unset other defaults for same customer & type
            Address.objects.filter(
                customer=self.customer,
                address_type=self.address_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class WishList(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='wishlist')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist of {self.customer.email}"


class WishListItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist = models.ForeignKey(WishList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product')

    def __str__(self):
        return f"{self.product.name} in {self.wishlist}"
