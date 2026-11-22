"""When Dawnchild wears its Christmas look (v0.186.0).

Three theme settings decide it. ``christmas_look`` is ``off`` (the default),
``on`` (shown now, to preview it) or ``dates``: shown every year from
``christmas_from`` to ``christmas_until``, both days included, each written
``DD-MM``. A range whose start comes after its end crosses New Year
(01-12 to 06-01 is December and the first week of January). A stored day that
is not a day of the year counts as that bound's default, so a typo never
leaves the look up all year or hides it for good.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

DEFAULT_FROM = '01-12'
DEFAULT_UNTIL = '06-01'
_DAY = re.compile(r'(\d{2})-(\d{2})')


def parse_day(text: str) -> tuple[int, int] | None:
    """(month, day) for ``DD-MM``, or None when it names no day of the year.

    29-02 is a day (in a leap year); a year without one simply never reaches it.
    """
    match = _DAY.fullmatch(text or '')
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    if not 1 <= day <= calendar.monthrange(2024, month)[1]:
        return None
    return month, day


def is_on(config: Mapping[str, Any], today: date) -> bool:
    """Whether the look shows on ``today`` under the theme's stored settings."""
    mode = config.get('christmas_look', 'off')
    if mode == 'on':
        return True
    if mode != 'dates':
        return False
    start = parse_day(str(config.get('christmas_from') or '')) or parse_day(DEFAULT_FROM)
    end = parse_day(str(config.get('christmas_until') or '')) or parse_day(DEFAULT_UNTIL)
    now = (today.month, today.day)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end
