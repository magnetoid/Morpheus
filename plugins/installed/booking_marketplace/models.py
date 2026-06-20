"""Booking marketplace — services bookable by time slot, across vendors.

Distinct from the `marketplace` plugin (which sells physical/digital products
with vendor orders + payouts). Here a `catalog.Vendor` offers `BookableService`s
(appointments / sessions / rentals) with weekly `AvailabilityWindow`s, and a
customer creates a `Booking` for a concrete start time. Ships DISABLED by
default — opt in from Dashboard → Apps.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from djmoney.models.fields import MoneyField


class BookableService(models.Model):
    """A time-slot service a vendor offers."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'catalog.Vendor', on_delete=models.CASCADE, related_name='bookable_services'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.vendor_id})'


class AvailabilityWindow(models.Model):
    """A weekly recurring window during which a service can be booked."""

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
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['weekday', 'start_time']

    def __str__(self) -> str:
        return f'{self.get_weekday_display()} {self.start_time}–{self.end_time}'


class Booking(models.Model):
    """A customer's reservation of a service at a concrete time."""

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
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    notes = models.TextField(blank=True)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_at']
        indexes = [models.Index(fields=['service', 'start_at'])]

    def __str__(self) -> str:
        return f'{self.service_id} @ {self.start_at:%Y-%m-%d %H:%M} ({self.status})'
