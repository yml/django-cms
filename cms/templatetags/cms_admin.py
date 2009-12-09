from django.conf import settings
from django import template
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _
from cms.models import MASK_PAGE, MASK_CHILDREN, MASK_DESCENDANTS
from cms.utils.admin import get_admin_menu_item_context

# all imports from original remove some later
from django.conf import settings
from django.contrib.admin.views.main import ALL_VAR, EMPTY_CHANGELIST_VALUE
from django.contrib.admin.views.main import ORDER_VAR, ORDER_TYPE_VAR, PAGE_VAR, SEARCH_VAR
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import dateformat
from django.utils.html import escape, conditional_escape
from django.utils.text import capfirst
from django.utils.safestring import mark_safe
from django.utils.translation import get_date_formats, get_partial_date_formats, ugettext as _
from django.utils.encoding import smart_unicode, smart_str, force_unicode
from django.template import Library
import datetime


register = template.Library()

def show_admin_menu(context, page):# , no_children=False):
    """Render the admin table of pages"""
    request = context['request']
    
    if context.has_key("cl"):
        filtered = context['cl'].is_filtered()
    elif context.has_key('filtered'):
        filtered = context['filtered']
    
    # following function is newly used for getting the context per item (line)
    # if something more will be required, then get_admin_menu_item_context
    # function have to be updated. 
    # This is done because item can be reloaded after some action over ajax.
    context.update(get_admin_menu_item_context(request, page, filtered))
    
    # this here is just context specific for menu rendering - items itself does
    # not use any of following variables
    #context.update({
    #    'no_children': no_children,
    #})
    return context
show_admin_menu = register.inclusion_tag('admin/cms/page/menu.html',
                                         takes_context=True)(show_admin_menu)


def clean_admin_list_filter(cl, spec):
    """
    used in admin to display only these users that have actually edited a page and not everybody
    """
    choices = sorted(list(spec.choices(cl)), key=lambda k: k['query_string'])
    query_string = None
    unique_choices = []
    for choice in choices:
        if choice['query_string'] != query_string:
            unique_choices.append(choice)
            query_string = choice['query_string']
    return {'title': spec.title(), 'choices' : unique_choices}
clean_admin_list_filter = register.inclusion_tag('admin/filter.html')(clean_admin_list_filter)



@register.filter
def boolean_icon(value):
    BOOLEAN_MAPPING = {True: 'yes', False: 'no', None: 'unknown'}
    return mark_safe(u'<img src="%simg/admin/icon-%s.gif" alt="%s" />' % (settings.ADMIN_MEDIA_PREFIX, BOOLEAN_MAPPING[value], value))

@register.filter
def moderator_choices(page, user):    
    """Returns simple moderator choices used for checkbox rendering, as a value
    is used mask value. Optimized, uses caching from change list.
    """
    moderation_value = page.get_moderation_value(user)
    
    moderate = (
        (MASK_PAGE, _('Moderate page'), _('Unbind page moderation'), 'page'), 
        (MASK_CHILDREN, _('Moderate children'), _('Unbind children moderation'), 'children'),
        (MASK_DESCENDANTS, _('Moderate descendants'), _('Unbind descendants moderation'), 'descendants'),
    )
    
    choices = []
    for mask_value, title_yes, title_no, kind in moderate:
        active = moderation_value and moderation_value & mask_value
        title = active and title_no or title_yes
        choices.append((mask_value, title, active, kind))
    
    return choices

@register.filter
def preview_link(page, language):
    if 'cms.middleware.multilingual.MultilingualURLMiddleware' in settings.MIDDLEWARE_CLASSES:
        return "/%s%s" % (language, page.get_absolute_url(language, fallback=True))
    return page.get_absolute_url(language)

def render_plugin(context, plugin):
    return {'content': plugin.render_plugin(context, admin=True)}

render_plugin = register.inclusion_tag('cms/content.html', takes_context=True)(render_plugin)

