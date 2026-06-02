"""optimize_images_task — runs the warmer + records a dashboard status."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.seo.tasks import last_image_optimize_status, optimize_images_task


class OptimizeImagesTaskTests(TestCase):
    def test_task_runs_and_records_done_status(self):
        # No images in the test DB → the warmer does nothing, but the task must
        # still complete and record a 'done' status the settings page reads.
        optimize_images_task(widths='400')
        st = last_image_optimize_status()
        self.assertIsNotNone(st)
        self.assertEqual(st['state'], 'done')
        self.assertIn('source images', st['summary'])
