from os.path import join
from datetime import datetime
from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _, get_language
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from publisher import Publisher
from publisher.errors import PublisherCantPublish
from cms.utils.urlutils import urljoin
from cms import settings
from cms.models import signals as cms_signals
from cms.utils.page import get_available_slug, check_title_slugs
from cms.exceptions import NoHomeFound
from cms.utils.helpers import reversion_register
from django.contrib.contenttypes import generic
from cms.utils.i18n import get_fallback_languages

class ModelWithPlugins(Publisher):
    created_by = models.CharField(_("created by"), max_length=70)
    changed_by = models.CharField(_("changed by"), max_length=70)
    creation_date = models.DateTimeField(editable=False, default=datetime.now)
    publication_date = models.DateTimeField(_("publication date"), null=True, blank=True, help_text=_('When the page should go live. Status must be "Published" for page to go live.'), db_index=True)
    publication_end_date = models.DateTimeField(_("publication end date"), null=True, blank=True, help_text=_('When to expire the page. Leave empty to never expire.'), db_index=True)
    published = models.BooleanField(_("is published"), blank=True)
    
    site = models.ForeignKey(Site, help_text=_('The site the page is accessible at.'), verbose_name=_("site"))
    
    cms_plugins = generic.GenericRelation('cms.CMSPlugin')

    class Meta:
        abstract = True   
 
    def __unicode__(self):
        return self.title
   
    def save(self, no_signals=False, change_state=True, commit=True, force_with_moderation=False, force_state=None):
        
        if self.publication_date is None and self.published:
            self.publication_date = datetime.now()
        
        # Drafts should not, unless they have been set to the future
        if self.published:
            if settings.CMS_SHOW_START_DATE:
                if self.publication_date and self.publication_date <= datetime.now():
                    self.publication_date = None
            else:
                self.publication_date = None
       
        from cms.utils.permissions import _thread_locals
        
        self.changed_by = _thread_locals.user.username
        if not self.pk:
            self.created_by = self.changed_by 
        
        if commit:
            super(ModelWithPlugins, self).save()

    def get_calculated_status(self):
        """
        get the calculated status of the page based on published_date,
        published_end_date, and status
        """
        if settings.CMS_SHOW_START_DATE:
            if self.publication_date > datetime.now():
                return False
        
        if settings.CMS_SHOW_END_DATE and self.publication_end_date:
            if self.publication_end_date < datetime.now():
                return True

        return self.published
    calculated_status = property(get_calculated_status)
   
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
   
    def is_public_published(self):
        """Returns true if public model is published.
        """
        if hasattr(self, 'public_published_cache'):
            # if it was cached in change list, return cached value
            return self.public_published_cache
        # othervise make db lookup
        if self.publisher_public_id:
            return self.publisher_public.published
        #return is_public_published(self)
        return False
