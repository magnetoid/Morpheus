---
type: decision
status: accepted
tags:
- adr
links:
- '0026-distribution-model-single-tenant-instances-per-client-agency-model-licensing-deferred-to-publish-time-open-core-or-fsl-with-prep-starting-now'
created: '2026-10-04T00:00:00'
updated: '2026-10-04T00:00:00'
rules:
- id: license-is-busl
  pattern: Apache License 2\.0|Apache-2\.0 —|is open source and free
  message: "Morpheus is licensed under the Business Source License 1.1 from
    v0.76.1 (ADR 0038). Apache 2.0 is only the Change License each version
    converts to after four years. Don't describe the platform as Apache or as
    open source in docs or marketing copy."
  where: README.md|CONTRIBUTING.md|CHARTER.md|docs/**/*.md
  severity: warn
---

# ADR 0038: Morpheus is licensed under the Business Source License 1.1 from v0.76.1

## Context

ADR 0026 chose the agency model (one instance per client under a commercial
per-client licence) and deferred the public licence to publish time, naming
open-core or FSL as candidates. The repository went public under Apache 2.0 on
2026-08-21, was private for part of September, and went public again on
2026-10-03 with a README written to bring in merchants, agencies and investors.
On 2026-10-04 the owner asked for a licence under which nobody may use the
platform without his permission.

The candidates were weighed against that wish: FSL only forbids *competing*
with the owner and would let any merchant self-host for free; PolyForm
Noncommercial fits but never opens up; "all rights reserved" fits but kills the
open story the README tells and deters developers. BUSL-1.1 with no Additional
Use Grant forbids all production use without a commercial licence, keeps the
code readable, is recognised by investors and lawyers, and converts each
version to open source on a schedule.

## Decision

- `LICENSE` is the Business Source License 1.1. Licensor: Marko Tiosavljevic.
  Additional Use Grant: **None** — the base grant (copy, modify, redistribute,
  non-production use) is all that is free. Change Date: four years from the date
  each version is published. Change License: Apache License, Version 2.0.
- Commercial licences are sold per store/instance (ADR 0026), by the owner,
  through marko@morpheus.direct.
- Versions up to and including v0.76.0 were published under Apache 2.0; those
  grants are irrevocable and are acknowledged, not denied. BUSL applies from
  v0.76.1.
- The owner holds all copyright (every non-bot commit is his; AI co-author
  trailers carry no copyright claim). Outside contributions, if ever accepted,
  need a contributor agreement that preserves the right to relicense, because
  BUSL's Change License mechanism depends on it.
- Third-party code keeps its own licence (`vendor/`, dependencies, MIT UI
  components). The covenant in ADR 0026 (no GPL/AGPL dependency in core)
  stands: Apache 2.0 as the Change License must stay possible.

## Consequences

- README, CONTRIBUTING, CHARTER and the morpheus.direct site no longer call the
  platform open source or Apache; they say source-available under BUSL-1.1 with
  a scheduled conversion. The `release_notes` About page needs no change (it
  never named the licence).
- GitHub cannot auto-detect BUSL-1.1, so the repository shows "View license"
  rather than a licence name. Acceptable.
- Anyone who copied an Apache-era version keeps Apache rights to that version.
  As of the switch the repository had zero forks and zero stars.
