/**
 * Morph.MediaUploader — shared image + video uploader widget.
 *
 * Drop it onto any page that needs to manage a list of product media
 * (images + optional video embeds). One Django partial + this file =
 * the whole UX.
 *
 * Mount markup (rendered server-side):
 *
 *   <div data-media-uploader
 *        data-image-upload-url="/dashboard/products/<id>/images/upload/"
 *        data-image-reorder-url="/dashboard/products/<id>/images/reorder/"
 *        data-image-edit-url="/dashboard/products/<id>/images/{id}/edit/"
 *        data-image-delete-url="/dashboard/products/<id>/images/{id}/delete/"
 *        data-video-add-url="/dashboard/products/<id>/videos/new/"
 *        data-video-edit-url="/dashboard/products/<id>/videos/{id}/edit/"
 *        data-video-delete-url="/dashboard/products/<id>/videos/{id}/delete/"
 *        data-cap="15">
 *     <div class="muploader-grid" data-media-grid>
 *       <!-- tiles rendered server-side from the model -->
 *     </div>
 *     <label class="muploader-dropzone" data-dropzone>...</label>
 *     <form class="muploader-video-form" data-video-form>...</form>
 *     <dialog class="muploader-modal" data-modal>...</dialog>
 *   </div>
 *
 * The component is auto-discovered on DOM ready via the same Morph
 * namespace as the other dashboard widgets — no manual init needed.
 */
