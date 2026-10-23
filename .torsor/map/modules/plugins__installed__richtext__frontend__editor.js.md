---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/richtext/frontend/editor.js

Symbols in `plugins/installed/richtext/frontend/editor.js`.

- L25 `ImageNode` (class) — ---- Custom leaf nodes: image + horizontal rule (Lexical has neither) ----
- L26 `constructor(src, alt, key)` (method)
- L27 `getType()` (method)
- L28 `clone(n)` (method)
- L29 `importDOM()` (method)
- L32 `importJSON(s)` (method)
- L33 `exportJSON()` (method)
- L34 `exportDOM()` (method)
- L42 `createDOM()` (method)
- L43 `updateDOM()` (method)
- L44 `decorate()` (method)
- L50 `$createImageNode(src, alt)` (function)
- L52 `HrNode` (class)
- L53 `getType()` (method)
- L54 `clone(n)` (method)
- L55 `importDOM()` (method)
- L56 `importJSON()` (method)
- L57 `exportJSON()` (method)
- L58 `exportDOM()` (method)
- L59 `createDOM()` (method)
- L60 `updateDOM()` (method)
- L61 `decorate()` (method)
- L63 `$createHrNode()` (function)
- L77 `paragraphsFromText(doc, text)` (function)
- L91 `normaliseTopLevel(doc)` (function)
- L116 `loadHTML(editor, html)` (function)
- L127 `serializeHTML(editor)` (function)
- L134 `applyBlock(editor, factory)` (function) — ---- Toolbar command dispatch ----
- L140 `dispatch(editor, action, ctx)` (function)
- L171 `pickAndUploadImage(editor, ctx)` (function)
- L191 `toggleSource(ctx)` (function) — Source (HTML) toggle: swap the contenteditable for a raw textarea.
- L203 `mountOne(wrap)` (function) — ---- Mount one [data-richtext] wrapper ----
- L264 `scan(root)` (function)
