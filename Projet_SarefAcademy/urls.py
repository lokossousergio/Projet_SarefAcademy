"""
URL configuration for Projet_SarefAcademy project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls import handler404, handler500
from django.views.generic import TemplateView, RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from SarefAcademy.sitemaps import StaticSitemap

handler404 = 'SarefAcademy.views.handel404'
handler500 = 'SarefAcademy.views.handel500'

sitemaps = {
    'static': StaticSitemap,
}


def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    if not sitemap_url.startswith('https://'):
        sitemap_url = 'https://sarefacademy.pythonanywhere.com/sitemap.xml'
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /administration/\n"
        "Disallow: /formateur/\n"
        "Disallow: /espace-etudiant/\n"
        "Disallow: /etudiant/\n"
        "Disallow: /configuration-initiale/\n"
        "Disallow: /mot-de-passe/\n\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(content, content_type="text/plain")


urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('', include('SarefAcademy.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
