from django import forms
from cms.plugins.flash.models import Flash

class FlashForm(forms.ModelForm):
    
    class Meta:
        model = Flash
        exclude = ('content_type', 'object_id', 'position', 'placeholder', 'language', 'plugin_type')
