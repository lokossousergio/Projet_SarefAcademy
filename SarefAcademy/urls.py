from django.contrib import admin
from django.urls import path, include

from SarefAcademy import views


urlpatterns = [
    path('',  views.index, name='index'),
    path('Marketing-digital',  views.Marketing_digital, name='Marketing-digital'),

    path('Design-graphique',  views.Design_graphique, name='Design-graphique'),

    path('Developpement-web',  views.Developpement_web, name='Developpement-web'),

    path('Archivage-numerique',  views.Archivage_numerique, name='Archivage-numerique'),

    path('Montage-video',  views.Montage_video, name='Montage-video'),

    path('Journalisme-web',  views.Journalisme_web, name='Journalisme-web'),

    path('connexion-etudiant',  views.connexion_etudiant, name='connexion-etudiant'),

    path('inscription-etudiant',  views.inscription_etudiant, name='inscription-etudiant'),

    path('dashboard-etudiant',  views.dashboard_etudiant, name='dashboard-etudiant'),




    path('bourse-de-formation',  views.bourse_de_formation, name='bourse-de-formation'),

    path('inscription_valide',  views.inscription_valide , name='inscription_valide'),

    path('connexion_admin',  views.connexion_admin, name='connexion_admin'),

    path('admin_dashboard',  views.admin_dashboard, name='admin_dashboard'),

    path('suspension_delai_candidature',  views.suspension_delai_candidature, name='suspension_delai_candidature'),

    path('deconnexion' , views.deconnexion , name="deconnexion"),

    path('supprimer_candidat/<int:id_user>' , views.supprimer_candidat , name="supprimer_candidat"),

    path('telecharger_pdf_jour' , views.telecharger_pdf_jour , name="telecharger_pdf_jour"),

    path('telecharger_pdf_all' , views.telecharger_pdf_all, name="telecharger_pdf_all")
    
]
#