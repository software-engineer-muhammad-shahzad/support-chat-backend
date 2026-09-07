from django.urls import path

from accounts.views import (
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserDetailView,
    AdminUserListCreateView,
)

urlpatterns = [
    path("users/", AdminUserListCreateView.as_view(), name="admin-user-list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path(
        "users/<int:pk>/deactivate/",
        AdminUserDeactivateView.as_view(),
        name="admin-user-deactivate",
    ),
    path(
        "users/<int:pk>/activate/",
        AdminUserActivateView.as_view(),
        name="admin-user-activate",
    ),
]
