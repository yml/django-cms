from django.db import models
from cms import settings
import mptt

class Category(models.Model):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('lft',)

    def delete(self):
        super(Category, self).delete()
        
mptt.register(Category)

class Title(models.Model):
    title = models.CharField(max_length=50)
    slug = models.SlugField()
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    category = models.ForeignKey(Category)
