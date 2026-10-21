"""Restoring a backup from Settings → Version & updates: superusers only.

The screen names the backup, says what restoring it replaces (each app counts
its own records since the backup was made) and what happens, and asks for the
store's name. Then it starts ``manage.py morph_restore`` in the background
(``core.restore.spawn``) and goes back to Version & updates. Linda has no tool
for this: a restore replaces everything saved since the backup.
"""

from __future__ import annotations

import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render

from core import restore
from core.utils.site import store_name

KIND_LABELS = {
    'nightly': 'Nightly',
    'pre-deploy': 'Before an update',
    'pre-restore': 'Before a restore',
}
VERSION_PAGE = '/dashboard/apps/release_notes/version/'


def _join(parts: list[str]) -> str:
    if len(parts) < 2:
        return ''.join(parts)
    return ', '.join(parts[:-1]) + ' and ' + parts[-1]


@staff_member_required
def restore_backup(request, kind: str, name: str):
    if not request.user.is_superuser:
        raise Http404
    backup = restore.find(kind, name)
    if backup is None:
        raise Http404
    error = ''
    if request.method == 'POST':
        typed = request.POST.get('confirm', '')
        if typed.strip() != store_name():
            error = "That isn't the store's name. Type it exactly as it is shown."
        else:
            # Under gunicorn this worker's parent is the master, which the restore
            # reloads once it is done (each process keeps settings in memory).
            server = request.META.get('SERVER_SOFTWARE', '')
            reload_pid = os.getppid() if server.startswith('gunicorn') else 0
            try:
                restore.spawn(
                    backup['path'],
                    confirm=typed,
                    by=request.user.get_username(),
                    reload_pid=reload_pid,
                )
            except OSError as exc:
                error = f'The restore could not start: {exc}'
            else:
                messages.success(
                    request,
                    'The restore is starting. Until it finishes, everyone sees a "restoring" '
                    'page. If it does not start, this page says why.',
                )
                return redirect(VERSION_PAGE)
    lost = _join([f'{row["count"]} {row["label"]}' for row in restore.losses(backup['taken_at'])])
    # Before anything runs: which migrations the running code needs that this
    # backup's database never ran (None when they cannot be read).
    applied = restore.backup_migrations(backup['path'])
    lacks = restore.missing_for(applied) if applied is not None else None
    return render(
        request,
        'release_notes/restore_confirm.html',
        {
            'backup': backup,
            'kind_label': KIND_LABELS[backup['kind']],
            'lost': lost,
            'lacks': lacks,
            'store_name': store_name(),
            'error': error,
            'version_page': VERSION_PAGE,
        },
        status=400 if error else 200,
    )
