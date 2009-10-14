from django.contrib import admin
from cms.admin.mpttadmin import MpttPluginAdmin
from cms.cmsmptt.models import Category

class CategoryAdmin(MpttPluginAdmin):
    
    placeholders = ['main']
    
    mandatory_placeholders = ('name', 'language') 
    top_fields = []
    general_fields = ['name'] 
    add_general_fields = ['name', 'language']
    hidden_fields = []
    additional_hidden_fields = []
    
admin.site.register(Category, CategoryAdmin)

    
