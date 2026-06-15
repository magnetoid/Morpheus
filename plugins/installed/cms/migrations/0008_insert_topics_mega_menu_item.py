"""Insert a Topics mega-menu item after Genres in the header + mobile menus.

The header/mobile menus were seeded before Topics existed as a nav kind, so
existing installs (incl. prod) have a Genres mega item but no Topics one. This
slots a `mega_topics` item right after `mega_categories` in each menu — but only
if that menu doesn't already have one (idempotent; never clobbers merchant edits
beyond the single insert). Fresh installs get Topics from `seed_nav_menus`.
"""

from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    Menu = apps.get_model('cms', 'Menu')
    MenuItem = apps.get_model('cms', 'MenuItem')
    for key in ('header', 'mobile'):
        menu = Menu.objects.filter(key=key).first()
        if menu is None:
            continue
        items = menu.items.all()
        if any(i.kind == 'mega_topics' for i in items):
            continue  # already present — leave the menu as the merchant has it
        genres = next((i for i in items if i.kind == 'mega_categories'), None)
        if genres is None:
            continue  # no Genres anchor → nothing to slot Topics beside
        MenuItem.objects.create(
            menu=menu,
            label='Topics',
            url='/topics/',
            kind='mega_topics',
            order=genres.order + 5,
        )


def backwards(apps, schema_editor):
    MenuItem = apps.get_model('cms', 'MenuItem')
    MenuItem.objects.filter(kind='mega_topics', menu__key__in=('header', 'mobile')).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('cms', '0007_alter_menuitem_kind'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
