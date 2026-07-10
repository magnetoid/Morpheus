"""Booking marketplace — experiences and products bookable by date + guests.

A `catalog.Vendor` (a local *host*) offers `BookableService`s (tours, activities,
rentals) that run on certain weekdays with a per-day seat `daily_capacity`.
Customers either:

- **book** a concrete `booking_date` for N `guests` (marketplace mode), or
- **enquire** ("Contact for price") via an `Enquiry` (listing mode — the
  default).

Pricing, the 12% service fee and capacity checks are derived server-side in
`services.py` — never trust client totals. Ships DISABLED by default; a deployment enables it
`services.py`; enable it from Dashboard → Apps.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from djmoney.models.fields import MoneyField

# Regions used to browse listings by area. Brand-neutral by default; a
# deployment configures its own via the BOOKING_REGIONS setting
# (`[("slug", "Label"), …]`). Empty by default so core ships no hardcoded
# geography — regions_index also derives areas from live data when unset.
REGIONS = getattr(settings, 'BOOKING_REGIONS', [])

# Generic destination types. Override per deployment via BOOKING_PLACE_TYPES.
PLACE_TYPES = getattr(
    settings,
    'BOOKING_PLACE_TYPES',
    [
        ('coastal', 'Coastal'),
        ('mountains', 'Mountains'),
        ('national_parks', 'National Parks'),
        ('cultural', 'Cultural Sites'),
        ('lakes', 'Lakes & Rivers'),
        ('cities', 'Cities & Towns'),
    ],
)


class BookableService(models.Model):
    """An experience a host offers — booked by date + guest count."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'catalog.Vendor', on_delete=models.CASCADE, related_name='bookable_services'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=300, blank=True, default='')
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        'catalog.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookable_services',
    )
    region = models.CharField(max_length=20, choices=REGIONS, blank=True, default='', db_index=True)
    location = models.CharField(
        max_length=120, blank=True, default='', help_text='Town or specific place.'
    )
    image = models.ImageField(upload_to='experiences/', blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=120)
    duration_label = models.CharField(
        max_length=60,
        blank=True,
        default='',
        help_text="Display duration, e.g. '4 hours' / 'Full day'.",
    )
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    original_price = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency='EUR',
        null=True,
        blank=True,
        help_text='Optional was-price for a strikethrough discount.',
    )
    is_bestseller = models.BooleanField(default=False, db_index=True)
    # Denormalised display rating (seeded / editorial); live reviews are in ServiceReview.
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    highlights = models.JSONField(default=list, blank=True)
    included = models.JSONField(default=list, blank=True)
    not_included = models.JSONField(default=list, blank=True)
    faqs = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"q": "...", "a": "..."}] — shown as "Guest questions".',
    )
    LISTING_KINDS = [
        ('experience', 'Experience'),  # date + departure + guests + tiers
        ('product', 'Product'),  # quantity + enquiry, no date/shipping
    ]
    listing_kind = models.CharField(
        max_length=12,
        choices=LISTING_KINDS,
        default='experience',
        db_index=True,
        help_text='Experience (bookable by date) or product (quantity + enquiry).',
    )
    meeting_point = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    languages = models.JSONField(default=list, blank=True)
    what_to_bring = models.JSONField(default=list, blank=True)
    itinerary = models.JSONField(
        default=list, blank=True, help_text='[{"title": "...", "detail": "..."}]'
    )
    # Per-DATE seat capacity (a tour can take this many guests/day across all
    # bookings). max_guests_per_booking caps a single party.
    daily_capacity = models.PositiveIntegerField(default=10)
    max_guests_per_booking = models.PositiveIntegerField(default=10)
    cancellation_policy = models.TextField(
        blank=True,
        default='Free cancellation up to 24 hours before the experience.',
    )
    requires_approval = models.BooleanField(
        default=False,
        help_text='If on, bookings start as pending until the host confirms.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.vendor_id})'


class AvailabilityWindow(models.Model):
    """A weekday on which the experience runs (optional start/end time).

    Presence of any window restricts bookable dates to those weekdays; with no
    windows the experience is treated as available every day (capacity-limited).
    """

    WEEKDAYS = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        BookableService, on_delete=models.CASCADE, related_name='availability'
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS, db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ['weekday', 'start_time']

    def __str__(self) -> str:
        return self.get_weekday_display()


class Booking(models.Model):
    """A customer's reservation of an experience for a date + guest count."""

    STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(BookableService, on_delete=models.PROTECT, related_name='bookings')
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_bookings',
    )
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40, blank=True, default='')
    booking_date = models.DateField(db_index=True)
    time_slot = models.CharField(max_length=40, blank=True, default='')
    guests = models.PositiveIntegerField(default=1)
    # All money is server-derived in services.create_booking (never client-sent).
    subtotal = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    service_fee = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    total_price = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    tier_breakdown = models.JSONField(default=list, blank=True)
    addons = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-booking_date', '-created_at']
        indexes = [models.Index(fields=['service', 'booking_date'])]

    def __str__(self) -> str:
        return f'{self.service_id} on {self.booking_date} ×{self.guests} ({self.status})'


