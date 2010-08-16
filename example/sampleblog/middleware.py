from example.sampleblog.models import BlogPost


class BlogMiddleware(object):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(request, 'toolbar_context') and \
                view_func.func_name == 'blogpost_detail':
            blogpost = BlogPost.objects.get(pk=view_kwargs['post_id'])
            #import ipdb;ipdb.set_trace()
            request.toolbar_context.update(
                {
                    'has_add_blogpost_permission':request.user.has_perm("sampleblog.add_blogpost"),
                    'has_delete_blogpost_permission':request.user.has_perm("sampleblog.delete_blogpost"),
                    'blogpost':blogpost,
                }
            )
        return None
        
