from django.urls import path

from .views import MessageListCreateView

urlpatterns = [
    path("<int:conversation_id>/messages/", MessageListCreateView.as_view(), name="conversation-messages"),
]
