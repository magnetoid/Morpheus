"""
manage.py morph_create_theme <name>
    [--label "Display Name"]
    [--description "..."]
    [--theme-version 0.1.0]
    [--from dot_books]              # optional: copy templates from an existing theme
    [--target themes/library]

Generates a working Morpheus theme scaffold and prints next-step instructions.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError

_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')


class Command(BaseCommand):
    help = 'Scaffold a new Morpheus theme in themes/library/'

    def add_arguments(self, parser) -> None:
        parser.add_argument('name', help='snake_case theme name (must match directory).')
        parser.add_argument('--label', default='', help='Human-readable name.')
        parser.add_argument('--description', default='', help='One-line description.')
        parser.add_argument('--theme-version', default='0.1.0', dest='theme_version')
        parser.add_argument(
            '--from',
            default='',
            dest='copy_from',
            help='Copy templates + static from an existing theme name.',
        )
        parser.add_argument(
            '--target',
            default='themes/library',
            help='Directory to create the theme in.',
        )

    def handle(self, *args, **opts) -> None:
        name = opts['name']
        if not _NAME_RE.match(name):
            raise CommandError(
                f'Invalid theme name {name!r}. Must be snake_case '
                '(letters, digits, underscores; start with a letter).'
            )

        target = Path(opts['target']) / name
        if target.exists():
            raise CommandError(f'{target} already exists.')

        label = opts['label'] or name.replace('_', ' ').title()
        version = opts['theme_version']
        description = opts['description'] or f'{label} theme.'

        files = self._build_files(name=name, label=label, version=version, description=description)
        for rel_path, content in files.items():
            full = target / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)
            self.stdout.write(self.style.SUCCESS(f'+ {full}'))

        if opts['copy_from']:
            self._copy_existing(opts['copy_from'], target, name)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Theme "{name}" scaffolded.'))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write(
            f'  1. Set MORPHEUS_ACTIVE_THEME={name} in your env, or update settings.py.'
        )
        self.stdout.write(
            '  2. python manage.py check  (theme should appear in the activation log)'
        )
        self.stdout.write('  3. python manage.py runserver')
        self.stdout.write('')
        self.stdout.write('Read docs/THEME_DEVELOPMENT.md for the full developer guide.')

    # ── Templates ─────────────────────────────────────────────────────────────

    def _build_files(
        self, *, name: str, label: str, version: str, description: str
    ) -> dict[str, str]:
        cls_prefix = ''.join(part.capitalize() for part in name.split('_'))
        out: dict[str, str] = {
            'theme.py': self._theme_py(
                cls_prefix=cls_prefix,
                name=name,
                label=label,
                version=version,
                description=description,
            ),
            'README.md': self._readme(name=name, label=label, description=description),
            'templates/storefront/base.html': self._base_html(label=label),
            'templates/storefront/home.html': self._home_html(),
            'templates/storefront/product_list.html': self._list_html(),
            'templates/storefront/product_detail.html': self._detail_html(),
            'templates/storefront/cart.html': self._cart_html(),
            'templates/storefront/checkout.html': self._checkout_html(),
            f'static/{name}/style.css': self._stylesheet(name=name),
        }
        return out

    @staticmethod
    def _theme_py(*, cls_prefix, name, label, version, description) -> str:
        return dedent(f'''
            """{label} theme manifest."""
            from __future__ import annotations

            from themes.base import MorpheusTheme


            class {cls_prefix}Theme(MorpheusTheme):
                name = "{name}"
                label = "{label}"
                version = "{version}"
                description = {description!r}
                preview_image = "preview.png"
                supports_plugins = ["storefront", "catalog", "orders"]

                def get_design_tokens(self) -> dict:
                    return {{
                        "colors": {{
                            "background": "#ffffff",
                            "foreground": "#0a0a0a",
                            "accent":     "#4f46e5",
                        }},
                        "fonts":  {{"display": "Inter", "body": "Inter"}},
                        "radii":  {{"sm": "4px", "md": "8px", "lg": "16px"}},
                        "spacing": {{"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "48px"}},
                    }}

                def get_config_schema(self) -> dict:
                    return {{
                        "type": "object",
                        "properties": {{
                            "show_announcement_bar": {{"type": "boolean", "default": True}},
                            "announcement_text":     {{"type": "string", "default": "Free shipping over $40"}},
                        }},
                    }}
        ''').lstrip()

    @staticmethod
    def _readme(*, name, label, description) -> str:
        return dedent(f"""
            # {label}

            {description}

            ## Files

            - `theme.py` — manifest (`{name}` class)
            - `templates/storefront/` — page overrides for the storefront plugin
            - `static/{name}/` — assets (CSS, JS, images, preview.png)

            ## Activate

            ```bash
            export MORPHEUS_ACTIVE_THEME={name}
            python manage.py runserver
            ```

            ## Customize design tokens

            Edit `theme.py` → `get_design_tokens()`. The dashboard renders a live editor.

            See `docs/THEME_DEVELOPMENT.md` for the full guide.
        """).lstrip()

    @staticmethod
    def _base_html(*, label) -> str:
        return (
            dedent(f"""
            {{% load static %}}<!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>{{% block title %}}{label}{{% endblock %}}</title>
              <link rel="stylesheet" href="{{% static "<<name>>/style.css" %}}">
              {{% block head %}}{{% endblock %}}
            </head>
            <body>
              <header class="topbar">
                <a href="/" class="brand">{label}</a>
                <nav>
                  <a href="/products/">Shop</a>
                  <a href="/cart/">Cart</a>
                </nav>
              </header>
              <main>{{% block content %}}{{% endblock %}}</main>
              <footer>
                <p>© {{% now "Y" %}} {label}. Made on Morpheus.</p>
              </footer>
            </body>
            </html>
        """)
            .lstrip()
            .replace('<<name>>', label.lower().replace(' ', '_'))
        )

    @staticmethod
    def _home_html() -> str:
        return dedent("""
            {% extends "storefront/base.html" %}
            {% block content %}
            <section class="hero">
              <h1>Make this your own.</h1>
              <p class="lede">A starter home page. Edit <code>templates/storefront/home.html</code>.</p>
              <a class="btn" href="/products/">Shop now</a>
            </section>
            <section class="grid">
              {% for product in featured_products %}
              <a href="/products/{{ product.slug }}/" class="card">
                {% if product.primary_image %}<img src="{{ product.primary_image.image.url }}" alt="{{ product.name }}">{% endif %}
                <h3>{{ product.name }}</h3>
                <p class="price">{{ product.price }}</p>
              </a>
              {% endfor %}
            </section>
            {% endblock %}
        """).lstrip()

    @staticmethod
    def _list_html() -> str:
        return dedent("""
            {% extends "storefront/base.html" %}
            {% block content %}
            <h1>Products</h1>
            <section class="grid">
              {% for p in products %}
              <a href="/products/{{ p.slug }}/" class="card">
                {% if p.primaryImage %}<img src="{{ p.primaryImage.url }}" alt="">{% endif %}
                <h3>{{ p.name }}</h3>
                <p class="price">{{ p.price.amount }} {{ p.price.currency }}</p>
              </a>
              {% empty %}
              <p>No products yet.</p>
              {% endfor %}
            </section>
            {% endblock %}
        """).lstrip()

    @staticmethod
    def _detail_html() -> str:
        return dedent("""
            {% extends "storefront/base.html" %}
            {% block content %}
            <article class="pdp">
              <h1>{{ product.name }}</h1>
              <p class="price">{{ product.price.amount }} {{ product.price.currency }}</p>
              <p>{{ product.description|safe }}</p>
              <form method="post" action="/cart/add/{{ product.id }}/">
                {% csrf_token %}
                <button type="submit" class="btn">Add to cart</button>
              </form>
            </article>
            {% endblock %}
        """).lstrip()

    @staticmethod
    def _cart_html() -> str:
        return dedent("""
            {% extends "storefront/base.html" %}
            {% block content %}
            <h1>Cart</h1>
            {% if cart.items %}
              <ul>
                {% for item in cart.items %}
                <li>{{ item.quantity }} × {{ item.product.name }} — {{ item.totalPrice.amount }}</li>
                {% endfor %}
              </ul>
              <a class="btn" href="/checkout/">Checkout</a>
            {% else %}
              <p>Your cart is empty.</p>
            {% endif %}
            {% endblock %}
        """).lstrip()

    @staticmethod
    def _checkout_html() -> str:
        return dedent("""
            {% extends "storefront/base.html" %}
            {% block content %}
            <h1>Checkout</h1>
            <form method="post">{% csrf_token %}<button type="submit" class="btn">Place order</button></form>
            {% endblock %}
        """).lstrip()

    @staticmethod
    def _stylesheet(*, name) -> str:
        return dedent(f"""
            /* {name} — starter stylesheet. Edit freely. */
            :root {{
              --bg: #ffffff;
              --fg: #0a0a0a;
              --accent: #4f46e5;
              --radius: 8px;
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              font-family: 'Inter', system-ui, sans-serif;
              background: var(--bg);
              color: var(--fg);
            }}
            a {{ color: inherit; text-decoration: none; }}
            .topbar {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem 2rem; border-bottom: 1px solid #eee; }}
            .topbar nav a {{ margin-left: 1rem; }}
            .brand {{ font-weight: 700; }}
            main {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
            footer {{ text-align: center; padding: 3rem 0; color: #666; font-size: 0.85rem; }}
            .hero {{ text-align: center; padding: 4rem 0; }}
            .hero h1 {{ font-size: clamp(2.5rem, 6vw, 4.5rem); }}
            .lede {{ color: #555; max-width: 50ch; margin: 1rem auto; }}
            .btn {{ display: inline-block; background: var(--accent); color: #fff; padding: 0.75rem 1.5rem; border-radius: var(--radius); border: 0; cursor: pointer; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1.5rem; }}
            .card {{ display: block; background: #fafafa; padding: 1rem; border-radius: var(--radius); }}
            .card img {{ width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: var(--radius); }}
            .price {{ font-weight: 600; }}
        """).lstrip()

    # ── Optional: copy from an existing theme ─────────────────────────────────

    def _copy_existing(self, source_name: str, target: Path, new_name: str) -> None:
        from django.conf import settings

        src = Path(settings.MORPHEUS_THEMES_DIR) / source_name
        if not src.is_dir():
            self.stdout.write(
                self.style.WARNING(f'--from theme {source_name!r} not found; skipped copy.')
            )
            return
        # Copy templates and static (overwrite the starter scaffold).
        for sub in ('templates', 'static'):
            src_sub = src / sub
            if src_sub.is_dir():
                dst_sub = target / sub
                if dst_sub.exists():
                    shutil.rmtree(dst_sub)
                shutil.copytree(src_sub, dst_sub)
                self.stdout.write(self.style.SUCCESS(f'  copied {sub}/ from {source_name}'))
        self.stdout.write(
            self.style.WARNING(
                f'  remember to edit theme.py to set name="{new_name}" — copied class still uses '
                f'{source_name!r}.'
            )
        )
