---
summary: Defines roles and what each one can do, and controls whether those limits are enforced yet.
---

## What it's for
This defines who can do what in the dashboard. Six ready-made roles cover common jobs — admin, marketing manager, inventory manager, support agent, analyst and content editor — each with its own set of permissions, and you can see which team members hold which role.

## Set it up
Decide how strictly roles are enforced with [the enforcement setting](field:rbac.enforcement_mode): "Log only" (the default) records what would be blocked without blocking anything, which is the safest way to try it; "Enforce" actually denies anyone without the right role; "Off" skips the check completely. You, as the owner, always pass either way, so you cannot lock yourself out.

## Common tasks
- See every role, what it can do, and who was recently granted which role, in [](page:roles).
- Move from "Log only" to "Enforce" once you've checked [the audit log](page:observability/audit) for what it would have blocked, using [the enforcement setting](field:rbac.enforcement_mode).

## Good to know
This page shows roles and recent grants; it does not itself grant or remove one — today that needs a developer with direct access to the store's database. Linda cannot do it either: staff roles are account administration, kept out of her reach on purpose. While enforcement is "Log only," nothing is actually blocked, so review [the audit log](page:observability/audit) before switching to "Enforce." Owners and other superusers are never blocked by a role check, whatever the setting.
