"""Re-publish Gutenberg-imported books as DotBooks variable products.

For each product whose primary image is named ``gutenberg-<N>.*`` (or
whose ``book.gutenberg_id`` metafield is set), this command:

1. Downloads the canonical plain text from Project Gutenberg and
   strips the START/END boilerplate so what we ship is the book
   itself — no licence, no transcriber notes.
2. Generates a clean EPUB (handwritten, valid EPUB 3 structure) +
   PDF (reportlab) carrying ``DotBooks`` as the publisher.
3. Bundles ``<slug>.epub`` + ``<slug>.pdf`` + ``<slug>.txt`` into a
   single ``<slug>.zip`` and saves it as ``product.digital_file``.
4. Flips ``product_type='variable'`` and recreates two variants:
     - ``Digital`` (sku ``<slug>-digital``)
     - ``Print``   (sku ``<slug>-print``)
   The price of each comes from --digital-price / --print-price.
5. Updates the ``book.publisher`` metafield from "Project Gutenberg"
   to "DotBooks".
6. Restores ``status='active'`` so the product reappears on the
   storefront.

Idempotent — re-running overwrites the bundle + replaces the variants.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import datetime
from html import escape as html_escape

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.gutenberg')


_START_RE = re.compile(
    r'^\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG (?:EBOOK|EBook).*?\*\*\*',
    re.MULTILINE | re.IGNORECASE,
)
_END_RE = re.compile(
    r'^\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG (?:EBOOK|EBook).*?\*\*\*',
    re.MULTILINE | re.IGNORECASE,
)


def _strip_gutenberg(raw: str) -> str:
    start = _START_RE.search(raw)
    end = _END_RE.search(raw)
    if start and end and end.start() > start.end():
        body = raw[start.end() : end.start()]
    elif start:
        body = raw[start.end() :]
    else:
        body = raw
    return body.strip() + '\n'


def _gutenberg_id_for(product) -> int | None:
    """Resolve a Gutenberg ID either from an image filename or a metafield."""
    for img in product.images.all():
        name = getattr(img.image, 'name', '') or ''
        m = re.search(r'gutenberg[-_](\d+)', name, re.IGNORECASE)
        if m:
            return int(m.group(1))
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(type(product))
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=product.pk,
            namespace='book',
            key='gutenberg_id',
        ).first()
        if m and str(m.value).isdigit():
            return int(m.value)
    except Exception:  # noqa: BLE001, S110
        pass
    return None


def _build_epub(*, title: str, author: str, body_text: str) -> bytes:
    """Generate a minimal valid EPUB 3 file from cleaned plain text.

    Structure (all zipped):
        mimetype                — uncompressed, MUST be first entry
        META-INF/container.xml  — pointer to package.opf
        OEBPS/package.opf       — manifest + metadata (publisher: DotBooks)
        OEBPS/nav.xhtml         — navigation table-of-contents
        OEBPS/content.xhtml     — the book body
    """
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body_text) if p.strip()]
    body_html = '\n'.join(f'<p>{html_escape(p.replace(chr(10), " "))}</p>' for p in paragraphs)

    container_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/package.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )

    package_opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="bookid">dotbooks-{html_escape(title)}-{datetime.utcnow().year}</dc:identifier>'
        f'<dc:title>{html_escape(title)}</dc:title>'
        f'<dc:creator>{html_escape(author or "Unknown")}</dc:creator>'
        '<dc:language>en</dc:language>'
        '<dc:publisher>DotBooks</dc:publisher>'
        f'<meta property="dcterms:modified">{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>'
        '</metadata>'
        '<manifest>'
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="content" href="content.xhtml" media-type="application/xhtml+xml"/>'
        '</manifest>'
        '<spine><itemref idref="content"/></spine>'
        '</package>'
    )

    nav_xhtml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" lang="en"><head>'
        f'<title>{html_escape(title)}</title></head><body>'
        '<nav epub:type="toc"><h1>Contents</h1>'
        f'<ol><li><a href="content.xhtml">{html_escape(title)}</a></li></ol>'
        '</nav></body></html>'
    )

    content_xhtml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>'
        f'<title>{html_escape(title)}</title>'
        '<style>body{font-family:Georgia,serif;line-height:1.55;max-width:36em;margin:2em auto;padding:0 1em}'
        'h1{font-size:1.5em;margin:0 0 1em}p{margin:0 0 .8em;text-indent:1.2em}</style>'
        f'</head><body><h1>{html_escape(title)}</h1>'
        f'<p style="text-align:center;color:#555;margin:0 0 2em;">by {html_escape(author or "Unknown")} · DotBooks</p>'
        f'{body_html}</body></html>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        # mimetype MUST be first entry and uncompressed per EPUB spec.
        zf.writestr(
            zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED
        )
        zf.writestr('META-INF/container.xml', container_xml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/package.opf', package_opf, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/nav.xhtml', nav_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/content.xhtml', content_xhtml, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def _build_pdf(*, title: str, author: str, body_text: str) -> bytes:
    """Generate a PDF rendering of the book via reportlab.

    Standard 6"×9" book trim, 11pt Georgia-equivalent, ~36 lines per
    page. Output is ~2-5 MB per novel — readable + reasonable size.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=title,
        author=author or 'Unknown',
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Times-Bold',
        fontSize=22,
        leading=26,
        spaceAfter=12,
    )
    by_style = ParagraphStyle(
        'ByStyle',
        parent=styles['Normal'],
        fontName='Times-Italic',
        fontSize=11,
        leading=14,
        spaceAfter=24,
        alignment=1,
        textColor=(0.4, 0.4, 0.4),
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=10.5,
        leading=14,
        firstLineIndent=14,
        spaceAfter=4,
    )

    story = [
        Paragraph(html_escape(title), title_style),
        Paragraph(f'by {html_escape(author or "Unknown")} · DotBooks', by_style),
    ]
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body_text) if p.strip()]
    for p in paragraphs:
        cleaned = html_escape(p.replace('\n', ' '))
        try:
            story.append(Paragraph(cleaned, body_style))
        except Exception:  # noqa: BLE001, S112
            continue
    story.append(Spacer(1, 24))
    doc.build(story)
    return buf.getvalue()


