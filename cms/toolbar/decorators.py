from functools import wraps

from django.forms.widgets import Media
from django.utils.decorators import decorator_from_middleware, available_attrs

from cms import settings as cms_settings
from cms.utils import get_template_from_request
from cms.utils.plugins import get_placeholders
from django.template.defaultfilters import title, safe
from django.utils import simplejson

def get_toolbar_context(request):
    from cms.plugin_pool import plugin_pool
    from cms.utils.admin import get_admin_menu_item_context
    """
    Renders the Toolbar.
    """
    auth = request.user.is_authenticated() and request.user.is_staff
    edit = request.session.get('cms_edit', False) and auth
    page = request.current_page
    move_dict = []
    if edit and page:
        template = get_template_from_request(request)
        placeholders = get_placeholders(template)
        for placeholder in placeholders:
            d = {}
            name = cms_settings.CMS_PLACEHOLDER_CONF.get("%s %s" % (page.get_template(), placeholder), {}).get("name", None)
            if not name:
                name = cms_settings.CMS_PLACEHOLDER_CONF.get(placeholder, {}).get("name", None)
            if not name:
                name = placeholder
            d['name'] = title(name)
            plugins = plugin_pool.get_all_plugins(placeholder, page)
            d['plugins'] = [] 
            for p in plugins:
                d['plugins'].append(p.value)
            d['type'] = placeholder
            move_dict.append(d)
        data = safe(simplejson.dumps(move_dict))
    else:
        data = {}
    if auth and page:
        context = get_admin_menu_item_context(request, page, filtered=False)
    else:
        context = {}
    context.update({
        'auth':auth,
        'page':page,
        'templates': cms_settings.CMS_TEMPLATES,
        'auth_error':not auth and 'cms_username' in request.POST,
        'placeholder_data':data,
        'edit':edit,
        'CMS_MEDIA_URL': cms_settings.CMS_MEDIA_URL,
    })
    return context


def add_toolbar_context(view_func):
    """
    Add the information required by django-cms toolbar to the context
    of the template.
    """
    def wrapped_view(request, *args, **kwargs):
        request.placeholder_media = Media()
        if request.method == "POST":
            if "edit" in request.GET and "cms_username" in request.POST:
                user = authenticate(username=request.POST.get('cms_username', ""), password=request.POST.get('cms_password', ""))
                if user:
                    login(request, user)
            if request.user.is_authenticated() and "logout_submit" in request.POST:
                logout(request)
                request.POST = {}
                request.method = 'GET'
        if request.user.is_authenticated() and request.user.is_staff:
            if "edit-off" in request.GET:
                request.session['cms_edit'] = False
            if "edit" in request.GET:
                request.session['cms_edit'] = True
        
        extra_context = get_toolbar_context(request)
        kwargs['extra_context'] = extra_context
        resp = view_func(request, *args, **kwargs)
        return resp
    return wraps(view_func, assigned=available_attrs(view_func))(wrapped_view)

