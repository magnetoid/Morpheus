import uuid

from django.db import models


class DailyReport(models.Model):
    CATEGORY_CHOICES = [
        ('code_opt', 'Code Optimization'),
        ('feat_enh', 'Feature Enhancements'),
        ('ecom_adv', 'E-commerce Advancements'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, db_index=True)
    summary = models.TextField(help_text='A short scannable summary of the report.')
    content = models.TextField(help_text='Markdown-formatted deep dive report.')
    is_published = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return f'{self.get_category_display()}: {self.title}'


class ReportReference(models.Model):
    """Supplementary resources, whitepapers, or case studies linked to a Daily Report."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name='references')
    title = models.CharField(max_length=255)
    url = models.URLField(max_length=500)

    def __str__(self):
        return self.title


class BrainBriefing(models.Model):
    """A long-form, AI-written advisory about the whole platform.

    Unlike the structured ``analysis`` (a short prioritized JSON list) and the
    seeded ``DailyReport`` industry write-ups, this is a single comprehensive
    narrative the configured AI generates from the live platform signals —
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
