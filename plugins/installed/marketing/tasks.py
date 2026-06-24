"""Marketing background tasks.

Cart-recovery email used to live here (``trigger_cart_recovery_sequence``)
but has been retired: recovery email is owned solely by the
``cart_abandonment`` plugin's consent-checked drip. This module is kept as
the home for future marketing beat/async tasks.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.marketing')
