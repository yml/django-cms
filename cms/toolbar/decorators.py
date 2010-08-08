from django.utils.decorators import decorator_from_middleware
from cms.toolbar.middleware import ToolbarMiddleware

add_toolbar = decorator_from_middleware(ToolbarMiddleware)