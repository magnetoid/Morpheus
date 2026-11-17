#!/usr/bin/env python3
"""Janus's pin, and what moving it would change.

``ARG JANUS_REF`` in the Dockerfile is the one place Janus is pinned. Everything
that installs Janus reads it through this script: CI's conformance job, the weekly
audit and the janus-bump workflow, which moves it by a draft pull request.

    python3 scripts/bump_janus.py env            # KEY=value lines for $GITHUB_ENV
    python3 scripts/bump_janus.py bump <sha>     # JANUS_KNOWN_GOOD <- JANUS_REF, JANUS_REF <- sha
    python3 scripts/bump_janus.py title --new <sha> --dir <results>
    python3 scripts/bump_janus.py body --new <sha> --dir <results> --run-url <url>

``bump`` changes those two lines and nothing else: the old pin becomes the build's
fallback, so an image whose new Janus breaks the contract installs the commit the
stores ran before. ``body`` reads what the bump workflow left in ``--dir``
(``compare.json``, ``contract-pinned.json``, ``contract-new.json``,
``conformance.txt``, ``conformance.json``, ``audit.txt``); a missing file reads as
a step that did not run.

Standard library only: the workflow runs it before anything is installed.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / 'Dockerfile'
RUNTIME = ROOT / 'core' / 'assistant' / 'janus_runtime.py'
CONTRACT = ROOT / 'core' / 'assistant' / 'janus_contract.py'

# fullmatch only: `$` also matches before a trailing newline.
SHA = re.compile(r'[0-9a-f]{40}')
_REPO = re.compile(r'https://github\.com/([\w.-]+/[\w.-]+?)\.git')
# GitHub refuses a pull request description longer than 65,536 characters.
BODY_LIMIT = 60_000
COMMITS_SHOWN = 100
AUDIT_LINES = 60


class BumpError(Exception):
    """The Dockerfile or the requested commit is not what a bump can work with."""


def _arg(text: str, name: str) -> str:
    found = re.findall(rf'^ARG {name}=(\S*)[ \t]*$', text, re.M)
    if len(found) != 1:
        raise BumpError(f'the Dockerfile has {len(found)} "ARG {name}=" lines, not one')
    return found[0]


def read(text: str) -> dict:
    """The pin as the Dockerfile states it: repository, slug, ref and fallback."""
    pin = {
        'repo': _arg(text, 'JANUS_REPO'),
        'ref': _arg(text, 'JANUS_REF'),
        'known_good': _arg(text, 'JANUS_KNOWN_GOOD'),
    }
    repo = _REPO.fullmatch(pin['repo'])
    if not repo:
        raise BumpError(f'JANUS_REPO is not a GitHub repository URL: {pin["repo"]}')
    for key in ('ref', 'known_good'):
        if not SHA.fullmatch(pin[key]):
            raise BumpError(f'{key} is not a commit (40 lowercase hex): {pin[key]}')
    pin['slug'] = repo.group(1)
    return pin


def _literal(path: Path, name: str):
    """A module-level constant read without importing the module."""
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise BumpError(f'{path.name} defines no {name}')


def pins() -> tuple[str, ...]:
    """What the image installs beside Janus (janus_runtime.PINS)."""
    return tuple(_literal(RUNTIME, 'PINS'))


def env_lines(text: str) -> list[str]:
    pin = read(text)
    return [
        f'JANUS_REPO={pin["repo"]}',
        f'JANUS_SLUG={pin["slug"]}',
        f'JANUS_REF={pin["ref"]}',
        f'JANUS_KNOWN_GOOD={pin["known_good"]}',
        f'JANUS_PINS={" ".join(pins())}',
    ]


def bump(text: str, new: str) -> str:
    """The Dockerfile with ``new`` pinned and the old pin as its fallback."""
    if not SHA.fullmatch(new):
        raise BumpError(f'not a commit (40 lowercase hex): {new!r}')
    pin = read(text)
    if new == pin['ref']:
        raise BumpError(f'Janus is already pinned to {new}')
    text = re.sub(r'^ARG JANUS_REF=\S*', f'ARG JANUS_REF={new}', text, count=1, flags=re.M)
    return re.sub(
        r'^ARG JANUS_KNOWN_GOOD=\S*',
        f'ARG JANUS_KNOWN_GOOD={pin["ref"]}',
        text,
        count=1,
        flags=re.M,
    )


# --- what a move changes ------------------------------------------------------------


def _load(directory: Path, name: str):
    path = directory / name
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return None
    if name.endswith('.json'):
        try:
            return json.loads(text)
        except ValueError:
            return None
    return text


def _plain(text: str) -> str:
    """Text from the Janus repository, made safe for a code span or a fenced block:
    no backticks (they close it), one line, and so no @mention or #reference."""
    return ' '.join(str(text).replace('`', "'").split())


