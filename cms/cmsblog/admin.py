from django.contrib import admin
from cms.admin.translationadmin import TranslationPluginVersionAdmin
from cms.cmsblog.models import BlogEntry, Title

class BlogEntryAdmin(TranslationPluginVersionAdmin):

    translation_model = Title
    translation_model_fk = 'entry'
    placeholders = ['main']

    list_display = ('languages', )

admin.site.register(BlogEntry, BlogEntryAdmin)