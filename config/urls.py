"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from conversations.views import ConversationAdminAssignView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls.auth")),
    path("api/admin/", include("accounts.urls.admin")),
    path("api/admin/", include("accounts.urls.agents")),
    path(
        "api/admin/conversations/<int:pk>/assign/",
        ConversationAdminAssignView.as_view(),
        name="admin-conversation-assign",
    ),
    path("api/users/", include("accounts.urls.users")),
    path("api/conversations/", include("conversations.urls")),
    path("api/conversations/", include("chat_messages.urls")),
    path("api/documents/", include("documents.urls")),
    # The AI assistant (agents/services/agent.py) — distinct from
    # api/admin/agents/ above, which manages human support staff.
    path("api/agents/", include("agents.urls")),
]
