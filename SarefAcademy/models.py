from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class ConfigVague(models.Model):
    nom = models.CharField(max_length=100)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    est_courante = models.BooleanField(default=False)
    annee_academique = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["est_courante"],
                condition=models.Q(est_courante=True),
                name="une_seule_vague_courante",
            ),
            models.UniqueConstraint(
                Lower("nom"),
                name="nom_vague_unique_sans_casse",
            ),
        ]

    def __str__(self):
        return self.nom


class Formation(models.Model):
    STATUT_CHOICES = [
        ("active", "Active"),
        ("brouillon", "Brouillon"),
        ("archivee", "Archivée"),
    ]

    nom = models.CharField(max_length=100)
    photo = models.FileField(upload_to="formation/", null=True, blank=True, verbose_name="Photo de couverture")
    duree = models.IntegerField(help_text="Durée en mois")
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    nb_tranches = models.PositiveSmallIntegerField(default=3)
    description = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="active")
    lien_whatsapp = models.URLField(blank=True)

    def __str__(self):
        return self.nom


class Modules(models.Model):
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="modules")
    titre = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)

    ordre = models.PositiveSmallIntegerField()
    est_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordre"]
        unique_together = [("formation", "ordre")]

    def __str__(self):
        return self.titre


class Chapitres(models.Model):
    modules = models.ForeignKey(Modules, on_delete=models.CASCADE, related_name="chapitres")
    nom = models.CharField(max_length=100)
    ordre = models.PositiveSmallIntegerField(default=1)
    duree = models.PositiveIntegerField(help_text="Durée en minutes")
    description = models.TextField(blank=True, help_text="Résumé et objectifs pédagogiques du chapitre")
    support_video_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="Lien de la vidéo")
    support_pdf = models.FileField(upload_to="documents/", null=True, blank=True, verbose_name="Support PDF")
    est_active = models.BooleanField(default=False, verbose_name="Visible par les apprenants")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Dernière mise à jour")

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.nom


class Etudiants(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=100)
    niveau_etudes = models.CharField(max_length=100)
    mot_de_passe = models.CharField(max_length=128, blank=True, default="")
    photo = models.FileField(upload_to="profils/", null=True, blank=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Candidats(models.Model):
    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("accepte", "Accepté"),
        ("refuse", "Refusé"),
    ]

    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="candidats")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="candidats")
    etudiant = models.ForeignKey(Etudiants, on_delete=models.CASCADE, related_name="candidats")
    motif_inscription = models.CharField(max_length=255)
    cv = models.FileField(upload_to="candidatures/cv/", null=True, blank=True, verbose_name="CV du candidat")
    date_candidature = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="en_attente")
    commentaire_admin = models.TextField(blank=True)
    date_decision = models.DateTimeField(null=True, blank=True)
    est_bloque = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["etudiant", "formation"],
                name="une_candidature_par_formation",
            )
        ]

    def __str__(self):
        return f"{self.etudiant} — {self.formation}"


class Formateurs(models.Model):
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=100)
    actif = models.BooleanField(default=True)
    doit_changer_mot_de_passe = models.BooleanField(default=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="profil_formateur",
        null=True,
        blank=True,
    )
    formations = models.ManyToManyField(Formation, related_name="formateurs", blank=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Paiement(models.Model):
    MODE_CHOICES = [
        ("especes", "Espèces"),
        ("mobile_money", "Mobile Money"),
        ("virement", "Virement"),
    ]

    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="paiements")
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="paiement")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="paiement")
    tranche = models.PositiveSmallIntegerField(help_text="Numéro de la tranche")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField()
    mode = models.CharField(max_length=15, choices=MODE_CHOICES, default="mobile_money")

    def __str__(self):
        return f"Paiement tranche {self.tranche} — {self.montant}"


class Archive(models.Model):
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="archive")
    date = models.DateTimeField()


class Resultat(models.Model):
    DECISION_CHOICES = [
        ("admis", "Admis"),
        ("non_admis", "Non admis"),
        ("abandon", "Abandon"),
    ]

    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="resultat")
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="resultat")
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES)
    attestation = models.FileField(upload_to="attestation/", null=True, blank=True, verbose_name="Attestation")


class Notification(models.Model):
    etudiant = models.ForeignKey(Etudiants, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    lien = models.CharField(max_length=255, blank=True)
    lu = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class ChapitreTermine(models.Model):
    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="chapitres_termines")
    chapitre = models.ForeignKey(Chapitres, on_delete=models.CASCADE, related_name="termines")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("candidats", "chapitre")]


class Parametre(models.Model):
    Date_ouverture_inscription = models.DateTimeField()
    Date_cloture_inscription = models.DateTimeField()
    Etat = models.CharField(max_length=10, default="Actif")


class Admin(models.Model):
    telephone = models.CharField(max_length=100, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_profil",
    )
