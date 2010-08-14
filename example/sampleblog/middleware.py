def get_current_blogpost(request):
    return None

class BlogMiddleware(object):
    def process_request(self, request):
        if hasattr(request, 'toolbar_context'):
            request.toolbar_context.update(
                {
                    'has_add_blogpost_permission':request.user.has_perm("sampleblog.add_blogpost"),
                    'has_delete_blogpost_permission':request.user.has_perm("sampleblog.delete_blogpost"),
                    'blogpost':get_current_blogpost(request),
                }
            )
        else:
            return None
        
