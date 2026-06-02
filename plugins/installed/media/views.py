"""Asset library views — browse / upload / edit / delete.

Single page with tabs across every asset type the merchant might care
about: images, video, audio, PDFs, spreadsheets, Word docs, other
documents, plus a special tab for *digital products* (Product rows
with ``product_type='digital'`` and an attached ``digital_file``).
"""

# ruff: noqa: PLC0415, UP037, PLR0911, S110 — inline model imports (cross-plugin, load-order-safe),
# quoted self-ref annotations, the tab-classifier branch count, and optional-source count swallows
# are all intentional and pre-date this change.
from __future__ import annotations

import json  # noqa: F401 — re-exported for picker callers
import logging

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from morpheus.views import staff_member_required
from plugins.installed.media.models import MediaAsset

logger = logging.getLogger('morpheus.media.views')


class _UnifiedAsset:
    """Adapter that exposes a uniform shape across MediaAsset,
    ProductImage, and Product.digital_file. The library template
    iterates these by attribute name, so we mimic MediaAsset's
    public surface (.is_image, .kind, .url, .filename, .mime_type,
    .alt_text, .width, .height, .human_size) and add .edit_url so
    the template can link back to the source of truth (admin
    product edit form for ProductImage / digital_file, media
    edit-meta for native MediaAsset rows).
    """

    __slots__ = (
        'id',
        'kind',
        'url',
        'filename',
        'mime_type',
        'alt_text',
        'title',
        'description',
        'tags',
        'width',
        'height',
        'size_bytes',
        'created_at',
        'edit_url',
        'save_url',
        'source',
        'source_label',
    )

    def __init__(
        self,
        *,
        id,
        kind,
        url,
        filename='',
        mime_type='',
        alt_text='',
        title='',
        description='',
        tags=None,
        width=None,
        height=None,
        size_bytes=0,
        created_at=None,
        edit_url='',
        save_url='',
        source='media',
        source_label='',
    ):
        self.id = id
        self.kind = kind
        self.url = url
        self.filename = filename
        self.mime_type = mime_type
        self.alt_text = alt_text
        self.title = title
        self.description = description
        self.tags = tags or []
        self.width = width
        self.height = height
        self.size_bytes = size_bytes
        self.created_at = created_at
        self.edit_url = edit_url
        self.save_url = save_url
        self.source = source
        self.source_label = source_label

    @property
    def is_image(self) -> bool:
        return self.kind == 'image'

    @property
    def editable(self) -> str:
        """How much meta the inline modal can edit: 'full' (MediaAsset →
        title/alt/description/tags), 'alt' (ProductImage → alt only), or
        'none' (digital files — preview + link + open-in-product only)."""
        if self.source == 'media':
            return 'full'
        if self.source == 'product_image':
            return 'alt'
        return 'none'

    @property
    def human_size(self) -> str:
        n = float(self.size_bytes or 0)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if n < 1024 or unit == 'GB':
                return f'{n:,.1f} {unit}' if unit != 'B' else f'{int(n)} B'
            n /= 1024
        return f'{n:,.1f} GB'

    @classmethod
    def from_media_asset(cls, a) -> '_UnifiedAsset':
        return cls(
            id=str(a.id),
            kind=a.kind,
            url=a.url,
            filename=a.filename,
            mime_type=a.mime_type,
            alt_text=a.alt_text,
            title=a.title,
            description=a.description,
            tags=list(a.tags or []),
            width=a.width,
            height=a.height,
            size_bytes=a.size_bytes,
            created_at=a.created_at,
            edit_url=f'/dashboard/media/{a.id}/edit/',
            save_url=f'/dashboard/media/{a.id}/edit/',
            source='media',
            source_label='Library',
        )

    @classmethod
    def from_product_image(cls, pi) -> '_UnifiedAsset':
        try:
            url = pi.image.url if pi.image else ''
            size = pi.image.size if pi.image and pi.image.storage.exists(pi.image.name) else 0
        except Exception:  # noqa: BLE001
            url, size = '', 0
        name = (pi.image.name or '').rsplit('/', 1)[-1]
        return cls(
            id=f'pi:{pi.id}',
            kind='image',
            url=url,
            filename=name or 'product-image',
            mime_type='image/' + (name.rsplit('.', 1)[-1].lower() if '.' in name else 'jpeg'),
            alt_text=pi.alt_text or '',
            size_bytes=size,
            created_at=pi.created_at,
            edit_url=f'/dashboard/products/{pi.product_id}/',
            save_url=f'/dashboard/products/{pi.product_id}/images/{pi.id}/edit/',
            source='product_image',
            source_label='Product image',
        )

    @classmethod
    def from_digital_file(cls, prod) -> '_UnifiedAsset':
        try:
            url = prod.digital_file.url if prod.digital_file else ''
            size = (
                prod.digital_file.size
                if prod.digital_file and prod.digital_file.storage.exists(prod.digital_file.name)
                else 0
            )
        except Exception:  # noqa: BLE001
            url, size = '', 0
        name = (prod.digital_file.name or '').rsplit('/', 1)[-1]
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        mime = {
            'pdf': 'application/pdf',
            'epub': 'application/epub+zip',
            'zip': 'application/zip',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'mobi': 'application/x-mobipocket-ebook',
        }.get(ext, 'application/octet-stream')
        # Label the source with the product's status so admin can tell
        # draft / archived digital files from the live catalogue at a
        # glance. The asset itself still surfaces (the file exists) —
        # the badge just disambiguates.
        status = (prod.status or '').lower()
        label_suffix = ''
        if status == 'draft':
            label_suffix = ' · DRAFT'
        elif status == 'archived':
            label_suffix = ' · ARCHIVED'
        return cls(
            id=f'dp:{prod.id}',
            kind='document',
            url=url,
            filename=name or f'{prod.slug}.bin',
            mime_type=mime,
            alt_text=prod.name,
            size_bytes=size,
            created_at=prod.updated_at,
            edit_url=f'/dashboard/products/{prod.id}/',
            source='digital_product',
            source_label=f'Digital product{label_suffix}',
        )

    @classmethod
    def from_variant_file(cls, variant) -> '_UnifiedAsset':
        """Per-variant digital file (ProductVariant.digital_file) — e.g. a book
        sold in multiple formats, each with its own PDF/EPUB/MOBI."""
        try:
            f = variant.digital_file
            url = f.url if f else ''
            size = f.size if f and f.storage.exists(f.name) else 0
        except Exception:  # noqa: BLE001
            url, size = '', 0
        name = (getattr(variant.digital_file, 'name', '') or '').rsplit('/', 1)[-1]
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        mime = {
            'pdf': 'application/pdf',
            'epub': 'application/epub+zip',
            'mobi': 'application/x-mobipocket-ebook',
            'zip': 'application/zip',
            'txt': 'text/plain',
        }.get(ext, 'application/octet-stream')
        prod_id = getattr(variant, 'product_id', None)
        prod = getattr(variant, 'product', None)
        return cls(
            id=f'pv:{variant.id}',
            kind='document',
            url=url,
            filename=name or f'variant-{variant.id}.bin',
            mime_type=mime,
            alt_text=(getattr(prod, 'name', '') or '')
            + (f' · {variant.name}' if getattr(variant, 'name', '') else ''),
            size_bytes=size,
            created_at=getattr(variant, 'created_at', None) or getattr(prod, 'updated_at', None),
            edit_url=f'/dashboard/products/{prod_id}/' if prod_id else '/dashboard/products/',
            source='digital_variant',
            source_label='Digital edition',
        )


