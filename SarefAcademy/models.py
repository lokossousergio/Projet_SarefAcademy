from django.db import models

# Create your models here.

class Canditats (models.Model):
    nom_prenom = models.CharField(max_length=100)
    email = models.EmailField()
    number = models.CharField(max_length=15)
    niveau_etudes = models.CharField(max_length=100)
    date_inscription = models.DateTimeField(auto_now_add=True)

class Admin(models.Model):
    email = models.EmailField()
    password = models.CharField(max_length=100)

class Parametre (models.Model):
    Date_ouverture_inscription = models.DateTimeField()
    Date_cloture_inscription = models.DateTimeField()
    Etat=models.CharField(max_length=10 , default="Actif")
   
