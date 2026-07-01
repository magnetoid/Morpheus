---
type: progress
status: active
tags:
- active
links: []
created: '2026-07-01T03:03:29'
updated: '2026-07-01T03:03:29'
---

# Progress

LIVE on prod (pushed to magnetoid/morpheus main):
- v0.2.17 (663aede): Linda per-page ✕ dismiss (per-URL localStorage; dismissed page skips the LLM call). DEPLOY VERIFIED HEALTHY — dotbooks.store held 200 the entire ~10min window (02:52–03:01), no 503 blip (template/JS-only change).
- ADR 0023 (4a4eb78): plugins behave like WordPress plugins — enable reveals / disable removes every surface; 3 machine-readable drift rules.

LOCAL-ONLY (committed, NOT yet pushed — batching to avoid Coolify thrash after the v0.2.17 push):
- b8fc602: formalized the two remaining load-bearing ADRs that had empty rules:[] into check_drift guards — 0006 (product-type = plugin OneToOne(→catalog.Product), never a catalog-model field or parallel table; PR #62 landmine) and 0021 (new sign-in path must fire staff_mfa second-factor gate; exactly one core AUTH_SECOND_FACTOR hook; CLAUDE.md MFA-bypass landmine). Verified: YAML parses, both rule sets load, check_drift(new_only)=No drift.

Torsor recommendation ("23 decisions but no machine-readable rules") was found STALE — 22/23 ADRs already carried pattern/message rules; the real gap was 5 empty rules:[] (0001 meta, 0002/0005 UI-placement — intentionally left; 0006/0021 now formalized).
