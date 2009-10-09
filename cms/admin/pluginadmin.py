from cms import settings
from cms.admin.change_list import CMSChangeList, get_changelist_admin
from cms.admin.dialog.views import get_copy_dialog
from cms.admin.forms import PageAddForm
from cms.admin.permissionadmin import PAGE_ADMIN_INLINES, \
    PagePermissionInlineAdmin
from cms.admin.utils import get_placeholders
from cms.admin.views import change_status, change_innavigation, add_plugin, \
    edit_plugin, remove_plugin, move_plugin, revert_plugins, change_moderation
from cms.admin.widgets import PluginEditor
from cms.exceptions import NoPermissionsException
from cms.models import Page, Title, CMSPlugin, PagePermission, \
    PageModeratorState, EmptyTitle, GlobalPagePermission
from cms.models.managers import PagePermissionsPermissionManager
from cms.plugin_pool import plugin_pool
from cms.utils import get_template_from_request, get_language_from_request
from cms.utils.admin import render_admin_menu_item
from cms.utils.moderator import update_moderation_message, \
    get_test_moderation_level, moderator_should_approve, approve_page, \
    will_require_moderation
from cms.utils.permissions import has_page_add_permission, \
    get_user_permission_level, has_global_change_permissions_permission
from copy import deepcopy
from django.contrib import admin
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.util import unquote
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django import forms
from django.forms.forms import get_declared_fields
from django.forms import Widget, Textarea, CharField, ModelForm
from django.forms.models import ModelFormMetaclass 
from django.http import HttpResponseRedirect, HttpResponse, Http404,\
    HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.template.defaultfilters import title
from django.utils.encoding import force_unicode
from django.utils.functional import curry
from django.utils.translation import ugettext as _
from os.path import join
from django.contrib.contenttypes.models import ContentType

