from django.urls import path
from . import views

urlpatterns = [
    # ===== Site Public & Formations =====
    path('', views.index, name='index'),
    path('Marketing-digital', views.Marketing_digital, name='Marketing-digital'),
    path('Design-graphique', views.Design_graphique, name='Design-graphique'),
    path('Developpement-web', views.Developpement_web, name='Developpement-web'),
    path('Archivage-numerique', views.Archivage_numerique, name='Archivage-numerique'),
    path('Montage-video', views.Montage_video, name='Montage-video'),
    path('Journalisme-web', views.Journalisme_web, name='Journalisme-web'),
    path('candidature-formation/', views.candidature_formation, name='candidature-formation'),
    path('bourse-de-formation', views.bourse_de_formation, name='bourse-de-formation'),
    path('inscription_valide', views.inscription_valide, name='inscription_valide'),
    path('tunel', views.tunel, name='tunel'),

    # ===== Authentification & Compte =====
    path('espace-etudiant/connexion/', views.connexion_etudiant, name='connexion-etudiant'),
    path('espace-etudiant/inscription/', views.inscription_etudiant, name='inscription-etudiant'),
    path('espace-etudiant/dashboard/', views.dashboard_etudiant, name='dashboard-etudiant'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),

    # ===== Espace Formateur =====
    path('formateur/', views.formateur_dashboard, name='formateur_dashboard'),
    path('formateur/module/<int:pk>/', views.formateur_module, name='formateur_module'),
    path('formateur/formations/', views.formateur_formations, name='formateur_formations'),
    path('formateur/formations/<int:formation_id>/', views.formateur_formation_detail, name='formateur_formation_detail'),
    path('formateur/formations/module/ajouter/', views.formateur_module_ajouter, name='formateur_module_ajouter'),
    path('formateur/formations/module/<int:pk>/modifier/', views.formateur_module_modifier, name='formateur_module_modifier'),
    path('formateur/formations/module/<int:pk>/supprimer/', views.formateur_module_supprimer, name='formateur_module_supprimer'),
    path('formateur/formations/chapitre/ajouter/', views.formateur_chapitre_ajouter, name='formateur_chapitre_ajouter'),

    # ===== Espace Apprenant =====
    path('apprenant/', views.apprenant_dashboard, name='apprenant_dashboard'),
    path('apprenant/formations/', views.apprenant_formations, name='apprenant_formations'),
    path('apprenant/formations/<int:pk>/', views.apprenant_formation_detail, name='apprenant_formation_detail'),
    path('apprenant/modules/', views.apprenant_modules, name='apprenant_modules'),
    path('apprenant/modules/<int:pk>/', views.apprenant_module_detail, name='apprenant_module_detail'),
    path('apprenant/paiements/', views.apprenant_paiements, name='apprenant_paiements'),
    path('apprenant/profil/', views.apprenant_profil, name='apprenant_profil'),
    path('apprenant/parametres/', views.apprenant_parametres, name='apprenant_parametres'),

    # ===== Espace Administration =====
    path('configuration-initiale/', views.admin_configuration_initiale, name='admin_configuration_initiale'),
    path('gestion/', views.admin_dashboard, name='admin_dashboard'),
    path('gestion/candidatures/', views.admin_candidatures, name='admin_candidatures'),
    path('gestion/candidatures/<int:pk>/', views.admin_candidature_detail, name='admin_candidature_detail'),
    path('gestion/apprenants/', views.admin_apprenants, name='admin_apprenants'),
    path('gestion/apprenants/<int:pk>/', views.admin_apprenant_detail, name='admin_apprenant_detail'),
    path('gestion/resultats/', views.admin_resultats, name='admin_resultats'),
    path('gestion/finance/', views.admin_finance, name='admin_finance'),
    path('gestion/organisation/', views.admin_organisation, name='admin_organisation'),
    path('gestion/formations/', views.admin_formations, name='admin_formations'),
    path('gestion/formations/<int:pk>/', views.admin_formation_detail, name='admin_formation_detail'),
    path('gestion/formateurs/', views.admin_formateurs, name='admin_formateurs'),
    path('gestion/formateurs/<int:pk>/', views.admin_formateur_detail, name='admin_formateur_detail'),
    path('gestion/vagues/', views.admin_vagues, name='admin_vagues'),
    path('gestion/vagues/<int:pk>/archive/', views.admin_vague_archive, name='admin_vague_archive'),
    path('gestion/parametres/', views.admin_parametres, name='admin_parametres'),

    path('connexion-admin/', views.connexion_admin, name='connexion_admin'),
    path('gestion/configuration-vague/', views.admin_configuration_vague, name='admin_configuration_vague'),
    path('gestion/chapitre/<int:formation_id>/<int:chapitre_id>/', views.admin_chapitre_detail, name='admin_chapitre_detail'),

    path('formateur/apprenants/', views.formateur_apprenants, name='formateur_apprenants'),
    path('formateur/chapitre/<int:formation_id>/<int:chapitre_id>/', views.formateur_chapitre_detail, name='formateur_chapitre_detail'),
]
