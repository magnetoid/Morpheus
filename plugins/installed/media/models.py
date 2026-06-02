"""MediaAsset — every uploaded file in one table."""
# ruff: noqa: UP037, PLC0415, S110 — quoted self-ref annotation, lazy PIL import, and the
# optional-dep (Pillow) swallow are intentional and pre-date this change.

from __future__ import annotations

import os
import uuid

from django.conf import settings
from django.db import models


def _upload_path(instance, filename: str) -> str:
    """Sharded upload path — keeps any single directory under ~10k files."""
    aid = str(instance.id).replace('-', '')
    return f'media/{aid[:2]}/{aid[2:4]}/{aid}/{filename}'


class MediaAsset(models.Model):
    """A reusable file in the media library.

    `kind` is a coarse bucket: image / document / video / audio / other.
    Detail lives in `mime_type`. `tags` is a flat list (not a separate
    model — Tag is a heavy abstraction we don't need yet) so search
    stays a single ILIKE on the JSON.
    """

    KIND_IMAGE = 'image'
    KIND_VIDEO = 'video'
    KIND_AUDIO = 'audio'
    KIND_DOCUMENT = 'document'
    KIND_OTHER = 'other'
    KIND_CHOICES = [
        (KIND_IMAGE, 'Image'),
        (KIND_VIDEO, 'Video'),
        (KIND_AUDIO, 'Audio'),
        (KIND_DOCUMENT, 'Document'),
        (KIND_OTHER, 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=_upload_path)
    filename = models.CharField(
        max_length=300, blank=True, help_text='Original filename, preserved for display.'
    )
    mime_type = models.CharField(max_length=100, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OTHER, db_index=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text='Display name / SEO title. Falls back to the filename when blank.',
    )
    alt_text = models.CharField(
        max_length=300,
        blank=True,
        help_text='Used for image accessibility; safe to leave blank for non-images.',
    )
    description = models.TextField(
        blank=True, help_text='Caption / long description. Surfaces in galleries and SEO metadata.'
    )
    tags = models.JSONField(
        default=list, blank=True, help_text='Flat list of strings. Used for filtering the library.'
    )

    # Image-specific dimensions; populated on upload when kind=image.
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kind', '-created_at']),
        ]

    def __str__(self) -> str:
        return self.filename or str(self.id)

    @property
    def url(self) -> str:
        try:
            return self.file.url
        except (ValueError, AttributeError):
            return ''

    @property
    def is_image(self) -> bool:
        return self.kind == self.KIND_IMAGE

    @property
    def human_size(self) -> str:
        """Bytes → KB / MB / GB string for display."""
        n = float(self.size_bytes or 0)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if n < 1024 or unit == 'GB':
                return f'{n:,.1f} {unit}' if unit != 'B' else f'{int(n)} B'
            n /= 1024
        return f'{n:,.1f} GB'

    @classmethod
    def from_upload(
        cls, *, uploaded_file, uploaded_by=None, alt_text: str = '', tags: list | None = None
    ) -> 'MediaAsset':
        """Create a MediaAsset from a Django UploadedFile.

        Auto-detects `kind` from the upload's content_type and reads
        image dimensions when possible. Filename is preserved verbatim
        (sharded by id under MEDIA_ROOT so collisions don't matter).
        """
        mime = (getattr(uploaded_file, 'content_type', '') or '').lower()
        if mime.startswith('image/'):
            kind = cls.KIND_IMAGE
        elif mime.startswith('video/'):
            kind = cls.KIND_VIDEO
        elif mime.startswith('audio/'):
            kind = cls.KIND_AUDIO
        elif mime in ('application/pdf', 'text/plain', 'text/csv') or mime.startswith(
            'application/vnd.'
        ):
            kind = cls.KIND_DOCUMENT
        else:
            kind = cls.KIND_OTHER

        asset = cls(
            kind=kind,
            mime_type=mime,
            filename=os.path.basename(getattr(uploaded_file, 'name', '') or ''),
            size_bytes=getattr(uploaded_file, 'size', 0) or 0,
            alt_text=alt_text or '',
            tags=list(tags or []),
            uploaded_by=uploaded_by,
        )
        asset.file.save(uploaded_file.name, uploaded_file, save=False)
        if kind == cls.KIND_IMAGE:
            try:
                from PIL import Image  # noqa: WPS433 — optional dep

                asset.file.seek(0)
                with Image.open(asset.file) as im:
                    asset.width, asset.height = im.size
            except Exception:  # noqa: BLE001 — Pillow optional / format not understood
                pass
        asset.save()
        return asset
