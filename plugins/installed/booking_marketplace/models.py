"""Booking marketplace — Montenegro experiences bookable by date + guests.

A `catalog.Vendor` (a local *host*) offers `BookableService`s (tours, activities,
rentals) that run on certain weekdays with a per-day seat `daily_capacity`.
Customers either:

- **book** a concrete `booking_date` for N `guests` (marketplace mode), or
- **enquire** ("Contact for price") via an `Enquiry` (listing mode — opt-in via
  BOOKING_ENQUIRY_MODE=1, mirrors the reference montenegro-experience-hub site).

Pricing, the 12% service fee and capacity checks are derived server-side in
`services.py` — never trust client totals. Ships DISABLED by default; the
Montenegro deployment enables it via migration 0002.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from djmoney.models.fields import MoneyField

# Montenegro regions — used to browse experiences by area (parity with the
# reference site's region tiles). Stored as a slug-ish key; label shown in UI.
REGIONS = [
    ('kotor', 'Kotor Bay'),
    ('budva', 'Budva Riviera'),
    ('durmitor', 'Durmitor & the North'),
    ('skadar', 'Lake Skadar'),
    ('podgorica', 'Podgorica'),
    ('ulcinj', 'Ulcinj & the south coast'),
    ('tivat', 'Tivat & Luštica'),
    ('cetinje', 'Cetinje & the Old Royal Capital'),
    ('other', 'Elsewhere in Montenegro'),
]

PLACE_TYPES = [
    ('coastal', 'Coastal'),
    ('mountains', 'Mountains'),
    ('national_parks', 'National Parks'),
    ('cultural', 'Cultural Sites'),
    ('lakes', 'Lakes & Rivers'),
    ('cities', 'Cities & Towns'),
]


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
        max_length=120, blank=True, default='', help_text='Town / specific place, e.g. Kotor.'
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
    # Per-departure seat capacity: each configured departure time can take this
    # many guests (or the whole day, when a service runs with no fixed departure
    # times). max_guests_per_booking caps a single party.
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
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['service', 'customer'], name='one_review_per_customer_service'
            )
        ]

    def __str__(self) -> str:
        return f'{self.rating}★ {self.service_id} by {self.author_name or self.customer_id}'


class Place(models.Model):
    """A Montenegro destination (town / area) with editorial content.

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
    # Enrichment (SEO/AEO): richer editorial body + structured answer-first data.
    overview = models.TextField(
        blank=True,
        default='',
        help_text='Extended editorial body, shown below the lead description.',
    )
    faqs = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"q": "...", "a": "..."}] — on-page FAQ + FAQPage JSON-LD.',
    )
    quick_facts = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"label": "...", "value": "..."}] — quick-facts strip.',
    )
    good_for = models.JSONField(
        default=list, blank=True, help_text='["families", "couples", ...] — audience pills.'
    )
    sections = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"heading": "...", "body": "..."}] — extended editorial blocks shown after the map (deep-dive content).',
    )
    external_links = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"label": "...", "url": "..."}] — outbound authoritative resources (UNESCO, tourism boards, national parks).',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    image = models.ImageField(upload_to='places/', blank=True, null=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
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
        app_label = 'booking_marketplace'
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        return f'{self.name} (+{self.price})'


# ---------------------------------------------------------------------------
# Accommodation ("stays") engine — dedicated hotel booking primitive.
# A hotel is a Property (owned by a catalog.Vendor); it has RoomTypes bookable
# by date range + occupancy. Availability is derived from overlapping bookings
# (see stays.py). Kept separate from BookableService on purpose — different
# semantics (date ranges, per-room inventory, occupancy).
# ---------------------------------------------------------------------------

PROPERTY_TYPES = [
    ('hotel', 'Hotel'),
    ('resort', 'Resort'),
    ('boutique', 'Boutique hotel'),
    ('apartment', 'Apartment'),
    ('villa', 'Villa'),
    ('guesthouse', 'Guesthouse'),
    ('hostel', 'Hostel'),
    ('mountain_lodge', 'Mountain lodge'),
]