(function () {
  'use strict';

  const Morph = window.Morph || (window.Morph = {});
  Morph.MediaUploader = {};

  function csrf() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  }

  function api(url, opts = {}) {
    return fetch(url, Object.assign({
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': csrf(),
        'X-Requested-With': 'XMLHttpRequest',
      },
    }, opts));
  }

  function init(root) {
    if (root.dataset._mediaUploaderBound === '1') return;
    root.dataset._mediaUploaderBound = '1';

    const grid = root.querySelector('[data-media-grid]');
    const fileInput = root.querySelector('[data-file-input]');
    const videoForm = root.querySelector('[data-video-form]');
    const modal = root.querySelector('[data-modal]');
    const addTile = root.querySelector('[data-add-tile]');
    const cap = parseInt(root.dataset.cap || '15', 10);

    const urls = {
      imageUpload: root.dataset.imageUploadUrl,
      imageReorder: root.dataset.imageReorderUrl,
      imageEdit: root.dataset.imageEditUrl,
      imageDelete: root.dataset.imageDeleteUrl,
      videoAdd: root.dataset.videoAddUrl,
      videoEdit: root.dataset.videoEditUrl,
      videoDelete: root.dataset.videoDeleteUrl,
    };

    // Django's <uuid:xxx> URL converter rejects a literal "{id}" during
    // reverse-resolution, so the templates emit this zero UUID as a
    // placeholder. fillId() swaps in the real tile ID.
    const PLACEHOLDER_ID = '00000000-0000-0000-0000-000000000000';
    function fillId(tpl, id) {
      return (tpl || '').replace(PLACEHOLDER_ID, id);
    }

    // ── Drag-and-drop file upload (anywhere on .muploader) ───────────
    // Discriminates external file drops (dataTransfer.types contains
    // 'Files') from internal tile-reorder drags so the wrong handler
    // doesn't fire. Counter pattern handles dragenter/dragleave on
    // nested children without flicker.
    let dragCounter = 0;
    function isFileDrag(e) {
      return Array.from(e.dataTransfer?.types || []).includes('Files');
    }
    root.addEventListener('dragenter', e => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      dragCounter += 1;
      root.classList.add('is-dragover');
    });
    root.addEventListener('dragleave', e => {
      if (!isFileDrag(e)) return;
      dragCounter = Math.max(0, dragCounter - 1);
      if (dragCounter === 0) root.classList.remove('is-dragover');
    });
    root.addEventListener('dragover', e => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    });
    root.addEventListener('drop', e => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      dragCounter = 0;
      root.classList.remove('is-dragover');
      const files = Array.from(e.dataTransfer?.files || []);
      if (files.length) uploadImages(files);
    });

    // Click-to-browse — the "Add" tile and any empty area inside the
    // grid (but NOT on existing tiles).
    function openPicker() {
      if (fileInput) fileInput.click();
    }
    if (addTile) addTile.addEventListener('click', openPicker);
    if (grid) {
      grid.addEventListener('click', e => {
        // Only trigger on the grid background itself — not on tiles or
        // controls. Tiles handle their own clicks (edit / delete).
        if (e.target === grid) openPicker();
      });
    }
    if (fileInput) {
      fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files || []);
        uploadImages(files);
        fileInput.value = '';
      });
    }

    async function uploadImages(files) {
      if (!files.length || !urls.imageUpload) return;
      // Count real media tiles only — exclude the trailing "Add" tile.
      const existingCount = grid
        ? grid.querySelectorAll('[data-id]').length
        : 0;
      let added = 0;
      for (const file of files) {
        if (!file.type.startsWith('image/')) continue;
        if (existingCount + added >= cap) {
          flashMessage(`Cap reached — ${cap} media items max per product.`);
          break;
        }
        const fd = new FormData();
        fd.append('image', file);
        fd.append('alt_text', '');
        try {
          const res = await api(urls.imageUpload, { body: fd });
          if (!res.ok) {
            let reason = `(${res.status})`;
            try { const d = await res.json(); if (d && d.error) reason = d.error; } catch (e) { /* non-JSON */ }
            flashMessage(`Upload failed: ${file.name} — ${reason}`);
            continue;
          }
          added += 1;
        } catch (err) {
          flashMessage(`Upload failed: ${file.name}`);
        }
      }
      if (added) location.reload();   // server re-renders the grid w/ new tile
    }

    // ── Video URL paste ───────────────────────────────────────────────
    if (videoForm) {
      videoForm.addEventListener('submit', async e => {
        e.preventDefault();
        const fd = new FormData(videoForm);
        if (!fd.get('url') && !fd.get('embed_html')) return;
        try {
          const res = await api(urls.videoAdd, { body: fd });
          if (res.ok) {
            location.reload();
          } else {
            flashMessage('Video add failed.');
          }
        } catch {
          flashMessage('Video add failed.');
        }
      });
    }

    // ── Tile click → edit modal ──────────────────────────────────────
    if (grid && modal) {
      grid.addEventListener('click', e => {
        const editBtn = e.target.closest('[data-edit-tile]');
        if (!editBtn) return;
        const tile = editBtn.closest('[data-id]');
        if (!tile) return;
        openModal(tile);
      });
    }

    // ── Per-tile quick-delete (X / trash button) ────────────────────
    // Avoids forcing the user into the edit modal just to remove media.
    if (grid) {
      grid.addEventListener('click', async e => {
        const delBtn = e.target.closest('[data-delete-tile]');
        if (!delBtn) return;
        e.preventDefault();
        e.stopPropagation();
        const tile = delBtn.closest('[data-id]');
        if (!tile) return;
        const kind = tile.dataset.kind;
        const id = tile.dataset.id;
        const label = kind === 'video' ? 'this video' : 'this image';
        if (!confirm(`Remove ${label} from the gallery?`)) return;
        const tpl = kind === 'image' ? urls.imageDelete : urls.videoDelete;
        if (!tpl) {
          flashMessage('Delete not available.');
          return;
        }
        try {
          const res = await api(fillId(tpl, id), { body: new FormData() });
          if (res.ok || res.redirected) {
            tile.remove();
            // Recompute slot labels on the remaining image tiles so
            // "Slot 1" / "Cover" stay in sync without a page reload.
            const imageTiles = grid.querySelectorAll('[data-kind="image"]');
            imageTiles.forEach((t, i) => {
              const slot = t.querySelector('.muploader-tile__slot');
              if (slot) slot.textContent = `Slot ${i + 1}`;
              t.classList.toggle('is-cover', i === 0);
              const pill = t.querySelector('.muploader-tile__cover-pill');
              if (i === 0 && !pill) {
                const span = document.createElement('span');
                span.className = 'muploader-tile__cover-pill';
                span.textContent = 'Cover';
                t.appendChild(span);
              } else if (i !== 0 && pill) {
                pill.remove();
              }
            });
          } else {
            flashMessage('Delete failed.');
          }
        } catch {
          flashMessage('Delete failed.');
        }
      });
    }

    function openModal(tile) {
      const kind = tile.dataset.kind;     // 'image' | 'video'
      const id = tile.dataset.id;
      modal.dataset.kind = kind;
      modal.dataset.id = id;
      // Reveal kind-specific fields.
      modal.querySelectorAll('[data-show-kind]').forEach(el => {
        el.hidden = !el.dataset.showKind.split(',').includes(kind);
      });
      // Populate.
      const altInput = modal.querySelector('[name="alt_text"]');
      const titleInput = modal.querySelector('[name="title"]');
      const posterInput = modal.querySelector('[name="poster_url"]');
      const preview = modal.querySelector('[data-preview]');
      if (preview) {
        if (kind === 'image') {
          const url = tile.querySelector('img')?.src || '';
          preview.innerHTML = url ? `<img src="${url}" alt="">` : '';
        } else {
          const url = tile.dataset.url || '';
          preview.innerHTML = url
            ? `<div class="muploader-modal__video">${url}</div>`
            : '';
        }
      }
      if (altInput) altInput.value = tile.dataset.alt || '';
      if (titleInput) titleInput.value = tile.dataset.title || '';
      if (posterInput) posterInput.value = tile.dataset.poster || '';
      modal.showModal?.() || modal.setAttribute('open', '');
    }

    function closeModal() {
      modal.close?.() || modal.removeAttribute('open');
    }

    if (modal) {
      modal.querySelector('[data-close]')?.addEventListener('click', e => {
        e.preventDefault();
        closeModal();
      });
      modal.querySelector('[data-save]')?.addEventListener('click', async e => {
        e.preventDefault();
        await saveModal();
      });
      modal.querySelector('[data-delete]')?.addEventListener('click', async e => {
        e.preventDefault();
        if (!confirm('Remove this from the gallery?')) return;
        await deleteFromModal();
      });
    }

    async function saveModal() {
      const kind = modal.dataset.kind;
      const id = modal.dataset.id;
      const url = fillId(kind === 'image' ? urls.imageEdit : urls.videoEdit, id);
      const fd = new FormData();
      if (kind === 'image') {
        fd.append('alt_text', modal.querySelector('[name="alt_text"]')?.value || '');
      } else {
        fd.append('title', modal.querySelector('[name="title"]')?.value || '');
        fd.append('poster_url', modal.querySelector('[name="poster_url"]')?.value || '');
      }
      try {
        const res = await api(url, { body: fd });
        if (res.ok) {
          // Patch the tile's data-attributes in place so the next
          // open shows the new values without a reload.
          const tile = grid?.querySelector(`[data-id="${id}"]`);
          if (tile && kind === 'image') {
            tile.dataset.alt = fd.get('alt_text');
          } else if (tile) {
            tile.dataset.title = fd.get('title');
            tile.dataset.poster = fd.get('poster_url');
          }
          closeModal();
        } else {
          flashMessage('Save failed.');
        }
      } catch {
        flashMessage('Save failed.');
      }
    }

    async function deleteFromModal() {
      const kind = modal.dataset.kind;
      const id = modal.dataset.id;
      const url = fillId(kind === 'image' ? urls.imageDelete : urls.videoDelete, id);
      try {
        const res = await api(url, { body: new FormData() });
        if (res.ok || res.redirected) {
          closeModal();
          location.reload();
        } else {
          flashMessage('Delete failed.');
        }
      } catch {
        flashMessage('Delete failed.');
      }
    }

    // ── Drag-reorder (image tiles only — videos sort separately) ────
    if (grid && urls.imageReorder) {
      let dragged = null;
      grid.addEventListener('dragstart', e => {
        const tile = e.target.closest('[data-id][data-kind="image"]');
        if (!tile) return;
        dragged = tile;
        tile.classList.add('is-dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      grid.addEventListener('dragend', () => {
        if (dragged) {
          dragged.classList.remove('is-dragging');
          dragged = null;
        }
      });
      grid.addEventListener('dragover', e => {
        e.preventDefault();
        if (!dragged) return;
        const over = e.target.closest('[data-id][data-kind="image"]');
        if (!over || over === dragged) return;
        const rect = over.getBoundingClientRect();
        const before = (e.clientY - rect.top) < (rect.height / 2);
        grid.insertBefore(dragged, before ? over : over.nextSibling);
      });
      grid.addEventListener('drop', async e => {
        // Only handle this drop when an internal tile is being dragged.
        // External file drops are handled at the .muploader level above;
        // letting them fall through here would fire a no-op reorder API
        // call with the unchanged IDs.
        if (!dragged) return;
        e.preventDefault();
        const imageIds = Array.from(
          grid.querySelectorAll('[data-kind="image"][data-id]')
        ).map(el => el.dataset.id);
        try {
          await api(urls.imageReorder, {
            headers: {
              'X-CSRFToken': csrf(),
              'X-Requested-With': 'XMLHttpRequest',
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'order=' + encodeURIComponent(imageIds.join(',')),
          });
          // Refresh "Cover" pill — slot 0 is the cover.
          syncCoverPill();
        } catch {
          /* reorder is best-effort */
        }
      });
      syncCoverPill();
    }

    function syncCoverPill() {
      const tiles = grid?.querySelectorAll('[data-kind="image"][data-id]') || [];
      tiles.forEach((t, i) => {
        t.classList.toggle('is-cover', i === 0);
      });
    }
  }

  function flashMessage(text) {
    if (window.morphToast) {
      morphToast(text, { kind: 'warn' });
    } else {
      console.warn('media-uploader:', text);
    }
  }

  Morph.MediaUploader.init = init;
  Morph.MediaUploader.initAll = function (root) {
    (root || document).querySelectorAll('[data-media-uploader]').forEach(init);
  };

  if (document.readyState !== 'loading') {
    Morph.MediaUploader.initAll();
  } else {
    document.addEventListener('DOMContentLoaded', () => Morph.MediaUploader.initAll());
  }
})();
