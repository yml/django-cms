from django.conf.urls.defaults import handler500, handler404, patterns, include, \
    url


urlpatterns = patterns('example.sampleblog.views',
    url(r'^blogpost/(?P<post_id>\d+?)/$',
        'blogpost_detail',
        name="blogpost_detail"),
)
    