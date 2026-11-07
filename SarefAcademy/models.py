"""
SAREF Academy — modèles (ta version, corrigée et complétée selon le cahier des charges).

Corrections de ta version
  - `models.Models` -> `models.Model` ; `desription` -> `description` ; `IntegerField(max_length=…)` n'existe pas.
  - `Admin(email, password)` : un mot de passe en clair est dangereux -> on utilise un utilisateur Django `is_staff`.
Ajouts (voir README) : statut de candidature, activation des modules, mode de paiement,
  progression par chapitre, notifications, lien WhatsApp, vague courante, etc.
Le statut « boursier » n'existe plus. Un étudiant peut postuler à plusieurs formations.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class ConfigVague(models.Model):
    nom = models.CharField(max_length=100)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    est_courante = models.BooleanField(default=False)                       # AJOUT : « vague en cours »
    annee_academique = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["est_courante"], condition=Q(est_courante=True),
                                               name="une_seule_vague_courante")]

    def __str__(self):
        return self.nom


class Formation(models.Model):
    STATUTS = [("active", "Active"), ("brouillon", "Brouillon"), ("archivee", "Archivée")]
    nom = models.CharField(max_length=100)
    duree = models.IntegerField(help_text="Durée en mois")
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    nb_tranches = models.PositiveSmallIntegerField(default=3)               # AJOUT : plan de paiement
    description = models.TextField(blank=True)                              # AJOUT
    statut = models.CharField(max_length=10, choices=STATUTS, default="brouillon")   # AJOUT
    lien_whatsapp = models.URLField(blank=True)                             # AJOUT : invitation WhatsApp

    def __str__(self):
        return self.nom


class Modules(models.Model):
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="modules")
    titre = models.CharField(max_length=150)                                # AJOUT (il n'y avait pas de titre)
    description = models.CharField(max_length=255, blank=True)              # corrigé (desription)
    ordre = models.PositiveSmallIntegerField()
    date_session = models.DateTimeField(null=True, blank=True)              # AJOUT : date du meet
    lien_meet = models.URLField(blank=True)                                 # AJOUT
    est_active = models.BooleanField(default=False)                         # AJOUT : activation après le meet

    class Meta:
        ordering = ["ordre"]
        unique_together = [("formation", "ordre")]


class Chapitres(models.Model):
    modules = models.ForeignKey(Modules, on_delete=models.CASCADE, related_name="chapitres")
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, help_text="Résumé et objectifs pédagogiques du chapitre")
    ordre = models.PositiveSmallIntegerField(default=1)                     # AJOUT
    duree = models.PositiveIntegerField(help_text="Durée en minutes")
    support_video_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="Lien de la vidéo")
    support_pdf = models.FileField(upload_to="documents/", null=True, blank=True, verbose_name="Support PDF")
    est_active = models.BooleanField(default=False, verbose_name="Visible par les apprenants")
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Dernière mise à jour")

    class Meta:
        ordering = ["ordre"]


class Etudiants(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.CASCADE, related_name="etudiant")   # AJOUT : connexion
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)                                  # EmailField au lieu de CharField
    telephone = models.CharField(max_length=100)
    niveau_etudes = models.CharField(max_length=100)
    photo = models.FileField(upload_to="profils/", null=True, blank=True)  # AJOUT : photo du profil
    date_inscription = models.DateTimeField(auto_now_add=True)


class Candidats(models.Model):
    STATUTS = [("en_attente", "En attente"), ("accepte", "Accepté"), ("refuse", "Refusé")]
    photo_profils = models.FileField(upload_to="profils/", null=True, blank=True, verbose_name="Photo de profil")
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="candidats")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="candidats")
    etudiant = models.ForeignKey(Etudiants, on_delete=models.CASCADE, related_name="candidats")
    motif_inscription = models.CharField(max_length=255)
    date_candidature = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=10, choices=STATUTS, default="en_attente")   # AJOUT
    commentaire_admin = models.TextField(blank=True)                                    # AJOUT (interne)
    date_decision = models.DateTimeField(null=True, blank=True)                         # AJOUT
    est_bloque = models.BooleanField(default=False)                                     # AJOUT : blocage impayé

    class Meta:
        constraints = [models.UniqueConstraint(fields=["etudiant", "formation", "configVague"],
                                               name="une_candidature_par_formation_et_vague")]


class Formateurs(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="profil_formateur")
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=100)
    formations = models.ManyToManyField(Formation, blank=True, related_name="formateurs")
    actif = models.BooleanField(default=True)
    doit_changer_mot_de_passe = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Paiement(models.Model):
    MODES = [("especes", "Espèces"), ("mobile_money", "Mobile Money"), ("virement", "Virement")]
    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="paiements")
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="paiement")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="paiement")
    tranche = models.PositiveSmallIntegerField(help_text="Numéro de la tranche")   # était un CharField
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField()
    mode = models.CharField(max_length=15, choices=MODES, default="mobile_money")  # AJOUT


class Archive(models.Model):
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="archive")
    date = models.DateTimeField()


class Resultat(models.Model):
    DECISIONS = [("admis", "Admis"), ("non_admis", "Non admis"), ("abandon", "Abandon")]
    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="resultat")
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="resultat")
    decision = models.CharField(max_length=10, choices=DECISIONS)
    attestation = models.FileField(upload_to="attestation/", null=True, blank=True, verbose_name="Attestation")


class ChapitreTermine(models.Model):                                        # AJOUT : progression de l'apprenant
    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="chapitres_termines")
    chapitre = models.ForeignKey(Chapitres, on_delete=models.CASCADE, related_name="termines")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("candidats", "chapitre")]


class Notification(models.Model):                                           # AJOUT : notifications dans l'espace
    etudiant = models.ForeignKey(Etudiants, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    lien = models.CharField(max_length=255, blank=True)
    lu = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class Admin(models.Model):                                                  # profil de l'équipe (plus de mot de passe en clair)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_profil")
    telephone = models.CharField(max_length=100, blank=True)

class Parametre(models.Model):
    Date_ouverture_inscription = models.DateTimeField()
    Date_cloture_inscription = models.DateTimeField()
    Etat = models.CharField(max_length=10, default="Actif")
