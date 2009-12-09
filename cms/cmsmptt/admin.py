from django.contrib import admin
from cms.admin.mpttadmin import MpttPluginAdmin
from cms.cmsmptt.models import Category, Title

class CategoryAdmin(MpttPluginAdmin):
    
    translation_model = Title
    translation_model_fk = 'category'
    placeholders = ['main']

    list_display = ('pk', 'languages', )
    
    mandatory_placeholders = ('title', 'slug', 'parent', 'language',  ) 
    top_fields = []
    general_fields = ['name', 'title', 'slug', 'parent',] 
    add_general_fields = ['name', 'title', 'slug', 'parent','language' ]
    hidden_fields = []
    additional_hidden_fields = []
    
admin.site.register(Category, CategoryAdmin)

    
