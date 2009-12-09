from django.shortcuts import get_object_or_404
from cms.models import Page, Title, CMSPlugin
from django.contrib.contenttypes.models import ContentType

from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, Http404, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import ugettext, ugettext_lazy as _
from django.template.context import RequestContext
from django.conf import settings
from django.template.defaultfilters import escapejs, force_escape
from django.views.decorators.http import require_POST

from cms.models import Page, Title, CMSPlugin, MASK_CHILDREN, MASK_DESCENDANTS,\
    MASK_PAGE
from cms.plugin_pool import plugin_pool
from cms.utils.admin import render_admin_menu_item
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from cms.utils import get_language_from_request

def save_all_plugins(request, content_object, excludes=None):
    
    if hasattr(content_object, 'has_change_permission') and not content_object.has_change_permission(request):
        raise Http404
    
    ctype = ContentType.objects.get_for_model(content_object.__class__)
    object_id = content_object.pk
    
    for plugin in CMSPlugin.objects.filter(content_type=ctype, object_id=object_id):
        if excludes:
            if plugin.pk in excludes:
                continue
        instance, admin = plugin.get_plugin_instance()
        if instance:
            instance.save()
        else:
            plugin.save()
        
def revert_plugins(request, version_id, obj):
    from reversion.models import Version
    version = get_object_or_404(Version, pk=version_id)
    revs = [related_version.object_version for related_version in version.revision.version_set.all()]
    cms_plugin_list = []
    plugin_list = []
    titles = []
    others = []
    content_object = obj
    ctype = ContentType.objects.get_for_model(content_object.__class__)
    object_id = content_object.pk    
    lang = get_language_from_request(request)
    for rev in revs:
        obj = rev.object
        if obj.__class__ == CMSPlugin:
            cms_plugin_list.append(obj)
        elif hasattr(obj, 'cmsplugin_ptr_id'):
            plugin_list.append(obj)
        elif obj.__class__ == Page:
            pass
            #page = obj #Page.objects.get(pk=obj.pk)
        elif obj.__class__ == Title:
            if not obj.language == lang: 
                titles.append(obj) 
        else:
            others.append(rev)
    if hasattr(content_object, 'has_change_permission') and not content_object.has_change_permission(request):
        raise Http404
    current_plugins = list(CMSPlugin.objects.filter(content_type=ctype, object_id=object_id))
    for plugin in cms_plugin_list:
        plugin.content_object = content_object
        plugin.save(no_signals=True)
    for plugin in cms_plugin_list:
        plugin.save()
        for p in plugin_list:
            if int(p.cmsplugin_ptr_id) == int(plugin.pk):
                plugin.set_base_attr(p)
                p.save()
        for old in current_plugins:
            if old.pk == plugin.pk:
                current_plugins.remove(old)
    for title in titles:
        title.page = content_object 
        try:
            title.save()
        except:
            title.pk = Title.objects.get(page=obj, language=title.language).pk
            title.save()
    for other in others:
        other.object.save()
    for plugin in current_plugins:
        plugin.delete()

