from os.path import join
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.sites.models import Site
from cms import settings
from django.contrib.contenttypes import generic

class ModelWithPlugins(models.Model):
   
    cms_plugins = generic.GenericRelation('cms.CMSPlugin')

    class Meta:
        abstract = True   
   
    def get_media_path(self, filename):
        """
        Returns path (relative to MEDIA_ROOT/MEDIA_URL) to directory for storing page-scope files.
        This allows multiple pages to contain files with identical names without namespace issues.
        Plugins such as Picture can use this method to initialise the 'upload_to' parameter for 
        File-based fields. For example:
            image = models.ImageField(_("image"), upload_to=CMSPlugin.get_media_path)
        where CMSPlugin.get_media_path calls self.page.get_media_path
        
        This location can be customised using the CMS_PAGE_MEDIA_PATH setting
        """
        return join(settings.CMS_PAGE_MEDIA_PATH, "%d/%s" % (self.id, self.__class__.__name__.lower()), filename)

    def delete(self):
        self.cms_plugins.all().delete()
        super(ModelWithPlugins, self).delete()