def _cell(text: str) -> str:
    text = _plain(text)[:160]
    return f'`{text}`' if text else ''


def _subject(commit: dict) -> str:
    message = (commit.get('commit') or {}).get('message') or ''
    return _plain(message.splitlines()[0] if message else '')[:120]


def _contract_sources() -> tuple[tuple[str, ...], tuple[str, ...]]:
    modules = tuple(_literal(CONTRACT, '_SOURCE_MODULES'))
    packages = tuple(_literal(CONTRACT, '_SOURCE_PACKAGES'))
    return modules, packages


def _read_by_contract(filename: str) -> bool:
    modules, packages = _contract_sources()
    return filename in modules or filename.startswith(tuple(f'{p}/' for p in packages))


def _commit_count(compare: dict | None) -> int | None:
    if not compare:
        return None
    for key in ('ahead_by', 'total_commits'):
        if isinstance(compare.get(key), int):
            return compare[key]
    return len(compare.get('commits') or [])


def title(pinned: str, new: str, compare: dict | None) -> str:
    count = _commit_count(compare)
    suffix = '' if count is None else f' ({count} commit{"" if count == 1 else "s"})'
    return f'Janus: move the pin to {new[:12]}{suffix}'


def _result(report: dict | None) -> str:
    if report is None:
        return 'did not run'
    return 'passes' if report.get('ok') else 'fails'


def _contract_section(pinned: dict | None, new: dict | None) -> list[str]:
    lines = ['### Contract', '']
    lines += [
        '| | pinned | candidate |',
        '|---|---|---|',
        f'| version | {_cell((pinned or {}).get("version", ""))} '
        f'| {_cell((new or {}).get("version", ""))} |',
        f'| commit | {_cell(((pinned or {}).get("commit") or "")[:12])} '
        f'| {_cell(((new or {}).get("commit") or "")[:12])} |',
        f'| result | {_result(pinned)} | {_result(new)} |',
        '',
    ]
    if new is None:
        return lines + ['The contract did not run on the candidate.', '']
    before = {c.get('name'): c for c in (pinned or {}).get('checks') or []}
    rows = []
    for check in new.get('checks') or []:
        old = before.get(check.get('name'))
        changed = old is None or bool(old.get('ok')) != bool(check.get('ok'))
        if changed or not check.get('ok'):
            was = 'new check' if old is None else ('ok' if old.get('ok') else 'fails')
            now = 'ok' if check.get('ok') else 'fails'
            kind = 'required' if check.get('required', True) else 'reported'
            rows.append(
                f'| {_cell(check.get("name", ""))} | {kind} | {was} | {now} '
                f'| {_cell(check.get("detail", ""))} |'
            )
    names_now = {c.get('name') for c in new.get('checks') or []}
    for name in before:
        if name not in names_now:
            rows.append(f'| {_cell(name)} | | ok | gone | |')
    if rows:
        lines += ['| check | kind | pinned | candidate | detail |', '|---|---|---|---|---|']
        lines += rows
    else:
        lines.append('No check changed, and every check passes.')
    old_notes = set((pinned or {}).get('notes') or [])
    new_notes = set(new.get('notes') or [])
    if old_notes != new_notes:
        lines += ['', 'Notes:']
        lines += [f'- added: {_cell(n)}' for n in sorted(new_notes - old_notes)]
        lines += [f'- gone: {_cell(n)}' for n in sorted(old_notes - new_notes)]
    return lines + ['']


def _conformance_section(log: str | None, report: dict | None) -> list[str]:
    lines = ['### Conformance', '']
    if log is None:
        return lines + ['The conformance suite did not run on the candidate.', '']
    ran = re.search(r'^Ran (\d+) tests? in ([\d.]+)s', log, re.M)
    outcome = re.findall(r'^(OK\b.*|FAILED\b.*)$', log, re.M)
    if ran:
        lines.append(
            f'Ran {ran.group(1)} tests in {float(ran.group(2)):.0f} s: '
            f'{_plain(outcome[-1]) if outcome else "no result line"}.'
        )
    else:
        lines.append('The suite ran no tests.')
    failing = re.findall(r'^(?:FAIL|ERROR): (\S+) \(([^)]+)\)', log, re.M)
    if failing:
        lines += ['', 'Failing:']
        lines += [f'- {_cell(f"{test} ({where})")}' for test, where in failing]
    if 'skipped=' in log:
        lines += ['', 'Some tests were skipped, which this job counts as a failure.']
    if report:
        lines += ['', 'What the model was offered:', '', '```json']
        lines += [_plain(json.dumps(report, sort_keys=True))]
        lines += ['```']
    return lines + ['']


