"""AI-traffic attribution (Wave 1 of docs/plans/cutting-edge-open-core-2026-07.md).

Humans arriving FROM an AI assistant are classified into utm_source as
'ai:<name>' (so every existing source rollup segments them); AI crawlers are
counted as catalog reads and excluded from visitor sessions/pageviews.
"""

from __future__ import annotations

from django.test import Client, TestCase
from django.utils import timezone

from plugins.installed.analytics.models import AnalyticsSession, DailyMetric
from plugins.installed.analytics.services import (
    ai_crawler_from_ua,
    ai_source_from_referrer,
    ai_traffic_summary,
    record_ai_crawler_hit,
)

GPTBOT_UA = 'Mozilla/5.0 AppleWebKit/537.36 (compatible; GPTBot/1.2; +https://openai.com/gptbot)'


class ClassifierTests(TestCase):
    def test_assistant_referrers(self):
        self.assertEqual(ai_source_from_referrer('https://chatgpt.com/c/abc123'), 'chatgpt')
        self.assertEqual(
            ai_source_from_referrer('https://www.perplexity.ai/search?q=x'), 'perplexity'
        )
        self.assertEqual(ai_source_from_referrer('https://claude.ai/chat/1'), 'claude')
        self.assertEqual(ai_source_from_referrer('https://gemini.google.com/app'), 'gemini')
        self.assertEqual(ai_source_from_referrer('https://google.com/search'), '')
        self.assertEqual(ai_source_from_referrer(''), '')
        # 'notchatgpt.com' must not suffix-match chatgpt.com
        self.assertEqual(ai_source_from_referrer('https://notchatgpt.com/x'), '')

    def test_crawler_uas(self):
        self.assertEqual(ai_crawler_from_ua(GPTBOT_UA), 'gptbot')
        self.assertEqual(ai_crawler_from_ua('Mozilla/5.0 (compatible; ClaudeBot/1.0)'), 'claudebot')
        self.assertEqual(ai_crawler_from_ua('Mozilla/5.0 (Macintosh) Safari/605.1'), '')


class SessionStampingTests(TestCase):
    def _visit(self, **extra):
        client = Client()
        client.cookies['morpheus_consent'] = '{"analytics": true, "functional": true, "marketing": true}'  # consented visitor
        return client.get('/', **extra)

    def test_ai_referral_lands_in_utm_source(self):
        self._visit(HTTP_REFERER='https://chatgpt.com/c/recommendation')
        s = AnalyticsSession.objects.latest('first_seen_at')
        self.assertEqual(s.utm_source, 'ai:chatgpt')
        self.assertEqual(s.utm_medium, 'ai-assistant')

    def test_explicit_utm_wins_over_inference(self):
        self._visit(HTTP_REFERER='https://chatgpt.com/c/x')  # arrives via ?utm too
        AnalyticsSession.objects.all().delete()
        consented = Client()
        consented.cookies['morpheus_consent'] = '{"analytics": true, "functional": true, "marketing": true}'
        consented.get('/?utm_source=newsletter', HTTP_REFERER='https://chatgpt.com/c/x')
        s = AnalyticsSession.objects.latest('first_seen_at')
        self.assertEqual(s.utm_source, 'newsletter')

    def test_normal_referrer_untouched(self):
        self._visit(HTTP_REFERER='https://google.com/search')
        s = AnalyticsSession.objects.latest('first_seen_at')
        self.assertEqual(s.utm_source, '')


class CrawlerTests(TestCase):
    def test_crawler_counted_not_sessioned(self):
        before = AnalyticsSession.objects.count()
        Client().get('/', HTTP_USER_AGENT=GPTBOT_UA)
        Client().get('/products/', HTTP_USER_AGENT=GPTBOT_UA)
        self.assertEqual(AnalyticsSession.objects.count(), before)  # no fake visitor
        row = DailyMetric.objects.get(metric='ai_crawler_hits', dimension='gptbot')
        self.assertEqual(row.value_int, 2)

    def test_counter_increments_across_calls(self):
        record_ai_crawler_hit('claudebot')
        record_ai_crawler_hit('claudebot')
        record_ai_crawler_hit('perplexitybot')
        summary = ai_traffic_summary(days=7)
        self.assertEqual(summary['crawler_hits']['claudebot'], 2)
        self.assertEqual(summary['crawler_hits_total'], 3)


class SummaryTests(TestCase):
    def test_summary_shape_and_session_counts(self):
        AnalyticsSession.objects.create(
            cookie_id='c1', utm_source='ai:chatgpt', first_seen_at=timezone.now()
        )
        AnalyticsSession.objects.create(
            cookie_id='c2', utm_source='ai:perplexity', first_seen_at=timezone.now()
        )
        AnalyticsSession.objects.create(cookie_id='c3', utm_source='newsletter')
        s = ai_traffic_summary(days=7)
        self.assertEqual(s['assistant_sessions'], {'chatgpt': 1, 'perplexity': 1})
        self.assertIn('assistant_revenue_total', s)

    def test_agent_tool_registered(self):
        from plugins.installed.analytics.agent_tools import analytics_ai_traffic_tool

        out = analytics_ai_traffic_tool.invoke({'days': 7})
        self.assertIn('crawler_hits_total', out.output)
