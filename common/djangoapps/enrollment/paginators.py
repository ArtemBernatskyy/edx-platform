from rest_framework.pagination import CursorPagination


class CourseEnrollmentsApiListPagination(CursorPagination):
    """
    Paginator for the Course enrollments list API.
    """
    page_size = 100
