"""Linda Generated — landing zone for Linda's gated, self-authored tools.

Code arrives here ONLY via the apply pipeline (core/assistant/apply.py, ADR 0014):
owner-approved → statically scanned → written to a selfdev/* branch → reviewed →
merged → deployed. The plugin owns this directory so the disable test holds:
toggle it off and every tool Linda generated disappears.
"""

from __future__ import annotations

from morpheus.plugin import Plugin


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