def _audit_section(audit: str | None) -> list[str]:
    lines = ['### pip-audit of the candidate venv (reported, not blocking)', '']
    if audit is None:
        return lines + ['pip-audit did not run.', '']
    rows = [_plain(line) for line in audit.splitlines() if line.strip()]
    if len(rows) > AUDIT_LINES:
        rows = rows[:AUDIT_LINES] + [f'… {len(rows) - AUDIT_LINES} more lines in the run']
    return lines + ['```text', *rows, '```', '']


def _commits_section(compare: dict | None) -> list[str]:
    if not compare:
        return ['### Commits', '', 'The compare call failed; read the range on GitHub.', '']
    commits = compare.get('commits') or []
    count = _commit_count(compare)
    lines = [f'### Commits ({min(len(commits), COMMITS_SHOWN)} of {count})', '', '```text']
    for commit in commits[-COMMITS_SHOWN:]:
        lines.append(f'{str(commit.get("sha", ""))[:12]}  {_subject(commit)}')
    lines.append('```')
    files = [str(f.get('filename', '')) for f in compare.get('files') or []]
    touched = sorted(f for f in files if _read_by_contract(f))
    lines += ['', f'Files changed: {len(files)}; in the files the contract reads: {len(touched)}.']
    if touched:
        lines += ['', '```text', *[_plain(f) for f in touched], '```']
    return lines + ['']


def body(*, pinned: str, new: str, slug: str, directory: Path, run_url: str) -> str:
    compare = _load(directory, 'compare.json')
    count = _commit_count(compare)
    compare_url = f'https://github.com/{slug}/compare/{pinned}...{new}'
    head = [
        f'## Janus `{pinned[:12]}` → `{new[:12]}`',
        '',
        f"{count if count is not None else 'Some'} commits on {slug}'s main since the "
        f'pin: [compare]({compare_url}).',
        '',
        f'Opened by the [janus-bump run]({run_url}), which installed the candidate as the '
        'image does and ran the contract, the conformance suite and pip-audit against it. '
        'The Dockerfile keeps the commit pinned now as `JANUS_KNOWN_GOOD`, so a build whose '
        'new Janus breaks the contract installs that one instead.',
        '',
        '### Before merging',
        '',
        '- Merging deploys the five stores. Push the release commit onto this branch '
        '(`python manage.py release --minor "Janus …"`): this pull request was opened with '
        "the workflow's token, which starts no workflows, so CI runs on that push.",
        '- Read the commits for changed config defaults, `janus chat` options, `state.db` '
        'tables and hooks. A new Janus surface Morpheus starts to rely on joins '
        '`core/assistant/janus_contract.py` in the same change.',
        '- A later run replaces this pull request while only the workflow has pushed to its '
        'branch, and leaves it alone once a person has.',
        '',
    ]
    sections = (
        _contract_section(
            _load(directory, 'contract-pinned.json'), _load(directory, 'contract-new.json')
        )
        + _conformance_section(
            _load(directory, 'conformance.txt'), _load(directory, 'conformance.json')
        )
        + _audit_section(_load(directory, 'audit.txt'))
    )
    text = '\n'.join(head + sections + _commits_section(compare))
    if len(text) > BODY_LIMIT:
        cut = text[:BODY_LIMIT]
        if cut.count('```') % 2:
            cut += '\n```'
        text = cut + '\n\n… cut to fit; the run summary has the rest.\n'
    return text


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='bump_janus.py', description=__doc__.split('\n')[0])
    parser.add_argument('--dockerfile', type=Path, default=DOCKERFILE)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('env', help='the pin as KEY=value lines')
    moving = sub.add_parser('bump', help='pin a new commit, keeping the old one as fallback')
    moving.add_argument('sha')
    for name in ('title', 'body'):
        described = sub.add_parser(name)
        described.add_argument('--new', required=True)
        described.add_argument('--dir', type=Path, required=True)
        if name == 'body':
            described.add_argument('--run-url', required=True)
    args = parser.parse_args(argv)
    try:
        text = args.dockerfile.read_text(encoding='utf-8')
        if args.command == 'env':
            print('\n'.join(env_lines(text)))
        elif args.command == 'bump':
            old = read(text)['ref']
            args.dockerfile.write_text(bump(text, args.sha), encoding='utf-8')
            print(f'JANUS_REF {old} -> {args.sha}; JANUS_KNOWN_GOOD -> {old}')
        else:
            if not SHA.fullmatch(args.new):
                raise BumpError(f'not a commit (40 lowercase hex): {args.new!r}')
            pin = read(text)
            if args.command == 'title':
                print(title(pin['ref'], args.new, _load(args.dir, 'compare.json')))
            else:
                print(
                    body(
                        pinned=pin['ref'],
                        new=args.new,
                        slug=pin['slug'],
                        directory=args.dir,
                        run_url=args.run_url,
                    )
                )
    except (BumpError, OSError) as e:
        print(f'bump_janus: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
