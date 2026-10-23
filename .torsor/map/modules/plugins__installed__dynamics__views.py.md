---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/dynamics/views.py

Symbols in `plugins/installed/dynamics/views.py`.

- L33 `_trail(*items)` (function)
- L39 `index(request)` (function) — Merchandising console: surfaces takeover table + carousel blocks.
- L64 `take_control(request, surface)` (function) — One click: bind a smart-strategy block to a theme surface.
- L90 `preview_block(request, block_id)` (function) — Live preview: the block's picks with per-product score explanations.
- L130 `edit_block(request, block_id=None)` (function) — Create (block_id is None) or edit a DynamicBlock.
- L173 `delete_block(request, block_id)` (function)
- L186 `_save_from_post(request, block)` (function) — Persist a DynamicBlock from POST data. Returns the saved instance,
- L243 `_checked(request, key)` (function)
- L247 `_apply_option_fields(block, request)` (function) — Parse the B2/B3/B4 option fields off POST onto `block` (before save).
- L301 `proposals(request)` (function) — Human-checkpoint review queue for the nightly merchandiser autopilot.
- L323 `proposal_action(request, proposal_id)` (function) — Approve (apply the low-risk config action) or dismiss one proposal.