def _federated_assets(view: str, search: str = '', tag: str = '') -> list[_UnifiedAsset]:
    """Read-time union of MediaAsset, ProductImage, and Product.digital_file.

    Filters apply uniformly across all three sources. Returned newest-first
    by created_at. Hard-capped at 500 federated rows to keep the page
    snappy — paginated views can plug in when this hits a real bottleneck.
    """
    items: list[_UnifiedAsset] = []

    # 1) Native MediaAsset rows — always available.
    qs = _filter_for_view(MediaAsset.objects.all(), view)
    if search:
        qs = qs.filter(Q(filename__icontains=search) | Q(alt_text__icontains=search))
    if tag:
        qs = qs.filter(tags__contains=[tag])
    items.extend(_UnifiedAsset.from_media_asset(a) for a in qs[:300])

    # 2) ProductImage rows — surface as images.
    if view in ('all', 'image'):
        try:
            from plugins.installed.catalog.models import ProductImage

            pi_qs = ProductImage.objects.select_related('product').order_by('-created_at')
            if search:
                pi_qs = pi_qs.filter(
                    Q(image__icontains=search)
                    | Q(alt_text__icontains=search)
                    | Q(product__name__icontains=search)
                )
            items.extend(_UnifiedAsset.from_product_image(pi) for pi in pi_qs[:300])
        except Exception as e:  # noqa: BLE001
            logger.debug('media.federated: ProductImage skipped: %s', e)

    # 3) Product.digital_file rows — surface as documents.
    if view in ('all', 'document', 'pdf', 'spreadsheet', 'word', 'other'):
        try:
            from plugins.installed.catalog.models import Product

            # Archived products are dead inventory — their digital files
            # shouldn't appear in the media library, otherwise admins see
            # files belonging to dead listings alongside live assets.
            # Drafts stay surfaced (they're work-in-progress, not dead).
            dp_qs = (
                Product.objects.filter(product_type='digital')
                .exclude(status='archived')
                .exclude(digital_file='')
                .exclude(digital_file__isnull=True)
                .order_by('-updated_at')
            )
            if search:
                dp_qs = dp_qs.filter(Q(name__icontains=search) | Q(digital_file__icontains=search))
            # Digital files are federated into the doc views, but must respect
            # the *specific* sub-tab — a .txt digital product must not surface
            # under PDFs (otherwise the PDF tab shows non-PDF files).
            items.extend(
                a
                for a in (_UnifiedAsset.from_digital_file(p) for p in dp_qs[:200])
                if _doc_view_matches(a.filename, a.mime_type, view)
            )
        except Exception as e:  # noqa: BLE001
            logger.debug('media.federated: digital_file skipped: %s', e)

        # 3b) Per-variant digital files (ProductVariant.digital_file) — a book
        # sold in several formats keeps its PDF/EPUB on the variant, not the
        # Product. These were invisible in the library before this branch.
        try:
            from plugins.installed.catalog.models import ProductVariant

            pv_qs = (
                ProductVariant.objects.select_related('product')
                .exclude(digital_file='')
                .exclude(digital_file__isnull=True)
                .order_by('-id')
            )
            if search:
                pv_qs = pv_qs.filter(
                    Q(digital_file__icontains=search) | Q(product__name__icontains=search)
                )
            items.extend(
                a
                for a in (_UnifiedAsset.from_variant_file(v) for v in pv_qs[:300])
                if _doc_view_matches(a.filename, a.mime_type, view)
            )
        except Exception as e:  # noqa: BLE001
            logger.debug('media.federated: variant digital_file skipped: %s', e)

    items.sort(key=lambda a: a.created_at or '', reverse=True)
    return items[:500]


