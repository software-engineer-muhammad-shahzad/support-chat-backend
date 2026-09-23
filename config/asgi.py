import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


django_asgi_app = get_asgi_application()

# Imported after get_asgi_application() — these modules touch Django models,
# which aren't ready until the line above has run.
from accounts.ws_auth import JWTAuthMiddleware  # noqa: E402
from chat_messages.routing import (  # noqa: E402
    websocket_urlpatterns as chat_websocket_urlpatterns,
)
from documents.routing import (  # noqa: E402
    websocket_urlpatterns as document_websocket_urlpatterns,
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(
            URLRouter(chat_websocket_urlpatterns + document_websocket_urlpatterns)
        ),
    }
)
