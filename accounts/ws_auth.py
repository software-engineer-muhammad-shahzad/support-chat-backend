"""WebSocket auth. The frontend uses JWT bearer tokens, not session cookies,
and a browser's native WebSocket API can't set an Authorization header — so
the token is passed as `?token=...` on the connection URL instead, and this
middleware resolves it into `scope["user"]` the same way DRF's
JWTAuthentication resolves the header on a normal request.

Without this, every websocket consumer sees an AnonymousUser and can't know
who's actually connecting — which is what `ChatConsumer` was doing before
presence needed a real identity to track.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_token(token: str):
    from accounts.models import User

    try:
        validated = AccessToken(token)
        return User.objects.get(pk=validated["user_id"])
    except (TokenError, User.DoesNotExist, KeyError, ValueError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]
        scope["user"] = await _user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
