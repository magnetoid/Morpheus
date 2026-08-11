"""Plugin SDK — the Django view glue.

Re-export of ``morpheus.views`` (decorators, response classes, shortcuts).
Prefer ``from morpheus.app.views import render, staff_required`` going forward.
"""

from __future__ import annotations

from morpheus.views import *  # noqa: F401,F403
from morpheus.views import __all__  # noqa: F401
