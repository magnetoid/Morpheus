"""Fix 15 — fs.search_files no longer leaks protected paths (secret oracle).

`grep -rln` reads .env / secrets / auth source to test the query, and returning
the matching FILENAME turned search into a boolean oracle over exactly the
content `fs.read_file` refuses (`SECRET_KEY=sk-ab` hits iff present → byte-by-byte
extraction, hunt #15). Results now pass through `core.safety.is_path_protected`.

Deterministic approach: patch the module's `subprocess.run` to return a fake
grep result listing both a protected path and a normal one, then assert the
protected path is filtered out and the normal one survives. The real .env is
never created or read.
"""

from __future__ import annotations

import subprocess
from unittest import mock

from django.test import SimpleTestCase

from core.agents import ToolError
from core.assistant.tools.filesystem import _PROJECT_ROOT, read_file_tool, search_files_tool
from core.safety import is_path_protected


class SearchFilesOracleTests(SimpleTestCase):
    def test_protected_match_dropped_normal_kept(self):
        protected = str(_PROJECT_ROOT / '.env')  # matches PROTECTED_PATHS
        normal = str(_PROJECT_ROOT / 'README.md')  # ordinary file
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f'{protected}\n{normal}\n', stderr=''
        )
        with mock.patch('core.assistant.tools.filesystem.subprocess.run', return_value=fake):
            output = search_files_tool.invoke({'query': 'x'}).output

        matches = output['matches']
        self.assertNotIn('.env', matches)  # oracle plugged — secret path dropped
        self.assertIn('README.md', matches)  # ordinary match still returned
        self.assertEqual(output['count'], len(matches))

    def test_the_boundary_is_what_filters(self):
        # It's `is_path_protected` doing the filtering: the protected path matches
        # the boundary, the ordinary one does not.
        self.assertTrue(is_path_protected('.env'))
        self.assertFalse(is_path_protected('README.md'))

    def test_read_file_still_refuses_protected_path(self):
        # Companion: the same single-source boundary refuses to READ .env, so the
        # search filter and the read guard agree on what's protected.
        with self.assertRaises(ToolError) as cm:
            read_file_tool.invoke({'path': '.env'})
        self.assertIn('protected', str(cm.exception).lower())
