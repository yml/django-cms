from cms import settings
from cms.admin.dialog.views import get_copy_dialog
from cms.admin.forms import PageAddForm
from cms.admin.permissionadmin import PAGE_ADMIN_INLINES, \
    PagePermissionInlineAdmin
from cms.admin.utils import get_placeholders
from cms.admin.views import revert_plugins, save_all_plugins
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
from django.template.defaultfilters import title, escapejs, force_escape, escape
from django.utils.encoding import force_unicode
from django.utils.functional import curry
from django.utils.translation import ugettext as _
from os.path import join
from django.contrib.contenttypes.models import ContentType

from cms.admin.translationadmin import TranslationAdmin

page_ctype = ContentType.objects.get_for_model(Page)

create_on_success = lambda x: x
    
if 'reversion' in settings.INSTALLED_APPS:
    import reversion
    create_on_success = reversion.revision.create_on_success

class PluginAdmin(TranslationAdmin):

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
        super(PluginAdmin, self).__init__(model, admin_site)

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
            return self.add_plugin(request)
        elif 'edit-plugin' in url:
            plugin_id = url.split("/")[-1]
            return self.edit_plugin(request, plugin_id, self.admin_site)
        elif 'remove-plugin' in url:
            return self.remove_plugin(request)
        elif 'move-plugin' in url:
            return self.move_plugin(request)
        if url.endswith('jsi18n') or url.endswith('jsi18n/'):
            return HttpResponseRedirect(reverse('admin:jsi18n'))
        if len(url.split("/?")):
            url = url.split("/?")[0]
        return super(PluginAdmin, self).__call__(request, url)

    def get_urls(self):
        """New way of urls handling.
        """
        from django.conf.urls.defaults import patterns, url
        info = "%sadmin_%s_%s" % (self.admin_site.name, self.model._meta.app_label, self.model._meta.module_name)
 
        # helper for url pattern generation
        pat = lambda regex, fn: url(regex, self.admin_site.admin_view(fn), name='%s_%s' % (info, fn.__name__))
        
        url_patterns = patterns('',
            pat(r'^.+/add-plugin/$', self.add_plugin),
            pat(r'^.+/edit-plugin/([0-9]+)/$', self.edit_plugin),
            pat(r'^(?:[0-9]+)/remove-plugin/$', self.remove_plugin),
            pat(r'^(?:[0-9]+)/move-plugin/$', self.move_plugin),
        )
        
        url_patterns.extend(super(PluginAdmin, self).get_urls())
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

    def get_plugin_list(self, request, obj, language, placeholder_name):    # a work in progress
        
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
            ctype = ContentType.objects.get_for_model(obj.__class__)
            plugin_list = CMSPlugin.objects.filter(content_type=ctype, object_id=obj.pk,
                language=language, placeholder=placeholder_name, parent=None
            ).order_by('position')
            return plugin_list
            
    def get_form(self, request, obj=None, **kwargs):
        """
        Get form for the model and modify its fields depending on
        the request.
        """
        
        language = self.get_language(request, obj)

        form = super(PluginAdmin, self).get_form(request, obj, **kwargs)

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
            
    def render_revision_form(self, request, obj, version, context, revert=False, recover=False):

        response = super(PluginAdmin, self).render_revision_form(request, obj, version, context, revert, recover)
        if request.method == "POST" \
            and ('history' in request.path or 'recover' in request.path) \
            and response.status_code == 302:
                
            # revert plugins
            revert_plugins(request, version.pk, obj)
        return response

    def add_plugin(self, request):
        if 'history' in request.path or 'recover' in request.path:
            return HttpResponse(str("error"))
        if request.method == "POST":
            plugin_type = request.POST['plugin_type']
            app, model = request.POST.get('app'), request.POST.get('model')
            object_id = request.POST.get('object_id', None)
            parent = None
            ctype = ContentType.objects.get(app_label=app, model=model)
            if object_id:
                content_object = ctype.get_object_for_this_type(pk=object_id)
                placeholder = request.POST['placeholder'].lower()
                language = request.POST['language']
                position = CMSPlugin.objects.filter(content_type=ctype, object_id=object_id, language=language, placeholder=placeholder).count()
                """
                if ctype.model_class() == Page:
                    limits = settings.CMS_PLACEHOLDER_CONF.get("%s %s" % (content_object.template, placeholder), {}).get('limits', None)
                    if not limits:
                        limits = settings.CMS_PLACEHOLDER_CONF.get(placeholder, {}).get('limits', None)
                    if limits:
                        global_limit = limits.get("global")
                        type_limit = limits.get(plugin_type)
                        if global_limit and position >= global_limit:
                            return HttpResponseBadRequest("This placeholder already has the maximum number of plugins")
                        elif type_limit:
                            type_count = CMSPlugin.objects.filter(content_type=ctype, object_id=object_id, language=language, placeholder=placeholder, plugin_type=plugin_type).count()
                            if type_count >= type_limit:
                                return HttpResponseBadRequest("This placeholder already has the maximum number allowed %s plugins.'%s'" % plugin_type)
                """
            else:
                parent_id = request.POST['parent_id']
                parent = get_object_or_404(CMSPlugin, pk=parent_id)
                placeholder = parent.placeholder
                content_object = parent.content_object
                object_id = content_object.pk
                language = parent.language
                position = None
    
            if hasattr(content_object, 'has_change_permission') and not content_object.has_change_permission(request):
                return HttpResponseForbidden(_("You do not have permission to change this page"))
                
            # Sanity check to make sure we're not getting bogus values from JavaScript:
            if not language or not language in [ l[0] for l in settings.LANGUAGES ]:
                return HttpResponseBadRequest(_("Language must be set to a supported language!"))
            
            plugin = CMSPlugin(content_type=ctype, object_id=object_id, language=language, plugin_type=plugin_type, position=position, placeholder=placeholder) 
    
            if parent:
                plugin.parent = parent
            plugin.save()
            if 'reversion' in settings.INSTALLED_APPS:
                content_object.save()
                save_all_plugins(request, content_object)
                reversion.revision.user = request.user
                plugin_name = unicode(plugin_pool.get_plugin(plugin_type).name)
                reversion.revision.comment = _(u"%(plugin_name)s plugin added to %(placeholder)s") % {'plugin_name':plugin_name, 'placeholder':placeholder}
            return HttpResponse(str(plugin.pk))
        raise Http404

    add_plugin = create_on_success(add_plugin)

    def edit_plugin(self, request, plugin_id):
        plugin_id = int(plugin_id)
        if not 'history' in request.path and not 'recover' in request.path:
            cms_plugin = get_object_or_404(CMSPlugin, pk=plugin_id)
            instance, plugin_admin = cms_plugin.get_plugin_instance(self.admin_site)
            if hasattr(cms_plugin.content_object, 'has_change_permission') and not cms_plugin.content_object.has_change_permission(request):
                raise PermissionDenied 
        else:
            # history view with reversion
            from reversion.models import Version
            version_id = request.path.split("/edit-plugin/")[0].split("/")[-1]
            Version.objects.get(pk=version_id)
            version = get_object_or_404(Version, pk=version_id)
            revs = [related_version.object_version for related_version in version.revision.version_set.all()]
            # TODO: check permissions
            
            for rev in revs:
                obj = rev.object
                if obj.__class__ == CMSPlugin and obj.pk == plugin_id:
                    cms_plugin = obj
                    break
            inst, plugin_admin = cms_plugin.get_plugin_instance(self.admin_site)
            instance = None
            if cms_plugin.get_plugin_class().model == CMSPlugin:
                instance = cms_plugin
            else:
                for rev in revs:
                    obj = rev.object
                    if hasattr(obj, "cmsplugin_ptr_id") and int(obj.cmsplugin_ptr_id) == int(cms_plugin.pk):
                        instance = obj
                        break
            if not instance:
                raise Http404("This plugin is not saved in a revision")
        
        plugin_admin.cms_plugin_instance = cms_plugin
        plugin_admin.placeholder = cms_plugin.placeholder # TODO: what for reversion..? should it be inst ...?
        
        if request.method == "POST":
            # set the continue flag, otherwise will plugin_admin make redirect to list
            # view, which actually does'nt exists
            request.POST['_continue'] = True
        
        if 'reversion' in settings.INSTALLED_APPS and ('history' in request.path or 'recover' in request.path):
            # in case of looking to history just render the plugin content
            context = RequestContext(request)
            return render_to_response(plugin_admin.render_template, plugin_admin.render(context, instance, plugin_admin.placeholder))
        
        
        if not instance:
            # instance doesn't exist, call add view
            response = plugin_admin.add_view(request)
     
        else:
            # already saved before, call change view
            # we actually have the instance here, but since i won't override
            # change_view method, is better if it will be loaded again, so
            # just pass id to plugin_admin
            response = plugin_admin.change_view(request, str(plugin_id))
        
        if request.method == "POST" and plugin_admin.object_successfully_changed:
            # if reversion is installed, save version of the page plugins
            if 'reversion' in settings.INSTALLED_APPS:
                # perform this only if object was successfully changed
                cms_plugin.content_object.save()
                save_all_plugins(request, cms_plugin.content_object, [cms_plugin.pk])
                reversion.revision.user = request.user
                plugin_name = unicode(plugin_pool.get_plugin(cms_plugin.plugin_type).name)
                reversion.revision.comment = _(u"%(plugin_name)s plugin edited at position %(position)s in %(placeholder)s") % {'plugin_name':plugin_name, 'position':cms_plugin.position, 'placeholder': cms_plugin.placeholder}
                
            # read the saved object from plugin_admin - ugly but works
            saved_object = plugin_admin.saved_object
            
            context = {
                'CMS_MEDIA_URL': settings.CMS_MEDIA_URL, 
                'plugin': saved_object, 
                'is_popup': True, 
                'name': unicode(saved_object), 
                "type": saved_object.get_plugin_name(),
                'plugin_id': plugin_id,
                'icon': force_escape(escapejs(saved_object.get_instance_icon_src())),
                'alt': force_escape(escapejs(saved_object.get_instance_icon_alt())),
            }
            return render_to_response('admin/cms/page/plugin_forms_ok.html', context, RequestContext(request))
            
        return response
        
    edit_plugin = create_on_success(edit_plugin)

    def move_plugin(self, request):
        if request.method == "POST" and not 'history' in request.path:
            pos = 0
            content_object = None
            if 'ids' in request.POST:
                for id in request.POST['ids'].split("_"):
                    plugin = CMSPlugin.objects.get(pk=id)
                    if not content_object:
                        content_object = plugin.content_object
                    
                    if hasattr(content_object, 'has_change_permission') and not content_object.has_change_permission(request):
                        raise Http404
                
                    if plugin.position != pos:
                        plugin.position = pos
                        plugin.save()
                    pos += 1
            elif 'plugin_id' in request.POST:
                plugin = CMSPlugin.objects.get(pk=int(request.POST['plugin_id']))
                placeholder = request.POST['placeholder']
                klass = plugin.content_object.__class__
                ctype = ContentType.objects.get_for_model(klass)
                content_object = plugin.content_object
                """
                if klass == Page:
                    placeholders = get_placeholders(request, content_object.template)
                    if not placeholder in placeholders:
                        return HttpResponse(str("error"))
                """
                plugin.placeholder = placeholder
                position = 0
                try:
                    position = CMSPlugin.objects.filter(content_type=ctype, object_id=plugin.content_object.pk, placeholder=placeholder).order_by('position')[0].position + 1
                except IndexError:
                    pass
                plugin.position = position
                plugin.save()
            else:
                HttpResponse(str("error"))
            if content_object and 'reversion' in settings.INSTALLED_APPS:
                content_object.save()
                save_all_plugins(request, content_object)
                reversion.revision.user = request.user
                reversion.revision.comment = unicode(_(u"Plugins where moved")) 
            return HttpResponse(str("ok"))
        else:
            return HttpResponse(str("error"))
            
    move_plugin = create_on_success(move_plugin)
    
    def remove_plugin(self, request):
        if request.method == "POST" and not 'history' in request.path:
            plugin_id = request.POST['plugin_id']
            plugin = get_object_or_404(CMSPlugin, pk=plugin_id)
            content_object = plugin.content_object
            
            if hasattr(content_object, 'has_change_permission') and not content_object.has_change_permission(request):
                raise Http404
            
            if settings.CMS_MODERATOR and hasattr(content_object, 'is_under_moderation') and content_object.is_under_moderation():
                plugin.delete()
            else:
                plugin.delete_with_public()
                
            plugin_name = unicode(plugin_pool.get_plugin(plugin.plugin_type).name)
            comment = _(u"%(plugin_name)s plugin at position %(position)s in %(placeholder)s was deleted.") % {'plugin_name':plugin_name, 'position':plugin.position, 'placeholder':plugin.placeholder}
            if 'reversion' in settings.INSTALLED_APPS:
                save_all_plugins(request, content_object)
                content_object.save()
                reversion.revision.user = request.user
                reversion.revision.comment = comment
            return HttpResponse("%s,%s" % (plugin_id, comment))
        raise Http404
    
    remove_plugin = create_on_success(remove_plugin)