# Mime → "view" classifier for fine-grained tabs within the document kind.
# Order is significant — first match wins.
_DOC_VIEWS = (
    ('pdf', 'PDFs', 'file-text', ('pdf',)),
    (
        'spreadsheet',
        'Spreadsheets',
        'sheet',
        ('spreadsheet', 'excel', 'csv', '.xls', '.xlsx', '.numbers'),
    ),
    ('word', 'Word docs', 'file-text', ('word', 'wordprocessingml', '.doc', '.docx', '.rtf')),
)


def _doc_view_matches(filename: str, mime: str, view: str) -> bool:
    """Whether a document-ish asset (by filename + mime) belongs in a doc
    sub-tab. Digital-product files are federated into the doc views, but must
    still respect the *specific* tab — a .txt must not show under PDFs.
    """
    if view == 'all':
        return True
    hay = f'{filename} {mime}'.lower()
    for key, _label, _icon, needles in _DOC_VIEWS:
        if view == key:
            return any(n in hay for n in needles)
    if view == 'document':  # "Other docs" — anything that isn't a specific doc type
        return not any(n in hay for _k, _l, _i, needles in _DOC_VIEWS for n in needles)
    return False  # image / video / audio / other → digital files don't belong


def _filter_for_view(qs, view: str):
    """Narrow ``qs`` to a single tab. Returns the same queryset when view='all'."""
    if view == 'image':
        return qs.filter(kind=MediaAsset.KIND_IMAGE)
    if view == 'video':
        return qs.filter(kind=MediaAsset.KIND_VIDEO)
    if view == 'audio':
        return qs.filter(kind=MediaAsset.KIND_AUDIO)
    if view == 'document':
        narrowed = qs.filter(kind=MediaAsset.KIND_DOCUMENT)
        for _, _, _, needles in _DOC_VIEWS:
            for n in needles:
                narrowed = narrowed.exclude(Q(mime_type__icontains=n) | Q(filename__icontains=n))
        return narrowed
    if view == 'other':
        return qs.filter(kind=MediaAsset.KIND_OTHER)
    for key, _, _, needles in _DOC_VIEWS:
        if view == key:
            q = Q()
            for n in needles:
                q |= Q(mime_type__icontains=n) | Q(filename__icontains=n)
            return qs.filter(kind=MediaAsset.KIND_DOCUMENT).filter(q)
    return qs


