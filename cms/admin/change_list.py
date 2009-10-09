from django.contrib import admin
from django.contrib.admin.views.main import ChangeList, ALL_VAR, IS_POPUP_VAR,\
    ORDER_TYPE_VAR, ORDER_VAR, SEARCH_VAR
from cms.models import Title, PagePermission, Page, PageModerator
from cms import settings
from cms.utils import get_language_from_request, find_children
from django.contrib.sites.models import Site
from cms.utils.permissions import get_user_sites_queryset
from cms.exceptions import NoHomeFound
from cms.models.moderatormodels import MASK_PAGE, MASK_CHILDREN,\
    MASK_DESCENDANTS, PageModeratorState

SITE_VAR = "site__exact"
COPY_VAR = "copy"

# imports from django/contrib/admin/options.py remove usused later
from django import forms, template
from django.forms.formsets import all_valid
from django.forms.models import modelform_factory, modelformset_factory, inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin import widgets
from django.contrib.admin import helpers
from django.contrib.admin.util import unquote, flatten_fieldsets, get_deleted_objects, model_ngettext, model_format_dict
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models.fields import BLANK_CHOICE_DASH
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.utils.datastructures import SortedDict
from django.utils.functional import update_wrapper
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.functional import curry
from django.utils.text import capfirst, get_text_list
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext, ugettext_lazy
from django.utils.encoding import force_unicode


