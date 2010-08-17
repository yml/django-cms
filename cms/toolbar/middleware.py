"""
Edit Toolbar middleware
"""
import urlparse
from cms import settings as cms_settings
from cms.utils import get_template_from_request
from cms.utils.plugins import get_placeholders
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse, NoReverseMatch
from django.http import HttpResponseRedirect
from django.template.context import Context, RequestContext
from django.template.defaultfilters import title, safe
from django.template.loader import render_to_string
from django.utils import simplejson
from django.utils.encoding import smart_unicode
from django.forms.widgets import Media

from cms.plugin_pool import plugin_pool
from cms.utils.admin import get_admin_menu_item_context

class Toolbar(object):
    def __init__(self, request):
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
        
        self.is_visible = self._get_visibility(request)
    
    def _get_visibility(self, request):
        if request.is_ajax():
            return False
        try:
            if request.path_info.startswith(reverse("admin:index")):
                return False
        except NoReverseMatch:
            pass
        if request.path_info.startswith(urlparse.urlparse(settings.MEDIA_URL)[2]):
            return False
        if "edit" in request.GET:
            return True
        if not hasattr(request, "user"):
            return False
        if not request.user.is_authenticated() or not request.user.is_staff:
            return False
        return True
    
    def get_context(self, request):
        """
        Renders the Toolbar.
        """
        has_auth = request.user.is_authenticated() and request.user.is_staff
        edit = request.session.get('cms_edit', False) and has_auth
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
        if has_auth and page:
            context = get_admin_menu_item_context(request, page, filtered=False)
        else:
            context = {}
        context.update({
            'has_auth':has_auth,
            'page':page,
            'templates': cms_settings.CMS_TEMPLATES,
            'auth_error':not has_auth and 'cms_username' in self.request.POST,
            'placeholder_data':data,
            'edit':edit,
            'CMS_MEDIA_URL': cms_settings.CMS_MEDIA_URL,
        })
        return context

class ToolbarMiddleware(object):
    """
    Middleware to set up CMS Toolbar.
    """
    def process_request(self, request):

        toolbar = Toolbar(request)
        if toolbar.is_visible:
            request.placeholder_media = Media()
            request.toolbar_context = toolbar.get_context(request)
                
    