def get_plugin_admin(admin_base):
    
    class RealPluginAdmin(admin_base):
    
        mandatory_placeholders = ('title', 'slug', 'language') 
        top_fields = []
        general_fields = ['title', 'slug'] 
        add_general_fields = ['title', 'slug', 'language']
        hidden_fields = []
        additional_hidden_fields = []
    
        # take care with changing fieldsets, get_fieldsets() method removes some
        # fields depending on permissions, but its very static!!
        # don't define fieldsets directly since some fields are not in the form yet
        def __init__(self, model, admin_site):
            super(RealPluginAdmin, self).__init__(model, admin_site)
    
            self.add_fieldsets = [
                (None, {
                    'fields': self.add_general_fields,
                    'classes': ('general',),
                }),
                (_('Hidden'), {
                    'fields': self.hidden_fields,
                    'classes': ('hidden',),
                }),
            ]
            
            self.update_fieldsets = [
                (_('Language'), {
                    'fields': ('language',),
                    'classes': ('language',),
                }),
                (None, {
                    'fields': self.general_fields,
                    'classes': ('general',),
                }),
                (_('Hidden'), {
                    'fields': self.hidden_fields + self.additional_hidden_fields,
                    'classes': ('hidden',),
                })
            ]
    
        class Media:
            css = {
                'all': [join(settings.CMS_MEDIA_URL, path) for path in (
                    'css/rte.css',
                    'css/pages.css',
                    'css/change_form.css',
                    'css/jquery.dialog.css',
                )]
            }
            js = [join(settings.CMS_MEDIA_URL, path) for path in (
                'js/lib/jquery.js',
                'js/lib/jquery.query.js',
                'js/lib/ui.core.js',
                'js/lib/ui.dialog.js',
                
            )]
    
    
        def __call__(self, request, url):
            """Delegate to the appropriate method, based on the URL.
            Old way of url handling, so we are compatible with older django
            versions.
            """
            if url is None:
                return self.list_pages(request)
            elif url.endswith('add-plugin'):
                return add_plugin(request)
            elif 'edit-plugin' in url:
                plugin_id = url.split("/")[-1]
                return edit_plugin(request, plugin_id, self.admin_site)
            elif 'remove-plugin' in url:
                return remove_plugin(request)
            elif 'move-plugin' in url:
                return move_plugin(request)
            if url.endswith('jsi18n') or url.endswith('jsi18n/'):
                return HttpResponseRedirect(reverse('admin:jsi18n'))
            if len(url.split("/?")):
                url = url.split("/?")[0]
            return super(RealPluginAdmin, self).__call__(request, url)
    
        def get_urls(self):
            """New way of urls handling.
            """
            from django.conf.urls.defaults import patterns, url
            info = "%sadmin_%s_%s" % (self.admin_site.name, self.model._meta.app_label, self.model._meta.module_name)
     
            # helper for url pattern generation
            pat = lambda regex, fn: url(regex, self.admin_site.admin_view(fn), name='%s_%s' % (info, fn.__name__))
            
            url_patterns = patterns('',
                
                pat(r'^.+/add-plugin/$', add_plugin),
                url(r'^.+/edit-plugin/([0-9]+)/$',
                    self.admin_site.admin_view(curry(edit_plugin, admin_site=self.admin_site)),
                    name='%s_edit_plugin' % info),
                pat(r'^(?:[0-9]+)/remove-plugin/$', remove_plugin),
                pat(r'^(?:[0-9]+)/move-plugin/$', move_plugin),
            )
            
            url_patterns.extend(super(RealPluginAdmin, self).get_urls())
            return url_patterns
        
        def redirect_jsi18n(self, request):
                return HttpResponseRedirect(reverse('admin:jsi18n'))
    
    
        def get_fieldsets(self, request, obj=None):
            """
            Add fieldsets of placeholders to the list of already existing
            fieldsets.
            """
            
            if obj: # edit
                given_fieldsets = deepcopy(self.update_fieldsets)
                for placeholder_name in self.get_placeholders(request, obj):
                    if placeholder_name not in self.mandatory_placeholders:
                        if placeholder_name in settings.CMS_PLACEHOLDER_CONF and "name" in settings.CMS_PLACEHOLDER_CONF[placeholder_name]:
                            name = settings.CMS_PLACEHOLDER_CONF[placeholder_name]["name"]
                        else:
                            name = placeholder_name
                        given_fieldsets += [(title(name), {'fields':[placeholder_name], 'classes':['plugin-holder']})]
            else: # new page
                given_fieldsets = deepcopy(self.add_fieldsets)
    
            return given_fieldsets
    
        def get_placeholders(self, request, obj):
            return self.placeholders
    
        def get_language(self, request, obj):
            return get_language_from_request(request, obj) # should default to language from language_code? 
    
        def get_plugin_list(self, request, obj, language, placeholder_name):    
            ctype = ContentType.objects.get_for_model(obj.__class__)
            plugin_list = CMSPlugin.objects.filter(content_type=ctype, object_id=obj.pk,
                language=language, placeholder=placeholder_name, parent=None
            ).order_by('position')
            return plugin_list
            
        def _get_plugin_list(self, request, obj, language, placeholder_name):    # a work in progress
            
            if "history" in request.path or 'recover' in request.path:
                
                version_id = request.path.split("/")[-2]
    
                from reversion.models import Version
                version = get_object_or_404(Version, pk=version_id)
                revs = [related_version.object_version for related_version in version.revision.version_set.all()]
                plugin_list = []
                plugins = []
                bases = {}
                for rev in revs:
                    obj = rev.object
                    if obj.__class__ == CMSPlugin:
                        if obj.language == language and obj.placeholder == placeholder_name and not obj.parent_id:
                            if obj.get_plugin_class() == CMSPlugin:
                                plugin_list.append(obj)
                            else:
                                bases[int(obj.pk)] = obj
                    if hasattr(obj, "cmsplugin_ptr_id"): 
                        plugins.append(obj)
                for plugin in plugins:
                    if int(plugin.cmsplugin_ptr_id) in bases:
                        bases[int(plugin.cmsplugin_ptr_id)].set_base_attr(plugin)
                        plugin_list.append(plugin)
                return plugin_list
                
            else:
                return super(Class, self).get_plugin_list(request, obj, language, placeholder_name)
                
        def get_form(self, request, obj=None, **kwargs):
            """
            Get form for the model and modify its fields depending on
            the request.
            """
            
            language = self.get_language(request, obj)
    
            form = super(RealPluginAdmin, self).get_form(request, obj, **kwargs)
    
            if obj:        
                for placeholder_name in self.get_placeholders(request, obj):
                    if placeholder_name not in self.mandatory_placeholders:
                        installed_plugins = plugin_pool.get_all_plugins(placeholder_name)
                        plugin_list = self.get_plugin_list(request, obj, language, placeholder_name)
                        widget = PluginEditor(attrs={'installed': installed_plugins, 'list': plugin_list})
                        form.base_fields[placeholder_name] = CharField(widget=widget, required=False)
            else:
                self.inlines = []    
                    
            if not 'language' in form.base_fields:
                form.base_fields['language'] = CharField(required=True)
            form.base_fields['language'].initial = language        
            
            return form
        
    return RealPluginAdmin

PluginAdmin = get_plugin_admin(get_changelist_admin(admin.ModelAdmin))

if 'reversion' in settings.INSTALLED_APPS:
    
    from reversion.admin import VersionAdmin
    
    VersionPluginAdmin = get_plugin_admin(get_changelist_admin(VersionAdmin)) 
