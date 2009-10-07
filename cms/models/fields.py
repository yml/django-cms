from django.db import models
from django.db.models.loading import get_model
from cms import settings

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
            all_languages = self.model.objects.filter(self.translationmodel_field=self.instance)
                .values_list("language", flat=True).distinct()
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

    def load_revision(self, version_id):
       if version_id:
            from reversion.models import Version
            version = get_object_or_404(Version, pk=version_id)
            revs = [related_version.object_version for related_version in version.revision.version_set.all()]
            for rev in revs:
                obj = rev.object
                if obj.__class__ == self.model:
                    self.instance.__dict__[self.translation_cache_name][obj.language] = obj

class TranslationForeignKey(models.ForeignKey):

    def __init__(self, to, **kwargs):
        self.translations_attribute = kwargs.pop('translations_attribute')
        super(TranslationForeignKey, __init__(to, **kwargs)

    def contribute_to_related_class(self, cls, related):
        super(TranslationForeignKey, self).contribute_to_related_class(cls, related)
        setattr(cls, self.translations_attribute, 
            TranslationDescriptor(self.__class__, self.field.name, related.get_accessor_name())
        )
