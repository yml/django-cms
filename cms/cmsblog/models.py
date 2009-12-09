from django.db import models
from cms.models.modelwithplugins import ModelWithPlugins
from cms.models.modelwithtranslations import TranslationModel

from cms import settings

class Title(models.Model): 
    entry = models.ForeignKey("BlogEntry")
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    title = models.CharField(max_length=255)
    slug = models.SlugField()
    
    def __unicode__(self):
        return u'%s - %s' % (self.language.upper(), self.title)
        
class BlogEntry(TranslationModel, ModelWithPlugins):
    published = models.BooleanField()

    class TranslationMeta:
        model = Title

    def __unicode__(self):
        if not getattr(self, 'title', None):
            try:
                self.title = self.title_set.get(language=settings.LANGUAGES[0][0])
            except:
                return '(None)'
        return self.title.title


        
if 'reversion' in settings.INSTALLED_APPS:
    from cms.utils.helpers import reversion_register
    reversion_register(Title)
    reversion_register(BlogEntry, follow=["title_set", "cms_plugins"])