# amenity slug -> (label, lucide-icon-name) — drives the amenities grid.
AMENITY_LABELS = {
    'pool': ('Swimming pool', 'waves'),
    'spa': ('Spa & wellness', 'sparkles'),
    'wifi': ('Free WiFi', 'wifi'),
    'parking': ('Parking', 'square-parking'),
    'restaurant': ('Restaurant', 'utensils'),
    'bar': ('Bar', 'wine'),
    'gym': ('Fitness centre', 'dumbbell'),
    'airport_shuttle': ('Airport shuttle', 'plane'),
    'beachfront': ('Beachfront', 'umbrella'),
    'pet_friendly': ('Pet friendly', 'paw-print'),
    'family_rooms': ('Family rooms', 'users'),
    'room_service': ('Room service', 'concierge-bell'),
    'concierge': ('Concierge', 'bell'),
    'ev_charging': ('EV charging', 'plug-zap'),
    'air_conditioning': ('Air conditioning', 'wind'),
    'sea_view': ('Sea view', 'eye'),
    'balcony': ('Balcony', 'door-open'),
    'minibar': ('Minibar', 'refrigerator'),
    'kitchenette': ('Kitchenette', 'cooking-pot'),
    'bathtub': ('Bathtub', 'bath'),
}


# Stay-policy keys -> display label, in the order a guest reads them. Owned
# here, never in a theme: adding or renaming a policy is a data change, and the
# template just loops what the view resolves (mirrors AMENITY_LABELS). An
# unknown key still renders — the view humanises it — so a new policy needs no
# theme edit.
POLICY_LABELS = {
    'cancellation': 'Cancellation',
    'children': 'Children',
    'pets': 'Pets',
    'payment': 'Payment',
}


class Property(models.Model):
    """A hotel / accommodation, owned by a catalog.Vendor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'catalog.Vendor', on_delete=models.CASCADE, related_name='properties'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    property_type = models.CharField(
        max_length=20, choices=PROPERTY_TYPES, default='hotel', db_index=True
    )
    star_rating = models.PositiveSmallIntegerField(default=0)  # 0–5
    short_description = models.CharField(max_length=300, blank=True, default='')
    description = models.TextField(blank=True, default='')
    region = models.CharField(max_length=20, choices=REGIONS, blank=True, default='', db_index=True)
    location = models.CharField(max_length=120, blank=True, default='')
    address = models.CharField(max_length=255, blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    policies = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to='properties/', blank=True, null=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    price_from = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking_marketplace'
        verbose_name_plural = 'Properties'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def recalc_price_from(self, save=True):
        """Set price_from to the cheapest active room's base_rate."""
        cheapest = self.room_types.filter(is_active=True).order_by('base_rate').first()
        if cheapest:
            self.price_from = cheapest.base_rate
            if save:
                self.save(update_fields=['price_from'])
        return self.price_from


