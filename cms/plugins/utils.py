import operator
from django.forms.widgets import Media
from django.contrib.contenttypes.models import ContentType
from cms.utils import get_language_from_request
from cms.utils.moderator import get_cmsplugin_queryset

def get_plugins(request, obj, lang=None):
    if not obj:
        return []
    lang = lang or get_language_from_request(request)
    contenttype = ContentType.objects.get_for_model(obj.__class__)
    if not hasattr(obj, '_%s_plugins_cache' % lang):
        setattr(obj, '_%s_plugins_cache' % lang,  get_cmsplugin_queryset(request).filter(
            content_type=contenttype, object_id=obj.pk, language=lang, parent__isnull=True
        ).order_by('placeholder', 'position').select_related() )
    return getattr(obj, '_%s_plugins_cache' % lang)

def get_plugin_media(request, plugin):
    instance, plugin = plugin.get_plugin_instance()
    return plugin.get_plugin_media(request, instance)

def get_plugins_media(request, obj):
    lang = get_language_from_request(request)
    if not hasattr(obj, '_%s_plugins_media_cache' % lang):
        plugins = get_plugins(request, obj, lang=lang)
        media_classes = [get_plugin_media(request, plugin) for plugin in plugins]
        if media_classes:
            setattr(obj, '_%s_plugins_media_cache' % lang, reduce(operator.add, media_classes))
        else:
             setattr(obj, '_%s_plugins_media_cache' % lang,  Media())
    return getattr(obj, '_%s_plugins_media_cache' % lang)