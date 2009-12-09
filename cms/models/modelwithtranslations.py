from django.db import models
from django.db.models.base import ModelBase

class TranslationModelBase(ModelBase):
    """
    Metaclass for all models with translations.
    """
    def __new__(cls, name, bases, attrs):
        new_class = super(TranslationModelBase, cls).__new__(cls, name, bases, attrs)
        if 'TranslationMeta' in attrs:
            _translation_model = getattr(attrs['TranslationMeta'], 'model', None)
            if not _translation_model:
                raise Exception, "Missing model attribute on TranslationMeta class"
            else:
                new_class._translation_model = _translation_model
        return new_class 

class TranslationModel(models.Model):
    __metaclass__ = TranslationModelBase
    
    class Meta:
        abstract = True