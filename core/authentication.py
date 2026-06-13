"""
Morpheus CMS — API Key Authentication & RBAC
Enforces scopes for external headless clients and Remote Plugins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions, permissions

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

from core.models import APIKey


class MorpheusAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Validates `Authorization: Bearer <key>` against the APIKey table.
    Returns (None, APIKey) — request.user stays anonymous, request.auth carries the key.
    """

    keyword = 'Bearer'

    def authenticate(self, request: Request) -> tuple[None, APIKey] | None:
        auth = authentication.get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth) == 1:
            raise exceptions.AuthenticationFailed(
                _('Invalid token header. No credentials provided.')
            )
        if len(auth) > 2:
            raise exceptions.AuthenticationFailed(
                _('Invalid token header. Token string should not contain spaces.')
            )
        try:
            token = auth[1].decode()
        except UnicodeError as e:
            raise exceptions.AuthenticationFailed(
                _('Invalid token header. Token string contains invalid characters.')
            ) from e
        return self.authenticate_credentials(token, request)

    def authenticate_credentials(
        self, key: str, request: Request | None = None
    ) -> tuple[None, APIKey]:
        from core.models import hash_api_key

        try:
            api_key = APIKey.objects.select_related('channel').get(
                key_hash=hash_api_key(key), is_active=True
            )
        except APIKey.DoesNotExist as e:
            raise exceptions.AuthenticationFailed(_('Invalid API key.')) from e
        if request is not None:
            request._morpheus_api_key = api_key  # type: ignore[attr-defined]
        return (None, api_key)


class HasScopePermission(permissions.BasePermission):
    """
    DRF permission that checks the authenticated APIKey carries a required scope.
    Falls back to `is_staff` when the caller is a session-authed admin.

    Usage:
        permission_classes = [HasScopePermission.for_scope('read:products')]
    """

    required_scope: str | None = None

    @classmethod
    def for_scope(cls, scope: str) -> type[HasScopePermission]:
        return type(
            f'HasScope_{scope.replace(":", "_")}',
            (cls,),
            {'required_scope': scope},
        )

    def has_permission(self, request: Request, view: APIView) -> bool:
        api_key = getattr(request, '_morpheus_api_key', None)
        if api_key is not None and self.required_scope is not None:
            return api_key.has_scope(self.required_scope)
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and getattr(user, 'is_staff', False))
