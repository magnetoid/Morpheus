---
summary: Backs up the store's database and uploaded files automatically every night.
---

## What it's for
This backs up the store's database and uploaded files automatically, once a night, and removes older backups once there are more than you asked to keep.

## Set it up
Choose how many backups to keep in [](field:backups.retention_count), whether to include uploaded media alongside the database in [](field:backups.include_media), and where backups are written in [](field:backups.backup_dir). Leave the directory blank to use the server's own backup location.

## Common tasks
- Change how many recent backups are kept in [](field:backups.retention_count).
- Leave uploaded media out of the nightly backup in [](field:backups.include_media) — useful if your media already lives somewhere else.
- Point backups at a different directory in [](field:backups.backup_dir).

## Good to know
Backups run once a night; there is no page here to browse past backups or restore one — that is a developer's job on the server itself. A failed backup is written to the error log, so it does not fail silently. A backup location outside the server's permanent storage is lost the next time the store is deployed, so leave the directory setting blank unless you know exactly where it should go.
