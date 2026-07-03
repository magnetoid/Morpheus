/* Morpheus rich-text editor — vanilla Lexical (no React). Built with esbuild
   into ../static/richtext/lexical-editor.bundle.js (committed). Exposes
   window.MorphRichText.scan(); enhances every [data-richtext] wrapper. */
import {
  createEditor, $getRoot, $getSelection, $isRangeSelection,
  $createParagraphNode, $insertNodes, FORMAT_TEXT_COMMAND,
  UNDO_COMMAND, REDO_COMMAND, DecoratorNode,
} from 'lexical';
import {
  HeadingNode, QuoteNode, registerRichText,
  $createHeadingNode, $createQuoteNode,
} from '@lexical/rich-text';
import {
  ListNode, ListItemNode, registerList,
  INSERT_ORDERED_LIST_COMMAND, INSERT_UNORDERED_LIST_COMMAND,
} from '@lexical/list';
import { LinkNode, $toggleLink } from '@lexical/link';
import { CodeNode, $createCodeNode } from '@lexical/code';
import { createEmptyHistoryState, registerHistory } from '@lexical/history';
import { $generateHtmlFromNodes, $generateNodesFromDOM } from '@lexical/html';
import { mergeRegister } from '@lexical/utils';
import { $setBlocksType } from '@lexical/selection';

/* ---- Custom leaf nodes: image + horizontal rule (Lexical has neither) ---- */
class ImageNode extends DecoratorNode {
  constructor(src, alt, key) { super(key); this.__src = src; this.__alt = alt || ''; }
  static getType() { return 'image'; }
  static clone(n) { return new ImageNode(n.__src, n.__alt, n.__key); }
  static importDOM() {
    return { img: () => ({ conversion: (el) => ({ node: new ImageNode(el.getAttribute('src') || '', el.getAttribute('alt') || '') }), priority: 0 }) };
  }
  static importJSON(s) { return new ImageNode(s.src, s.alt); }
  exportJSON() { return { type: 'image', version: 1, src: this.__src, alt: this.__alt }; }
  exportDOM() {
    const img = document.createElement('img');
    img.setAttribute('src', this.__src);
    if (this.__alt) img.setAttribute('alt', this.__alt);
    img.setAttribute('loading', 'lazy');
    img.className = 'rte-img';
    return { element: img };
  }
  createDOM() { const span = document.createElement('span'); span.className = 'rte-img-wrap'; return span; }
  updateDOM() { return false; }
  decorate() {
    const img = document.createElement('img');
    img.src = this.__src; img.alt = this.__alt; img.loading = 'lazy'; img.className = 'rte-img';
    return img;
  }
}
function $createImageNode(src, alt) { return new ImageNode(src, alt); }

class HrNode extends DecoratorNode {
  static getType() { return 'horizontalrule'; }
  static clone(n) { return new HrNode(n.__key); }
  static importDOM() { return { hr: () => ({ conversion: () => ({ node: new HrNode() }), priority: 0 }) }; }
  static importJSON() { return new HrNode(); }
  exportJSON() { return { type: 'horizontalrule', version: 1 }; }
  exportDOM() { return { element: document.createElement('hr') }; }
  createDOM() { const span = document.createElement('span'); span.className = 'rte-hr-wrap'; return span; }
  updateDOM() { return false; }
  decorate() { return document.createElement('hr'); }
}
function $createHrNode() { return new HrNode(); }

const NODES = [HeadingNode, QuoteNode, ListNode, ListItemNode, LinkNode, CodeNode, ImageNode, HrNode];

/* ---- HTML in/out ---- */
function loadHTML(editor, html) {
  editor.update(() => {
    const root = $getRoot(); root.clear();
    const trimmed = (html || '').trim();
    if (!trimmed) { root.append($createParagraphNode()); return; }
    const dom = new DOMParser().parseFromString(trimmed, 'text/html');
    const nodes = $generateNodesFromDOM(editor, dom);
    root.append(...nodes);
    if (root.getChildrenSize() === 0) root.append($createParagraphNode());
  });
}
function serializeHTML(editor) {
  let html = '';
  editor.getEditorState().read(() => { html = $generateHtmlFromNodes(editor, null); });
  return html;
}