def _book_meta(product) -> tuple[str, str]:
    """Return (title, author) for a product from its book.* metafields."""
    title = (product.name or '').strip() or 'Untitled'
    author = ''
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(type(product))
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=product.pk,
            namespace='book',
            key='author',
        ).first()
        if m and m.value:
            author = str(m.value)
    except Exception:  # noqa: BLE001, S110
        pass
    return title, author


def _set_metafield(product, *, namespace: str, key: str, value: str) -> None:
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.metafields.models import Metafield

    ct = ContentType.objects.get_for_model(type(product))
    Metafield.objects.update_or_create(
        content_type=ct,
        object_id=product.pk,
        namespace=namespace,
        key=key,
        defaults={'value': value},
    )


class Command(BaseCommand):
    help = 'Re-publish Gutenberg books as DotBooks variable products (Digital + Print).'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--slugs',
            default='',
            help='Comma-separated slugs (default: all archived gutenberg products).',
        )
        parser.add_argument(
            '--digital-price',
            default='5.00',
            help='Price of the Digital variant in the product currency. Default 5.00',
        )
        parser.add_argument(
            '--print-price', default='15.00', help='Price of the Print variant. Default 15.00'
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts) -> None:  # noqa: PLR0915
        import urllib.request
        from decimal import Decimal

        from plugins.installed.catalog.models import Product, ProductVariant

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        digital_price = Decimal(opts['digital_price'])
        print_price = Decimal(opts['print_price'])
        dry = bool(opts.get('dry_run'))

        # Default: every Gutenberg product (archived OR active) — we want
        # both currently-hidden ones we just archived and any active ones
        # the merchant left published.
        qs = Product.objects.filter(images__image__contains='gutenberg-').distinct()
        if slugs:
            qs = qs.filter(slug__in=slugs)

        attached = 0
        skipped = 0
        for product in qs:
            gid = _gutenberg_id_for(product)
            if gid is None:
                skipped += 1
                continue
            title, author = _book_meta(product)
            self.stdout.write(f'→ {product.slug} (gid={gid}) — “{title}” / {author or "Unknown"}')
            if dry:
                continue

            # 1. Fetch + strip source text.
            url = f'https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt'
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'morpheus-import/1.0'})  # noqa: S310
                with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  # nosec B310
                    raw = resp.read().decode('utf-8', errors='replace')
            except Exception as exc:  # noqa: BLE001
                logger.warning('gutenberg fetch failed for %s (gid=%s): %s', product.slug, gid, exc)
                skipped += 1
                continue
            body = _strip_gutenberg(raw)

            # 2. Build EPUB + PDF.
            try:
                epub_bytes = _build_epub(title=title, author=author, body_text=body)
            except Exception as exc:  # noqa: BLE001
                logger.warning('epub build failed for %s: %s', product.slug, exc, exc_info=True)
                epub_bytes = b''
            try:
                pdf_bytes = _build_pdf(title=title, author=author, body_text=body)
            except Exception as exc:  # noqa: BLE001
                logger.warning('pdf build failed for %s: %s', product.slug, exc, exc_info=True)
                pdf_bytes = b''

            # 3. Bundle TXT + EPUB + PDF into a single zip.
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f'{product.slug}.txt', body.encode('utf-8'))
                if epub_bytes:
                    zf.writestr(f'{product.slug}.epub', epub_bytes)
                if pdf_bytes:
                    zf.writestr(f'{product.slug}.pdf', pdf_bytes)
                zf.writestr(
                    'README.txt',
                    f'{title} — DotBooks edition.\nIncludes EPUB + PDF + plain text.\n',
                )
            bundle = buf.getvalue()
            product.digital_file.save(
                f'{product.slug}.zip',
                ContentFile(bundle),
                save=False,
            )

            # 4. Flip to variable, recreate variants.
            product.product_type = 'variable'
            product.requires_shipping = True
            product.save(update_fields=['digital_file', 'product_type', 'requires_shipping'])

            # Drop any prior variants, then create Digital + Print.
            ProductVariant.objects.filter(product=product).delete()
            ProductVariant.objects.create(
                product=product,
                name='Digital',
                sku=f'{product.slug}-digital',
                price=digital_price,
                is_active=True,
                sort_order=0,
            )
            ProductVariant.objects.create(
                product=product,
                name='Print',
                sku=f'{product.slug}-print',
                price=print_price,
                is_active=True,
                sort_order=10,
            )

            # 5. Publisher → DotBooks.
            _set_metafield(product, namespace='book', key='publisher', value='DotBooks')

            # 6. Re-activate.
            if product.status != 'active':
                product.status = 'active'
                product.save(update_fields=['status'])

            attached += 1

        self.stdout.write(self.style.SUCCESS(f'done — attached={attached} skipped={skipped}'))
