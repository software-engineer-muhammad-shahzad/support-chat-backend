from django.urls import path

from accounts.views import UserProfileView

urlpatterns = [
    path("<int:pk>/", UserProfileView.as_view(), name="user-profile"),
]
