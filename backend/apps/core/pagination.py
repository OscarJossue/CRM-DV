from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ReactAdminPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        response = Response({"count": self.page.paginator.count, "results": data})
        response["X-Total-Count"] = self.page.paginator.count
        response["Content-Range"] = f"items 0-{len(data)}/{self.page.paginator.count}"
        return response