class RoomType(models.Model):
    """A bookable room category within a Property."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='room_types')
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    description = models.TextField(blank=True, default='')
    max_occupancy = models.PositiveSmallIntegerField(default=2)
    max_adults = models.PositiveSmallIntegerField(default=2)
    max_children = models.PositiveSmallIntegerField(default=0)
    bed_configuration = models.CharField(max_length=120, blank=True, default='')
    size_sqm = models.PositiveIntegerField(null=True, blank=True)
    base_rate = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    room_count = models.PositiveSmallIntegerField(default=1)
    amenities = models.JSONField(default=list, blank=True)
    image = models.ImageField(upload_to='rooms/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'booking_marketplace'
        ordering = ['sort_order', 'base_rate']
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'slug'], name='uniq_roomtype_slug_per_property'
            )
        ]

    def __str__(self) -> str:
        return f'{self.name} @ {self.property_id}'


class StayBooking(models.Model):
    """A reservation of a RoomType for a check-in→check-out date range."""

    STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name='bookings')
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name='bookings')
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stay_bookings',
    )
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40, blank=True, default='')
    check_in = models.DateField(db_index=True)
    check_out = models.DateField()
    nights = models.PositiveSmallIntegerField(default=1)
    rooms = models.PositiveSmallIntegerField(default=1)
    adults = models.PositiveSmallIntegerField(default=2)
    children = models.PositiveSmallIntegerField(default=0)
    nightly_breakdown = models.JSONField(default=list, blank=True)
    subtotal = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    service_fee = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    tourist_tax = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    total = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', default=0)
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking_marketplace'
        ordering = ['-check_in', '-created_at']
        indexes = [models.Index(fields=['room_type', 'check_in', 'check_out'])]

    def __str__(self) -> str:
        return f'{self.property_id} {self.check_in}→{self.check_out} ×{self.rooms} ({self.status})'


class StayEnquiry(models.Model):
    """A 'Contact for price' accommodation lead (listing mode; anon-allowed)."""

    STATUS = [('new', 'New'), ('contacted', 'Contacted'), ('closed', 'Closed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property, on_delete=models.SET_NULL, null=True, blank=True, related_name='enquiries'
    )
    room_type = models.ForeignKey(
        RoomType, on_delete=models.SET_NULL, null=True, blank=True, related_name='enquiries'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stay_enquiries',
    )
    name = models.CharField(max_length=200, blank=True, default='')
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True, default='')
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    rooms = models.PositiveSmallIntegerField(null=True, blank=True)
    adults = models.PositiveSmallIntegerField(null=True, blank=True)
    children = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS, default='new', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking_marketplace'
        ordering = ['-created_at']
        verbose_name_plural = 'Stay enquiries'

    def __str__(self) -> str:
        return f'Stay enquiry from {self.email} ({self.status})'


class PropertyImage(models.Model):
    """Gallery image for a Property."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='properties/gallery/')
    alt = models.CharField(max_length=160, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'booking_marketplace'
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        return f'{self.property.name} image #{self.pk}'


EVENT_CATEGORIES = [
    ('music', 'Music & festivals'),
    ('culture', 'Culture & arts'),
    ('food', 'Food & wine'),
    ('tradition', 'Tradition & carnival'),
    ('sport', 'Sport & outdoors'),
]


class Event(models.Model):
    """A Montenegro event — festival, carnival, regatta, concert season.

    Deliberately a CALENDAR entry, not a bookable product. Almost every event
    worth listing here (Kotor Carnival, Boka Night, Grad teatar) is run by a
    municipality or a festival body, sells through its own channel, and recurs
    annually on dates that move. Modelling it as a `BookableService` would mean
    inventing seats, prices and a checkout none of these have.

    So the dates are editorial strings (`when_label`, e.g. "Early February"),
    plus an optional concrete `start_date`/`end_date` for the current edition.
    `month` is the sort/filter key that survives when exact dates are unknown —
    which is the normal state for an event nine months out.

    Linked to a `Place` where one exists, so a destination page can list what is
    on there and an event page can point back at the town.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    category = models.CharField(
        max_length=20, choices=EVENT_CATEGORIES, blank=True, default='', db_index=True
    )
    region = models.CharField(max_length=20, choices=REGIONS, blank=True, default='', db_index=True)
    place = models.ForeignKey(
        'booking_marketplace.Place',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        help_text='Destination this event belongs to, when there is one.',
    )
    venue = models.CharField(max_length=160, blank=True, default='')

    # Editorial timing. `month` (1–12) is the reliable sort key; the dates are
    # optional because most editions are announced only weeks ahead.
    when_label = models.CharField(
        max_length=80, blank=True, default='', help_text='e.g. "Early February", "Mid-July"'
    )
    month = models.PositiveSmallIntegerField(default=0, db_index=True, help_text='1–12, 0 = unset')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_annual = models.BooleanField(default=True, help_text='Recurs every year.')

    summary = models.CharField(max_length=300, blank=True, default='')
    description = models.TextField(blank=True, default='')
    highlights = models.JSONField(default=list, blank=True)
    faqs = models.JSONField(default=list, blank=True, help_text="[{'q':…, 'a':…}]")
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    official_url = models.URLField(blank=True, default='')

    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking_marketplace'
        ordering = ['month', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'month']),
            models.Index(fields=['region', 'is_active']),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def when_display(self) -> str:
        """Human timing: the editorial label, else the month name, else ''."""
        if self.when_label:
            return self.when_label
        if self.month:
            import calendar

            return calendar.month_name[self.month]
        return ''
