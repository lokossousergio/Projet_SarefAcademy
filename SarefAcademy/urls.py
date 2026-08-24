from django.contrib import admin
from django.urls import path, include

from SarefAcademy import views

urlpatterns = [
    path('',  views.index, name='index'),
    path('connexion_admin/',  views.connexion_admin, name='connexion_admin'),
    path('admin_dashboard/',  views.admin_dashboard, name='admin_dashboard'),
    path('suspension_delai_candidature/',  views.suspension_delai_candidature, name='suspension_delai_candidature'),
    path('deconnexion/' , views.deconnexion , name="deconnexion"),
    
]