def _build_tabs(view: str) -> list[dict]:
    """Pre-counted tab list rendered into the template.

    Counts include federated rows (ProductImage + Product.digital_file)
    so the tab numbers match what the user actually sees on each tab.
    """
    base = MediaAsset.objects.all()

    # Federated counts. Digital files (Product + per-variant) are classified by
    # the same doc-tab rule the grid uses, so each tab's number matches what it
    # actually shows. Tolerate missing tables (fresh install) by zeroing out.
    pi_count = 0
    digital_count = 0
    doc_files: list[tuple[str, str]] = []
    try:
        from plugins.installed.catalog.models import Product, ProductImage, ProductVariant

        pi_count = ProductImage.objects.count()
        digital_count = Product.objects.filter(product_type='digital').count()
        prod_names = (
            Product.objects.filter(product_type='digital')
            .exclude(status='archived')
            .exclude(digital_file='')
            .exclude(digital_file__isnull=True)
            .values_list('digital_file', flat=True)
        )
        var_names = (
            ProductVariant.objects.exclude(digital_file='')
            .exclude(digital_file__isnull=True)
            .values_list('digital_file', flat=True)
        )
        doc_files = [(str(n).rsplit('/', 1)[-1], '') for n in prod_names]
        doc_files += [(str(n).rsplit('/', 1)[-1], '') for n in var_names]
    except Exception:  # noqa: BLE001
        pass

    def _doc_count(v: str) -> int:
        return sum(1 for fn, mm in doc_files if _doc_view_matches(fn, mm, v))

    dp_total = len(doc_files)

    tabs = [
        {
            'key': 'all',
            'label': 'All',
            'icon': 'layers',
            'count': base.count() + pi_count + dp_total,
            'active': view in ('all', ''),
        }
    ]
    for key, label, icon in (
        ('image', 'Images', 'image'),
        ('video', 'Videos', 'film'),
        ('audio', 'Audio', 'music'),
    ):
        c = base.filter(kind=key).count()
        if key == 'image':
            c += pi_count
        tabs.append(
            {
                'key': key,
                'label': label,
                'icon': icon,
                'count': c,
                'active': view == key,
            }
        )
    for key, label, icon, _ in _DOC_VIEWS:
        tabs.append(
            {
                'key': key,
                'label': label,
                'icon': icon,
                'count': _filter_for_view(base, key).count() + _doc_count(key),
                'active': view == key,
            }
        )
    tabs.append(
        {
            'key': 'document',
            'label': 'Other docs',
            'icon': 'file',
            'count': _filter_for_view(base, 'document').count() + _doc_count('document'),
            'active': view == 'document',
        }
    )
    tabs.append(
        {
            'key': 'other',
            'label': 'Other',
            'icon': 'box',
            'count': base.filter(kind=MediaAsset.KIND_OTHER).count(),
            'active': view == 'other',
        }
    )
    tabs.append(
        {
            'key': 'digital_products',
            'label': 'Digital products',
            'icon': 'download',
            'count': digital_count,
            'active': view == 'digital_products',
        }
    )
    return tabs


@staff_member_required
def library(request: HttpRequest) -> HttpResponse:
    """Browse the asset library — single page with tabs across every type."""
    view = (request.GET.get('view') or 'all').strip().lower() or 'all'

    # Special branch — digital products live in the catalog Product table.
    if view == 'digital_products':
        digital_products: list = []
        try:
            from plugins.installed.catalog.models import Product

            digital_products = list(
                Product.objects.filter(product_type='digital').order_by('-updated_at')[:200]
            )
        except Exception as e:  # noqa: BLE001
            logger.debug('media.library: digital products query failed: %s', e)
        return render(
            request,
            'media/library.html',
            {
                'view': view,
                'kind_tabs': _build_tabs(view),
                'digital_products': digital_products,
                'active_nav': 'assets',
            },
        )

    search = (request.GET.get('q') or '').strip()
    tag = (request.GET.get('tag') or '').strip()
    assets = _federated_assets(view, search=search, tag=tag)

    return render(
        request,
        'media/library.html',
        {
            'assets': assets,
            'view': view,
            'search': search,
            'tag': tag,
            'kind_tabs': _build_tabs(view),
            'active_nav': 'assets',
        },
    )


