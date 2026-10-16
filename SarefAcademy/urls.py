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

    path('candidature-formation/', views.candidature_formation, name='candidature-formation'),

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

    # path('telecharger_pdf_jour' , views.telecharger_pdf_jour , name="telecharger_pdf_jour"),

    # path('telecharger_pdf_all' , views.telecharger_pdf_all, name="telecharger_pdf_all"),

 # ----- Candidature (page seule)
    path("candidature/", views.candidature, name="candidature"),

    # ----- Espace apprenant
    path("apprenant/", views.apprenant_dashboard, name="apprenant_dashboard"),
    path("apprenant/formations/", views.apprenant_formations, name="apprenant_formations"),
    path("apprenant/formations/<int:pk>/", views.apprenant_formation_detail, name="apprenant_formation_detail"),
    path("apprenant/modules/", views.apprenant_modules, name="apprenant_modules"),
    path("apprenant/modules/<int:pk>/", views.apprenant_module_detail, name="apprenant_module_detail"),
    path("apprenant/paiements/", views.apprenant_paiements, name="apprenant_paiements"),
    path("apprenant/profil/", views.apprenant_profil, name="apprenant_profil"),
    path("apprenant/parametres/", views.apprenant_parametres, name="apprenant_parametres"),

    # ----- Espace admin
    path("gestion/", views.admin_dashboard, name="admin_dashboard"),
    path("gestion/candidatures/", views.admin_candidatures, name="admin_candidatures"),
    path("gestion/candidatures/<int:pk>/", views.admin_candidature_detail, name="admin_candidature_detail"),
    path("gestion/apprenants/", views.admin_apprenants, name="admin_apprenants"),
    path("gestion/apprenants/<int:pk>/", views.admin_apprenant_detail, name="admin_apprenant_detail"),
    path("gestion/resultats/", views.admin_resultats, name="admin_resultats"),
    path("gestion/finance/", views.admin_finance, name="admin_finance"),
    path("gestion/organisation/", views.admin_organisation, name="admin_organisation"),
    path("gestion/formations/", views.admin_formations, name="admin_formations"),
    path("gestion/formations/<int:pk>/", views.admin_formation_detail, name="admin_formation_detail"),
    path("gestion/formateurs/", views.admin_formateurs, name="admin_formateurs"),
    path("gestion/vagues/", views.admin_vagues, name="admin_vagues"),
    path("gestion/vagues/<int:pk>/archive/", views.admin_vague_archive, name="admin_vague_archive"),
    path("gestion/parametres/", views.admin_parametres, name="admin_parametres"),
]
#