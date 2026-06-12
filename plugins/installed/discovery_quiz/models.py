"""Discovery quiz: questions, options, and answer logs.

`Quiz` is the merchant's authored quiz. `Question` and `Option`
are its components. `QuizResultTemplate` maps an answer pattern
to a category + intro copy. `QuizSubmission` is a customer's
filled-in answer set.
"""
from __future__ import annotations

from morpheus import models


class Quiz(models.Model):
    slug = models.SlugField(unique=True, max_length=80)
    title = models.CharField(max_length=200)
    intro = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title


class Question(models.Model):
    TYPE_CHOICES = (('single', 'Single choice'), ('multi', 'Multi choice'), ('text', 'Text input'))

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveIntegerField(default=0)
    text = models.CharField(max_length=400)
    qtype = models.CharField(max_length=10, choices=TYPE_CHOICES, default='single')
    # Optional mapping: which option keys lead to which category.
    # JSON: {"opt-key-1": "category-slug", ...}
    mapping_json = models.TextField(default='{}', blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self) -> str:
        return self.text


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    key = models.SlugField(max_length=60)
    label = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('question', 'key')


class QuizResultTemplate(models.Model):
    """Maps a category-slug to a personalised landing page."""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='result_templates')
    category_slug = models.SlugField(max_length=80)
    intro = models.TextField(blank=True)
    cta_label = models.CharField(max_length=80, blank=True)

    class Meta:
        unique_together = ('quiz', 'category_slug')


class QuizSubmission(models.Model):
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='submissions')
    answers_json = models.TextField(default='{}', help_text='{question_id: [option_key, ...] or str}')
    result_category = models.SlugField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['quiz', '-submitted_at'])]
