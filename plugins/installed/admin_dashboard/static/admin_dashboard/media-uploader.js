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
    const dropzone = root.querySelector('[data-dropzone]');
    const fileInput = root.querySelector('[data-file-input]');
    const videoForm = root.querySelector('[data-video-form]');
    const modal = root.querySelector('[data-modal]');
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

    // ── Drag-and-drop file upload ────────────────────────────────────
    function setDragActive(on) {
      if (dropzone) dropzone.classList.toggle('is-dragover', on);
    }
    if (dropzone) {
      ['dragenter', 'dragover'].forEach(ev =>
        dropzone.addEventListener(ev, e => {
          e.preventDefault();
          e.stopPropagation();
          setDragActive(true);
        }));
      ['dragleave', 'drop'].forEach(ev =>
        dropzone.addEventListener(ev, e => {
          e.preventDefault();
          e.stopPropagation();
          setDragActive(false);
        }));
      dropzone.addEventListener('drop', e => {
        const files = Array.from(e.dataTransfer?.files || []);
        uploadImages(files);
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
      const existingCount = grid?.children.length || 0;
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
            flashMessage(`Upload failed: ${file.name} (${res.status})`);
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
      const url = (kind === 'image' ? urls.imageEdit : urls.videoEdit)
        .replace('{id}', id);
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
      const url = (kind === 'image' ? urls.imageDelete : urls.videoDelete)
        .replace('{id}', id);
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