def result_headers(cl):
    lookup_opts = cl.lookup_opts

    for i, field_name in enumerate(cl.list_display):
        attr = None
        th_classes = []
        try:
            f = lookup_opts.get_field(field_name)
            admin_order_field = None
        except models.FieldDoesNotExist:
            # For non-field list_display values, check for the function
            # attribute "short_description". If that doesn't exist, fall back
            # to the method name. And __str__ and __unicode__ are special-cases.
            if field_name == '__unicode__':
                header = force_unicode(lookup_opts.verbose_name)
            elif field_name == '__str__':
                header = smart_str(lookup_opts.verbose_name)
            else:
                if callable(field_name):
                    attr = field_name # field_name can be a callable
                else:
                    try:
                        attr = getattr(cl.model_admin, field_name)
                    except AttributeError:
                        try:
                            attr = getattr(cl, field_name)
                        except AttributeError:
                            try:
                                attr = getattr(cl.model, field_name)
                            except AttributeError:
                                raise AttributeError, \
                                    "'%s' model or '%s' objects have no attribute '%s'" % \
                                        (lookup_opts.object_name, cl.model_admin.__class__, field_name)

                try:
                    header = attr.short_description
                except AttributeError:
                    if callable(field_name):
                        header = field_name.__name__
                    else:
                        header = field_name
                    header = header.replace('_', ' ')
                    
            real_field_name = (field_name == '__str__' or field_name == '__unicode__') and 'description' or (callable(field_name) and field_name.__name__) or field_name
            real_field_name = real_field_name.replace('_', '-')

            th_classes.append('%s' % real_field_name)
            
            # It is a non-field, but perhaps one that is sortable
            admin_order_field = getattr(attr, "admin_order_field", None)
            if not admin_order_field:
                yield {"text": header,
                        "class_attrib": mark_safe(th_classes and ' class="%s"' % ' '.join(th_classes) or '')}
                continue

            # So this _is_ a sortable non-field.  Go to the yield
            # after the else clause.
        else:
            header = f.verbose_name

        new_order_type = 'asc'
                    

        if field_name == cl.order_field or admin_order_field == cl.order_field:
            th_classes.append('sorted %sending' % cl.order_type.lower())
            new_order_type = {'asc': 'desc', 'desc': 'asc'}[cl.order_type.lower()]

        yield {"text": header,
               "sortable": True,
               "url": cl.get_query_string({ORDER_VAR: i, ORDER_TYPE_VAR: new_order_type}),
               "class_attrib": mark_safe(th_classes and ' class="%s"' % ' '.join(th_classes) or '')}
               
def items_with_class_for_result(cl, result, form, extra, use_div=False):
    first = True
    pk = cl.lookup_opts.pk.attname
    for field_name in cl.list_display:
        row_class = ''
        real_field_name = (field_name == '__str__' or field_name == '__unicode__') and 'description' or (callable(field_name) and field_name.__name__) or field_name
        try:
            f = cl.lookup_opts.get_field(field_name)
        except models.FieldDoesNotExist:
            # For non-field list_display values, the value is either a method,
            # property or returned via a callable.
            try:
                if callable(field_name):
                    attr = field_name
                    value = attr(result)
                elif hasattr(cl.model_admin, field_name) and \
                   not field_name == '__str__' and not field_name == '__unicode__':
                    attr = getattr(cl.model_admin, field_name)
                    takes_extra = getattr(attr, 'takes_extra', False)
                    value = takes_extra and attr(result, extra) or attr(result)
                else:
                    attr = getattr(result, field_name)
                    if callable(attr):
                        value = attr()
                    else:
                        value = attr
                allow_tags = getattr(attr, 'allow_tags', False)
                boolean = getattr(attr, 'boolean', False)
                if boolean:
                    allow_tags = True
                    result_repr = _boolean_icon(value)
                else:
                    result_repr = smart_unicode(value)
            except (AttributeError, ObjectDoesNotExist):
                result_repr = EMPTY_CHANGELIST_VALUE
            else:
                # Strip HTML tags in the resulting text, except if the
                # function has an "allow_tags" attribute set to True.
                if not allow_tags:
                    result_repr = escape(result_repr)
                else:
                    result_repr = mark_safe(result_repr)
        else:
            field_val = getattr(result, f.attname)

            if isinstance(f.rel, models.ManyToOneRel):
                if field_val is not None:
                    result_repr = escape(getattr(result, f.name))
                else:
                    result_repr = EMPTY_CHANGELIST_VALUE
            # Dates and times are special: They're formatted in a certain way.
            elif isinstance(f, models.DateField) or isinstance(f, models.TimeField):
                if field_val:
                    (date_format, datetime_format, time_format) = get_date_formats()
                    if isinstance(f, models.DateTimeField):
                        result_repr = capfirst(dateformat.format(field_val, datetime_format))
                    elif isinstance(f, models.TimeField):
                        result_repr = capfirst(dateformat.time_format(field_val, time_format))
                    else:
                        result_repr = capfirst(dateformat.format(field_val, date_format))
                else:
                    result_repr = EMPTY_CHANGELIST_VALUE
                row_class = ' class="nowrap"'
            # Booleans are special: We use images.
            elif isinstance(f, models.BooleanField) or isinstance(f, models.NullBooleanField):
                result_repr = _boolean_icon(field_val)
            # DecimalFields are special: Zero-pad the decimals.
            elif isinstance(f, models.DecimalField):
                if field_val is not None:
                    result_repr = ('%%.%sf' % f.decimal_places) % field_val
                else:
                    result_repr = EMPTY_CHANGELIST_VALUE
            # Fields with choices are special: Use the representation
            # of the choice.
            elif f.flatchoices:
                result_repr = dict(f.flatchoices).get(field_val, EMPTY_CHANGELIST_VALUE)
            else:
                result_repr = escape(field_val)
        if force_unicode(result_repr) == '':
            result_repr = mark_safe('&nbsp;')
        real_field_name = real_field_name.replace('_', '-')
        row_class = row_class and row_class[:-1] + '' + force_unicode(real_field_name) + '"' or ' class="%s"' % force_unicode(real_field_name)
        # If list_display_links not defined, add the link tag to the first field
        if (first and not cl.list_display_links) or field_name in cl.list_display_links:
            table_tag = use_div and 'div' or {True:'th', False:'td'}[first]
            first = False
            url = cl.url_for_result(result)
            # Convert the pk to something that can be used in Javascript.
            # Problem cases are long ints (23L) and non-ASCII strings.
            if cl.to_field:
                attr = str(cl.to_field)
            else:
                attr = pk
            value = result.serializable_value(attr)
            result_id = repr(force_unicode(value))[1:]
            yield mark_safe(u'<%s%s><a href="%s"%s>%s</a></%s>' % \
                (table_tag,  row_class, url, (cl.is_popup and ' onclick="opener.dismissRelatedLookupPopup(window, %s); return false;"' % result_id or ''), conditional_escape(result_repr), table_tag))
        else:
            # By default the fields come from ModelAdmin.list_editable, but if we pull
            # the fields out of the form instead of list_editable custom admins
            # can provide fields on a per request basis
            if form and field_name in form.fields:
                bf = form[field_name]
                result_repr = mark_safe(force_unicode(bf.errors) + force_unicode(bf))
            else:
                result_repr = conditional_escape(result_repr)
            yield mark_safe(u'<%s%s>%s</%s>' % (use_div and 'div' or 'td', row_class, result_repr, use_div and 'div' or 'td',))
    if form:
        yield mark_safe(force_unicode(form[cl.model._meta.pk.name]))
        
