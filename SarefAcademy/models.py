from django.db import models

# Create your models here.





class ConfigVague(models.Model):
     nom=models.CharField(max_length=100)
     date_debut = models.DateTimeField()
     date_fin = models.DateTimeField()


class Formation (models.Model):
    nom=models.CharField(max_length=100)
    duree= models.IntegerField(max_length=10)
    prix = models.DecimalField(max_digits=10, decimal_places=2)


class Modules(models.Model):
    formation = models.ForeignKey(Formation , on_delete=models.CASCADE  , related_name="modules")
    desription=models.CharField(max_length=100)
    ordre= models.IntegerField(max_length=10)

class Chapitres (models.Model):
    modules= models.ForeignKey(Modules , on_delete=models.CASCADE , related_name="chapitres")
    nom = models.CharField(max_length=100)
    duree= models.IntegerField(max_length=10)
    support_video_url = models.URLField(
        max_length=500, 
        null=True, 
        blank=True, 
        verbose_name="Lien de la vidéo"
    )
    support_pdf = models.FileField(
        upload_to='documents/', 
        null=True, 
        blank=True, 
        verbose_name="Support PDF"
    )






class Etudiants (models.Model):
    nom=models.CharField(max_length=100)
    prenom=models.CharField(max_length=100)
    email=models.CharField(max_length=100)
    telephone=models.CharField(max_length=100)
    niveau_etudes = models.CharField(max_length=100)
    date_inscription = models.DateTimeField(auto_now_add=True)


class Candidats (models.Model):
    photo_profils= models.FileField(
            upload_to='profils/', 
            null=True, 
            blank=True, 
            verbose_name="Support PDF"
        )
    
    configVague = models.ForeignKey(ConfigVague , on_delete=models.CASCADE  ,related_name="candidats")
    formation = models.ForeignKey(Formation , on_delete=models.CASCADE  , related_name="candidats")
    etudiant= models.ForeignKey(Etudiants , on_delete=models.CASCADE , related_name="candidats")
    motif_inscription = models.CharField(max_length=255)
    date_candidature = models.DateTimeField(auto_now_add=True)


class Formateurs(models.Model):
    nom=models.CharField(max_length=255)
    prenom=models.CharField(max_length=100)
    email=models.CharField(max_length=100)
    telephone=models.CharField(max_length=100)
    formation = models.ForeignKey(Formation , on_delete=models.CASCADE  , related_name="formateurs")


class Paiement (models.Model):
    candidats= models.ForeignKey(Candidats  , on_delete=models.CASCADE , related_name="paiements")
    configVague = models.ForeignKey(ConfigVague , on_delete=models.CASCADE  ,related_name="paiement")
    formation = models.ForeignKey(Formation , on_delete=models.CASCADE  , related_name="paiement")
    tranche=models.CharField(max_length=100)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField()


class Archive (models.Model):
    configVague = models.ForeignKey(ConfigVague , on_delete=models.CASCADE  ,related_name="archive")
    date = models.DateTimeField()



   
class Resultat(models.Model):
     candidats= models.ForeignKey(Candidats  , on_delete=models.CASCADE , related_name="resultat")
     configVague = models.ForeignKey(ConfigVague , on_delete=models.CASCADE  ,related_name="resultat")
     decision=models.CharField(max_length=10 )
     attestation= models.FileField(
                 upload_to='attestation/', 
                 null=True, 
                 blank=True, 
                 verbose_name="attesatation"
             )
         





class Admin(models.Model):
    email = models.EmailField()
    password = models.CharField(max_length=100)

class Parametre (models.Model):
    Date_ouverture_inscription = models.DateTimeField()
    Date_cloture_inscription = models.DateTimeField()
    Etat=models.CharField(max_length=10 , default="Actif")