from django.urls import path

from accounts.views import AdminAgentDetailView, AdminAgentListCreateView

urlpatterns = [
    path("agents/", AdminAgentListCreateView.as_view(), name="admin-agent-list"),
    path("agents/<int:pk>/", AdminAgentDetailView.as_view(), name="admin-agent-detail"),
    # Activate/deactivate now go through the generic
    # /api/admin/users/<id>/(de)activate/ — works for any role.
]
