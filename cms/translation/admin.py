from django.contrib import admin
from django.forms.models import model_to_dict, fields_for_model, save_instance
from cms.utils import get_language_from_request

def get_admin_base():
    return admin.ModelAdmin

admin_base = get_admin_base()

class TranslationAdmin(admin_base):

    translation_model = None
    translation_model_fk = ''
    translation_model_language = 'language'    

    def get_translation(self, request, obj):

        language = get_language_from_request(request)

        if obj:


            get_kwargs = {
                self.translation_model_fk: obj,
                self.translation_model_language: language
            }

            try:
                return self.translation_model.objects.get(**get_kwargs)
            except:
                return self.translation_model(**get_kwargs)

        return self.translation_model(**{self.translation_model_language: language})

    def get_form(self, request, obj=None, **kwargs):

        form = super(TranslationAdmin, self).get_form(request, obj, **kwargs)

        add_fields = fields_for_model(self.translation_model, exclude=[self.translation_model_fk])

        translation_obj = self.get_translation(request, obj)
        initial = model_to_dict(translation_obj)

        for name, field in add_fields.items():
            form.base_fields[name] = field
            if name in initial:
                form.base_fields[name].initial = initial[name]

        return form


    def save_model(self, request, obj, form, change):

        super(TranslationAdmin, self).save_model(request, obj, form, change)

        translation_obj = self.get_translation(request, obj)

        new_translation_obj = save_instance(form, translation_obj, commit=False)

        setattr(new_translation_obj, self.translation_model_fk, obj)

        new_translation_obj.save()

        

        
        
