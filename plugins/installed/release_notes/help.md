---
summary: The help you are reading, plus About Morpheus OS and the version this store runs with every release's notes.
---

## What it's for

This app keeps the store's own documentation inside the dashboard. Every app has a page here: what it is for, how to set it up, the jobs people use it for, and where its screens and settings are. The lists of screens, settings and Linda's abilities are read from the running store each time you open a page, so they match what you see in the menus.

It also holds [About Morpheus OS](page:about), the project's page about the platform and its licence, and [Version & updates](page:version), which shows the version this store runs and when it was installed, the backup of the database made before the last update that changed it, and the notes for every release.

## Common tasks

- Find an app by typing a word into the search box at the top of the Help page.
- Open the help for the page you are on with the Help link at the top right of any dashboard page.
- Ask Linda how to do something in the dashboard. Linda reads the same help before answering.
- Restore a backup: a superuser opens [Version & updates](page:version), picks one under Backups, reads what it will replace, and types the store's name.

## Good to know

Every staff member can read help, whatever their role. The screens it links to still decide who may open them.

Before an update that changes the database, the store backs the database up first and keeps the last five of these backups; if the backup fails, the update stops before changing anything. A store that runs from a built image, as most do, updates when a new version is released, so its Version & updates page has no update button.

A restore puts all the store's data back as it was when the backup was made, or changes nothing if it fails. The store first backs up its data as it is, so a restore can be undone the same way, and shows everyone a "restoring" page while it runs. Access goes back as it was too: staff accounts and API tokens revoked since then work again. Linda cannot restore a backup: it replaces everything saved since.
