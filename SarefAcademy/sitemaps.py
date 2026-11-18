from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticSitemap(Sitemap):
    protocol = "https"

    def items(self):
        return [
            'index',
            'bourse-de-formation',
            'Marketing-digital',
            'Design-graphique',
            'Developpement-web',
            'Archivage-numerique',
            'Montage-video',
            'Journalisme-web',
            'candidature-formation',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == 'index':
            return 1.0
        elif item == 'bourse-de-formation':
            return 0.9
        elif item == 'candidature-formation':
            return 0.7
        return 0.8

    def changefreq(self, item):
        if item == 'index':
            return 'daily'
        elif item == 'bourse-de-formation':
            return 'weekly'
        return 'weekly'
