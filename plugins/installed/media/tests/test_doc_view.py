"""Doc sub-tab matching — federated digital files must respect the specific
tab. Regression guard: a .txt digital product must not surface under PDFs.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from plugins.installed.media.views import _doc_view_matches


class DocViewMatchTests(SimpleTestCase):
    def test_txt_not_in_pdf_tab(self):
        self.assertFalse(_doc_view_matches('notes.txt', 'text/plain', 'pdf'))

    def test_pdf_in_pdf_tab(self):
        self.assertTrue(_doc_view_matches('book.pdf', 'application/pdf', 'pdf'))

    def test_everything_in_all(self):
        self.assertTrue(_doc_view_matches('notes.txt', 'text/plain', 'all'))

    def test_txt_in_other_docs(self):
        self.assertTrue(_doc_view_matches('notes.txt', 'text/plain', 'document'))

    def test_pdf_excluded_from_other_docs(self):
        self.assertFalse(_doc_view_matches('book.pdf', 'application/pdf', 'document'))

    def test_csv_in_spreadsheet_tab_not_pdf(self):
        self.assertTrue(_doc_view_matches('data.csv', 'text/csv', 'spreadsheet'))
        self.assertFalse(_doc_view_matches('data.csv', 'text/csv', 'pdf'))