class CMSChangeList(ChangeList):
    real_queryset = False
    
    def __init__(self, request, *args, **kwargs):
        super(CMSChangeList, self).__init__(request, *args, **kwargs)
        try:
            self.query_set = self.get_query_set(request)
        except:
            raise
        self.get_results(request)
        
        if SITE_VAR in self.params:
            self._current_site = Site.objects.get(pk=self.params[SITE_VAR])
        else:
            site_pk = request.session.get('cms_admin_site', None)
            if site_pk:
                self._current_site = Site.objects.get(pk=site_pk)
            else:
                self._current_site = Site.objects.get_current()
        
        request.session['cms_admin_site'] = self._current_site.pk
        self.set_sites(request)
        
    def get_query_set(self, request=None):
        if COPY_VAR in self.params:
            del self.params[COPY_VAR]
        
            
        qs = super(CMSChangeList, self).get_query_set().drafts()
        if request:
            permissions = Page.permissions.get_change_list_id_list(request.user)
            if permissions != Page.permissions.GRANT_ALL:
                qs = qs.filter(pk__in=permissions)
                self.root_query_set = self.root_query_set.filter(pk__in=permissions)
            self.real_queryset = True
            if not SITE_VAR in self.params:
                qs = qs.filter(site=request.session.get('cms_admin_site', None))
        qs = qs.order_by('tree_id', 'parent', 'lft')
        return qs
    
    def is_filtered(self):
        lookup_params = self.params.copy() # a dictionary of the query string
        for i in (ALL_VAR, ORDER_VAR, ORDER_TYPE_VAR, SEARCH_VAR, IS_POPUP_VAR, SITE_VAR):
            if i in lookup_params:
                del lookup_params[i]
        if not lookup_params.items() and not self.query:
            return False
        return True
    
    def get_results(self, request):
        if self.real_queryset:
            super(CMSChangeList, self).get_results(request)
            if not self.is_filtered():
                self.full_result_count = self.result_count = self.root_query_set.count()
            else:
                self.full_result_count = self.root_query_set.count()
    
    def set_items(self, request):
        lang = get_language_from_request(request)
        pages = self.get_query_set(request).drafts().order_by('tree_id', 'parent', 'lft').select_related()
        
        perm_edit_ids = Page.permissions.get_change_id_list(request.user)
        perm_publish_ids = Page.permissions.get_publish_id_list(request.user)
        perm_advanced_settings_ids = Page.permissions.get_advanced_settings_id_list(request.user)
        perm_change_list_ids = Page.permissions.get_change_list_id_list(request.user)
        
        if perm_edit_ids and perm_edit_ids != Page.permissions.GRANT_ALL:
            #pages = pages.filter(pk__in=perm_edit_ids)
            pages = pages.filter(pk__in=perm_change_list_ids)   
        
        if settings.CMS_MODERATOR:
            # get all ids of public instances, so we can cache them
            # TODO: add some filtering here, so the set is the same like page set...
            published_public_page_id_set = Page.objects.public().filter(published=True).values_list('id', flat=True)
            
            # get all moderations for current user and all pages
            pages_moderator_set = PageModerator.objects \
                .filter(user=request.user, page__site__id=self._current_site.pk) \
                .values_list('page', 'moderate_page', 'moderate_children', 'moderate_descendants')
            # put page / moderations into singe dictionary, where key is page.id 
            # and value is sum of moderations, so if he can moderate page and descendants
            # value will be MASK_PAGE + MASK_DESCENDANTS
            page_moderator = map(lambda item: (item[0], item[1] * MASK_PAGE + item[2] * MASK_CHILDREN + item[3] * MASK_DESCENDANTS), pages_moderator_set)
            page_moderator = dict(page_moderator)
            
            # page moderator states
            pm_qs = PageModeratorState.objects.filter(page__site=self._current_site)
            pm_qs.query.group_by = ['page_id']
            pagemoderator_states_id_set = pm_qs.values_list('page', flat=True)
            
        ids = []
        root_pages = []
        pages = list(pages)
        all_pages = pages[:]
        try:
            home_pk = Page.objects.drafts().get_home(self.current_site()).pk
        except NoHomeFound:
            home_pk = 0
            
        for page in pages:
            children = []

            # note: We are using change_list permission here, because we must
            # display also pages which user must not edit, but he haves a 
            # permission for adding a child under this page. Otherwise he would
            # not be able to add anything under page which he can't change. 
            if not page.parent_id or (perm_change_list_ids != Page.permissions.GRANT_ALL and not int(page.parent_id) in perm_change_list_ids):
                page.root_node = True
            else:
                page.root_node = False
            ids.append(page.pk)
            
            if settings.CMS_PERMISSION:
                # caching the permissions
                page.permission_edit_cache = perm_edit_ids == Page.permissions.GRANT_ALL or page.pk in perm_edit_ids
                page.permission_publish_cache = perm_publish_ids == Page.permissions.GRANT_ALL or page.pk in perm_publish_ids
                page.permission_advanced_settings_cache = perm_publish_ids == Page.permissions.GRANT_ALL or page.pk in perm_advanced_settings_ids
                page.permission_user_cache = request.user
            
            if settings.CMS_MODERATOR:
                # set public instance existence state
                page.public_published_cache = page.publisher_public_id in published_public_page_id_set
                
                # moderation for current user
                moderation_value = 0
                try:
                    moderation_value = page_moderator[page.pk]
                except:
                    pass
                page._moderation_value_cahce = moderation_value
                page._moderation_value_cache_for_user_id = request.user.pk
                
                #moderation states
                page._has_moderator_state_chache = page.pk in pagemoderator_states_id_set
                
            if page.root_node or self.is_filtered():
                page.last = True
                if len(children):
                    children[-1].last = False
                page.menu_level = 0
                root_pages.append(page)
                if page.parent_id:
                    page.get_cached_ancestors()
                else:
                    page.ancestors_ascending = []
                page.home_pk_cache = home_pk
                if not self.is_filtered():
                    find_children(page, pages, 1000, 1000, [], -1, soft_roots=False, request=request, no_extended=True, to_levels=1000)
                else:
                    page.childrens = []
        
        # TODO: OPTIMIZE!!
        titles = Title.objects.filter(page__in=ids)
        for page in all_pages:# add the title and slugs and some meta data
            page.title_cache = {}
            page.all_languages = []
            for title in titles:
                if title.page_id == page.pk:
                    page.title_cache[title.language] = title
                    if not title.language in page.all_languages:
                        page.all_languages.append(title.language)
            page.all_languages.sort()
        self.root_pages = root_pages
        
    def get_items(self):
        return self.root_pages
    
    def set_sites(self, request):
        """Sets sites property to current instance - used in tree view for
        sites combo.
        """
        if settings.CMS_PERMISSION:
            self.sites = get_user_sites_queryset(request.user)   
        else:
            self.sites = Site.objects.all()
        self.has_access_to_multiple_sites = len(self.sites) > 1
    
    def current_site(self):
        return self._current_site
        
