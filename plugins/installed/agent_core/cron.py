"""Five-field cron schedules for automations, read on the store's clock.

``minute hour day-of-month month day-of-week``, as in cron: ``*``, numbers,
ranges ``a-b``, steps ``*/n`` / ``a-b/n`` / ``a/n``, lists ``a,b`` and English
three-letter names for months and days (``0`` and ``7`` are both Sunday). When
both day fields are restricted a day matches either one; when either starts
with ``*`` it must match both — the rule cron itself uses. No seconds field and
no ``@daily`` macros. croniter is not a dependency, and this is all
Automations needs (docs/plans/morpheus-improvement-plan-2026-10.md, W3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

_MONTHS = {
    name: i + 1
    for i, name in enumerate(
        ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
    )
}
_DAYS = {name: i for i, name in enumerate(('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'))}

# (name, lowest, highest, names)
_FIELDS = (
    ('minute', 0, 59, {}),
    ('hour', 0, 23, {}),
    ('day of month', 1, 31, {}),
    ('month', 1, 12, _MONTHS),
    ('day of week', 0, 7, _DAYS),
)

#: How far ahead a schedule may first fire: five years covers 29 February.
_HORIZON_DAYS = 366 * 5

HELP = 'five fields: minute hour day-of-month month day-of-week, e.g. "0 9 * * 1-5"'


@dataclass(frozen=True)
class Cron:
    minutes: tuple[int, ...]
    hours: tuple[int, ...]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]  # 0 = Sunday
    any_day: bool
    any_weekday: bool

    def _runs_on(self, day: date) -> bool:
        if day.month not in self.months:
            return False
        dom = day.day in self.days
        dow = day.isoweekday() % 7 in self.weekdays
        return (dom and dow) if (self.any_day or self.any_weekday) else (dom or dow)

    def next_after(self, moment: datetime) -> datetime:
        """The first time after ``moment`` the schedule fires, on ``moment``'s clock."""
        start = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
        day = start.date()
        for _ in range(_HORIZON_DAYS):
            if self._runs_on(day):
                first = day == start.date()
                for hour in self.hours:
                    if first and hour < start.hour:
                        continue
                    for minute in self.minutes:
                        if first and hour == start.hour and minute < start.minute:
                            continue
                        return start.replace(
                            year=day.year, month=day.month, day=day.day, hour=hour, minute=minute
                        )
            day += timedelta(days=1)
        raise ValueError('This schedule never fires.')


def _value(token: str, name: str, names: dict) -> int:
    if token.isdigit():
        return int(token)
    if token in names:
        return names[token]
    raise ValueError(f'"{token}" is not a valid {name}.')


def _field(text: str, name: str, low: int, high: int, names: dict) -> frozenset[int]:
    values: set[int] = set()
    for item in text.lower().split(','):
        span, slash, step_text = item.partition('/')
        step = 1
        if slash:
            if not step_text.isdigit() or int(step_text) == 0:
                raise ValueError(f'"{item}" has a bad step in the {name} field.')
            step = int(step_text)
        if span == '*':
            start, end = low, high
        else:
            first, dash, last = span.partition('-')
            start = _value(first, name, names)
            end = _value(last, name, names) if dash else (high if slash else start)
        if start > end:
            raise ValueError(f'"{item}" runs backwards in the {name} field.')
        if start < low or end > high:
            raise ValueError(f'"{item}" is outside the {name} field ({low}–{high}).')
        values.update(range(start, end + 1, step))
    return frozenset(values)


def parse(expr: str) -> Cron:
    """A ``Cron`` from five fields; ``ValueError`` with a readable reason otherwise."""
    parts = (expr or '').split()
    if len(parts) != len(_FIELDS):
        raise ValueError(f'A cron schedule has {HELP}.')
    sets = [_field(part, *spec) for part, spec in zip(parts, _FIELDS, strict=True)]
    schedule = Cron(
        minutes=tuple(sorted(sets[0])),
        hours=tuple(sorted(sets[1])),
        days=sets[2],
        months=sets[3],
        weekdays=frozenset(d % 7 for d in sets[4]),
        any_day=parts[2].startswith('*'),
        any_weekday=parts[4].startswith('*'),
    )
    schedule.next_after(datetime(2000, 1, 1))  # noqa: DTZ001 — only checks that it fires at all
    return schedule


def shortest_gap(schedule: Cron, after: datetime, runs: int = 100) -> timedelta:
    """The shortest time between two runs among the next ``runs``."""
    previous = schedule.next_after(after)
    shortest = timedelta(days=_HORIZON_DAYS)
    for _ in range(runs):
        following = schedule.next_after(previous)
        shortest = min(shortest, following - previous)
        if following - after > timedelta(days=400):
            break
        previous = following
    return shortest


def schedule_error(expr: str, *, engine: str) -> str:
    """Why ``expr`` cannot schedule an automation run by ``engine``, or ''."""
    from plugins.installed.agent_core.scheduler import min_interval_s

    try:
        schedule = parse(expr)
    except ValueError as e:
        return str(e)
    floor = min_interval_s(engine)
    if shortest_gap(schedule, datetime(2000, 1, 1)) < timedelta(seconds=floor):  # noqa: DTZ001
        return (
            f'"{expr}" runs too often: Linda automations run at most every {floor // 60} minutes.'
        )
    return ''
