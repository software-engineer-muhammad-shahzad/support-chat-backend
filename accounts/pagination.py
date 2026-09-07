from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class AdminUserPagination(PageNumberPagination):
    """Pagination for admin user/agent/customer listings (?page=&page_size=)."""

    page_size = 3
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        # total_pages/current_page/page_size let the frontend render real
        # page-number buttons and a "Showings X-Y of Z" range, instead of
        # just Previous/Next.
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