def get_changelist_admin(admin_base):
    
    class RealReplaceChangeListAdmin(admin_base):
        
        changelist_class = ChangeList
        # copying most of this view only to replace the changelist
        def changelist_view(self, request, extra_context=None):
            "The 'change list' admin view for this model."
            from django.contrib.admin.views.main import ERROR_FLAG
            opts = self.model._meta
            app_label = opts.app_label
            if not self.has_change_permission(request, None):
                raise PermissionDenied
        
            # Check actions to see if any are available on this changelist
            actions = self.get_actions(request)
        
            # Remove action checkboxes if there aren't any actions available.
            list_display = list(self.list_display)
            if not actions:
                try:
                    list_display.remove('action_checkbox')
                except ValueError:
                    pass
        
            try:
                cl = self.changelist_class(request, self.model, list_display, self.list_display_links, self.list_filter,
                    self.date_hierarchy, self.search_fields, self.list_select_related, self.list_per_page, self.list_editable, self)
            except IncorrectLookupParameters:
                # Wacky lookup parameters were given, so redirect to the main
                # changelist page, without parameters, and pass an 'invalid=1'
                # parameter via the query string. If wacky parameters were given and
                # the 'invalid=1' parameter was already in the query string, something
                # is screwed up with the database, so display an error page.
                if ERROR_FLAG in request.GET.keys():
                    return render_to_response('admin/invalid_setup.html', {'title': _('Database error')})
                return HttpResponseRedirect(request.path + '?' + ERROR_FLAG + '=1')
        
            # If the request was POSTed, this might be a bulk action or a bulk edit.
            # Try to look up an action first, but if this isn't an action the POST
            # will fall through to the bulk edit check, below.
            if actions and request.method == 'POST':
                response = self.response_action(request, queryset=cl.get_query_set())
                if response:
                    return response
        
            # If we're allowing changelist editing, we need to construct a formset
            # for the changelist given all the fields to be edited. Then we'll
            # use the formset to validate/process POSTed data.
            formset = cl.formset = None
        
            # Handle POSTed bulk-edit data.
            if request.method == "POST" and self.list_editable:
                FormSet = self.get_changelist_formset(request)
                formset = cl.formset = FormSet(request.POST, request.FILES, queryset=cl.result_list)
                if formset.is_valid():
                    changecount = 0
                    for form in formset.forms:
                        if form.has_changed():
                            obj = self.save_form(request, form, change=True)
                            self.save_model(request, obj, form, change=True)
                            form.save_m2m()
                            change_msg = self.construct_change_message(request, form, None)
                            self.log_change(request, obj, change_msg)
                            changecount += 1
        
                    if changecount:
                        if changecount == 1:
                            name = force_unicode(opts.verbose_name)
                        else:
                            name = force_unicode(opts.verbose_name_plural)
                        msg = ungettext("%(count)s %(name)s was changed successfully.",
                                        "%(count)s %(name)s were changed successfully.",
                                        changecount) % {'count': changecount,
                                                        'name': name,
                                                        'obj': force_unicode(obj)}
                        self.message_user(request, msg)
        
                    return HttpResponseRedirect(request.get_full_path())
        
            # Handle GET -- construct a formset for display.
            elif self.list_editable:
                FormSet = self.get_changelist_formset(request)
                formset = cl.formset = FormSet(queryset=cl.result_list)
        
            # Build the list of media to be used by the formset.
            if formset:
                media = self.media + formset.media
            else:
                media = self.media
        
            # Build the action form and populate it with available actions.
            if actions:
                action_form = self.action_form(auto_id=None)
                action_form.fields['action'].choices = self.get_action_choices(request)
            else:
                action_form = None
        
            context = {
                'title': cl.title,
                'is_popup': cl.is_popup,
                'cl': cl,
                'media': media,
                'has_add_permission': self.has_add_permission(request),
                'root_path': self.admin_site.root_path,
                'app_label': app_label,
                'action_form': action_form,
                'actions_on_top': self.actions_on_top,
                'actions_on_bottom': self.actions_on_bottom,
            }
            context.update(extra_context or {})
            context_instance = template.RequestContext(request, current_app=self.admin_site.name)
            return render_to_response(self.change_list_template or [
                'admin/%s/%s/change_list.html' % (app_label, opts.object_name.lower()),
                'admin/%s/change_list.html' % app_label,
                'admin/change_list.html'
            ], context, context_instance=context_instance)
            
    return RealReplaceChangeListAdmin