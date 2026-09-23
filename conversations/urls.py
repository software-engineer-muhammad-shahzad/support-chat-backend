from django.urls import path

from .views import ConversationDetailView, ConversationListCreateView, ConversationSelfAssignView

urlpatterns = [
    path("", ConversationListCreateView.as_view(), name="conversation-list-create"),
    path("<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("<int:pk>/assign/", ConversationSelfAssignView.as_view(), name="conversation-self-assign"),
]
