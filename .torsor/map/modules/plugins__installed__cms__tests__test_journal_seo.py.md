---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/cms/tests/test_journal_seo.py

Symbols in `plugins/installed/cms/tests/test_journal_seo.py`.

- L12 `JournalDictSeoTests` (class)
- L13 `test_extracts_first_body_image_and_author(self)` (method)
- L28 `test_explicit_cover_metadata_wins_over_body_image(self)` (method)
- L40 `test_author_falls_back_to_store_name(self)` (method)
- L49 `test_date_label_shows_real_publish_date_and_read_time(self)` (method)
- L66 `JournalDuplicateHeadingTests` (class) — A body authored as a full document repeats the title the template renders.
- L75 `_page(self, body: str, slug: str='dup')` (method)
- L84 `test_strips_leading_h1_and_the_byline_under_it(self)` (method)
- L95 `test_leaves_a_body_that_does_not_open_with_a_heading_alone(self)` (method)
- L101 `test_a_first_paragraph_survives_when_no_heading_preceded_it(self)` (method)
- L107 `test_word_count_measures_what_the_page_renders(self)` (method)
- L112 `JournalFaqPairsTests` (class) — FAQPage is built only from H2s that are genuinely questions.
- L115 `_pairs(self, body: str)` (method)
- L120 `test_a_labelled_faq_section_wins(self)` (method) — The article says "Frequently Asked Questions" — believe it.
- L142 `test_serbian_faq_heading_is_recognised(self)` (method)
- L151 `test_a_labelled_section_with_one_question_falls_through(self)` (method)
- L155 `test_question_headings_become_pairs(self)` (method)
- L172 `test_a_single_question_is_not_an_faq(self)` (method)
- L175 `test_headings_with_no_real_answer_are_dropped(self)` (method)
- L178 `test_long_answers_are_cut_on_a_sentence_boundary(self)` (method)
- L184 `test_an_article_with_no_questions_emits_nothing(self)` (method)