def results(cl, request):
    extras = [{} for r in cl.result_list]
    if hasattr(cl, 'model_admin'):
        if hasattr(cl.model_admin, 'refine_results'):
            refine_results = cl.model_admin.refine_results
            result_list, forms, extras = refine_results(cl.result_list, cl.formset and cl.formset.forms or None, extras, request)
        else:
            result_list, forms, extras = cl.result_list, cl.formset and cl.formset.forms or None, extras
    if forms:
        for res, form, extra in zip(result_list, forms, extras):
            yield (extra, list(items_with_class_for_result(cl, res, form, extra)))
    else:
        for res, extra in zip(cl.result_list, extras):
            yield (extra, list(items_with_class_for_result(cl, res, None, extra)))

def apply_result_list(cl, request):
    return {'cl': cl,
            'result_headers': list(result_headers(cl)),
            'results': list(results(cl, request))}
            
def mptt_results(cl, request):
    extras = [{} for r in cl.result_list]
    if hasattr(cl, 'model_admin'):
        if hasattr(cl.model_admin, 'refine_results'):
            refine_results = cl.model_admin.refine_results
            result_list, forms, extras = refine_results(cl.result_list, cl.formset and cl.formset.forms or None, extras, request)
        else:
            result_list, forms, extras = cl.result_list, cl.formset and cl.formset.forms or None, extras
    if forms:
        for res, form, extra in zip(result_list, forms, extras):
            yield (extra, list(items_with_class_for_result(cl, res, form, extra, use_div=True)))
    else:
        for res, extra in zip(cl.result_list, extras):
            yield (extra, list(items_with_class_for_result(cl, res, None, extra, use_div=True)))
            
def mptt_result_list(cl, request):
    return {'cl': cl,
            'result_headers': list(result_headers(cl)),
            'results': list(mptt_results(cl, request))}

apply_result_list = register.inclusion_tag("admin/apply_change_list_results.html")(apply_result_list)

mptt_result_list = register.inclusion_tag("admin/mptt_change_list_results.html")(mptt_result_list)

def page_submit_row(context):
    opts = context['opts']
    change = context['change']
    is_popup = context['is_popup']
    save_as = context['save_as']
    show_delete_translation = context.get('show_delete_translation')  
    language = context['language']
    return {
        'onclick_attrib': (opts.get_ordered_objects() and change
                            and 'onclick="submitOrderForm();"' or ''),
        'show_delete_link': (not is_popup and context['has_delete_permission']
                              and (change or context['show_delete'])),
        'show_save_as_new': not is_popup and change and save_as,
        'show_save_and_add_another': context['has_add_permission'] and 
                            not is_popup and (not save_as or context['add']),
        'show_save_and_continue': not is_popup and context['has_change_permission'],
        'is_popup': is_popup,
        'show_save': True,
        'language': language,
        'language_name': [name for langcode, name in settings.CMS_LANGUAGES if langcode == language][0],
        'show_delete_translation': show_delete_translation
    }
page_submit_row = register.inclusion_tag('admin/page_submit_line.html', takes_context=True)(page_submit_row)
