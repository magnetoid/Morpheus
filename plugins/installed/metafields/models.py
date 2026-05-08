"""Metafield model — `(content_type, object_id, namespace, key) → value`."""
from __future__ import annotations

import json
import uuid
from typing import Any

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class MetafieldManager(models.Manager):
    """Manager API used by templates and plugin code.

    Read::
        from plugins.installed.metafields.models import Metafield
        meta = Metafield.objects.for_obj(product)        # → {'.brand': 'Acme', '.warranty_months': 24}
        meta = Metafield.objects.for_obj(product, ns='catalog')  # only that namespace

    Write::
        Metafield.objects.set(product, namespace='', key='warranty_months',
                              value=24, value_type='integer')
        Metafield.objects.delete_for(product, namespace='', key='warranty_months')
    """

    def for_obj(self, instance, *, ns: str | None = None) -> dict[str, Any]:
        """Return a flat ``{"namespace.key": typed_value}`` dict."""
        ct = ContentType.objects.get_for_model(type(instance))
        qs = self.filter(content_type=ct, object_id=str(instance.pk))
        if ns is not None:
            qs = qs.filter(namespace=ns)
        out: dict[str, Any] = {}
        for m in qs:
            full_key = f'{m.namespace}.{m.key}' if m.namespace else m.key
            out[full_key] = m.typed_value
        return out

    def set(self, instance, *, namespace: str = '', key: str,
            value: Any, value_type: str = '') -> 'Metafield':
        """Idempotent upsert. `value` is JSON-serialised on the way in."""
        ct = ContentType.objects.get_for_model(type(instance))
        if not value_type:
            value_type = self._infer_value_type(value)
        encoded = self._encode(value, value_type)
        obj, _ = self.update_or_create(
            content_type=ct,
            object_id=str(instance.pk),
            namespace=namespace or '',
            key=key,
            defaults={'value': encoded, 'value_type': value_type},
        )
        return obj

    def delete_for(self, instance, *, namespace: str = '', key: str) -> int:
        ct = ContentType.objects.get_for_model(type(instance))
        deleted, _ = self.filter(
            content_type=ct, object_id=str(instance.pk),
            namespace=namespace or '', key=key,
        ).delete()
        return deleted

    @staticmethod
    def _infer_value_type(value: Any) -> str:
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, int):
            return 'integer'
        if isinstance(value, float):
            return 'number'
        if isinstance(value, (dict, list)):
            return 'json'
        return 'string'

    @staticmethod
    def _encode(value: Any, value_type: str) -> str:
        if value is None:
            return ''
        if value_type in ('json', 'list', 'object'):
            return json.dumps(value, default=str)
        if value_type == 'boolean':
            return 'true' if value else 'false'
        return str(value)


class Metafield(models.Model):
    """A single `(content_type, object_id, namespace, key) → value` triple.

    `value_type` is a hint that drives:
      * how `typed_value` decodes the stored string,
      * how the dashboard renders the editor (text / number / date /
        file picker / JSON),
      * how downstream consumers (storefront, GraphQL) expose the value.
    """
    VALUE_TYPES = [
        ('string', 'String'),
        ('text', 'Long text'),
        ('integer', 'Integer'),
        ('number', 'Number'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('date', 'Date'),
        ('datetime', 'Date + time'),
        ('url', 'URL'),
        ('email', 'Email'),
        ('color', 'Colour'),
        ('file_id', 'Media asset id'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64, db_index=True,
                                 help_text='Stringified primary key — works for ints + UUIDs.')
    target = GenericForeignKey('content_type', 'object_id')

    namespace = models.CharField(max_length=80, blank=True, default='',
                                 help_text='Convention: `<plugin>.<feature>` for plugin-owned, blank for merchant-defined.')
    key = models.CharField(max_length=120,
                           help_text='Snake-case identifier within the namespace.')
    value = models.TextField(blank=True, default='')
    value_type = models.CharField(max_length=20, choices=VALUE_TYPES, default='string')
    description = models.CharField(max_length=300, blank=True, default='',
                                   help_text='Optional — shown in the dashboard editor.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MetafieldManager()

    class Meta:
        unique_together = [('content_type', 'object_id', 'namespace', 'key')]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['namespace', 'key']),
        ]
        ordering = ['namespace', 'key']

    def __str__(self) -> str:
        prefix = f'{self.namespace}.' if self.namespace else ''
        return f'{prefix}{self.key} = {self.value[:40]!r}'

    @property
    def full_key(self) -> str:
        return f'{self.namespace}.{self.key}' if self.namespace else self.key

    @property
    def typed_value(self) -> Any:
        """Decode the stored string into the value_type's native form."""
        v = self.value or ''
        t = self.value_type
        try:
            if t == 'integer':
                return int(v) if v else 0
            if t == 'number':
                return float(v) if v else 0.0
            if t == 'boolean':
                return v.lower() in ('1', 'true', 'yes', 'on')
            if t in ('json', 'list', 'object'):
                return json.loads(v) if v else None
        except Exception:  # noqa: BLE001 — fall through to raw string
            pass
        return v
