from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

# =============================================================================
# Modèles de SAREF Academy
#
# Organisation générale :
#   - ConfigVague : une session de formation (vague). Une seule est « en cours ».
#   - Formation -> Modules -> Chapitres : le contenu pédagogique.
#   - Etudiants : les comptes apprenants (authentification maison, pas auth_user).
#   - Candidats : la candidature d'un étudiant à une formation pour une vague.
#     Une fois acceptée, c'est elle qui porte les paiements, les résultats et
#     la progression (ChapitreTermine).
#   - Formateurs : profil lié à un compte Django (auth_user) créé par l'admin.
#   - Les administrateurs sont des superusers Django (createsuperuser).
# =============================================================================


class ConfigVague(models.Model):
    """Une vague (session) de formation, avec sa période et son année académique.

    Une seule vague peut être « courante » à la fois (contrainte en base).
    Les candidatures, paiements et résultats sont toujours rattachés à une vague.
    """

    nom = models.CharField(max_length=100)  # unique, sans tenir compte de la casse
    date_debut = models.DateTimeField()  # ouverture de la vague
    date_fin = models.DateTimeField()  # clôture de la vague
    est_courante = models.BooleanField(default=False)  # vague en cours (une seule)
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
    """Une formation proposée (ex. Développement web), avec son prix et sa durée."""

    STATUT_CHOICES = [
        ("active", "Active"),
        ("brouillon", "Brouillon"),
        ("archivee", "Archivée"),
    ]

    nom = models.CharField(max_length=100)
    photo = models.FileField(upload_to="formation/", null=True, blank=True, verbose_name="Photo de couverture")
    duree = models.IntegerField(help_text="Durée en mois")
    prix = models.DecimalField(max_digits=10, decimal_places=2)  # prix total en FCFA
    nb_tranches = models.PositiveSmallIntegerField(default=3)  # paiement en N tranches
    description = models.TextField(blank=True)
    # Seules les formations « active » sont proposées aux candidats.
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="active")
    lien_whatsapp = models.URLField(blank=True)

    def __str__(self):
        return self.nom


class Modules(models.Model):
    """Un module d'une formation ; regroupe des chapitres, dans un ordre donné."""

    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="modules")
    titre = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)

    ordre = models.PositiveSmallIntegerField()
    est_active = models.BooleanField(default=True)  # module publié pour les apprenants

    class Meta:
        ordering = ["ordre"]
        unique_together = [("formation", "ordre")]

    def __str__(self):
        return self.titre


# -----------------------------------------------------------------------------
# Vidéos des chapitres : transforme n'importe quel lien collé (YouTube, Vimeo,
# Google Drive, Dailymotion ou fichier vidéo) en lecteur intégrable au site.
# -----------------------------------------------------------------------------
import re as _re
from urllib.parse import parse_qs as _parse_qs, urlparse as _urlparse

_EXTENSIONS_VIDEO = (".mp4", ".webm", ".ogg", ".ogv", ".mov", ".m4v")


