from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from apps.tournament.urls import main, account, tournament
from analytics import urls as analytics_urls

urlpatterns = [
    path('', include('main.urls')),
    path('admin/', admin.site.urls),
    path('profile/', include('profile.urls')),
    path('account/', include('account.urls')),
    path('tournament/', include('tournament.urls')),
    path('analytics/', include(analytics_urls, namespace='analytics'))
]

if settings.TELEGRAM_BOT_TOKEN:
    from django_telegrambot import urls as django_telegrambot_urls
    urlpatterns += [
        path('', include(django_telegrambot_urls)),
    ]

if settings.DEBUG:
    import debug_toolbar
    from apps.tester import urls as tester_urls
    urlpatterns += [
         path('', include(tester_urls, namespace='tester')),
        path('__debug__/', include(debug_toolbar.urls)),
    ]

