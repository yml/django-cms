from django.db import models
from django.contrib.contenttypes.models import ContentType
from cms.utils.i18n import get_fallback_languages

class TranslationDescriptor(object):

    def __init__(self, model, translationmodel_field, reverse_name):
        self.model = model
        self.translationmodel_field = translationmodel_field
        self.reverse_name = reverse_name
        self.translation_cache_name = self.model.__name__.lower() + '_translation_cache'
        self.languages_cache_name = self.model.__name__.lower() + '_language_cache'

    def __get__(self, instance=None, owner=None):
        if instance is None:
            raise AttributeError(
                "The '%s' attribute can only be accessed from %s instances."
                % (self.name, owner.__name__))
        self.instance = instance
 
    def __set__(self, instance, value):
        raise AttributeError(
            "The '%s' attribute can not be set" % self.name)
        
    def get_languages(self):
        """
        get the list of all existing languages for this page
        """
        try:
            return self.instance.__dict__[self.languages_cache_name]
        except KeyError:
            all_languages = self.model.objects.filter(**{self.translationmodel_field: self.instance}).values_list("language", flat=True).distinct()
            all_languages = list(all_languages)
            all_languages.sort()
            self.instance.__dict__[self.languages_cache_name] = all_languages
        return all_languages
    
    def get_translation_obj(self, language=None):

        """Helper function for accessing wanted / current title.
        If wanted title doesn't exists, EmptyTitle instance will be returned.
        """
        
        language = self._get_translation_cache(language)
        if language in self.translation_cache:
            return self.translation_cache[language]
        from cms.models.titlemodels import EmptyTitle
        return EmptyTitle()
    
    def get_translation_obj_attribute(self, attrname, language=None):
        """Helper function for getting attribute or None from wanted/current title.
        """
        try:
            return getattr(self.get_translation_obj(language), attrname)
        except AttributeError:
            return None

    def __getattr__(self, name):
        if name.find('_') and name.split('_', -1)[1] in [l[0] in settings.LANGUAGES]:
            lang = name.split('_', -1)[1]
            attr = name.split('_', -1)[0] 
            return self.get_translation_obj_attribute(self, attr, lang)
 
    def _get_translation_cache(self, language=None):
        if not language:
            language = get_language()
        load = False
        if not self.translation_cache_name in self.instance.__dict__:
            load = True
            self.instance.__dict__[self.translation_cache_name] = {}
        elif not language in self.instance.__dict__[self.translation_cache_name]:
            fallback_langs = get_fallback_languages(language)
            for lang in fallback_langs:
                if lang in self.instance.__dict__[self.translation_cache_name]:
                    return lang
            load = True
        else:
            translation = self.model.objects.get_translation(self, language)
            if translation:
                self.instance.__dict__[self.translation_cache_name][translation.language] = translation
            language = translation.language
        return language

    def reload(self):
        del self.instance.__dict__[self.translation_cache_name]

    def load_revision(self, revision):
       if revision:
            content_type = ContentType.objects.get_for_model(self.model)
            revs = [related_version.object_version 
                for related_version in revision.version_set.filter(content_type=content_type)]
            for rev in revs:
                obj = rev.object
                self.instance.__dict__[self.translation_cache_name][obj.language] = obj

    def copy_to(self, object):
        for obj in getattr(self.instance, self.reverse_name).all():
            obj.pk = None
            setattr(obj, self.translationmodel_field, object)
            obj.save()
     
class TranslationsManager(models.Manager): # um, just use the regular manager and override if publisher is needed?

    def __init__(self, translationmodel_field):
        self.translationmodel_field = translationmodel_field
        super(TranslationsManager, self).__init__()

    def get_translation(self, for_object, language, language_fallback=False):
        """
        Gets the latest content for a particular page and language. Falls back
        to another language if wanted.
        """
        try:
            translation = self.get(language=language, **{translationmodel_field: for_object})
            return translation 
        except self.model.DoesNotExist:
            if language_fallback:
                try:
                    translations = self.filter(**{translationmodel_field: for_object})
                    fallbacks = get_fallback_languages(language)
                    for l in fallbacks:
                        for translation in translations:
                            if l == translation.language:
                                return translation
                    return None
                except self.model.DoesNotExist:
                    pass
            else:
                raise
        return None
    
    def get_slug(self, slug, site=None, use_site=False):
        """
        Returns the latest slug for the given slug and checks if it's available
        on the current site.
        """
        kw = {}
        if use_site:
            if not site:
                site = Site.objects.get_current()
            kw[self.translationmodel_field + '__site'] = site
        kw['slug'] = slug

        try:
            translations = self.filter(**kw).select_related()#'page')
        except self.model.DoesNotExist:
            return None 
        else:
            return translations 
        
    def set_or_create(self, for_object, language, **kwargs):
        """
        set or create a title for a particular page and language
        """
        try:
            obj = self.get(language=language, **{self.translationmodel_field: for_object})
            for key, value in kwargs:
                if not value is None:
                    setattr(obj, key, value)

        except self.model.DoesNotExist:
            kwargs[self.translationmodel_field] = for_object
            obj = self.model(language=language, **kwargs)

        self.set_custom(obj, **kwargs)

        obj.save()
        return obj

    def set_custom(self, obj, **kwargs):
        if 'overwrite_url' in kwargs:
            obj.has_url_overwrite = True
            obj.path = kwargs['overwrite_url']
        else:
            obj.has_url_overwrite = False

class TranslationForeignKey(models.ForeignKey):

    def __init__(self, to, **kwargs):
        self.translations_attribute = kwargs.pop('translation_attribute')
        self.translations_manager = kwargs.pop('translations_manager', TranslationsManager)
        super(TranslationForeignKey, self).__init__(to, **kwargs)

    def contribute_to_class(self, cls, name):
        super(TranslationForeignKey, self).contribute_to_class(cls, name)
        cls.add_to_class('objects', self.translations_manager(self.name))

    def contribute_to_related_class(self, cls, related):
        super(TranslationForeignKey, self).contribute_to_related_class(cls, related)
        setattr(cls, self.translations_attribute, 
            TranslationDescriptor(related.model, self.name, related.get_accessor_name())
        )
