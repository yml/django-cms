from cms import settings
from django.conf import settings as django_settings
from mptt.utils import tree_item_iterator
from os.path import join
from django.utils.encoding import force_unicode

from cms.admin.pluginadmin import PluginAdmin

class MpttPluginAdmin(PluginAdmin):
    
    actions = None
    change_list_template = 'admin/mptt_change_list.html'
    list_display = ('edit_links', 'col_actions')
        
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
        
    def refine_results(self, results, forms, extras, request):
        
        if hasattr(super(MpttPluginAdmin, self), 'refine_results'):
            results, forms, extras = super(MpttPluginAdmin, self).refine_results(results, forms, extras, request)

        # add object permissions to extra in the superclasses refine_results

        for index, result_structure in enumerate(tree_item_iterator(results)):
            extras[index]['structure'] = result_structure[1] # add info on leaf nodes too?
            extras[index]['li_metadata'] = self.get_li_metadata(result_structure[0], extras[index])
            extras[index]['li_classes'] = self.get_li_classes(result_structure[0], extras[index])
        
        return (results, forms, extras)

    def get_li_metadata(self, obj, extra):
         return {}

    def get_li_classes(self, obj, extra): # grab info on permissions from extra 
        return []
    
    def edit_links(self, obj, extra):
        return u"""
        <a href="%i" class="title" title="edit this page">%s</a>	
        <a href="%i" class="changelink" title="edit this page">edit</a>
        """ % (obj.pk, force_unicode(obj), obj.pk)
        
    edit_links.allow_tags = True
    edit_links.takes_extra = True
    
    def col_actions(self, obj, extra):
        return u"""
        <span id="move-target-%i" class="move-target-container">
            <a href="#" class="move-target left" title="insert above">
                <img alt="" src="%s">
            </a>
            <span class="line first"> |
            </span>
            <a href="#" class="move-target right" title="insert below"><img alt="" src="%s"></a>
            <span class="line second"> |</span>
                <a href="#" class="move-target last-child" title="insert inside"></a>
        </span>
        """ % (obj.pk, join(django_settings.ADMIN_MEDIA_PREFIX, 'img/admin/arrow-up.gif'), join(django_settings.ADMIN_MEDIA_PREFIX, 'img/admin/arrow-down.gif'))
        
    col_actions.allow_tags = True      
    col_actions.takes_extra = True