/* ---- Toolbar command dispatch ---- */
function applyBlock(editor, factory) {
  editor.update(() => {
    const sel = $getSelection();
    if ($isRangeSelection(sel)) $setBlocksType(sel, factory);
  });
}
function dispatch(editor, action, ctx) {
  switch (action) {
    case 'bold': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'bold'); break;
    case 'italic': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'italic'); break;
    case 'strike': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'strikethrough'); break;
    case 'code': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'code'); break;
    case 'h2': applyBlock(editor, () => $createHeadingNode('h2')); break;
    case 'h3': applyBlock(editor, () => $createHeadingNode('h3')); break;
    case 'paragraph': applyBlock(editor, () => $createParagraphNode()); break;
    case 'blockquote': applyBlock(editor, () => $createQuoteNode()); break;
    case 'codeBlock': applyBlock(editor, () => $createCodeNode()); break;
    case 'bulletList': editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined); break;
    case 'orderedList': editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined); break;
    case 'hr': editor.update(() => { $insertNodes([$createHrNode()]); }); break;
    case 'link': {
      const url = window.prompt('Link URL'); if (url === null) break;
      editor.update(() => { $toggleLink(url || null); }); break;
    }
    case 'unlink': editor.update(() => { $toggleLink(null); }); break;
    case 'clear': editor.update(() => {
      const sel = $getSelection();
      if ($isRangeSelection(sel)) { ['bold', 'italic', 'strikethrough', 'code'].forEach((f) => { if (sel.hasFormat(f)) sel.formatText(f); }); }
    }); break;
    case 'undo': editor.dispatchCommand(UNDO_COMMAND, undefined); break;
    case 'redo': editor.dispatchCommand(REDO_COMMAND, undefined); break;
    case 'image': pickAndUploadImage(editor, ctx); break;
    case 'source': toggleSource(ctx); break;
    default: break;
  }
}

async function pickAndUploadImage(editor, ctx) {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = 'image/*';
  input.onchange = async () => {
    const file = input.files && input.files[0]; if (!file) return;
    const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
    const fd = new FormData(); fd.append('file', file);
    const resp = await fetch(ctx.uploadUrl, {
      method: 'POST', body: fd, credentials: 'same-origin',
      headers: tokenEl ? { 'X-CSRFToken': tokenEl.value } : {},
    });
    const data = await resp.json();
    if (resp.ok && data.url) {
      editor.update(() => { $insertNodes([$createImageNode(data.url, data.alt_text || data.filename || '')]); });
    }
  };
  input.click();
}

/* Source (HTML) toggle: swap the contenteditable for a raw textarea. */
function toggleSource(ctx) {
  const src = ctx.source;
  if (src.hidden) {
    src.value = serializeHTML(ctx.editor);
    src.hidden = false; ctx.mount.style.display = 'none';
  } else {
    loadHTML(ctx.editor, src.value);
    src.hidden = true; ctx.mount.style.display = '';
  }
}

/* ---- Mount one [data-richtext] wrapper ---- */
function mountOne(wrap) {
  const mount = wrap.querySelector('[data-rte-mount]');
  const hidden = wrap.querySelector('.rte-hidden');
  const source = wrap.querySelector('.rte-source');
  const toolbar = wrap.querySelector('.rte-toolbar');
  if (!mount || !hidden) return;

  const editor = createEditor({
    namespace: 'morph-richtext', nodes: NODES,
    onError: (e) => { console.error('richtext:', e); },
    theme: { paragraph: 'rte-p', heading: { h2: 'rte-h2', h3: 'rte-h3' }, list: { ul: 'rte-ul', ol: 'rte-ol' }, quote: 'rte-quote', link: 'rte-link' },
  });
  mount.contentEditable = 'true';
  mount.setAttribute('role', 'textbox');
  mount.setAttribute('aria-multiline', 'true');
  editor.setRootElement(mount);

  const ctx = { editor, mount, source, uploadUrl: wrap.getAttribute('data-upload-url') || '/dashboard/media/api/upload/' };

  mergeRegister(
    registerRichText(editor),
    registerList(editor),
    registerHistory(editor, createEmptyHistoryState(), 300),
  );

  // Decorator nodes (img, hr) mount their DOM here — required for vanilla.
  editor.registerDecoratorListener((decorators) => {
    for (const [key, el] of Object.entries(decorators)) {
      const host = editor.getElementByKey(key);
      if (host && el instanceof Node && !host.contains(el)) host.appendChild(el);
    }
  });

  loadHTML(editor, hidden.value);

  editor.registerUpdateListener(() => {
    const html = serializeHTML(editor);
    hidden.value = html;
    if (source && !source.hidden) source.value = html;
  });

  if (toolbar) {
    toolbar.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-rte]'); if (!btn) return;
      e.preventDefault();
      dispatch(editor, btn.getAttribute('data-rte'), ctx);
      editor.focus();
    });
  }

  const handle = {
    getHTML: () => serializeHTML(editor),
    setHTML: (html) => loadHTML(editor, html),
    focus: () => editor.focus(),
    destroy: () => editor.setRootElement(null),
  };
  const exposeAs = wrap.getAttribute('data-expose-as');
  if (exposeAs) window[exposeAs] = handle;
  return handle;
}

export function scan(root) {
  const scope = root || document;
  scope.querySelectorAll('[data-richtext]:not([data-richtext-ready])').forEach((wrap) => {
    wrap.setAttribute('data-richtext-ready', '1');
    try { mountOne(wrap); } catch (e) { console.error('richtext mount failed:', e); }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => scan(document));
} else {
  scan(document);
}
