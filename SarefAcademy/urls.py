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
    path('espace-etudiant/deconnexion/', views.deconnexion_etudiant, name='deconnexion-etudiant'),
    path('espace-etudiant/mot-de-passe-oublie/', views.mot_de_passe_oublie, name='mot-de-passe-oublie'),
    path('espace-etudiant/verifier-code/', views.verifier_code_etudiant, name='verifier_code_etudiant'),
    path('connexion-formateur/', views.connexion_formateur, name='connexion-formateur'),
    path('deconnexion-formateur/', views.deconnexion_formateur, name='deconnexion-formateur'),
    path('connexion-admin/', views.connexion_admin, name='connexion-admin'),
    path('deconnexion-admin/', views.deconnexion_admin, name='deconnexion-admin'),
    path('mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),

    # ===== Espace Formateur =====
    path('formateur/', views.formateur_dashboard, name='formateur_dashboard'),
    path('formateur/formations/', views.formateur_formations, name='formateur_formations'),
    path('formateur/formations/<int:formation_id>/', views.formateur_formation_detail, name='formateur_formation_detail'),
    path('formateur/chapitre/<int:formation_id>/<int:chapitre_id>/', views.formateur_chapitre_detail, name='formateur_chapitre_detail'),
    path('formateur/etudiants/', views.formateur_etudiants, name='formateur_etudiants'),

    # ===== Espace Étudiant =====
    path('etudiant/', views.etudiant_dashboard, name='etudiant_dashboard'),
    path('etudiant/formations/', views.etudiant_formations, name='etudiant_formations'),
    path('etudiant/formations/<int:pk>/', views.etudiant_formation_detail, name='etudiant_formation_detail'),
    path('etudiant/modules/', views.etudiant_modules, name='etudiant_modules'),
    path('etudiant/modules/<int:pk>/', views.etudiant_module_detail, name='etudiant_module_detail'),
    path('etudiant/paiements/', views.etudiant_paiements, name='etudiant_paiements'),
    path('etudiant/profil/', views.etudiant_profil, name='etudiant_profil'),
    path('etudiant/parametres/', views.etudiant_parametres, name='etudiant_parametres'),

    # ===== Espace Administration =====
    path('configuration-initiale/', views.admin_configuration_initiale, name='admin_configuration_initiale'),
    path('administration/', views.admin_dashboard, name='admin_dashboard'),
    path('administration/candidatures/', views.admin_candidatures, name='admin_candidatures'),
    path('administration/candidatures/<int:pk>/', views.admin_candidature_detail, name='admin_candidature_detail'),
    path('administration/etudiants/', views.admin_etudiants, name='admin_etudiants'),
    path('administration/etudiants/<int:pk>/', views.admin_etudiant_detail, name='admin_etudiant_detail'),
    path('administration/resultats/', views.admin_resultats, name='admin_resultats'),
    path('administration/finance/', views.admin_finance, name='admin_finance'),
    path('administration/organisation/', views.admin_organisation, name='admin_organisation'),
    path('administration/formations/', views.admin_formations, name='admin_formations'),
    path('administration/formations/<int:pk>/', views.admin_formation_detail, name='admin_formation_detail'),
    path('administration/formateurs/', views.admin_formateurs, name='admin_formateurs'),
    path('administration/formateurs/<int:pk>/', views.admin_formateur_detail, name='admin_formateur_detail'),
    path('administration/vagues/', views.admin_vagues, name='admin_vagues'),
    path('administration/vagues/<int:pk>/archive/', views.admin_vague_archive, name='admin_vague_archive'),
    # Dossier complet d'un apprenant dans une vague (finances, résultats, attestation)
    path('administration/vagues/<int:pk>/etudiants/<int:candidat_pk>/', views.admin_vague_inscription, name='admin_vague_inscription'),
    path('administration/mon-compte/', views.admin_mon_compte, name='admin_mon_compte'),
    path('administration/configuration-vague/', views.admin_configuration_vague, name='admin_configuration_vague'),
    path('administration/chapitre/<int:formation_id>/<int:chapitre_id>/', views.admin_chapitre_detail, name='admin_chapitre_detail'),
]

