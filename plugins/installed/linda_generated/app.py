"""Linda Generated — landing zone for Linda's gated, self-authored tools.

Code arrived here ONLY via the apply pipeline (core/assistant/apply.py, ADR 0014):
owner-approved → statically scanned → written to a selfdev/* branch → reviewed →
merged → deployed. That pipeline was removed in v0.65.0, when Janus replaced
Linda's in-process engine, so nothing adds tools here any more; the app still
loads any already merged. The plugin owns this directory so the disable test
holds: toggle it off and every tool Linda generated disappears.
"""

from __future__ import annotations

from morpheus.app import Plugin


class LindaGeneratedPlugin(Plugin):
    name = 'linda_generated'
    label = 'Linda Generated'
    version = '0.1.0'
    description = (
        "Landing zone for Linda's self-authored tools. Populated only by the "
        'gated apply pipeline (ADR 0014). Empty until the owner enables and '
        'approves self-development. Disable to remove all generated tools.'
    )
    requires = []

    def ready(self) -> None:
        pass
