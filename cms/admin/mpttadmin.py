from cms import settings
from cms.admin.translationadmin import ApplyLanguageChangelist
from mptt.utils import tree_item_iterator
from os.path import join

class ApplyLanguageMpttChangelist(ApplyLanguageChangelist):
 
    call_super = True
       
    def apply_to_results(self, results, request):
        
        if self.call_super:
            results = super(ApplyLanguageMpttChangelist, self).apply_to_results(results, request)
        
        for index, result_structure in enumerate(tree_item_iterator(results)):
            setattr(results[index], 'structure', result_structure[1])
        
        return results
    
    def edit_links(self, obj):
        return """
        <a href="%i" class="title" title="edit this page">umm</a>	
		<a href="%i" class="changelink" title="edit this page">edit</a>
        """ % (obj.pk, obj.pk)
        
    edit_links.allow_tags = True
        
class ApplyMpttChangelist(ApplyLanguageMpttChangelist):
    
    call_super = False
        
def get_mptt_admin(admin_base, changelist_class=ApplyMpttChangelist):
    
    class RealMpttAdmin(admin_base):
        
        actions = None
        change_list_template = 'admin/mptt_change_list.html'
        
        def __init__(self, *args, **kwargs):
            super(RealMpttAdmin, self).__init__(*args, **kwargs)
            self.list_display = ('edit_links',)
        
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
    
    RealMpttAdmin.changelist_class = changelist_class
        
    return RealMpttAdmin
        
from cms.admin.change_list import ReplaceChangeListAdmin
from cms.admin.pluginadmin import PluginAdmin
from cms.admin.translationadmin import TranslationAdmin, TranslationPluginAdmin

MpttAdmin = get_mptt_admin(ReplaceChangeListAdmin)

MpttPluginAdmin = get_mptt_admin(PluginAdmin)

MpttTranslationAdmin = get_mptt_admin(TranslationPluginAdmin , changelist_class=ApplyLanguageMpttChangelist)

MpttTranslationPluginAdmin = get_mptt_admin(TranslationPluginAdmin, changelist_class=ApplyLanguageMpttChangelist)

if 'reversion' in settings.INSTALLED_APPS:
    
    from cms.admin.versionadmin import VersionAdmin    
    from cms.admin.pluginadmin import PluginVersionAdmin
    from cms.admin.translationadmin import TranslationVersionAdmin, TranslationPluginVersionAdmin

    MpttVersionAdmin = get_mptt_admin(VersionAdmin)
    
    MpttTranslationVersionAdmin = get_mptt_admin(TranslationVersionAdmin, changelist_class=ApplyLanguageMpttChangelist)
    
    MpttPluginVersionAdmin = get_mptt_admin(PluginVersionAdmin)
    
    MpttTranslationPluginVersionAdmin = get_mptt_admin(TranslationPluginVersionAdmin)