import uuid

from django.db import models


class BrainBriefing(models.Model):
    """A long-form, AI-written advisory about the whole platform.

    Unlike the structured ``analysis`` (a short prioritized JSON list), this is
    a single comprehensive narrative the configured AI generates from the live
    platform signals —
    improvements, patches, changes, risks, and notable observations, in prose.
    The latest row is what the Brain's "Advisory" tab shows. Generated on the
    6-hour beat and on demand, then persisted so a page GET never calls the LLM.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, default='', help_text='Short scannable lead.')
    content = models.TextField(help_text='Long-form Markdown advisory briefing.')
    generated_by = models.CharField(
        max_length=160, blank=True, default='', help_text='Provider · model that wrote it.'
    )
    tokens_used = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f'{self.title} ({self.generated_at:%Y-%m-%d %H:%M})'
