from django.urls import re_path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(
        "ws/chat/(?P<conversation_id>\d+)/$",
        ChatConsumer.as_asgi(),
    ),
]
