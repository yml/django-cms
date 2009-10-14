from django.db import models

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
