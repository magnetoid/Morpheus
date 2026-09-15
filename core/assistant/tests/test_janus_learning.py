"""What Janus learns survives without a disk volume (core/assistant/janus_learning.py).

The home directory is a temp dir that every redeploy wipes. These tests write
files the way Janus does, harvest them, then hydrate a brand-new home — which is
exactly what a redeploy or a second container looks like.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

import core.assistant.janus_engine as eng
from core.assistant import janus_learning as jl
from core.assistant.models import JanusLearning
from plugins.models import PluginConfig

D = jl.ENTRY_DELIMITER


def _home():
    tmp = TemporaryDirectory()
    return tmp, Path(tmp.name)


def _put(home: Path, rel: str, text: str) -> None:
    path = home / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


JOURNAL = 'memories/daily/2026-09-15.md'
HEAD = '# Memory journal — 2026-09-15\n\n'


def _entry(note: str, *, scope: str = 'MEMORY', event: str = 'added') -> str:
    """One journal line as tools/memory_tool.py:append_daily_snapshot writes it."""
    body = note.strip().replace('\n', '\n  ')
    return f'- `09:30` **{scope}** {event}: {body}\n'


def _skill(name: str, description: str = 'Does a thing') -> str:
    return f'---\nname: {name}\ndescription: {description}\n---\n\nSteps for {name}.\n'


class MergeTests(SimpleTestCase):
    """Two conversations can learn at once; neither may erase the other."""

    def test_memory_notes_added_concurrently_are_both_kept(self):
        base = 'Ships from Belgrade'
        mine = f'{base}{D}Prices include VAT'
        theirs = f'{base}{D}Closed on Sundays'
        merged = jl.merge(jl.MEMORY_FILE, base, mine, theirs)
        self.assertEqual(merged, f'{base}{D}Closed on Sundays{D}Prices include VAT')

    def test_memory_note_removed_in_the_turn_is_removed(self):
        merged = jl.merge(jl.MEMORY_FILE, f'a{D}b', 'a', f'a{D}b{D}c')
        self.assertEqual(merged, f'a{D}c')

    def test_memory_note_replaced_in_the_turn(self):
        self.assertEqual(jl.merge(jl.MEMORY_FILE, f'a{D}old', f'a{D}new', f'a{D}old'), f'a{D}new')

    def test_last_note_removed_deletes_the_file(self):
        self.assertIsNone(jl.merge(jl.MEMORY_FILE, 'a', None, 'a'))

    def test_lessons_merge_by_id(self):
        def dump(*ids):
            return json.dumps([{'id': i, 'lesson': i} for i in ids])

        merged = json.loads(
            jl.merge(jl.LESSONS_FILE, dump('x'), dump('x', 'mine'), dump('x', 'theirs'))
        )
        self.assertEqual([r['id'] for r in merged], ['x', 'theirs', 'mine'])
        merged = json.loads(
            jl.merge(jl.LESSONS_FILE, dump('x', 'y'), dump('y'), dump('x', 'y', 'z'))
        )
        self.assertEqual([r['id'] for r in merged], ['y', 'z'])

    def test_unreadable_lessons_keep_what_is_stored(self):
        self.assertEqual(
            jl.merge(jl.LESSONS_FILE, '[]', '{broken', '[{"id": "a"}]'), '[{"id": "a"}]'
        )

    def test_journal_merges_by_appended_entries(self):
        base = f'{HEAD}{_entry("one")}'
        merged = jl.merge(JOURNAL, base, base + _entry('mine'), base + _entry('theirs'))
        self.assertEqual(merged, f'{HEAD}{_entry("one")}{_entry("theirs")}{_entry("mine")}')

    def test_journal_never_keeps_entries_about_a_person(self):
        # The journal is shared by the store; notes about one staff member are not.
        turn = f'{HEAD}{_entry("Ana prefers short answers", scope="USER")}{_entry("Ships from Belgrade")}'
        self.assertEqual(
            jl.merge(JOURNAL, None, turn, None), f'{HEAD}{_entry("Ships from Belgrade")}'
        )
        only_user = f'{HEAD}{_entry("Ana prefers short answers", scope="USER")}'
        self.assertIsNone(jl.merge(JOURNAL, None, only_user, None))

    def test_skill_file_changed_in_the_turn_wins(self):
        self.assertEqual(jl.merge('skills/a/SKILL.md', 'v1', 'v2', 'v1'), 'v2')

    def test_skill_file_deleted_in_the_turn_is_deleted(self):
        self.assertIsNone(jl.merge('skills/a/SKILL.md', 'v1', None, 'v1'))

    def test_deletion_does_not_erase_someone_elses_newer_edit(self):
        self.assertEqual(jl.merge('skills/a/SKILL.md', 'v1', None, 'v2'), 'v2')


class ScanTests(SimpleTestCase):
    """Only what Janus learned is kept — never its bundled skills or anything executable."""

    def setUp(self):
        tmp, self.home = _home()
        self.addCleanup(tmp.cleanup)

    def test_learned_files_are_found(self):
        _put(self.home, jl.MEMORY_FILE, 'note')
        _put(self.home, jl.LESSONS_FILE, '[]')
        _put(self.home, 'memories/daily/2026-09-15.md', 'journal')
        _put(self.home, 'skills/ops/restock/SKILL.md', _skill('restock'))
        _put(self.home, 'skills/ops/restock/references/suppliers.md', 'list')
        self.assertEqual(
            set(jl.scan(self.home)),
            {
                jl.MEMORY_FILE,
                jl.LESSONS_FILE,
                'memories/daily/2026-09-15.md',
                'skills/ops/restock/SKILL.md',
                'skills/ops/restock/references/suppliers.md',
            },
        )

    def test_bundled_skills_are_not_learned(self):
        _put(self.home, 'skills/.bundled_manifest', 'github-pr:abc123\nrenamed:def\n')
        _put(self.home, 'skills/dev/github-pr/SKILL.md', _skill('github-pr'))
        _put(self.home, 'skills/dev/other-dir/SKILL.md', _skill('renamed'))
        self.assertEqual(jl.scan(self.home), {})

    def test_scripts_hidden_files_and_locks_are_not_kept(self):
        _put(self.home, 'skills/ops/restock/SKILL.md', _skill('restock'))
        _put(self.home, 'skills/ops/restock/scripts/run.sh', 'rm -rf /')
        _put(self.home, 'skills/.archive/old/SKILL.md', _skill('old'))
        _put(self.home, 'memories/MEMORY.md.lock', '')
        _put(self.home, 'memories/MEMORY.md.bak.1700000000', 'x')
        self.assertEqual(set(jl.scan(self.home)), {'skills/ops/restock/SKILL.md'})

    def test_symlinks_are_not_followed(self):
        with TemporaryDirectory() as outside:
            _put(Path(outside), 'secret.md', 'DATABASE_URL=postgres://')
            _put(self.home, 'skills/ops/restock/SKILL.md', _skill('restock'))
            os.symlink(Path(outside) / 'secret.md', self.home / 'skills/ops/restock/leak.md')
            os.symlink(outside, self.home / 'skills/ops/restock/refs')
            self.assertEqual(set(jl.scan(self.home)), {'skills/ops/restock/SKILL.md'})

    def test_oversized_file_is_not_kept(self):
        _put(self.home, jl.MEMORY_FILE, 'x' * (jl.MAX_FILE_CHARS + 1))
        self.assertEqual(jl.scan(self.home), {})


class SyncTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.ana = users.objects.create_user(
            username='ana', email='a@x.com', password='x', is_staff=True
        )
        self.bo = users.objects.create_user(
            username='bo', email='b@x.com', password='x', is_staff=True
        )

    def _fresh_home(self) -> Path:
        tmp, home = _home()
        self.addCleanup(tmp.cleanup)
        return home

    def _learn(self, files: dict[str, str | None], *, user=None, home=None, key='conv-1'):
        """One turn: hydrate, let 'Janus' change files, harvest."""
        home = home or self._fresh_home()
        snapshot = jl.hydrate(home, user=user)
        for rel, text in files.items():
            if text is None:
                (home / rel).unlink()
            else:
                _put(home, rel, text)
        return jl.harvest(home, snapshot, conversation_key=key, user=user), home

    def test_learning_survives_a_wiped_home(self):
        notes = f'Ships from Belgrade{D}Prices include VAT'
        self._learn(
            {
                jl.MEMORY_FILE: notes,
                'skills/ops/restock/SKILL.md': _skill('restock'),
                jl.LESSONS_FILE: json.dumps([{'id': 'a', 'lesson': 'check stock first'}]),
            },
            user=self.ana,
        )
        redeployed = self._fresh_home()
        jl.hydrate(redeployed, user=self.ana)
        self.assertEqual((redeployed / jl.MEMORY_FILE).read_text(encoding='utf-8'), notes)
        self.assertEqual(
            (redeployed / 'skills/ops/restock/SKILL.md').read_text(encoding='utf-8'),
            _skill('restock'),
        )
        self.assertIn(
            'check stock first', (redeployed / jl.LESSONS_FILE).read_text(encoding='utf-8')
        )

    def test_hydrated_memory_round_trips_the_way_janus_checks_it(self):
        # tools/memory_tool.py locks a memory file against writes when parsing and
        # re-joining its entries does not reproduce the file.
        self._learn({jl.MEMORY_FILE: f'one{D}two\nlines{D}three'})
        home = self._fresh_home()
        jl.hydrate(home)
        raw = (home / jl.MEMORY_FILE).read_text(encoding='utf-8')
        parsed = [e.strip() for e in raw.split(D) if e.strip()]
        self.assertEqual(raw.strip(), D.join(parsed))

    def test_two_conversations_learning_at_once_keep_both(self):
        _, home = self._learn({jl.MEMORY_FILE: 'base'})
        other = self._fresh_home()
        snap_a = jl.hydrate(home)
        snap_b = jl.hydrate(other)
        _put(home, jl.MEMORY_FILE, f'base{D}from a')
        _put(other, jl.MEMORY_FILE, f'base{D}from b')
        jl.harvest(home, snap_a, conversation_key='a')
        jl.harvest(other, snap_b, conversation_key='b')
        stored = JanusLearning.objects.get(path=jl.MEMORY_FILE).content
        self.assertEqual(stored, f'base{D}from a{D}from b')

    def test_notes_about_a_person_stay_with_that_person(self):
        self._learn({jl.USER_FILE: 'Ana prefers short answers'}, user=self.ana)
        bo_home = self._fresh_home()
        jl.hydrate(bo_home, user=self.bo)
        self.assertFalse((bo_home / jl.USER_FILE).exists())
        ana_home = self._fresh_home()
        jl.hydrate(ana_home, user=self.ana)
        self.assertEqual(
            (ana_home / jl.USER_FILE).read_text(encoding='utf-8'), 'Ana prefers short answers'
        )
        self.assertEqual(JanusLearning.objects.get(path=jl.USER_FILE).scope, f'user:{self.ana.pk}')

    def test_without_a_staff_member_no_personal_notes_are_kept(self):
        changed, _ = self._learn({jl.USER_FILE: 'nobody'})
        self.assertEqual(changed, [])
        self.assertFalse(JanusLearning.objects.filter(path=jl.USER_FILE).exists())

    def test_hydrate_removes_what_the_merchant_deleted(self):
        _, home = self._learn({'skills/ops/restock/SKILL.md': _skill('restock')})
        jl.delete_skill('skills/ops/restock')
        jl.hydrate(home)
        self.assertFalse((home / 'skills/ops/restock/SKILL.md').exists())
        self.assertFalse((home / 'skills/ops').exists())

    def test_a_turn_cannot_author_a_flood_of_skill_files(self):
        files = {
            f'skills/bulk/s{i}/SKILL.md': _skill(f's{i}')
            for i in range(jl.MAX_NEW_FILES_PER_TURN + 1)
        }
        files[jl.MEMORY_FILE] = 'still kept'
        changed, _ = self._learn(files)
        self.assertEqual(changed, [jl.MEMORY_FILE])
        self.assertFalse(JanusLearning.objects.filter(kind='skill').exists())

    def test_a_stored_path_cannot_escape_the_home(self):
        JanusLearning.objects.create(path='skills/../../escape.md', kind='skill', content='x')
        JanusLearning.objects.create(path='/etc/cron.d/x', kind='skill', content='x')
        home = self._fresh_home()
        self.assertIsNotNone(jl.hydrate(home))
        self.assertEqual(list(home.parent.glob('escape.md')), [])
        self.assertEqual(jl.scan(home), {})

    def test_what_a_turn_learned_is_audited_with_the_human(self):
        from core.audit.models import AuditEvent

        self._learn({jl.MEMORY_FILE: 'note'}, user=self.ana, key='conv-9')
        event = AuditEvent.objects.get(event_type='janus.learned')
        self.assertEqual(event.actor, self.ana)
        self.assertEqual(event.metadata['paths'], [jl.MEMORY_FILE])
        self.assertEqual(event.metadata['conversation'], 'conv-9')

    def test_review_deletes_one_note(self):
        self._learn({jl.MEMORY_FILE: f'keep{D}drop'})
        drop = next(n for n in jl.notes()['store'] if n['text'] == 'drop')
        self.assertTrue(jl.forget_note(which='store', entry_id=drop['id']))
        self.assertEqual(JanusLearning.objects.get(path=jl.MEMORY_FILE).content, 'keep')

    def test_a_deleted_note_is_also_gone_from_the_journal(self):
        # recall_memory searches the journal, so a note left there is not forgotten.
        drop = 'Supplier code is\nKX-44'
        self._learn(
            {
                jl.MEMORY_FILE: f'keep{D}{drop}',
                JOURNAL: f'{HEAD}{_entry("keep")}{_entry(drop)}{_entry(drop, event="revised")}',
            }
        )
        note = next(n for n in jl.notes()['store'] if n['text'] == drop)
        jl.forget_note(which='store', entry_id=note['id'])
        self.assertEqual(JanusLearning.objects.get(path=JOURNAL).content, f'{HEAD}{_entry("keep")}')
        keep = jl.notes()['store'][0]
        jl.forget_note(which='store', entry_id=keep['id'])
        self.assertFalse(JanusLearning.objects.filter(kind='journal').exists())

    def test_a_persons_journal_entry_never_reaches_a_colleague(self):
        self._learn(
            {
                jl.USER_FILE: 'Ana is on leave in October',
                JOURNAL: f'{HEAD}{_entry("Ana is on leave in October", scope="USER")}',
            },
            user=self.ana,
        )
        bo_home = self._fresh_home()
        jl.hydrate(bo_home, user=self.bo)
        self.assertEqual(jl.scan(bo_home), {})

    def test_review_lists_skills_with_their_description(self):
        self._learn(
            {
                'skills/ops/restock/SKILL.md': _skill('restock', 'Reorder low stock'),
                'skills/ops/restock/references/suppliers.md': 'list',
            }
        )
        [skill] = jl.skills()
        self.assertEqual(
            (skill['name'], skill['description'], skill['files']),
            ('restock', 'Reorder low stock', 2),
        )


class _FakeJanus:
    """Stands in for the `janus chat` process: sees the home, writes what it learned."""

    def __init__(self, writes=None, raise_timeout=False):
        self.writes = writes or {}
        self.raise_timeout = raise_timeout
        self.seen: dict[str, str] = {}
        self.argv: list[str] = []

    def __call__(self, argv, **kwargs):
        home = Path(kwargs['env']['JANUS_HOME'])
        self.argv = argv
        self.seen = jl.scan(home)
        for rel, text in self.writes.items():
            _put(home, rel, text)
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(argv, 1)
        return mock.Mock(stdout='ok', stderr='', returncode=0)


class EngineLearningTests(TestCase):
    """The real turn path with an unpatched home directory — only the process is fake."""

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.user = get_user_model().objects.create_user(
            username='ana', email='a@x.com', password='x', is_staff=True
        )

    def _turn(self, fake, *, key, home):
        with (
            override_settings(LINDA_JANUS_HOME=str(home)),
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng.subprocess, 'run', side_effect=fake),
        ):
            return eng.run_janus_turn(
                message='hi', conversation_key=key, system_prompt='p', context={'user': self.user}
            )

    def test_a_note_from_one_conversation_reaches_the_next_after_a_redeploy(self):
        self._turn(
            _FakeJanus({jl.MEMORY_FILE: 'Ships from Belgrade'}), key='c1', home=self.tmp / 'a'
        )
        later = _FakeJanus()
        self._turn(later, key='c2', home=self.tmp / 'redeployed')
        self.assertEqual(later.seen.get(jl.MEMORY_FILE), 'Ships from Belgrade')
        argv_toolsets = later.argv[later.argv.index('-t') + 1].split(',')
        self.assertIn('memory', argv_toolsets)

    def test_what_was_saved_before_a_timeout_is_kept(self):
        out = self._turn(
            _FakeJanus({jl.MEMORY_FILE: 'saved in time'}, raise_timeout=True),
            key='c1',
            home=self.tmp,
        )
        self.assertIn('timed out', out['error'])
        self.assertEqual(JanusLearning.objects.get(path=jl.MEMORY_FILE).content, 'saved in time')

    def test_learning_switched_off_keeps_nothing_and_loads_nothing(self):
        self._turn(_FakeJanus({jl.MEMORY_FILE: 'old note'}), key='c1', home=self.tmp)
        PluginConfig.objects.update_or_create(
            plugin_name='janus', defaults={'config': {'learning': False}}
        )
        off = _FakeJanus({jl.MEMORY_FILE: f'old note{D}new note'})
        self._turn(off, key='c1', home=self.tmp)
        self.assertEqual(off.seen, {})  # the old note was cleared from the home first
        self.assertNotIn('memory', off.argv[off.argv.index('-t') + 1].split(','))
        self.assertEqual(JanusLearning.objects.get(path=jl.MEMORY_FILE).content, 'old note')
        self.assertIn('memory_enabled: false', eng._config_text('https://s/mcp/'))
