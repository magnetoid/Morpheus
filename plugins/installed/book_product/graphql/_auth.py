"""Scope/staff auth for book_product mutations: the one shared check.

It used to be a copy of catalog's old check — staff-only, a direct read of the
token stash, and a fail-OPEN `except` when the scopes helper was missing — so a
core API key holding `catalog.write` was refused here. See
`api.graphql_permissions.mutation_scope_error`.
"""

from __future__ import annotations

from api.graphql_permissions import mutation_scope_error as check_scope

__all__ = ['check_scope']
