from __future__ import annotations

import strawberry


@strawberry.input
class AddressInput:
    first_name: str = ''
    last_name: str = ''
    line1: str = ''
    line2: str = ''
    city: str = ''
    state: str = ''
    postal_code: str = ''
    country: str = ''
    phone: str = ''
