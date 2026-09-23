from django.urls import re_path

from .consumers import DocumentStatusConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/documents/(?P<document_id>\d+)/$",
        DocumentStatusConsumer.as_asgi(),
    ),
]