@staff_member_required
@require_http_methods(['POST'])
def upload(request: HttpRequest) -> HttpResponse:
    """Multipart upload — single or multi-file."""
    files = request.FILES.getlist('file') or request.FILES.getlist('files')
    if not files:
        messages.error(request, 'No files in upload.')
        return redirect('media:library')

    user = request.user if request.user.is_authenticated else None
    created = 0
    for f in files:
        try:
            MediaAsset.from_upload(uploaded_file=f, uploaded_by=user)
            created += 1
        except Exception as e:  # noqa: BLE001 — log + keep going
            logger.warning('media: upload failed for %s: %s', f.name, e, exc_info=True)
            messages.error(request, f'Failed to upload {f.name}: {e}')
    if created:
        messages.success(request, f'Uploaded {created} file(s).')
    return redirect('media:library')


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_upload(request: HttpRequest) -> JsonResponse:
    """JSON-returning upload endpoint — used by the picker modal so the
    image lands without a full page reload. Accepts a single `file`
    field. Returns the new asset's id + url + dimensions.
    """
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'no file'}, status=400)
    user = request.user if request.user.is_authenticated else None
    try:
        asset = MediaAsset.from_upload(uploaded_file=f, uploaded_by=user)
    except Exception as e:  # noqa: BLE001
        logger.warning('media: api upload failed: %s', e, exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse(
        {
            'id': str(asset.id),
            'url': asset.url,
            'filename': asset.filename,
            'kind': asset.kind,
            'mime_type': asset.mime_type,
            'width': asset.width,
            'height': asset.height,
            'size_bytes': asset.size_bytes,
            'alt_text': asset.alt_text,
        }
    )


@staff_member_required
@require_http_methods(['POST'])
def delete(request: HttpRequest, asset_id) -> HttpResponse:
    asset = get_object_or_404(MediaAsset, pk=asset_id)
    asset.file.delete(save=False)  # remove from storage too
    name = asset.filename
    asset.delete()
    messages.success(request, f'Deleted "{name}".')
    return redirect('media:library')


@staff_member_required
def edit_meta(request: HttpRequest, asset_id) -> HttpResponse:
    """Edit title / alt text / description / tags. The file itself is
    replaced via re-upload.

    Responds with JSON when called over AJAX (the library's inline SEO
    modal) so the client never mistakes an HTML redirect for success —
    see the ``dashboard-ajax-json-contract`` landmine.
    """
    asset = get_object_or_404(MediaAsset, pk=asset_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        asset.title = (request.POST.get('title') or '')[:200]
        asset.alt_text = (request.POST.get('alt_text') or '')[:300]
        asset.description = (request.POST.get('description') or '').strip()
        raw_tags = (request.POST.get('tags') or '').strip()
        asset.tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
        asset.save(update_fields=['title', 'alt_text', 'description', 'tags', 'updated_at'])
        if is_ajax:
            return JsonResponse(
                {
                    'ok': True,
                    'asset': {
                        'id': str(asset.id),
                        'title': asset.title,
                        'alt_text': asset.alt_text,
                        'description': asset.description,
                        'tags': asset.tags,
                        'display': asset.title or asset.filename or 'untitled',
                    },
                }
            )
        messages.success(request, 'Asset updated.')
        return redirect('media:library')
    return render(
        request,
        'media/edit_meta.html',
        {
            'asset': asset,
            'tags_str': ', '.join(asset.tags or []),
            'active_nav': 'media',
        },
    )


@staff_member_required
def picker_modal(request: HttpRequest) -> HttpResponse:
    """Embeddable picker — used in iframes / dialogs in other forms.

    Returns a stripped-down library view with click-to-select rows.
    The host page wires up `window.postMessage({type: 'media:picked',
    asset: {…}})` from a small script in the modal.
    """
    qs = MediaAsset.objects.all()
    kind = (request.GET.get('kind') or '').strip()
    if kind:
        qs = qs.filter(kind=kind)
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(filename__icontains=search) | qs.filter(alt_text__icontains=search)
    return render(
        request,
        'media/picker.html',
        {
            'assets': list(qs[:60]),
            'kind': kind,
            'search': search,
        },
    )