def lecteur_video(url):
    """Retourne {"type": "iframe" | "video", "src": ...} pour lire la vidéo
    directement sur le site, ou None si le lien est vide.

    Exemples acceptés :
      https://www.youtube.com/watch?v=ID  ·  https://youtu.be/ID  ·  /shorts/ID
      https://vimeo.com/123456            ·  https://drive.google.com/file/d/ID/view
      https://www.dailymotion.com/video/ID ·  https://exemple.com/cours.mp4
    """
    if not url:
        return None
    url = url.strip()
    lien = _urlparse(url)
    hote = (lien.netloc or "").lower().removeprefix("www.").removeprefix("m.")
    chemin = lien.path or ""

    # Fichier vidéo direct : lecteur HTML5 natif.
    if chemin.lower().endswith(_EXTENSIONS_VIDEO):
        return {"type": "video", "src": url}

    # YouTube : on récupère l'identifiant de la vidéo quel que soit le format du lien.
    if hote in ("youtube.com", "youtube-nocookie.com", "youtu.be", "music.youtube.com"):
        video_id = None
        if hote == "youtu.be":
            video_id = chemin.strip("/").split("/")[0]
        elif chemin == "/watch":
            video_id = (_parse_qs(lien.query).get("v") or [None])[0]
        else:
            m = _re.match(r"^/(?:embed|shorts|live|v)/([^/?#]+)", chemin)
            video_id = m.group(1) if m else None
        if video_id and _re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
            # Domaine « nocookie » + rel=0 : pas de suggestions d'autres chaînes à la fin.
            return {"type": "iframe", "src": f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1&playsinline=1"}

    # Vimeo : vimeo.com/123456 ou player.vimeo.com/video/123456
    if hote in ("vimeo.com", "player.vimeo.com"):
        m = _re.search(r"/(?:video/)?(\d+)", chemin)
        if m:
            return {"type": "iframe", "src": f"https://player.vimeo.com/video/{m.group(1)}"}

    # Google Drive : /file/d/ID/view (ou ?id=ID) -> /file/d/ID/preview
    if hote == "drive.google.com":
        m = _re.search(r"/file/d/([^/]+)", chemin)
        file_id = m.group(1) if m else (_parse_qs(lien.query).get("id") or [None])[0]
        if file_id:
            return {"type": "iframe", "src": f"https://drive.google.com/file/d/{file_id}/preview"}

    # Dailymotion : /video/ID ou dai.ly/ID
    if hote in ("dailymotion.com", "dai.ly"):
        m = _re.search(r"(?:/video/|^/)([A-Za-z0-9]+)", chemin)
        if m:
            return {"type": "iframe", "src": f"https://www.dailymotion.com/embed/video/{m.group(1)}"}

    # Autre lien : on tente de l'intégrer tel quel.
    return {"type": "iframe", "src": url}


class Chapitres(models.Model):
    """Un chapitre (leçon) d'un module : vidéo et/ou support PDF."""

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

    @property
    def video(self):
        """Lecteur prêt à afficher pour la vidéo du chapitre (voir lecteur_video)."""
        return lecteur_video(self.support_video_url)


class Etudiants(models.Model):
    """Compte apprenant. L'authentification est gérée par la session
    (clé « etudiant_id »), le mot de passe est stocké haché dans mot_de_passe.
    """

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=100)
    niveau_etudes = models.CharField(max_length=100)
    mot_de_passe = models.CharField(max_length=128, blank=True, default="")
    photo = models.FileField(upload_to="profils/", null=True, blank=True)
    date_inscription = models.DateTimeField(auto_now_add=True)
    # Bloqué par l'administration : plus aucun accès aux cours, y compris pour
    # les formations acceptées après le blocage.
    est_bloque = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Candidats(models.Model):
    """Candidature d'un étudiant à une formation, pour une vague donnée.

    Une fois acceptée, la candidature représente l'inscription de l'apprenant :
    les paiements, les résultats et les chapitres terminés y sont rattachés.
    Un étudiant ne peut postuler qu'une fois à une même formation.
    """

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
    commentaire_admin = models.TextField(blank=True)  # note interne de l'équipe
    date_decision = models.DateTimeField(null=True, blank=True)  # date d'acceptation/refus

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["etudiant", "formation"],
                name="une_candidature_par_formation",
            )
        ]

    def __str__(self):
        return f"{self.etudiant} — {self.formation}"

    @property
    def est_bloque(self):
        """Le blocage est porté par l'étudiant et vaut pour toutes ses formations."""
        return self.etudiant.est_bloque

    @property
    def a_acces(self):
        """L'étudiant peut suivre les cours : candidature acceptée et accès non bloqué."""
        return self.statut == "accepte" and not self.est_bloque


class Formateurs(models.Model):
    """Profil formateur, relié à un compte Django (auth_user) créé par l'admin.

    Le formateur se connecte sur /connexion-formateur/ et ne voit que les
    formations qui lui sont attribuées.
    """

    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=100)
    actif = models.BooleanField(default=True)  # un formateur inactif ne peut plus se connecter
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
    """Un versement effectué par un apprenant pour une tranche de sa formation."""

    MODE_CHOICES = [
        ("especes", "Espèces"),
        ("mobile_money", "Mobile Money"),
        ("virement", "Virement"),
    ]

    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="paiements")
    # Vague et formation sont copiées depuis la candidature pour filtrer vite.
    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="paiement")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="paiement")
    tranche = models.PositiveSmallIntegerField(help_text="Numéro de la tranche")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField()
    mode = models.CharField(max_length=15, choices=MODE_CHOICES, default="mobile_money")

    def __str__(self):
        return f"Paiement tranche {self.tranche} — {self.montant}"


class Archive(models.Model):
    """Trace de l'archivage d'une vague : une vague archivée ne peut plus être réactivée."""

    configVague = models.ForeignKey(ConfigVague, on_delete=models.CASCADE, related_name="archive")
    date = models.DateTimeField()


class Resultat(models.Model):
    """Résultat final d'un apprenant pour sa formation, avec l'attestation éventuelle."""

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
    """Message affiché dans l'espace de l'étudiant (ex. décision de candidature)."""

    etudiant = models.ForeignKey(Etudiants, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    lien = models.CharField(max_length=255, blank=True)
    lu = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class ChapitreTermine(models.Model):
    """Chapitre marqué comme terminé par un apprenant : sert à calculer sa progression."""

    candidats = models.ForeignKey(Candidats, on_delete=models.CASCADE, related_name="chapitres_termines")
    chapitre = models.ForeignKey(Chapitres, on_delete=models.CASCADE, related_name="termines")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("candidats", "chapitre")]


class Parametre(models.Model):
    """Ancien paramétrage des inscriptions (non utilisé : remplacé par ConfigVague)."""

    Date_ouverture_inscription = models.DateTimeField()
    Date_cloture_inscription = models.DateTimeField()
    Etat = models.CharField(max_length=10, default="Actif")


class Admin(models.Model):
    """Ancien profil administrateur (non utilisé : les admins sont des superusers Django)."""

    telephone = models.CharField(max_length=100, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_profil",
    )

