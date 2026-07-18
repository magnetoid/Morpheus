"""Book production-footprint estimates — pure functions, no DB, no settings.

Every constant is an *estimate* with a cited basis; callers must label output
"estimated" in the UI. All factors are overridable (wired from plugin settings
in services.py) so a merchant can plug in their own supplier data. Nothing here
raises — missing physical data yields a zeroed result with ``has_data=False``
and the caller decides whether to render.

Units: grams for mass, kilograms for CO2e, plain floats.
"""

from __future__ import annotations

# Baseline factors. Sources are ranges from pulp-and-paper LCA literature; the
# defaults sit at the conservative middle so we never overstate the footprint.
DEFAULTS: dict = {
    # A bound book's mass is mostly its paper text block; the rest is cover
    # board, ink and glue. 0.85 is a conservative text-block fraction.
    'paper_fraction': 0.85,
    # ~2.5 kg of wood per kg of virgin printing paper (industry range 2.0–3.5).
    'wood_factor': 2.5,
    # ~1.3 kg CO2e per kg of paper produced (virgin-fibre pulp + paper mill).
    'co2_per_kg_paper': 1.3,
    # Fixed per-book print/bind/transport-to-warehouse overhead (kg CO2e).
    'print_overhead_kg': 0.3,
    # A planted tree sequesters ~21 kg CO2 per year as it matures — the common
    # figure used to size voluntary offsets.
    'kg_co2_per_tree': 21.0,
    # Grams per sheet of ~80gsm A4/letter stock — for the human "sheets" tally.
    'grams_per_sheet': 5.0,
    # Fallback paper weight (g/m²) by print type, used only when the book has no
    # recorded weight and we estimate mass from page area. Hardcover text blocks
    # use heavier stock; mass-market uses the lightest.
    'gsm_by_type': {'hardcover': 100.0, 'paperback': 80.0, 'mass_market': 60.0},
}


def _factors(overrides: dict | None) -> dict:
    """Shallow-merge caller overrides onto DEFAULTS (gsm_by_type merged too)."""
    f = dict(DEFAULTS)
    if overrides:
        gsm = dict(DEFAULTS['gsm_by_type'])
        gsm.update(overrides.get('gsm_by_type') or {})
        f.update({k: v for k, v in overrides.items() if k != 'gsm_by_type'})
        f['gsm_by_type'] = gsm
    return f


def estimate_paper_mass_g(
    *,
    weight_g: float | None = None,
    product_weight_kg: float | None = None,
    page_count: int | None = None,
    width_mm: int | None = None,
    height_mm: int | None = None,
    print_type: str = 'paperback',
    factors: dict | None = None,
) -> float:
    """Best-effort paper (text-block) mass in grams. 0.0 when undeterminable.

    Preference order: recorded book weight → catalog product weight → estimate
    from page area × sheet count × stock gsm.
    """
    f = _factors(factors)
    frac = f['paper_fraction']
    if weight_g and weight_g > 0:
        return float(weight_g) * frac
    if product_weight_kg and product_weight_kg > 0:
        return float(product_weight_kg) * 1000.0 * frac
    if page_count and width_mm and height_mm and page_count > 0:
        # Two printed pages per physical sheet; area in m² × gsm = grams/sheet.
        sheets = page_count / 2.0
        area_m2 = (width_mm / 1000.0) * (height_mm / 1000.0)
        gsm = f['gsm_by_type'].get(print_type, f['gsm_by_type']['paperback'])
        return sheets * area_m2 * gsm
    return 0.0


def impact(
    *,
    weight_g: float | None = None,
    product_weight_kg: float | None = None,
    page_count: int | None = None,
    width_mm: int | None = None,
    height_mm: int | None = None,
    print_type: str = 'paperback',
    factors: dict | None = None,
) -> dict:
    """Full production-footprint estimate for one book.

    Returns keys: paper_g, wood_g, co2_kg, sheets, tree_fraction, has_data.
    ``has_data`` is False when no physical attribute let us estimate mass.
    """
    f = _factors(factors)
    paper_g = estimate_paper_mass_g(
        weight_g=weight_g,
        product_weight_kg=product_weight_kg,
        page_count=page_count,
        width_mm=width_mm,
        height_mm=height_mm,
        print_type=print_type,
        factors=f,
    )
    if paper_g <= 0:
        return {
            'paper_g': 0.0,
            'wood_g': 0.0,
            'co2_kg': 0.0,
            'sheets': 0.0,
            'tree_fraction': 0.0,
            'has_data': False,
        }
    wood_g = paper_g * f['wood_factor']
    co2_kg = (paper_g / 1000.0) * f['co2_per_kg_paper'] + f['print_overhead_kg']
    return {
        'paper_g': round(paper_g, 1),
        'wood_g': round(wood_g, 1),
        'co2_kg': round(co2_kg, 3),
        'sheets': round(paper_g / f['grams_per_sheet'], 0),
        'tree_fraction': round(co2_kg / f['kg_co2_per_tree'], 4),
        'has_data': True,
    }
