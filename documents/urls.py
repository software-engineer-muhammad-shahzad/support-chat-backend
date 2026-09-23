from django.urls import path

from .views import (
    DocumentBulkDeleteView,
    DocumentDeleteAllView,
    DocumentDetailView,
    DocumentIngestView,
    DocumentListView,
    DocumentUploadView,
)

urlpatterns = [
    path("", DocumentListView.as_view(), name="document-list"),
    path("upload/", DocumentUploadView.as_view(), name="document-upload"),
    path("delete-all/", DocumentDeleteAllView.as_view(), name="document-delete-all"),
    path("bulk-delete/", DocumentBulkDeleteView.as_view(), name="document-bulk-delete"),
    path("<int:pk>/ingest/", DocumentIngestView.as_view(), name="document-ingest"),
    # GET (poll status) + DELETE (permanent delete) on the same resource.
    path("<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),
]
