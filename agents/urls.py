from django.urls import path

from .views import AgentAskView

urlpatterns = [
    path("ask/", AgentAskView.as_view(), name="agent-ask"),
]
