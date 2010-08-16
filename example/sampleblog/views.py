from django.views.generic.list_detail import object_detail
from sampleblog.models import BlogPost

def blogpost_detail(request, post_id):
    return object_detail(request, queryset=BlogPost.objects.all(),
                         object_id=post_id,
                         template_name="sampleblog/blogpost_detail.html",
                         template_object_name="blogpost")
