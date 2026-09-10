from django.contrib import admin
from django.urls import path, include

from SarefAcademy import views

urlpatterns = [
    path('',  views.index, name='index'),
    path('insrciption-valide',  views.insrciption_valide, name='insrciption-valide'),
    path('connexion_admin',  views.connexion_admin, name='connexion_admin'),
    path('admin_dashboard',  views.admin_dashboard, name='admin_dashboard'),
    path('suspension_delai_candidature',  views.suspension_delai_candidature, name='suspension_delai_candidature'),
    path('deconnexion' , views.deconnexion , name="deconnexion"),
    path('supprimer_candidat/<int:id_user>' , views.supprimer_candidat , name="supprimer_candidat"),
    path('telecharger_pdf_jour' , views.telecharger_pdf_jour , name="telecharger_pdf_jour"),
    path('telecharger_pdf_all' , views.telecharger_pdf_all, name="telecharger_pdf_all")
    
]
#