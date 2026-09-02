from django.urls import path

from accounts.views import AdminUserDetailView, AdminUserListCreateView

urlpatterns = [
    path("users/", AdminUserListCreateView.as_view(), name="admin-user-list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
]
