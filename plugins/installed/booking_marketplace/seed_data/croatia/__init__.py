"""Croatia Experience's catalogue: real places, experiences, hotels and events.

Read by `manage.py seed_croatia` (docs/plans/croatia-catalogue-2026-11.md). Each module
holds one batch, and this one joins them. `tests/test_croatia_catalogue.py` checks every
entry against the models and the owner's rules: no host, rating, "was" price or rooms.
"""

from __future__ import annotations

from . import (
    events,
    experiences_dalmatia_north,
    experiences_dubrovnik,
    experiences_north,
    experiences_split,
    hotels,
    places_continental,
    places_dubrovnik_lika,
    places_istria,
    places_kvarner_zagreb,
    places_split,
    places_zadar_sibenik,
)

PLACES: list[dict] = [
    *places_istria.PLACES,
    *places_kvarner_zagreb.PLACES,
    *places_zadar_sibenik.PLACES,
    *places_split.PLACES,
    *places_dubrovnik_lika.PLACES,
    *places_continental.PLACES,
]
EXPERIENCES: list[dict] = [
    *experiences_north.EXPERIENCES,
    *experiences_dalmatia_north.EXPERIENCES,
    *experiences_split.EXPERIENCES,
    *experiences_dubrovnik.EXPERIENCES,
]
HOTELS: list[dict] = hotels.HOTELS
EVENTS: list[dict] = events.EVENTS