class Enquiry(models.Model):
    """A "Contact for price" lead captured in listing mode (anon-allowed)."""

    STATUS = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('closed', 'Closed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        BookableService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_enquiries',
    )
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    guests = models.PositiveIntegerField(null=True, blank=True)
    time_slot = models.CharField(max_length=40, blank=True, default='')
    tier_breakdown = models.JSONField(default=list, blank=True)
    addons = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='new', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Enquiries'

    def __str__(self) -> str:
        return f'Enquiry from {self.email} ({self.status})'


class ServiceReview(models.Model):
    """A guest review of an experience — gated on a real confirmed/completed
    booking in services.create_review (server-side trust, like the reference)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(BookableService, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_reviews',
    )
    booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews'
    )
    author_name = models.CharField(max_length=200, blank=True, default='')
    rating = models.PositiveSmallIntegerField(default=5)
    title = models.CharField(max_length=200, blank=True, default='')
    body = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['service', 'customer'], name='one_review_per_customer_service'
            )
        ]

    def __str__(self) -> str:
        return f'{self.rating}★ {self.service_id} by {self.author_name or self.customer_id}'


class Place(models.Model):
    """A destination (town or area) with editorial content.

    Parity with the reference site's Places section. A place's detail page lists
    the experiences that run there (matched by location name or region).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    region = models.CharField(max_length=20, choices=REGIONS, blank=True, default='', db_index=True)
    place_type = models.CharField(
        max_length=20, choices=PLACE_TYPES, blank=True, default='', db_index=True
    )
    summary = models.CharField(max_length=300, blank=True, default='')
    description = models.TextField(blank=True, default='')
    highlights = models.JSONField(default=list, blank=True)
    image = models.ImageField(upload_to='places/', blank=True, null=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self) -> str:
        return self.name


class ServiceImage(models.Model):
    """Gallery image for an experience (beyond the single cover `image`)."""

    service = models.ForeignKey(BookableService, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='experiences/gallery/')
    alt = models.CharField(max_length=160, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        return f'{self.service.name} image #{self.pk}'


class PricingTier(models.Model):
    """A per-person price band for an experience (Adult / Child / …).

    A service with no active tiers falls back to its flat `price` as a single
    implicit tier (see services.price_quote)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(BookableService, on_delete=models.CASCADE, related_name='tiers')
    name = models.CharField(max_length=80)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    min_qty = models.PositiveIntegerField(default=0)
    max_qty = models.PositiveIntegerField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        return f'{self.name} @ {self.price}'


class AddOn(models.Model):
    """An optional paid extra for an experience (gear, pickup, photos)."""

    PRICE_TYPES = [('per_person', 'Per person'), ('per_booking', 'Per booking')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(BookableService, on_delete=models.CASCADE, related_name='addons')
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True, default='')
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    price_type = models.CharField(max_length=12, choices=PRICE_TYPES, default='per_person')
    is_required = models.BooleanField(default=False)
    max_qty = models.PositiveIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        return f'{self.name} (+{self.price})'
