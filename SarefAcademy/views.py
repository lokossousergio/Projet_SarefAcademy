from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError
from decimal import ROUND_DOWN, Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
import csv
import secrets
import re
from functools import wraps
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from .models import (
    Admin,
    Archive,
    Candidats,
    ChapitreTermine,
    Chapitres,
    ConfigVague,
    Etudiants,
    Formation,
    Formateurs,
    Modules,
    Notification,
    Paiement,
    Parametre,
    Resultat,
)
from django.templatetags.static import static
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .emails import EnvoiEmailErreur, envoyer_email


def mot_de_passe_valide(valeur):
    return len(valeur) >= 8 and any(c.isalpha() for c in valeur) and any(c.isdigit() for c in valeur)


def etudiant_requis(view):
    """Protège une page étudiant avec l'identifiant conservé en session."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        etudiant_id = request.session.get("etudiant_id")
        if not etudiant_id:
            next_url = request.get_full_path()
            if "candidature" in next_url:
                messages.info(request, "Il faut avoir un compte étudiant avant de postuler.")
            else:
                messages.error(request, "Connectez-vous pour accéder à votre espace étudiant.")
            login_url = reverse("connexion-etudiant")
            return redirect(f"{login_url}?next={quote(next_url)}")
        try:
            request.etudiant = Etudiants.objects.get(pk=etudiant_id)
        except Etudiants.DoesNotExist:
            # On retire seulement la connexion étudiant (pas celle de l'admin/formateur).
            request.session.pop("etudiant_id", None)
            messages.error(request, "Votre session a expiré. Veuillez vous reconnecter.")
            login_url = reverse("connexion-etudiant")
            return redirect(f"{login_url}?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)
    return wrapper


# -----------------------------------------------------------------------------
# Sessions séparées par espace
#
# Un navigateur ne peut avoir qu'un seul utilisateur Django connecté (login()).
# Pour qu'un admin, un formateur et un étudiant puissent être connectés en même
# temps dans le même navigateur :
#   - l'admin utilise la connexion Django classique (request.user) ;
#   - le formateur est mémorisé dans ses propres clés de session ;
#   - l'étudiant est mémorisé dans la clé « etudiant_id ».
# Chaque déconnexion ne retire que les clés de son espace.
# -----------------------------------------------------------------------------

SESSION_FORMATEUR_ID = "formateur_user_id"
SESSION_FORMATEUR_HASH = "formateur_auth_hash"
# Clés à conserver quand l'admin se connecte ou se déconnecte (login/logout
# de Django vident la session).
CLES_AUTRES_ESPACES = ("etudiant_id", SESSION_FORMATEUR_ID, SESSION_FORMATEUR_HASH)


def _conserver_autres_espaces(request, action):
    """Exécute login()/logout() de Django sans déconnecter formateur ni étudiant."""
    sauvegarde = {cle: request.session[cle] for cle in CLES_AUTRES_ESPACES if cle in request.session}
    action()
    for cle, valeur in sauvegarde.items():
        request.session[cle] = valeur


def _deconnecter_formateur(request):
    """Retire uniquement la connexion formateur de la session."""
    request.session.pop(SESSION_FORMATEUR_ID, None)
    request.session.pop(SESSION_FORMATEUR_HASH, None)


def _formateur_connecte(request):
    """Retourne le profil du formateur connecté, ou None.

    Vérifie que le compte existe toujours, est actif, et que son mot de passe
    n'a pas changé depuis la connexion (sinon la session est invalidée).
    """
    user_id = request.session.get(SESSION_FORMATEUR_ID)
    if not user_id:
        return None
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or request.session.get(SESSION_FORMATEUR_HASH) != user.get_session_auth_hash():
        return None
    formateur = getattr(user, "profil_formateur", None)
    if formateur is None or not formateur.actif:
        return None
    return formateur


def formateur_requis(view):
    """Laisse entrer uniquement un formateur connecté et actif."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        formateur = _formateur_connecte(request)
        if formateur is None:
            _deconnecter_formateur(request)
            messages.error(request, "Connectez-vous avec un compte formateur actif.")
            return redirect(f"{reverse('connexion-formateur')}?next={quote(request.get_full_path())}")
        request.formateur = formateur
        return view(request, *args, **kwargs)
    return wrapper


def admin_requis(view):
    """Réservé aux administrateurs créés avec « python manage.py createsuperuser »."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Connectez-vous pour accéder à l’administration.")
            return redirect(f"{reverse('connexion-admin')}?next={quote(request.get_full_path())}")
        if not request.user.is_superuser:
            _conserver_autres_espaces(request, lambda: logout(request))
            messages.error(request, "Ce compte n’a pas accès à l’administration.")
            return redirect("connexion-admin")
        return view(request, *args, **kwargs)
    return wrapper


# -----------------------------------------------------------------------------
# Pages publiques
# -----------------------------------------------------------------------------

def index(request):
    return render(request, 'index.html')


def Marketing_digital(request):
    return render(request, 'formations/formation_marketing_digital.html')


def Design_graphique(request):
    return render(request, 'formations/formation_design_graphique.html')


def Montage_video(request):
    return render(request, 'formations/formation_montage_video.html')


def Developpement_web(request):
    return render(request, 'formations/formation_developpement_web.html')


def Archivage_numerique(request):
    return render(request, 'formations/formation_archivage_numerique.html')


def Journalisme_web(request):
    return render(request, 'formations/formation_Journalisme_web.html')


def bourse_de_formation(request):
    return render(request, 'bourse_de_formation.html')


def inscription_valide(request):
    return render(request, 'info.html')


def tunel(request):
    return render(request, 'tunel.html')


# -----------------------------------------------------------------------------
# Authentification et accès aux espaces
# -----------------------------------------------------------------------------

def _authentifier(request):
    """Authentifie avec un nom d'utilisateur ou une adresse e-mail."""
    identifiant = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    User = get_user_model()
    user_cible = User.objects.filter(Q(username__iexact=identifiant) | Q(email__iexact=identifiant)).first()
    username_auth = user_cible.username if user_cible else identifiant
    return authenticate(request, username=username_auth, password=password)


def connexion_formateur(request):
    """Connexion des formateurs (comptes User créés par l'administrateur).

    Le formateur est mémorisé dans ses propres clés de session (et non avec
    login()), pour ne pas déconnecter un admin connecté dans le même navigateur.
    """
    next_url = request.POST.get("next") or request.GET.get("next")
    if not (next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})):
        next_url = None

    # Déjà connecté : on va directement dans l'espace formateur.
    if _formateur_connecte(request):
        return redirect(next_url or 'formateur_dashboard')

    if request.method == 'POST':
        user = _authentifier(request)
        profil = getattr(user, 'profil_formateur', None) if user else None
        if profil is not None and profil.actif:
            request.session.cycle_key()  # nouvel identifiant de session (sécurité)
            request.session[SESSION_FORMATEUR_ID] = user.pk
            request.session[SESSION_FORMATEUR_HASH] = user.get_session_auth_hash()
            return redirect(next_url or 'formateur_dashboard')
        # Même message dans tous les cas : on ne révèle pas si le compte existe
        # ni s'il s'agit d'un autre type de compte (admin, inactif...).
        messages.error(request, "Identifiant ou mot de passe incorrect.")

    return render(request, 'connexion_formateur.html', {"next": next_url or ""})


def connexion_admin(request):
    """Connexion des administrateurs (comptes créés avec createsuperuser)."""
    if request.method == 'POST':
        user = _authentifier(request)
        if user is not None and user.is_superuser:
            # login() peut vider la session : on garde formateur et étudiant connectés.
            _conserver_autres_espaces(request, lambda: login(request, user))
            # Pas de vague en cours : simple alerte, l'accès au tableau de bord reste libre.
            if not ConfigVague.objects.filter(est_courante=True).exists():
                messages.warning(
                    request,
                    "Aucune vague n’est en cours : les candidatures sont fermées. "
                    "Vous pouvez en configurer une depuis « Configurer une vague ».",
                )
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('admin_dashboard')

        messages.error(request, "Identifiant ou mot de passe incorrect.")

    return render(request, 'connexion_admin.html', {"next": request.GET.get('next', '')})


def deconnexion_formateur(request):
    """Déconnecte uniquement le formateur (admin et étudiant restent connectés)."""
    _deconnecter_formateur(request)
    return redirect('connexion-formateur')


def deconnexion_admin(request):
    """Déconnecte uniquement l'admin (formateur et étudiant restent connectés)."""
    _conserver_autres_espaces(request, lambda: logout(request))
    return redirect('connexion-admin')


@formateur_requis
def changer_mot_de_passe(request):
    return redirect('formateur_dashboard')


# -----------------------------------------------------------------------------
# Candidatures
# -----------------------------------------------------------------------------

@etudiant_requis
def candidature_formation(request):
    """Gère l'enregistrement d'une candidature pour l'étudiant connecté."""
    etudiant = request.etudiant

    if request.method == "POST":
        donnees = {
            "formation": request.POST.get("formation", "").strip(),
            "motivation": request.POST.get("motivation", "").strip(),
            "niveau_etudes": request.POST.get("niveau_etudes", "").strip(),
        }
        cv = request.FILES.get("cv")
        erreurs = []

        # 1. Vérification de la vague en cours
        vague_courante = ConfigVague.objects.filter(est_courante=True).first()
        if not vague_courante:
            erreurs.append("Aucune vague n’est en cours. Les candidatures sont fermées.")

        # 2. Vérification de la formation choisie
        if not donnees["formation"].isdigit():
            erreurs.append("Choisissez une formation valide.")
            formation = None
        else:
            formation = Formation.objects.filter(
                pk=donnees["formation"],
                statut="active",
            ).first()
            if not formation:
                erreurs.append("Cette formation n’est pas disponible.")

        # 3. Vérification du niveau d'études
        if not donnees["niveau_etudes"]:
            erreurs.append("Veuillez sélectionner votre niveau d’études.")

        # 4. Vérification de la motivation
        if len(donnees["motivation"]) < 40:
            erreurs.append("Présentez votre motivation en 40 caractères minimum.")
        elif len(donnees["motivation"]) > 255:
            erreurs.append("Votre motivation ne doit pas dépasser 255 caractères.")

        # 5. Vérification du CV (PDF, max 5 Mo)
        if not cv:
            erreurs.append("Ajoutez votre CV au format PDF.")
        elif cv.size > 5 * 1024 * 1024:
            erreurs.append("Le CV ne doit pas dépasser 5 Mo.")
        elif (
            getattr(cv, "content_type", "").lower() != "application/pdf"
            and not cv.name.lower().endswith(".pdf")
        ):
            erreurs.append("Le CV doit être un fichier PDF.")

        # 6. Vérification si déjà postulé à cette formation
        if formation and Candidats.objects.filter(
            etudiant=etudiant,
            formation=formation,
        ).exists():
            erreurs.append("Vous avez déjà postulé à cette formation. Une deuxième candidature n’est pas autorisée.")

        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
            request.session["candidature_form_data"] = donnees
            return redirect("candidature-formation")

        # 7. Enregistrement dans la table Candidats et mise à jour niveau_etudes
        try:
            with transaction.atomic():
                vague_active = ConfigVague.objects.select_for_update().filter(
                    est_courante=True
                ).first()
                if not vague_active:
                    messages.error(request, "La vague vient d’être fermée. Votre candidature n’a pas été envoyée.")
                    request.session["candidature_form_data"] = donnees
                    return redirect("candidature-formation")

                if Candidats.objects.filter(etudiant=etudiant, formation=formation).exists():
                    messages.error(request, "Vous avez déjà postulé à cette formation.")
                    request.session["candidature_form_data"] = donnees
                    return redirect("candidature-formation")

                # Mise à jour du niveau d'études de l'étudiant
                if donnees["niveau_etudes"]:
                    etudiant.niveau_etudes = donnees["niveau_etudes"]
                    etudiant.save(update_fields=["niveau_etudes"])

                Candidats.objects.create(
                    configVague=vague_active,
                    formation=formation,
                    etudiant=etudiant,
                    motif_inscription=donnees["motivation"],
                    cv=cv,
                )

            messages.success(request, "Votre candidature a été envoyée à l’équipe pédagogique.")
            return redirect("etudiant_dashboard")

        except IntegrityError:
            messages.error(request, "Vous avez déjà postulé à cette formation.")
            request.session["candidature_form_data"] = donnees
            return redirect("candidature-formation")

    donnees = request.session.pop("candidature_form_data", None)
    vague_courante = ConfigVague.objects.filter(est_courante=True).first()
    candidatures_existantes = Candidats.objects.filter(
        etudiant=etudiant
    ).select_related("formation", "configVague")
    formations_postulees_ids = list(candidatures_existantes.values_list("formation_id", flat=True))
    formations_deja_choisies = Formation.objects.filter(
        pk__in=formations_postulees_ids
    ).order_by("nom")
    formations_disponibles = Formation.objects.filter(
        statut="active"
    ).exclude(
        pk__in=formations_postulees_ids
    ).order_by("nom")

    toutes_les_formations = Formation.objects.filter(statut="active").order_by("nom")
    toutes_postulees = len(toutes_les_formations) > 0 and len(formations_disponibles) == 0

    if not vague_courante:
        messages.info(request, "Aucune vague n’est en cours. Les candidatures sont fermées pour le moment.")

    return render(request, "bourse_postule/candidature.html", {
        "etudiant": etudiant,
        "vague_courante": vague_courante,
        "toutes_les_formations": toutes_les_formations,
        "formations_postulees_ids": formations_postulees_ids,
        "formations_disponibles": formations_disponibles,
        "formations_deja_choisies": formations_deja_choisies,
        "toutes_postulees": toutes_postulees,
        "donnees": donnees,
    })


def connexion_etudiant(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if not next_url or not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_target = None
    else:
        next_target = next_url

    if request.session.get("etudiant_id"):
        return redirect(next_target or "etudiant_dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        etudiant = Etudiants.objects.filter(email__iexact=email).first()

        # Le mot de passe est vérifié directement sur le profil étudiant.
        if etudiant and etudiant.mot_de_passe and check_password(password, etudiant.mot_de_passe):
            request.session.cycle_key()
            request.session["etudiant_id"] = etudiant.pk
            messages.success(request, f"Connexion réussie. Bon retour{', ' + etudiant.prenom if etudiant.prenom else ''} !")
            if next_target:
                return redirect(next_target)
            return redirect("etudiant_dashboard")

        messages.error(request, "Adresse e-mail ou mot de passe incorrect.")

    return render(request, "Espace_etudiants/connexion.html", {"next": next_target})


def inscription_etudiant(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if not next_url or not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_target = None
    else:
        next_target = next_url

    if request.session.get("etudiant_id"):
        return redirect(next_target or "etudiant_dashboard")

    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        prenom = request.POST.get("prenom", "").strip()
        email = request.POST.get("email", "").strip().lower()
        telephone = request.POST.get("telephone", "").strip()
        password = request.POST.get("password", "")
        niveau_etudes = request.POST.get("niveau_etudes", "").strip() or "Non renseigné"

        # Vérifie l'e-mail déjà utilisé et la règle minimale du mot de passe.
        if Etudiants.objects.filter(email__iexact=email).exists():
            messages.error(request, "Cette adresse e-mail est déjà utilisée.")
        elif not mot_de_passe_valide(password):
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères, une lettre et un chiffre.")
        else:
            etudiant = Etudiants.objects.create(
                nom=nom,
                prenom=prenom,
                email=email,
                telephone=telephone,
                niveau_etudes=niveau_etudes,
                mot_de_passe=make_password(password),
            )
            request.session.cycle_key()
            request.session["etudiant_id"] = etudiant.pk
            messages.success(request, "Votre compte a été créé. Bienvenue sur Saref Academy !")
            if next_target:
                return redirect(next_target)
            return redirect("etudiant_dashboard")

    return render(request, "Espace_etudiants/inscription.html", {"next": next_target})


def deconnexion_etudiant(request):
    request.session.pop("etudiant_id", None)
    messages.success(request, "Vous êtes déconnecté(e).")
    return redirect("connexion-etudiant")


# -----------------------------------------------------------------------------
# Mot de passe oublié : code à 6 chiffres envoyé par e-mail (Brevo)
# -----------------------------------------------------------------------------
RESET_DUREE_MINUTES = 10      # durée de validité du code
RESET_MAX_TENTATIVES = 5      # essais autorisés avant de devoir redemander un code
RESET_DELAI_RENVOI = 60       # secondes minimum entre deux envois
RESET_CLES_SESSION = ("reset_email", "reset_code_hash", "reset_expiration", "reset_attempts", "reset_envoye_le")


def _hash_code(code):
    """Empreinte HMAC du code : le code en clair n'est jamais stocké en session."""
    return salted_hmac("saref.reset_code", code).hexdigest()


def _vider_session_reset(request):
    for key in RESET_CLES_SESSION:
        request.session.pop(key, None)


def _secondes_avant_renvoi(request, email):
    """Secondes restantes avant de pouvoir renvoyer un code à cette adresse (0 si possible)."""
    envoye_le = request.session.get("reset_envoye_le")
    if not envoye_le or request.session.get("reset_email", "").lower() != email.lower():
        return 0
    ecoule = (timezone.now() - datetime.fromisoformat(envoye_le)).total_seconds()
    return max(0, int(RESET_DELAI_RENVOI - ecoule))


def _envoyer_code_reset(request, etudiant):
    """Génère un code, l'envoie par e-mail puis l'enregistre en session.

    Le code n'est mémorisé qu'après un envoi réussi : en cas d'échec, l'ancien
    code éventuel reste valable. Retourne True si l'e-mail est parti.
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    logo_url = request.build_absolute_uri(static("images/logo-saref-512x512.png"))
    # Un logo servi en local (localhost) ne s'affiche pas dans une messagerie.
    if "localhost" in logo_url or "127.0.0.1" in logo_url:
        logo_url = ""

    try:
        envoyer_email(
            destinataire=etudiant.email,
            nom_destinataire=f"{etudiant.prenom} {etudiant.nom}".strip(),
            sujet=f"{code} est votre code de vérification — Saref Academy",
            template="emails/code_verification",
            contexte={
                "code": code,
                "prenom": etudiant.prenom,
                "duree": RESET_DUREE_MINUTES,
                "lien": request.build_absolute_uri(reverse("verifier_code_etudiant")),
                "logo_url": logo_url,
            },
        )
    except EnvoiEmailErreur as exc:
        messages.error(request, str(exc))
        return False

    maintenant = timezone.now()
    request.session["reset_email"] = etudiant.email
    request.session["reset_code_hash"] = _hash_code(code)
    request.session["reset_expiration"] = (maintenant + timedelta(minutes=RESET_DUREE_MINUTES)).isoformat()
    request.session["reset_envoye_le"] = maintenant.isoformat()
    request.session["reset_attempts"] = 0
    return True


def mot_de_passe_oublie(request):
    """Étape 1 : l'étudiant saisit son e-mail, on vérifie le compte et on envoie le code."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        page = "Espace_etudiants/mot_de_passe_oublie.html"

        # 1. Format de l'adresse
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Saisissez une adresse e-mail valide.")
            return render(request, page)

        # 2. L'adresse doit correspondre à un compte étudiant existant
        etudiant = Etudiants.objects.filter(email__iexact=email).first()
        if not etudiant:
            messages.error(request, "Aucun compte étudiant n’est associé à cette adresse e-mail.")
            return render(request, page)

        # 3. Anti-spam : un seul envoi par minute pour la même adresse
        attente = _secondes_avant_renvoi(request, etudiant.email)
        if attente:
            messages.warning(request, f"Un code vient déjà d’être envoyé. Patientez {attente} s avant d’en demander un nouveau.")
            return redirect("verifier_code_etudiant")

        # 4. Envoi via Brevo (les erreurs sont affichées dans la modale)
        if not _envoyer_code_reset(request, etudiant):
            return render(request, page)

        messages.success(request, f"Un code de vérification a été envoyé à {etudiant.email}.")
        return redirect("verifier_code_etudiant")

    return render(request, "Espace_etudiants/mot_de_passe_oublie.html")


def renvoyer_code_etudiant(request):
    """Renvoie un nouveau code à l'adresse déjà saisie (POST uniquement)."""
    email = request.session.get("reset_email")
    if request.method != "POST" or not email:
        return redirect("mot-de-passe-oublie")

    attente = _secondes_avant_renvoi(request, email)
    if attente:
        messages.warning(request, f"Patientez encore {attente} s avant de demander un nouveau code.")
        return redirect("verifier_code_etudiant")

    etudiant = Etudiants.objects.filter(email__iexact=email).first()
    if not etudiant:
        _vider_session_reset(request)
        messages.error(request, "Ce compte n’existe plus. Recommencez la procédure.")
        return redirect("mot-de-passe-oublie")

    if _envoyer_code_reset(request, etudiant):
        messages.success(request, f"Un nouveau code a été envoyé à {etudiant.email}.")
    return redirect("verifier_code_etudiant")


def verifier_code_etudiant(request):
    """Étape 2 : vérification du code puis enregistrement du nouveau mot de passe."""
    # Accès direct sans demande de code en cours : retour à l'étape 1.
    if not request.session.get("reset_code_hash"):
        messages.info(request, "Saisissez d’abord votre adresse e-mail pour recevoir un code.")
        return redirect("mot-de-passe-oublie")

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        tentatives = request.session.get("reset_attempts", 0)
        expiration = datetime.fromisoformat(request.session["reset_expiration"])

        if timezone.now() > expiration:
            _vider_session_reset(request)
            messages.error(request, "Le code a expiré. Demandez-en un nouveau.")
            return redirect("mot-de-passe-oublie")

        if tentatives >= RESET_MAX_TENTATIVES:
            messages.error(request, "Trop de tentatives incorrectes. Demandez un nouveau code.")
        elif not re.fullmatch(r"\d{6}", code):
            messages.error(request, "Le code doit contenir exactement 6 chiffres.")
        elif not constant_time_compare(_hash_code(code), request.session["reset_code_hash"]):
            tentatives += 1
            request.session["reset_attempts"] = tentatives
            restantes = RESET_MAX_TENTATIVES - tentatives
            if restantes:
                messages.error(request, f"Le code saisi est incorrect. Il vous reste {restantes} tentative(s).")
            else:
                messages.error(request, "Trop de tentatives incorrectes. Demandez un nouveau code.")
        elif not mot_de_passe_valide(password):
            messages.error(request, "Le nouveau mot de passe doit contenir 8 caractères au minimum, avec une lettre et un chiffre.")
        elif password != password2:
            messages.error(request, "Les deux mots de passe ne correspondent pas.")
        else:
            etudiant = Etudiants.objects.filter(email__iexact=request.session["reset_email"]).first()
            _vider_session_reset(request)  # code à usage unique
            if not etudiant:
                messages.error(request, "Aucun compte étudiant associé à cette demande.")
                return redirect("mot-de-passe-oublie")
            etudiant.mot_de_passe = make_password(password)
            etudiant.save(update_fields=["mot_de_passe"])
            messages.success(request, "Votre mot de passe a été modifié. Vous pouvez vous connecter.")
            return redirect("connexion-etudiant")

    return render(request, "Espace_etudiants/verifier_code.html", {
        "delai_renvoi": _secondes_avant_renvoi(request, request.session.get("reset_email", "")),
    })


def dashboard_etudiant(request):
    return redirect("etudiant_dashboard")


# -----------------------------------------------------------------------------
# Espace formateur
# -----------------------------------------------------------------------------

@formateur_requis
def formateur_dashboard(request):
    formateur = request.formateur
    formations = formateur.formations.prefetch_related('modules').all()
    return render(request, 'formateur/dashboard.html', {
        'formateur': formateur,
        'formations': formations,
        'nb_formations': formations.count(),
    })


@formateur_requis
def formateur_etudiants(request):
    """Étudiants du formateur, regroupés par formation, vague par vague.

    Deux onglets (paramètre GET « onglet ») :
      - « en_cours » : les étudiants de la vague en cours ;
      - « archives » : les étudiants d'une ancienne vague, choisie avec ?vague=<id>
        (par défaut la plus récente).
    Seules les candidatures acceptées (= étudiants inscrits) sont affichées,
    et uniquement pour les formations attribuées au formateur.
    """
    formateur = request.formateur
    formations = formateur.formations.order_by("nom")
    onglet = request.GET.get("onglet", "en_cours")
    if onglet not in ("en_cours", "archives"):
        onglet = "en_cours"

    vague_courante = ConfigVague.objects.filter(est_courante=True).first()

    # Anciennes vagues où le formateur a eu au moins un étudiant inscrit.
    vagues_passees = ConfigVague.objects.filter(
        candidats__formation__in=formations,
        candidats__statut="accepte",
    ).distinct().order_by("-date_debut")
    if vague_courante:
        vagues_passees = vagues_passees.exclude(pk=vague_courante.pk)
    vagues_passees = list(vagues_passees)

    # Vague affichée selon l'onglet.
    if onglet == "en_cours":
        vague = vague_courante
    else:
        vague_id = request.GET.get("vague", "")
        vague = next((v for v in vagues_passees if str(v.pk) == vague_id), None)
        vague = vague or (vagues_passees[0] if vagues_passees else None)

    # Nombre de chapitres publiés par formation, pour la progression.
    chapitres_par_formation = dict(
        Chapitres.objects.filter(est_active=True, modules__est_active=True, modules__formation__in=formations)
        .values("modules__formation")
        .annotate(n=Count("id"))
        .values_list("modules__formation", "n")
    )

    # Une carte par formation, avec ses étudiants inscrits dans la vague affichée.
    q = request.GET.get("q", "").strip()
    groupes = []
    nb_etudiants = 0
    if vague:
        inscriptions = (
            Candidats.objects.filter(configVague=vague, formation__in=formations, statut="accepte")
            .select_related("etudiant", "formation", "configVague")
            .annotate(nb_termines=Count(
                "chapitres_termines",
                filter=Q(chapitres_termines__chapitre__est_active=True),
                distinct=True,
            ))
            .order_by("etudiant__nom", "etudiant__prenom")
        )
        if q:
            inscriptions = inscriptions.filter(
                Q(etudiant__nom__icontains=q) | Q(etudiant__prenom__icontains=q) | Q(etudiant__email__icontains=q)
            )
        par_formation = {}
        for inscription in inscriptions:
            total = chapitres_par_formation.get(inscription.formation_id, 0)
            inscription.progression = min(round(inscription.nb_termines * 100 / total), 100) if total else 0
            par_formation.setdefault(inscription.formation_id, []).append(inscription)
        for formation in formations:
            etudiants = par_formation.get(formation.pk, [])
            nb_etudiants += len(etudiants)
            groupes.append({
                "formation": formation,
                "etudiants": etudiants,
                # Progression moyenne de la cohorte dans cette formation.
                "progression_moyenne": round(sum(e.progression for e in etudiants) / len(etudiants)) if etudiants else 0,
            })

    return render(request, "formateur/etudiants.html", {
        "formateur": formateur,
        "formations": formations,
        "onglet": onglet,
        "vague": vague,
        "vague_courante": vague_courante,
        "vagues_passees": vagues_passees,
        "groupes": groupes,
        "nb_etudiants": nb_etudiants,
        "filtre_q": q,
    })


@formateur_requis
def formateur_formations(request):
    formateur = request.formateur
    formations = formateur.formations.prefetch_related('modules', 'candidats').order_by('nom')
    return render(request, 'formateur/formations.html', {
        'formateur': formateur,
        'formations': formations,
    })


@formateur_requis
def formateur_formation_detail(request, formation_id):
    formateur = request.formateur
    formation = get_object_or_404(formateur.formations, pk=formation_id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "supprimer_module":
            module = get_object_or_404(
                Modules,
                pk=request.POST.get("module_id"),
                formation=formation,
            )
            titre_module = module.titre
            module.delete()
            messages.success(request, f"Le module « {titre_module} » et ses chapitres ont été supprimés.")

        elif action == "supprimer_chapitre":
            chapitre = get_object_or_404(
                Chapitres,
                pk=request.POST.get("chapitre_id"),
                modules__formation=formation,
            )
            nom_chapitre = chapitre.nom
            chapitre.delete()
            messages.success(request, f"Le chapitre « {nom_chapitre} » a été supprimé.")

        elif action == "ajouter_module":
            titre = request.POST.get("titre", "").strip()
            description = request.POST.get("description", "").strip()
            try:
                ordre = int(request.POST.get("ordre") or formation.modules.count() + 1)
                Modules.objects.create(
                    formation=formation,
                    titre=titre,
                    description=description,
                    ordre=ordre,
                )
                messages.success(request, "Le module a été ajouté à cette formation.")
            except (ValueError, IntegrityError):
                messages.error(request, "Impossible d’ajouter ce module. Vérifiez son ordre.")

        elif action == "modifier_module":
            module = get_object_or_404(
                Modules,
                pk=request.POST.get("module_id"),
                formation=formation,
            )
            try:
                module.titre = request.POST.get("titre", "").strip()
                module.description = request.POST.get("description", "").strip()
                module.ordre = int(request.POST.get("ordre", "1"))
                module.est_active = request.POST.get("est_active") == "1"
                module.save()
                messages.success(request, "Le module a été modifié.")
            except (ValueError, IntegrityError):
                messages.error(request, "Impossible de modifier ce module. Vérifiez son ordre.")

        elif action == "ajouter_chapitre":
            module = get_object_or_404(
                Modules,
                pk=request.POST.get("module"),
                formation=formation,
            )
            pdf = request.FILES.get("support_pdf")
            if pdf and pdf.size > 20 * 1024 * 1024:
                messages.error(request, "Le support PDF ne doit pas dépasser 20 Mo.")
            else:
                try:
                    ordre = module.chapitres.count() + 1
                    Chapitres.objects.create(
                        modules=module,
                        nom=request.POST.get("nom", "").strip(),
                        ordre=ordre,
                        duree=int(request.POST.get("duree", "0")),
                        support_video_url=request.POST.get("support_video_url", "").strip() or None,
                        support_pdf=pdf,
                    )
                    messages.success(request, f"Le chapitre a été ajouté au module « {module.titre} ».")
                except ValueError:
                    messages.error(request, "La durée du chapitre doit être un nombre valide.")

        return redirect("formateur_formation_detail", formation_id=formation.pk)

    modules = formation.modules.prefetch_related("chapitres").all()
    nb_modules = modules.count()
    nb_modules_actifs = modules.filter(est_active=True).count()
    dernier_module = modules.last()
    return render(request, "formateur/formation_detail.html", {
        "formateur": formateur,
        "formation": formation,
        "modules": modules,
        "nb_modules": nb_modules,
        "nb_modules_actifs": nb_modules_actifs,
        "nb_inscrits": formation.candidats.filter(statut="accepte").count(),
        "prochain_ordre_module": dernier_module.ordre + 1 if dernier_module else 1,
        "pourcentage_modules_actifs": round(nb_modules_actifs * 100 / nb_modules) if nb_modules else 0,
        "nb_chapitres": Chapitres.objects.filter(modules__formation=formation).count(),
    })


@formateur_requis
def formateur_chapitre_detail(request, formation_id, chapitre_id):
    formateur = request.formateur
    formation = get_object_or_404(formateur.formations, pk=formation_id)
    chapitre = get_object_or_404(
        Chapitres,
        pk=chapitre_id,
        modules__formation=formation,
    )
    module = chapitre.modules

    if request.method == "POST":
        pdf = request.FILES.get("support_pdf")
        retirer_pdf = request.POST.get("retirer_support_pdf") == "1"
        if pdf and pdf.size > 20 * 1024 * 1024:
            messages.error(request, "Le support PDF ne doit pas dépasser 20 Mo.")
        elif pdf and not getattr(pdf, "content_type", "").startswith("application/pdf"):
            messages.error(request, "Le support doit être un fichier PDF.")
        else:
            try:
                duree = int(request.POST.get("duree", "0"))
                if duree < 1:
                    raise ValueError

                ancien_pdf = chapitre.support_pdf
                chapitre.nom = request.POST.get("nom", "").strip()
                chapitre.duree = duree
                chapitre.description = request.POST.get("description", "").strip()
                chapitre.support_video_url = request.POST.get("support_video_url", "").strip() or None
                chapitre.est_active = request.POST.get("est_active") == "1"

                if pdf:
                    chapitre.support_pdf = pdf
                elif retirer_pdf:
                    chapitre.support_pdf = None
                chapitre.save()

                if ancien_pdf and (pdf or retirer_pdf):
                    ancien_pdf.delete(save=False)
                if retirer_pdf and not pdf:
                    messages.success(request, "Le chapitre a été mis à jour et son PDF a été retiré.")
                else:
                    messages.success(request, "Le chapitre a été mis à jour.")
            except ValueError:
                messages.error(request, "La durée du chapitre doit être un nombre supérieur à zéro.")

        return redirect("formateur_chapitre_detail", formation_id=formation.pk, chapitre_id=chapitre.pk)

    return render(request, "formateur/chapitre_detail.html", {
        "formateur": formateur,
        "formation": formation,
        "formation_id": formation.pk,
        "module": module,
        "chapitre": chapitre,
        "chapitres": module.chapitres.all(),
    })


# -----------------------------------------------------------------------------
# Espace étudiant
# -----------------------------------------------------------------------------

@etudiant_requis
def etudiant_dashboard(request):
    etudiant = request.etudiant
    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    # Formations ouvertes : candidature acceptée et accès non bloqué par l'administration.
    candidatures_acceptees = [c for c in candidatures if c.a_acces]
    return render(request, "etudiant/dashboard.html", {
        "etudiant": etudiant,
        "candidatures": candidatures,
        "candidatures_acceptees": candidatures_acceptees,
    })


@etudiant_requis
def etudiant_formations(request):
    etudiant = request.etudiant
    # Toutes les candidatures de l'étudiant
    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    # IDs des formations déjà postulées (pour ne pas les proposer en "disponibles")
    formations_postulees_ids = candidatures.values_list("formation_id", flat=True)
    # Formations actives auxquelles il n'a pas encore postulé
    formations_disponibles = Formation.objects.filter(statut="active").exclude(pk__in=formations_postulees_ids)
    return render(request, "etudiant/formations.html", {
        "etudiant": etudiant,
        "candidatures": candidatures,
        "formations_disponibles": formations_disponibles,
    })


@etudiant_requis
def etudiant_formation_detail(request, pk):
    etudiant = request.etudiant
    # pk ici est le pk de la Candidature (pas de la Formation)
    candidat = get_object_or_404(Candidats, pk=pk, etudiant=etudiant)
    formation = candidat.formation
    if candidat.est_bloque:
        # Accès bloqué par l'administration : aucun module n'est affiché.
        modules = Modules.objects.none()
    elif candidat.statut == "accepte":
        modules = formation.modules.prefetch_related("chapitres").filter(est_active=True)
    else:
        modules = formation.modules.prefetch_related("chapitres")
    # Chapitres terminés par cet étudiant pour cette candidature
    chapitres_termines_ids = set(
        ChapitreTermine.objects.filter(candidats=candidat).values_list("chapitre_id", flat=True)
    )
    nb_chapitres = Chapitres.objects.filter(modules__formation=formation, est_active=True).count()
    progression = round(len(chapitres_termines_ids) / nb_chapitres * 100) if nb_chapitres else 0
    return render(request, "etudiant/formation_detail.html", {
        "etudiant": etudiant,
        "candidat": candidat,
        "formation": formation,
        "modules": modules,
        "chapitres_termines": chapitres_termines_ids,
        "nb_chapitres": nb_chapitres,
        "progression": progression,
    })


@etudiant_requis
def etudiant_modules(request):
    etudiant = request.etudiant
    # Formations ouvertes : candidature acceptée et accès non bloqué
    # Étudiant bloqué par l'administration : aucun module n'est affiché.
    if etudiant.est_bloque:
        formations_acceptees_ids = set()
        formations_ids = set()
    else:
        formations_acceptees_ids = set(
            etudiant.candidats.filter(statut="accepte").values_list("formation_id", flat=True)
        )
        formations_ids = set(etudiant.candidats.values_list("formation_id", flat=True))
    modules = Modules.objects.filter(
        formation_id__in=formations_ids
    ).select_related("formation").prefetch_related("chapitres").order_by("formation__nom", "ordre")
    return render(request, "etudiant/modules.html", {
        "etudiant": etudiant,
        "modules": modules,
        "formations_acceptees": formations_acceptees_ids,
    })


@etudiant_requis
def etudiant_module_detail(request, pk):
    etudiant = request.etudiant
    module = get_object_or_404(Modules, pk=pk)
    candidat = Candidats.objects.filter(etudiant=etudiant, formation=module.formation).first()
    # Accès refusé si la candidature n'est pas acceptée, si l'accès est bloqué
    # par l'administration ou si le module n'est pas publié.
    if candidat is None or not candidat.a_acces or not module.est_active:
        if candidat is not None and candidat.est_bloque:
            messages.error(request, "Votre accès à cette formation a été bloqué par l’administration.")
        else:
            messages.error(request, "Ce module n’est pas accessible.")
        return redirect("etudiant_modules")
    # Chapitre à afficher (passé en paramètre GET)
    chapitre_pk = request.GET.get("chapitre")
    if chapitre_pk:
        chapitre = get_object_or_404(Chapitres, pk=chapitre_pk, modules=module, est_active=True)
    else:
        chapitre = module.chapitres.filter(est_active=True).first()
    # Marquer comme terminé si demandé
    if chapitre and request.method == "POST" and request.POST.get("action") == "terminer":
        ChapitreTermine.objects.get_or_create(candidats=candidat, chapitre=chapitre)
        return redirect(f"{request.path}?chapitre={chapitre.pk}")
    # Chapitres terminés pour la navigation
    chapitres_termines_ids = set(
        ChapitreTermine.objects.filter(candidats=candidat).values_list("chapitre_id", flat=True)
    )
    chapitres = module.chapitres.filter(est_active=True)
    return render(request, "etudiant/chapitre_detail.html", {
        "etudiant": etudiant,
        "candidat": candidat,
        "module": module,
        "chapitre": chapitre,
        "chapitres": chapitres,
        "chapitres_termines": chapitres_termines_ids,
    })


@etudiant_requis
def etudiant_paiements(request):
    etudiant = request.etudiant
    candidatures_acceptees = etudiant.candidats.filter(
        statut="accepte"
    ).select_related("formation", "configVague").prefetch_related("paiements")
    # Tous les paiements de l'étudiant
    paiements = Paiement.objects.filter(
        candidats__etudiant=etudiant
    ).select_related("formation", "candidats__configVague").order_by("-date")
    # Montant dû = somme des prix des formations acceptées
    montant_du = sum(c.formation.prix for c in candidatures_acceptees)
    total_paye = paiements.aggregate(total=Sum("montant"))["total"] or 0
    reste_a_payer = max(montant_du - total_paye, 0)
    return render(request, "etudiant/paiements.html", {
        "etudiant": etudiant,
        "candidatures_acceptees": candidatures_acceptees,
        "paiements": paiements,
        "montant_du": montant_du,
        "total_paye": total_paye,
        "reste_a_payer": reste_a_payer,
    })


@etudiant_requis
def etudiant_profil(request):
    etudiant = request.etudiant
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "modifier_profil":
            nom = request.POST.get("nom", "").strip()
            prenom = request.POST.get("prenom", "").strip()
            telephone = request.POST.get("telephone", "").strip()
            niveau_etudes = request.POST.get("niveau_etudes", "").strip()
            erreurs = []
            if not nom:
                erreurs.append("Le nom est obligatoire.")
            if not prenom:
                erreurs.append("Le prénom est obligatoire.")
            # Validation photo côté serveur
            photo = request.FILES.get("photo")
            if photo:
                types_autorises = ["image/jpeg", "image/png", "image/webp"]
                taille_max = 2 * 1024 * 1024  # 2 Mo
                if photo.content_type not in types_autorises:
                    erreurs.append("Type de fichier non autorisé. Utilisez JPG, PNG ou WEBP.")
                elif photo.size > taille_max:
                    erreurs.append("La photo est trop volumineuse. Taille maximale : 2 Mo.")
            if erreurs:
                for e in erreurs:
                    messages.error(request, e)
            else:
                etudiant.nom = nom
                etudiant.prenom = prenom
                etudiant.telephone = telephone
                etudiant.niveau_etudes = niveau_etudes
                if photo:
                    etudiant.photo = photo
                etudiant.save()
                messages.success(request, "Profil mis à jour avec succès.")
                return redirect("etudiant_profil")
        elif action == "changer_mot_de_passe":
            ancien = request.POST.get("ancien_mot_de_passe", "")
            nouveau = request.POST.get("nouveau_mot_de_passe", "")
            confirmation = request.POST.get("confirmation_mot_de_passe", "")
            if not check_password(ancien, etudiant.mot_de_passe):
                messages.error(request, "L'ancien mot de passe est incorrect.")
            elif not mot_de_passe_valide(nouveau):
                messages.error(request, "Le nouveau mot de passe doit comporter au moins 8 caractères, une lettre et un chiffre.")
            elif nouveau != confirmation:
                messages.error(request, "Les deux nouveaux mots de passe ne correspondent pas.")
            else:
                etudiant.mot_de_passe = make_password(nouveau)
                etudiant.save(update_fields=["mot_de_passe"])
                messages.success(request, "Mot de passe modifié avec succès.")
                return redirect("etudiant_profil")
    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    return render(request, "etudiant/profil.html", {
        "etudiant": etudiant,
        "candidatures": candidatures,
    })


@etudiant_requis
def etudiant_parametres(request):
    return render(request, "etudiant/parametres.html", {"etudiant": request.etudiant})


# -----------------------------------------------------------------------------
# Espace administration
# -----------------------------------------------------------------------------

@admin_requis
def admin_configuration_initiale(request):
    return render(request, 'administration/configuration_initiale.html')


@admin_requis
def admin_configuration_vague(request):
    if request.method == "POST":
        # Récupère les valeurs du formulaire.
        donnees = {
            "nom": request.POST.get("nom", "").strip(),
            "annee_academique": request.POST.get("annee_academique", "").strip(),
            "date_debut": request.POST.get("date_debut", "").strip(),
            "date_fin": request.POST.get("date_fin", "").strip(),
            "est_active": request.POST.get("est_active") == "on",
        }
        erreurs = []

        # Vérifie le nom et l'année académique.
        if not donnees["nom"]:
            erreurs.append("Le nom de la vague est obligatoire.")
        elif len(donnees["nom"]) > 100:
            erreurs.append("Le nom de la vague ne doit pas dépasser 100 caractères.")
        elif ConfigVague.objects.filter(nom__iexact=donnees["nom"]).exists():
            erreurs.append("Ce nom de vague est déjà utilisé. Choisissez un autre nom.")
        annee = re.fullmatch(r"(\d{4})-(\d{4})", donnees["annee_academique"])
        if not annee or int(annee.group(2)) != int(annee.group(1)) + 1:
            erreurs.append("L’année doit être au format AAAA-AAAA, par exemple 2026-2027.")

        # Convertit les dates et vérifie leur ordre.
        try:
            date_debut = datetime.strptime(donnees["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(donnees["date_fin"], "%Y-%m-%d").date()
            if date_fin < date_debut:
                erreurs.append("La date de clôture doit être égale ou postérieure à la date d’ouverture.")
        except ValueError:
            erreurs.append("Choisissez une date d’ouverture et une date de clôture valides.")

        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
            request.session["configuration_vague_data"] = donnees
            return redirect("admin_configuration_vague")

        confirmation_remplacement = request.POST.get("confirmer_remplacement") == "1"
        confirmation_requise = False

        try:
            with transaction.atomic():
                # Verrouille la vague actuelle pendant le remplacement.
                vague_actuelle = ConfigVague.objects.select_for_update().filter(
                    est_courante=True
                ).first()

                # Demande toujours une confirmation avant d’archiver l’ancienne.
                if donnees["est_active"] and vague_actuelle and not confirmation_remplacement:
                    confirmation_requise = True
                else:
                    if donnees["est_active"] and vague_actuelle:
                        vague_actuelle.est_courante = False
                        vague_actuelle.save(update_fields=["est_courante"])

                        # Garde une trace de la date d’archivage.
                        if not Archive.objects.filter(configVague=vague_actuelle).exists():
                            Archive.objects.create(
                                configVague=vague_actuelle,
                                date=timezone.now(),
                            )

                    ConfigVague.objects.create(
                        nom=donnees["nom"],
                        annee_academique=donnees["annee_academique"],
                        date_debut=timezone.make_aware(
                            datetime.combine(date_debut, datetime.min.time())
                        ),
                        date_fin=timezone.make_aware(
                            datetime.combine(date_fin, datetime.max.time())
                        ),
                        est_courante=donnees["est_active"],
                    )

            if confirmation_requise:
                request.session["configuration_vague_data"] = donnees
                request.session["confirmation_remplacement_vague"] = True
                return redirect("admin_configuration_vague")

            messages.success(request, f"La vague « {donnees['nom']} » a été enregistrée.")
            return redirect("admin_dashboard")
        except IntegrityError:
            if ConfigVague.objects.filter(nom__iexact=donnees["nom"]).exists():
                messages.error(request, "Ce nom de vague est déjà utilisé. Choisissez un autre nom.")
            else:
                messages.error(request, "La vague n’a pas pu être enregistrée. Réessayez.")
            request.session["configuration_vague_data"] = donnees
            return redirect("admin_configuration_vague")

    donnees = request.session.pop("configuration_vague_data", None)
    confirmation_remplacement = request.session.pop("confirmation_remplacement_vague", False)
    vague_courante = ConfigVague.objects.filter(est_courante=True).first()
    return render(request, "administration/configuration_vague.html", {
        "donnees": donnees,
        "vague_courante": vague_courante,
        "confirmation_remplacement": confirmation_remplacement,
        "noms_vagues": list(ConfigVague.objects.values_list("nom", flat=True)),
    })


@admin_requis
def admin_dashboard(request):
    vague_courante = ConfigVague.objects.filter(est_courante=True).first()
    if vague_courante:
        candidatures = Candidats.objects.filter(configVague=vague_courante)
        nb_candidatures = candidatures.count()
        nb_candidatures_attente = candidatures.filter(statut="en_attente").count()
        nb_etudiants = candidatures.values("etudiant_id").distinct().count()
        candidatures_recentes = candidatures.select_related(
            "etudiant", "formation"
        ).order_by("-date_candidature")[:5]
    else:
        nb_candidatures = 0
        nb_candidatures_attente = 0
        nb_etudiants = 0
        candidatures_recentes = Candidats.objects.none()

    return render(request, 'administration/dashboard.html', {
        "vague_courante": vague_courante,
        "nb_candidatures": nb_candidatures,
        "nb_candidatures_attente": nb_candidatures_attente,
        "nb_etudiants": nb_etudiants,
        "candidatures_recentes": candidatures_recentes,
        "nb_formations": Formation.objects.count(),
        "nb_formations_actives": Formation.objects.filter(statut="active").count(),
        "nb_formateurs_actifs": Formateurs.objects.filter(actif=True).count(),
    })


@admin_requis
def admin_candidatures(request):
    vague_courante = ConfigVague.objects.filter(est_courante=True).first()
    formations = Formation.objects.all().order_by("nom")

    # Seules les candidatures de la vague en cours sont gérées ici. Celles des
    # vagues passées se consultent depuis « Vagues & années ».
    if vague_courante:
        candidatures_qs = Candidats.objects.filter(configVague=vague_courante)
    else:
        candidatures_qs = Candidats.objects.none()
    candidatures_qs = candidatures_qs.select_related("etudiant", "formation", "configVague")

    # Statistiques globales en une seule requête SQL optimale
    stats = candidatures_qs.aggregate(
        nb_total=Count("id"),
        nb_attente=Count("id", filter=Q(statut="en_attente")),
        nb_accepte=Count("id", filter=Q(statut="accepte")),
        nb_refuse=Count("id", filter=Q(statut="refuse")),
    )

    # Filtres GET
    statut = request.GET.get("statut", "").strip()
    if statut in ["attente", "en_attente"]:
        candidatures_qs = candidatures_qs.filter(statut="en_attente")
    elif statut in ["accepte", "refuse"]:
        candidatures_qs = candidatures_qs.filter(statut=statut)

    q = request.GET.get("q", "").strip()
    if q:
        candidatures_qs = candidatures_qs.filter(
            Q(etudiant__nom__icontains=q)
            | Q(etudiant__prenom__icontains=q)
            | Q(etudiant__email__icontains=q)
        )

    formation_filtre = request.GET.get("formation", "").strip()
    if formation_filtre:
        candidatures_qs = candidatures_qs.filter(formation__nom__icontains=formation_filtre)

    tri = request.GET.get("tri", "").strip()
    if tri in ["nom", "Nom (A–Z)"]:
        candidatures_qs = candidatures_qs.order_by("etudiant__nom", "etudiant__prenom")
    else:
        candidatures_qs = candidatures_qs.order_by("-date_candidature")

    # Export CSV
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="candidatures.csv"'
        writer = csv.writer(response)
        writer.writerow(["Nom", "Prénom", "Email", "Téléphone", "Formation", "Vague", "Statut", "Date de candidature"])
        for c in candidatures_qs:
            writer.writerow([
                c.etudiant.nom,
                c.etudiant.prenom,
                c.etudiant.email,
                c.etudiant.telephone,
                c.formation.nom,
                c.configVague.nom,
                c.get_statut_display(),
                c.date_candidature.strftime("%d/%m/%Y %H:%M") if c.date_candidature else "",
            ])
        return response

    # Pagination optimale
    paginator = Paginator(candidatures_qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "administration/candidatures.html", {
        "candidatures": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "vague_courante": vague_courante,
        "formations": formations,
        "nb_total": stats["nb_total"] or 0,
        "nb_attente": stats["nb_attente"] or 0,
        "nb_accepte": stats["nb_accepte"] or 0,
        "nb_refuse": stats["nb_refuse"] or 0,
        "filtre_statut": statut,
        "filtre_q": q,
        "filtre_formation": formation_filtre,
        "filtre_tri": tri,
    })


@admin_requis
def admin_candidature_detail(request, pk):
    candidat = get_object_or_404(
        Candidats.objects.select_related("etudiant", "formation", "configVague"),
        pk=pk,
    )

    # Les décisions ne sont possibles que pour la vague en cours.
    decision_possible = candidat.configVague.est_courante

    if request.method == "POST":
        if not decision_possible:
            messages.warning(
                request,
                "Cette candidature appartient à une vague qui n’est plus en cours : "
                "elle est consultable mais ne peut plus être modifiée.",
            )
            return redirect("admin_candidature_detail", pk=candidat.pk)

        nouveau_statut = request.POST.get("statut", "").strip()
        commentaire = request.POST.get("commentaire_admin", "").strip()

        with transaction.atomic():
            if nouveau_statut in ["accepte", "refuse", "en_attente"]:
                candidat.statut = nouveau_statut
                candidat.date_decision = timezone.now()

            candidat.commentaire_admin = commentaire
            candidat.save()

            if nouveau_statut in ["accepte", "refuse"]:
                statut_texte = "acceptée" if nouveau_statut == "accepte" else "refusée"
                Notification.objects.create(
                    etudiant=candidat.etudiant,
                    message=f"Votre candidature pour la formation « {candidat.formation.nom} » a été {statut_texte}.",
                    lien="/etudiant/formations/",
                )

        messages.success(request, f"La décision pour la candidature de {candidat.etudiant} a été enregistrée.")
        return redirect("admin_candidature_detail", pk=candidat.pk)

    autres_candidatures = Candidats.objects.filter(
        etudiant=candidat.etudiant
    ).exclude(pk=candidat.pk).select_related("formation", "configVague").order_by("-date_candidature")

    return render(request, "administration/candidature_detail.html", {
        "candidat": candidat,
        "autres_candidatures": autres_candidatures,
        "decision_possible": decision_possible,
        "pk": pk,
    })


@admin_requis
def admin_etudiants(request):
    formations = Formation.objects.all().order_by("nom")

    # Statistiques globales
    total_etudiants = Etudiants.objects.count()
    une_semaine = timezone.now() - timedelta(days=7)
    actifs_semaine = Etudiants.objects.filter(
        Q(candidats__chapitres_termines__date__gte=une_semaine)
        | Q(date_inscription__gte=une_semaine)
    ).distinct().count()

    avec_candidature_count = Etudiants.objects.filter(candidats__isnull=False).distinct().count()
    sans_candidature_count = total_etudiants - avec_candidature_count

    bloques_count = Etudiants.objects.filter(est_bloque=True).count()

    etudiants_qs = Etudiants.objects.annotate(
        nb_candidatures=Count("candidats", distinct=True),
    )

    # Filtre Type (Avec candidature vs Sans candidature)
    filtre_type = request.GET.get("type", "").strip()
    if filtre_type == "avec":
        etudiants_qs = etudiants_qs.filter(nb_candidatures__gt=0)
    elif filtre_type == "sans":
        etudiants_qs = etudiants_qs.filter(nb_candidatures=0)

    # Filtres GET
    q = request.GET.get("q", "").strip()
    if q:
        etudiants_qs = etudiants_qs.filter(
            Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(email__icontains=q)
            | Q(telephone__icontains=q)
        )

    formation_filtre = request.GET.get("formation", "").strip()
    if formation_filtre:
        etudiants_qs = etudiants_qs.filter(candidats__formation__nom__icontains=formation_filtre)

    statut_filtre = request.GET.get("statut", "").strip().lower()
    if statut_filtre in ["bloqué", "bloque"]:
        etudiants_qs = etudiants_qs.filter(est_bloque=True)
    elif statut_filtre == "actif":
        etudiants_qs = etudiants_qs.filter(est_bloque=False)

    etudiants_qs = etudiants_qs.distinct().order_by("-date_inscription")

    # Export CSV si demandé
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        nom_fichier = f"etudiants_{filtre_type or 'tous'}.csv"
        response["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
        writer = csv.writer(response)
        writer.writerow(["Nom", "Prénom", "Email", "Téléphone", "Niveau d'études", "Candidatures", "Inscrit le", "Statut"])
        for e in etudiants_qs:
            statut = "Bloqué" if e.est_bloque else "Actif"
            writer.writerow([
                e.nom,
                e.prenom,
                e.email,
                e.telephone,
                e.niveau_etudes,
                e.nb_candidatures,
                e.date_inscription.strftime("%d/%m/%Y") if e.date_inscription else "",
                statut,
            ])
        return response

    paginator = Paginator(etudiants_qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "administration/etudiants.html", {
        "etudiants": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "formations": formations,
        "total_etudiants": total_etudiants,
        "avec_candidature_count": avec_candidature_count,
        "sans_candidature_count": sans_candidature_count,
        "actifs_semaine": actifs_semaine,
        "bloques_count": bloques_count,
        "filtre_type": filtre_type,
        "filtre_q": q,
        "filtre_formation": formation_filtre,
        "filtre_statut": statut_filtre,
    })


@admin_requis
def admin_etudiant_detail(request, pk):
    etudiant = get_object_or_404(Etudiants, pk=pk)

    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    est_bloque = etudiant.est_bloque

    if request.method == "POST":
        # Le blocage porte sur l'étudiant : il s'applique à toutes ses
        # formations, y compris celles acceptées plus tard.
        nouveau_blocage = not est_bloque
        etudiant.est_bloque = nouveau_blocage
        etudiant.save(update_fields=["est_bloque"])
        if nouveau_blocage:
            messages.warning(request, f"L’accès de {etudiant.prenom} {etudiant.nom} a été bloqué.")
        else:
            messages.success(request, f"L’accès de {etudiant.prenom} {etudiant.nom} a été rétabli.")
        return redirect("admin_etudiant_detail", pk=etudiant.pk)

    nb_candidatures = candidatures.count()
    nb_acceptees = candidatures.filter(statut="accepte").count()

    # Paiements et reste à payer
    paiements = Paiement.objects.filter(candidats__in=candidatures).select_related("formation", "configVague").order_by("-date")
    total_paye = paiements.aggregate(total=Sum("montant"))["total"] or Decimal(0)
    total_du = sum((cand.formation.prix for cand in candidatures if cand.statut == "accepte"), Decimal(0))
    reste_a_payer = max(Decimal(0), total_du - total_paye)

    # Lien WhatsApp nettoyé
    tel_digits = "".join(c for c in etudiant.telephone if c.isdigit())
    if tel_digits.startswith("00"):
        tel_digits = tel_digits[2:]
    elif not tel_digits.startswith("229") and len(tel_digits) <= 10:
        tel_digits = "229" + tel_digits
    whatsapp_url = f"https://wa.me/{tel_digits}" if tel_digits else "#"

    return render(request, "administration/etudiant_detail.html", {
        "etudiant": etudiant,
        "est_bloque": est_bloque,
        "candidatures": candidatures,
        "nb_candidatures": nb_candidatures,
        "nb_acceptees": nb_acceptees,
        "paiements": paiements,
        "total_paye": total_paye,
        "total_du": total_du,
        "reste_a_payer": reste_a_payer,
        "whatsapp_url": whatsapp_url,
    })


# -----------------------------------------------------------------------------
# Finance et résultats (toujours par vague)
# -----------------------------------------------------------------------------

def _vague_selectionnee(request):
    """Retourne la vague à afficher sur les pages Finance et Résultats.

    Ordre de priorité : la vague demandée dans l'URL (?vague=<id>), sinon la
    vague en cours, sinon la vague la plus récente. Retourne None s'il
    n'existe encore aucune vague.
    """
    vague_id = request.GET.get("vague") or request.POST.get("vague")
    if vague_id and str(vague_id).isdigit():
        vague = ConfigVague.objects.filter(pk=vague_id).first()
        if vague:
            return vague
    return (
        ConfigVague.objects.filter(est_courante=True).first()
        or ConfigVague.objects.order_by("-date_debut").first()
    )


def _liste_vagues():
    """Toutes les vagues (plus récentes d'abord) avec un indicateur « archivée »."""
    vagues = list(ConfigVague.objects.order_by("-date_debut"))
    archivees = set(Archive.objects.values_list("configVague_id", flat=True))
    for v in vagues:
        v.est_archivee = v.pk in archivees
    return vagues


def _redirection_vague(nom_url, vague):
    """Redirige vers une page admin en conservant la vague sélectionnée."""
    return redirect(f"{reverse(nom_url)}?vague={vague.pk}")


@admin_requis
def admin_finance(request):
    """Suivi des paiements des apprenants d'une vague.

    GET  : indicateurs, plans de paiement par formation et liste des
           inscriptions (candidatures acceptées) avec payé / reste.
    POST : enregistrement d'un paiement (refusé si la vague est archivée).
    """
    vague = _vague_selectionnee(request)
    vagues = _liste_vagues()
    est_archivee = bool(vague) and Archive.objects.filter(configVague=vague).exists()

    # --- Enregistrement d'un paiement -----------------------------------------
    if request.method == "POST" and vague:
        if est_archivee:
            messages.warning(request, "Cette vague est archivée : aucun paiement ne peut plus être enregistré.")
            return _redirection_vague("admin_finance", vague)

        candidat = Candidats.objects.filter(
            pk=request.POST.get("candidat"), configVague=vague, statut="accepte"
        ).select_related("formation", "etudiant").first()
        erreurs = []
        if candidat is None:
            erreurs.append("Choisissez un étudiant inscrit à cette vague.")

        # Contrôle de la tranche : entre 1 et le nombre de tranches de la formation.
        try:
            tranche = int(request.POST.get("tranche", ""))
        except ValueError:
            tranche = 0
        if candidat and not 1 <= tranche <= (candidat.formation.nb_tranches or 1):
            erreurs.append("Le numéro de tranche n’est pas valide pour cette formation.")

        # Contrôle du montant : positif et pas plus que le reste à payer.
        try:
            montant = Decimal(request.POST.get("montant", "").replace(" ", "").replace(",", "."))
        except Exception:
            montant = Decimal("0")
        if montant <= 0:
            erreurs.append("Le montant doit être supérieur à 0.")
        elif candidat:
            deja_paye = candidat.paiements.aggregate(total=Sum("montant"))["total"]
            reste = _situation_financiere(candidat, deja_paye)["reste"]
            if montant > reste:
                erreurs.append(f"Le montant dépasse le reste à payer ({reste:,.0f} FCFA).".replace(",", " "))

        mode = request.POST.get("mode", "")
        if mode not in dict(Paiement.MODE_CHOICES):
            erreurs.append("Choisissez un mode de paiement.")

        # Date du paiement (aujourd'hui si non renseignée).
        date_texte = request.POST.get("date", "")
        try:
            date_paiement = timezone.make_aware(datetime.strptime(date_texte, "%Y-%m-%d")) if date_texte else timezone.now()
        except ValueError:
            erreurs.append("La date du paiement n’est pas valide.")
            date_paiement = None

        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
        else:
            Paiement.objects.create(
                candidats=candidat,
                configVague=vague,
                formation=candidat.formation,
                tranche=tranche,
                montant=montant,
                date=date_paiement,
                mode=mode,
            )
            messages.success(
                request,
                f"Paiement de {montant:,.0f} FCFA enregistré pour {candidat.etudiant} (tranche {tranche}).".replace(",", " "),
            )
        return _redirection_vague("admin_finance", vague)

    # --- Lecture : inscriptions de la vague avec leur situation financière ----
    inscriptions = []
    if vague:
        inscriptions = list(
            Candidats.objects.filter(configVague=vague, statut="accepte")
            .select_related("etudiant", "formation")
            .annotate(total_paye=Coalesce(Sum("paiements__montant"), Decimal("0")))
            .order_by("etudiant__nom", "etudiant__prenom")
        )
    for inscription in inscriptions:
        inscription.finances = _situation_financiere(inscription, inscription.total_paye)
        # Statut financier : soldé, partiel (au moins un versement) ou aucun paiement.
        if inscription.finances["solde"]:
            inscription.statut_finance = "solde"
        elif inscription.finances["total_paye"] > 0:
            inscription.statut_finance = "partiel"
        else:
            inscription.statut_finance = "aucun"

    # Indicateurs calculés sur toute la vague (avant les filtres).
    stats = {
        "total": len(inscriptions),
        "encaisse": sum((i.finances["total_paye"] for i in inscriptions), Decimal("0")),
        "reste": sum((i.finances["reste"] for i in inscriptions), Decimal("0")),
        "solde": sum(1 for i in inscriptions if i.statut_finance == "solde"),
        "partiel": sum(1 for i in inscriptions if i.statut_finance == "partiel"),
        "aucun": sum(1 for i in inscriptions if i.statut_finance == "aucun"),
    }

    # Plans de paiement des formations présentes dans la vague.
    plans = []
    for formation in sorted({i.formation for i in inscriptions}, key=lambda f: f.nom):
        nb = formation.nb_tranches or 1
        plans.append({
            "formation": formation,
            "nb_tranches": nb,
            "montant_tranche": (formation.prix / nb) if formation.prix else Decimal("0"),
            "nb_inscrits": sum(1 for i in inscriptions if i.formation_id == formation.pk),
        })

    # Inscriptions qui peuvent encore recevoir un paiement (pour le formulaire).
    a_encaisser = [i for i in inscriptions if not i.finances["solde"]]

    # Filtres (statut + recherche) puis pagination.
    filtre_statut = request.GET.get("statut", "")
    q = request.GET.get("q", "").strip()
    liste = inscriptions
    if filtre_statut in ("solde", "partiel", "aucun"):
        liste = [i for i in liste if i.statut_finance == filtre_statut]
    if q:
        q_min = q.lower()
        liste = [
            i for i in liste
            if q_min in f"{i.etudiant.prenom} {i.etudiant.nom} {i.etudiant.email} {i.formation.nom}".lower()
        ]
    page_obj = Paginator(liste, 20).get_page(request.GET.get("page"))

    return render(request, "administration/finance.html", {
        "vague": vague,
        "vagues": vagues,
        "est_archivee": est_archivee,
        "inscriptions": page_obj,
        "page_obj": page_obj,
        "stats": stats,
        "plans": plans,
        "a_encaisser": a_encaisser,
        "modes": Paiement.MODE_CHOICES,
        "filtre_statut": filtre_statut,
        "filtre_q": q,
        "aujourdhui": timezone.localdate(),
    })


@admin_requis
def admin_resultats(request):
    """Résultats finaux et attestations des apprenants d'une vague.

    GET  : progression de chaque inscription, décision et attestation.
    POST : saisie ou modification d'un résultat (+ dépôt de l'attestation PDF).
           Refusé si la vague est archivée.
    """
    vague = _vague_selectionnee(request)
    vagues = _liste_vagues()
    est_archivee = bool(vague) and Archive.objects.filter(configVague=vague).exists()

    # --- Saisie / modification d'un résultat ----------------------------------
    if request.method == "POST" and vague:
        if est_archivee:
            messages.warning(request, "Cette vague est archivée : les résultats ne peuvent plus être modifiés.")
            return _redirection_vague("admin_resultats", vague)

        candidat = Candidats.objects.filter(
            pk=request.POST.get("candidat"), configVague=vague, statut="accepte"
        ).select_related("etudiant", "formation").first()
        decision = request.POST.get("decision", "")
        attestation = request.FILES.get("attestation")

        erreurs = []
        if candidat is None:
            erreurs.append("Choisissez un étudiant inscrit à cette vague.")
        if decision not in dict(Resultat.DECISION_CHOICES):
            erreurs.append("Choisissez une décision.")
        # L'attestation est facultative mais doit être un PDF de 5 Mo maximum.
        if attestation:
            if not attestation.name.lower().endswith(".pdf"):
                erreurs.append("L’attestation doit être un fichier PDF.")
            elif attestation.size > 5 * 1024 * 1024:
                erreurs.append("L’attestation ne doit pas dépasser 5 Mo.")
        if attestation and decision != "admis":
            erreurs.append("Une attestation ne peut être déposée que pour un étudiant admis.")

        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
            return _redirection_vague("admin_resultats", vague)

        # Un seul résultat par inscription : on met à jour s'il existe déjà.
        resultat = candidat.resultat.order_by("-pk").first()
        if resultat is None:
            resultat = Resultat(candidats=candidat, configVague=vague)
        resultat.decision = decision
        ancienne_attestation = resultat.attestation if resultat.pk else None
        if attestation:
            resultat.attestation = attestation
        elif decision != "admis":
            # Plus d'attestation si l'étudiant n'est plus admis.
            resultat.attestation = None
        resultat.save()
        # Supprime du disque l'ancien PDF s'il a été remplacé ou retiré.
        if ancienne_attestation and ancienne_attestation.name != (resultat.attestation.name if resultat.attestation else None):
            ancienne_attestation.storage.delete(ancienne_attestation.name)

        # Prévient l'étudiant dans son espace.
        Notification.objects.create(
            etudiant=candidat.etudiant,
            message=f"Votre résultat pour « {candidat.formation.nom} » est disponible : {resultat.get_decision_display()}.",
            lien="/etudiant/formations/",
        )
        messages.success(request, f"Résultat enregistré pour {candidat.etudiant} : {resultat.get_decision_display()}.")
        return _redirection_vague("admin_resultats", vague)

    # --- Lecture : progression et résultat de chaque inscription --------------
    inscriptions = []
    if vague:
        inscriptions = list(
            Candidats.objects.filter(configVague=vague, statut="accepte")
            .select_related("etudiant", "formation")
            .prefetch_related("resultat")
            .annotate(nb_termines=Count(
                "chapitres_termines",
                filter=Q(chapitres_termines__chapitre__est_active=True),
                distinct=True,
            ))
            .order_by("formation__nom", "etudiant__nom", "etudiant__prenom")
        )

    # Nombre de chapitres publiés par formation (pour calculer la progression).
    chapitres_par_formation = dict(
        Chapitres.objects.filter(est_active=True, modules__est_active=True)
        .values("modules__formation")
        .annotate(n=Count("id"))
        .values_list("modules__formation", "n")
    )
    for inscription in inscriptions:
        total = chapitres_par_formation.get(inscription.formation_id, 0)
        inscription.progression = min(round(inscription.nb_termines * 100 / total), 100) if total else 0
        resultats = list(inscription.resultat.all())
        inscription.dernier_resultat = resultats[-1] if resultats else None
        inscription.statut_resultat = inscription.dernier_resultat.decision if inscription.dernier_resultat else "attente"

    stats = {
        "total": len(inscriptions),
        "admis": sum(1 for i in inscriptions if i.statut_resultat == "admis"),
        "non_admis": sum(1 for i in inscriptions if i.statut_resultat == "non_admis"),
        "abandon": sum(1 for i in inscriptions if i.statut_resultat == "abandon"),
        "attente": sum(1 for i in inscriptions if i.statut_resultat == "attente"),
        # Admis sans attestation déposée.
        "attestations_manquantes": sum(
            1 for i in inscriptions
            if i.statut_resultat == "admis" and not i.dernier_resultat.attestation
        ),
    }

    filtre_statut = request.GET.get("statut", "")
    q = request.GET.get("q", "").strip()
    liste = inscriptions
    if filtre_statut in ("attente", "admis", "non_admis", "abandon"):
        liste = [i for i in liste if i.statut_resultat == filtre_statut]
    if q:
        q_min = q.lower()
        liste = [
            i for i in liste
            if q_min in f"{i.etudiant.prenom} {i.etudiant.nom} {i.etudiant.email} {i.formation.nom}".lower()
        ]
    page_obj = Paginator(liste, 20).get_page(request.GET.get("page"))

    return render(request, "administration/resultats.html", {
        "vague": vague,
        "vagues": vagues,
        "est_archivee": est_archivee,
        "inscriptions": page_obj,
        "page_obj": page_obj,
        "toutes_inscriptions": inscriptions,
        "stats": stats,
        "decisions": Resultat.DECISION_CHOICES,
        "filtre_statut": filtre_statut,
        "filtre_q": q,
    })


@admin_requis
def admin_organisation(request):
    return render(request, 'administration/organisation.html')


@admin_requis
def admin_formations(request):
    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        description = request.POST.get("description", "").strip()
        duree_raw = request.POST.get("duree", "").strip()
        prix_raw = request.POST.get("prix", "0").strip().replace(" ", "").replace(",", ".")
        tranches_raw = request.POST.get("nb_tranches", "3").strip()
        statut = request.POST.get("statut", "active").strip()
        photo = request.FILES.get("photo")

        erreurs = []
        if not nom or len(nom) < 2:
            erreurs.append("Le nom de la formation doit comporter au moins 2 caractères.")

        try:
            duree = int(duree_raw)
            if duree < 1:
                erreurs.append("La durée doit être d’au moins 1 mois.")
        except (ValueError, TypeError):
            erreurs.append("La durée doit être un nombre entier valide.")
            duree = 1

        try:
            prix = Decimal(prix_raw)
            if prix < 0:
                erreurs.append("Le prix ne peut pas être négatif.")
        except (InvalidOperation, TypeError):
            erreurs.append("Le prix doit être un montant numérique valide.")
            prix = Decimal("0")

        try:
            nb_tranches = int(tranches_raw)
            if nb_tranches < 1:
                erreurs.append("Le nombre de tranches doit être d’au moins 1.")
        except (ValueError, TypeError):
            erreurs.append("Le nombre de tranches doit être un nombre entier valide.")
            nb_tranches = 1

        if photo and photo.size > 2 * 1024 * 1024:
            erreurs.append("L’image de couverture ne doit pas dépasser 2 Mo.")
        elif photo and not photo.content_type.startswith("image/"):
            erreurs.append("Le fichier de couverture doit être une image valide.")

        if erreurs:
            for err in erreurs:
                messages.error(request, err)
        else:
            formation = Formation.objects.create(
                nom=nom,
                duree=duree,
                prix=prix,
                nb_tranches=nb_tranches,
                description=description,
                photo=photo,
                statut=statut,
            )
            messages.success(request, f"La formation « {formation.nom} » a été créée avec succès.")
            return redirect("admin_formations")

    formations = Formation.objects.all().order_by("nom")
    return render(request, "administration/formations.html", {"formations": formations})


@admin_requis
def admin_formation_detail(request, pk):
    formation = get_object_or_404(Formation, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")

        # Le formulaire d'édition garde ses valeurs si une validation échoue.
        if action == "modifier_formation":
            # Récupère les champs saisis pour les remettre dans la modale en cas d'erreur.
            edit_data = {
                "nom": request.POST.get("nom", "").strip(),
                "duree": request.POST.get("duree", "").strip(),
                "prix": request.POST.get("prix", "").strip(),
                "nb_tranches": request.POST.get("nb_tranches", "").strip(),
                "statut": request.POST.get("statut", "").strip(),
                "description": request.POST.get("description", "").strip(),
                "lien_whatsapp": request.POST.get("lien_whatsapp", "").strip(),
            }
            edit_data_key = f"formation_edit_data_{pk}"
            request.session[edit_data_key] = edit_data
            photo = request.FILES.get("photo")
            erreurs = []

            # Convertit les nombres avant de modifier l'objet Formation.
            try:
                duree = int(edit_data["duree"])
                prix = Decimal(edit_data["prix"])
                nb_tranches = int(edit_data["nb_tranches"])
                if duree < 1 or prix < 0 or nb_tranches < 1:
                    erreurs.append("La durée et le nombre de tranches doivent être positifs; le prix ne peut pas être négatif.")
            except (ValueError, InvalidOperation):
                erreurs.append("Vérifiez la durée, le prix et le nombre de tranches.")

            if not edit_data["nom"]:
                erreurs.append("Le nom de la formation est obligatoire.")
            if edit_data["statut"] not in dict(Formation.STATUT_CHOICES):
                erreurs.append("Choisissez un statut valide pour la formation.")
            if photo and photo.size > 2 * 1024 * 1024:
                erreurs.append("L’image de couverture ne doit pas dépasser 2 Mo.")
            elif photo and not getattr(photo, "content_type", "").startswith("image/"):
                erreurs.append("Le fichier de couverture doit être une image.")

            if erreurs:
                for erreur in erreurs:
                    messages.error(request, erreur)
            else:
                formation.nom = edit_data["nom"]
                formation.duree = duree
                formation.prix = prix
                formation.nb_tranches = nb_tranches
                formation.statut = edit_data["statut"]
                formation.description = edit_data["description"]
                formation.lien_whatsapp = edit_data["lien_whatsapp"]
                if photo:
                    formation.photo = photo

                try:
                    formation.full_clean()
                    formation.save()
                    request.session.pop(edit_data_key, None)
                    messages.success(request, f"La formation « {formation.nom} » a été modifiée.")
                except ValidationError as error:
                    detail = []
                    for field_errors in error.message_dict.values():
                        detail.extend(field_errors)
                    messages.error(request, "; ".join(detail) or "Vérifiez les informations de la formation.")

        elif action == "supprimer_module":
            module = get_object_or_404(
                Modules,
                pk=request.POST.get("module_id"),
                formation=formation,
            )
            titre_module = module.titre
            module.delete()
            messages.success(request, f"Le module « {titre_module} » et ses chapitres ont été supprimés.")

        elif action == "supprimer_chapitre":
            chapitre = get_object_or_404(
                Chapitres,
                pk=request.POST.get("chapitre_id"),
                modules__formation=formation,
            )
            nom_chapitre = chapitre.nom
            chapitre.delete()
            messages.success(request, f"Le chapitre « {nom_chapitre} » a été supprimé.")

        elif action == "ajouter_module":
            titre = request.POST.get("titre", "").strip()
            description = request.POST.get("description", "").strip()
            try:
                ordre = int(request.POST.get("ordre") or formation.modules.count() + 1)
                Modules.objects.create(
                    formation=formation,
                    titre=titre,
                    description=description,
                    ordre=ordre,
                )
                messages.success(request, "Le module a été ajouté à cette formation.")
            except (ValueError, IntegrityError):
                messages.error(request, "Impossible d’ajouter ce module. Vérifiez son ordre.")

        elif action == "modifier_module":
            module = get_object_or_404(
                Modules,
                pk=request.POST.get("module_id"),
                formation=formation,
            )
            try:
                module.titre = request.POST.get("titre", "").strip()
                module.description = request.POST.get("description", "").strip()
                module.ordre = int(request.POST.get("ordre", "1"))
                module.est_active = request.POST.get("est_active") == "1"
                module.save()
                messages.success(request, "Le module a été modifié.")
            except (ValueError, IntegrityError):
                messages.error(request, "Impossible de modifier ce module. Vérifiez son ordre.")

        elif action == "ajouter_chapitre":
            module = get_object_or_404(
                Modules,
                pk=request.POST.get("module"),
                formation=formation,
            )
            pdf = request.FILES.get("support_pdf")
            if pdf and pdf.size > 20 * 1024 * 1024:
                messages.error(request, "Le support PDF ne doit pas dépasser 20 Mo.")
            else:
                try:
                    ordre = module.chapitres.count() + 1
                    Chapitres.objects.create(
                        modules=module,
                        nom=request.POST.get("nom", "").strip(),
                        ordre=ordre,
                        duree=int(request.POST.get("duree", "0")),
                        support_video_url=request.POST.get("support_video_url", "").strip() or None,
                        support_pdf=pdf,
                    )
                    messages.success(request, f"Le chapitre a été ajouté au module « {module.titre} ».")
                except ValueError:
                    messages.error(request, "La durée du chapitre doit être un nombre valide.")

        return redirect("admin_formation_detail", pk=formation.pk)

    modules = formation.modules.prefetch_related("chapitres").all()
    edit_data = request.session.pop(f"formation_edit_data_{pk}", None)
    nb_modules = modules.count()
    nb_modules_actifs = modules.filter(est_active=True).count()
    dernier_module = modules.last()
    return render(request, "administration/formation_detail.html", {
        "formation": formation,
        "modules": modules,
        "nb_modules": nb_modules,
        "nb_modules_actifs": nb_modules_actifs,
        "prochain_ordre_module": dernier_module.ordre + 1 if dernier_module else 1,
        "pourcentage_modules_actifs": round(nb_modules_actifs * 100 / nb_modules) if nb_modules else 0,
        "nb_chapitres": Chapitres.objects.filter(modules__formation=formation).count(),
        "formateurs": formation.formateurs.all(),
        "vague_courante": ConfigVague.objects.filter(est_courante=True).first(),
        "formation_edit_data": edit_data,
    })


@admin_requis
def admin_chapitre_detail(request, formation_id, chapitre_id):
    formation = get_object_or_404(Formation, pk=formation_id)
    chapitre = get_object_or_404(
        Chapitres,
        pk=chapitre_id,
        modules__formation=formation,
    )
    module = chapitre.modules

    if request.method == "POST":
        pdf = request.FILES.get("support_pdf")
        retirer_pdf = request.POST.get("retirer_support_pdf") == "1"
        if pdf and pdf.size > 20 * 1024 * 1024:
            messages.error(request, "Le support PDF ne doit pas dépasser 20 Mo.")
        elif pdf and not getattr(pdf, "content_type", "").startswith("application/pdf"):
            messages.error(request, "Le support doit être un fichier PDF.")
        else:
            try:
                duree = int(request.POST.get("duree", "0"))
                if duree < 1:
                    raise ValueError

                ancien_pdf = chapitre.support_pdf
                chapitre.nom = request.POST.get("nom", "").strip()
                chapitre.duree = duree
                chapitre.description = request.POST.get("description", "").strip()
                chapitre.support_video_url = request.POST.get("support_video_url", "").strip() or None
                chapitre.est_active = request.POST.get("est_active") == "1"

                # Si un nouveau fichier est choisi, il remplace l'ancien PDF.
                if pdf:
                    chapitre.support_pdf = pdf
                elif retirer_pdf:
                    chapitre.support_pdf = None
                chapitre.save()

                # Supprime l'ancien fichier du stockage après la sauvegarde.
                if ancien_pdf and (pdf or retirer_pdf):
                    ancien_pdf.delete(save=False)
                if retirer_pdf and not pdf:
                    messages.success(request, "Le chapitre a été mis à jour et son PDF a été retiré.")
                else:
                    messages.success(request, "Le chapitre a été mis à jour.")
            except ValueError:
                messages.error(request, "La durée du chapitre doit être un nombre supérieur à zéro.")

        return redirect("admin_chapitre_detail", formation_id=formation.pk, chapitre_id=chapitre.pk)

    return render(request, "administration/chapitre_detail.html", {
        "formation": formation,
        "formation_id": formation.pk,
        "module": module,
        "chapitre": chapitre,
        "chapitres": module.chapitres.all(),
    })


@admin_requis
def admin_formateurs(request):
    if request.method == "POST":
        if request.POST.get("action") == "create_formateur":
            creation_data = {
                "prenom": request.POST.get("prenom", "").strip(),
                "nom": request.POST.get("nom", "").strip(),
                "email": request.POST.get("email", "").strip().lower(),
                "telephone": request.POST.get("telephone", "").strip(),
                "formation": request.POST.get("formations", "").strip(),
            }
            password = request.POST.get("password", "").strip()
            telephone = creation_data["telephone"]
            telephone_digits = "".join(character for character in telephone if character.isdigit())
            formation = Formation.objects.filter(pk=creation_data["formation"]).first()
            erreurs = []

            if not all((creation_data["prenom"], creation_data["nom"], creation_data["email"], telephone, password)):
                erreurs.append("Tous les champs sont obligatoires.")
            if len(creation_data["prenom"]) < 2 or len(creation_data["nom"]) < 2:
                erreurs.append("Le prénom et le nom doivent contenir au moins 2 caractères.")
            try:
                validate_email(creation_data["email"])
            except ValidationError:
                erreurs.append("Saisissez une adresse email valide.")
            if re.fullmatch(r"(?:\+\d|00\d)[0-9\s().-]*", telephone) is None or not 8 <= len(telephone_digits) <= 15:
                erreurs.append("Saisissez un numéro international valide avec son indicatif, par exemple +229.")
            if not mot_de_passe_valide(password):
                erreurs.append("Le mot de passe doit contenir au moins 8 caractères, une lettre et un chiffre.")
            if formation is None:
                erreurs.append("Choisissez une formation existante.")

            User = get_user_model()
            if creation_data["email"] and (
                Formateurs.objects.filter(email__iexact=creation_data["email"]).exists()
                or User.objects.filter(username__iexact=creation_data["email"]).exists()
            ):
                erreurs.append("Cette adresse email est déjà utilisée.")

            if erreurs:
                for erreur in erreurs:
                    messages.error(request, erreur)
                request.session["formateur_creation_data"] = creation_data
            else:
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=creation_data["email"],
                            email=creation_data["email"],
                            password=password,
                        )
                        formateur = Formateurs.objects.create(
                            prenom=creation_data["prenom"],
                            nom=creation_data["nom"],
                            email=creation_data["email"],
                            telephone=telephone,
                            actif=True,
                            doit_changer_mot_de_passe=True,
                            user=user,
                        )
                        formateur.formations.add(formation)

                    message_whatsapp = (
                        f"Bonjour {formateur.prenom} {formateur.nom}, voici vos accès à l’espace formateur SAREF Academy. "
                        f"Lien : {request.build_absolute_uri(reverse('connexion-formateur'))} Identifiant : {formateur.email}. "
                        f"Mot de passe provisoire : {password}. Connectez-vous puis changez-le à votre première connexion."
                    )
                    telephone_whatsapp = telephone_digits[2:] if telephone.startswith("00") else telephone_digits
                    request.session["formateur_created_access"] = {
                        "name": str(formateur),
                        "email": formateur.email,
                        "password": password,
                        "whatsapp_url": f"https://wa.me/{telephone_whatsapp}?text={quote(message_whatsapp)}",
                    }
                    messages.success(request, "Le formateur et son compte ont été créés.")
                except IntegrityError:
                    request.session["formateur_creation_data"] = creation_data
                    messages.error(request, "La création a échoué : cet email est déjà associé à un compte.")

        return redirect("admin_formateurs")

    creation_data = request.session.pop("formateur_creation_data", None)
    created_access = request.session.pop("formateur_created_access", None)

    formateurs = Formateurs.objects.prefetch_related("formations").order_by("prenom", "nom")
    formations = Formation.objects.all().order_by("nom")
    return render(request, "administration/formateurs.html", {
        "formateurs": formateurs,
        "formateurs_actifs": formateurs.filter(actif=True).count(),
        "formateurs_inactifs": formateurs.filter(actif=False).count(),
        "formations": formations,
        "creation_data": creation_data,
        "created_access": created_access,
    })


@admin_requis
def admin_formateur_detail(request, pk):
    if request.method == "POST":
        formateur = get_object_or_404(Formateurs, pk=pk)
        if request.POST.get("action") == "delete_formateur":
            nom_formateur = str(formateur)
            user = formateur.user
            try:
                with transaction.atomic():
                    formateur.delete()
                    if user and not (
                        user.is_staff
                        or user.is_superuser
                        or Admin.objects.filter(user=user).exists()
                    ):
                        user.delete()
                request.session.pop(f"formateur_profile_data_{pk}", None)
                request.session.pop(f"formateur_profile_access_{pk}", None)
                messages.success(request, f"Le profil de {nom_formateur} a été supprimé.")
                return redirect("admin_formateurs")
            except IntegrityError:
                messages.error(request, "Impossible de supprimer ce profil pour le moment.")
                return redirect("admin_formateur_detail", pk=pk)

        prenom = request.POST.get("prenom", "").strip()
        nom = request.POST.get("nom", "").strip()
        email = request.POST.get("email", "").strip().lower()
        telephone = request.POST.get("telephone", "").strip()
        formation_ids = request.POST.getlist("formations")
        password = request.POST.get("password_provisoire", "").strip()
        form_data = {
            "prenom": prenom,
            "nom": nom,
            "email": email,
            "telephone": telephone,
            "formations": formation_ids,
            "actif": request.POST.get("actif") == "1",
        }
        session_data_key = f"formateur_profile_data_{pk}"
        access_data_key = f"formateur_profile_access_{pk}"
        request.session[session_data_key] = form_data
        request.session.pop(access_data_key, None)

        if not all((prenom, nom, email, telephone)):
            messages.error(request, "Le prénom, le nom, l’adresse email et le téléphone sont obligatoires.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, "Saisissez une adresse email valide.")
            else:
                User = get_user_model()
                email_taken = Formateurs.objects.filter(email__iexact=email).exclude(pk=formateur.pk).exists()
                user_taken = User.objects.filter(username__iexact=email).exclude(pk=formateur.user_id).exists()
                selected_formations = list(Formation.objects.filter(pk__in=formation_ids))

                if email_taken or user_taken:
                    messages.error(request, "Cette adresse email est déjà utilisée par un autre compte.")
                elif len(selected_formations) != len(set(formation_ids)):
                    messages.error(request, "Une des formations sélectionnées n’existe plus.")
                elif password and not mot_de_passe_valide(password):
                    messages.error(request, "Le mot de passe provisoire doit contenir au moins 8 caractères, une lettre et un chiffre.")
                else:
                    try:
                        with transaction.atomic():
                            formateur.prenom = prenom
                            formateur.nom = nom
                            formateur.email = email
                            formateur.telephone = telephone
                            formateur.actif = request.POST.get("actif") == "1"
                            formateur.save()
                            formateur.formations.set(selected_formations)

                            if formateur.user_id:
                                user = formateur.user
                                user.username = email
                                user.email = email
                                if password:
                                    user.set_password(password)
                            elif password:
                                user = User.objects.create_user(
                                    username=email,
                                    email=email,
                                    password=password,
                                )
                                formateur.user = user

                            if formateur.user_id or password:
                                update_fields = ["user"]
                                if password:
                                    formateur.doit_changer_mot_de_passe = True
                                    update_fields.append("doit_changer_mot_de_passe")
                                formateur.save(update_fields=update_fields)
                                if formateur.user_id:
                                    user.save()

                        messages.success(request, "Le profil du formateur a été mis à jour.")
                        request.session.pop(session_data_key, None)
                        if password:
                            telephone_international = telephone.startswith(("+", "00"))
                            telephone_whatsapp = "".join(ch for ch in telephone if ch.isdigit())
                            if telephone_whatsapp.startswith("00"):
                                telephone_whatsapp = telephone_whatsapp[2:]
                            message = (
                                f"Bonjour {prenom} {nom}, voici votre nouvel accès SAREF Academy. "
                                f"Lien : {request.build_absolute_uri(reverse('connexion-formateur'))} "
                                f"Identifiant : {email}. Mot de passe provisoire : {password}. "
                                "Connectez-vous puis changez-le immédiatement."
                            )
                            request.session[access_data_key] = {
                                "password": password,
                                "whatsapp_url": (
                                    f"https://wa.me/{telephone_whatsapp}?text={quote(message)}"
                                    if telephone_international and len(telephone_whatsapp) >= 8 else ""
                                ),
                            }
                            messages.info(request, "Le mot de passe provisoire ne sera affiché qu’une fois.")
                    except IntegrityError:
                        messages.error(request, "Impossible d’enregistrer le profil : cette adresse email est déjà utilisée.")
        return redirect("admin_formateur_detail", pk=pk)

    formateur = get_object_or_404(Formateurs.objects.prefetch_related("formations"), pk=pk)
    formations = Formation.objects.all().order_by("nom")
    form_data = request.session.pop(f"formateur_profile_data_{pk}", None)
    access_to_share = request.session.pop(f"formateur_profile_access_{pk}", None)
    return render(request, "administration/formateur_detail.html", {
        "formateur": formateur,
        "formations": formations,
        "form_data": form_data,
        "access_to_share": access_to_share,
    })


@admin_requis
def admin_vagues(request):
    vagues = ConfigVague.objects.annotate(
        nb_etudiants=Count("candidats", filter=Q(candidats__statut="accepte"), distinct=True),
        nb_archives=Count("archive", distinct=True),
    ).order_by("-date_debut")
    return render(request, 'administration/vagues.html', {"vagues": vagues})


@admin_requis
def admin_vague_archive(request, pk):
    vague = get_object_or_404(ConfigVague, pk=pk)

    action = request.POST.get("action") if request.method == "POST" else ""

    # Une vague inactive peut redevenir active, sauf si elle est archivée.
    if action == "reactiver":
        if request.POST.get("confirmer_reactivation") != "1":
            messages.error(request, "Confirme la réactivation de cette vague avant de continuer.")
            return redirect("admin_vague_archive", pk=vague.pk)

        try:
            with transaction.atomic():
                vague = ConfigVague.objects.select_for_update().get(pk=pk)

                if Archive.objects.filter(configVague=vague).exists():
                    messages.error(request, "Une vague archivée ne peut pas être réactivée.")
                else:
                    vague_active = ConfigVague.objects.select_for_update().filter(
                        est_courante=True
                    ).exclude(pk=vague.pk).first()

                    # Si une autre vague est active, on l’archive avant le changement.
                    if vague_active:
                        vague_active.est_courante = False
                        vague_active.save(update_fields=["est_courante"])
                        if not Archive.objects.filter(configVague=vague_active).exists():
                            Archive.objects.create(
                                configVague=vague_active,
                                date=timezone.now(),
                            )

                    vague.est_courante = True
                    vague.save(update_fields=["est_courante"])
                    messages.success(request, f"La vague « {vague.nom} » est maintenant active.")
        except IntegrityError:
            messages.error(request, "Une autre vague vient d’être activée. Réessaie.")

        return redirect("admin_vague_archive", pk=vague.pk)

    if action in ["archiver", "desactiver"]:
        with transaction.atomic():
            vague = ConfigVague.objects.select_for_update().get(pk=pk)

            if action == "desactiver" and vague.est_courante:
                vague.est_courante = False
                vague.save(update_fields=["est_courante"])
                messages.success(request, f"La vague « {vague.nom} » a été désactivée.")
            elif action == "desactiver":
                messages.info(request, "Cette vague n’est pas active.")
            elif not Archive.objects.filter(configVague=vague).exists():
                vague.est_courante = False
                vague.save(update_fields=["est_courante"])
                Archive.objects.create(configVague=vague, date=timezone.now())
                messages.success(request, f"La vague « {vague.nom} » a été archivée.")
            else:
                messages.info(request, "Cette vague est déjà archivée.")
        return redirect("admin_vague_archive", pk=vague.pk)

    # Étudiants de la vague = candidatures acceptées, regroupées par formation.
    # On calcule en une requête le total payé par chaque inscription.
    apprenants = list(
        Candidats.objects.filter(configVague=vague, statut="accepte")
        .select_related("etudiant", "formation")
        .prefetch_related("resultat")
        .annotate(total_paye=Coalesce(Sum("paiements__montant"), Decimal("0")))
        .order_by("formation__nom", "etudiant__nom", "etudiant__prenom")
    )
    # Ajoute à chaque inscription son résumé financier et son résultat,
    # pour l'affichage direct dans le tableau.
    for inscription in apprenants:
        inscription.finances = _situation_financiere(inscription, inscription.total_paye)
        resultats = list(inscription.resultat.all())
        inscription.dernier_resultat = resultats[-1] if resultats else None

    # Indicateurs globaux de la vague.
    total_encaisse = sum((i.finances["total_paye"] for i in apprenants), Decimal("0"))
    total_attendu = sum((i.finances["prix"] for i in apprenants), Decimal("0"))
    nb_admis = sum(1 for i in apprenants if i.dernier_resultat and i.dernier_resultat.decision == "admis")
    nb_attestations = sum(1 for i in apprenants if i.dernier_resultat and i.dernier_resultat.attestation)

    archive = Archive.objects.filter(configVague=vague).order_by("-date").first()
    return render(request, "administration/vague_archive.html", {
        "vague": vague,
        "etudiants": apprenants,
        "nb_etudiants": len(apprenants),
        "total_encaisse": total_encaisse,
        "total_reste": max(total_attendu - total_encaisse, Decimal("0")),
        "nb_admis": nb_admis,
        "nb_attestations": nb_attestations,
        "nb_formations": Formation.objects.filter(
            candidats__configVague=vague,
            candidats__statut="accepte",
        ).distinct().count(),
        "archive": archive,
        "est_archivee": archive is not None,
        "autre_vague_courante": ConfigVague.objects.filter(
            est_courante=True
        ).exclude(pk=vague.pk).first(),
    })


def _situation_financiere(candidat, total_paye):
    """Calcule le résumé financier d'une inscription.

    Retourne un dictionnaire avec le prix de la formation, le montant payé,
    le reste à payer et le pourcentage réglé (plafonné à 100 %).
    """
    prix = candidat.formation.prix or Decimal("0")
    total_paye = total_paye or Decimal("0")
    reste = max(prix - total_paye, Decimal("0"))
    pourcentage = min(round(total_paye * 100 / prix), 100) if prix else 100
    return {
        "prix": prix,
        "total_paye": total_paye,
        "reste": reste,
        "pourcentage": pourcentage,
        "solde": reste == 0,
    }


@admin_requis
def admin_vague_inscription(request, pk, candidat_pk):
    """Dossier complet d'un apprenant pour une vague donnée.

    Regroupe sur une seule page : l'identité de l'étudiant, sa candidature,
    sa situation financière (tranches et paiements), sa progression dans
    les cours, son résultat et son attestation.
    Seules les candidatures acceptées de la vague sont consultables ici.
    """
    vague = get_object_or_404(ConfigVague, pk=pk)
    candidat = get_object_or_404(
        Candidats.objects.select_related("etudiant", "formation"),
        pk=candidat_pk,
        configVague=vague,
        statut="accepte",
    )
    etudiant = candidat.etudiant
    formation = candidat.formation

    # --- Finances ------------------------------------------------------------
    paiements = candidat.paiements.order_by("date")
    total_paye = paiements.aggregate(total=Sum("montant"))["total"]
    finances = _situation_financiere(candidat, total_paye)

    # Découpage du prix en tranches arrondies au centime ; la dernière tranche
    # reprend le reste pour que la somme des tranches égale exactement le prix.
    # Chaque tranche indique ce qui a déjà été versé pour elle (d'après le
    # numéro de tranche enregistré sur les paiements).
    nb_tranches = formation.nb_tranches or 1
    montant_base = (finances["prix"] / nb_tranches).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    montant_derniere = finances["prix"] - montant_base * (nb_tranches - 1)
    payes_par_tranche = {
        ligne["tranche"]: ligne["total"]
        for ligne in paiements.values("tranche").annotate(total=Sum("montant"))
    }
    tranches = []
    for numero in range(1, nb_tranches + 1):
        montant_tranche = montant_derniere if numero == nb_tranches else montant_base
        verse = payes_par_tranche.get(numero, Decimal("0"))
        if verse >= montant_tranche and montant_tranche > 0:
            etat = "payee"
        elif verse > 0:
            etat = "partielle"
        else:
            etat = "a_payer"
        tranches.append({"numero": numero, "montant": montant_tranche, "verse": verse, "etat": etat})

    # --- Progression pédagogique ---------------------------------------------
    nb_chapitres = Chapitres.objects.filter(
        modules__formation=formation, modules__est_active=True, est_active=True
    ).count()
    nb_termines = ChapitreTermine.objects.filter(
        candidats=candidat, chapitre__est_active=True
    ).count()
    progression = min(round(nb_termines * 100 / nb_chapitres), 100) if nb_chapitres else 0

    # --- Résultat et attestation ---------------------------------------------
    resultat = candidat.resultat.order_by("-pk").first()

    # Autres formations suivies par le même étudiant dans cette vague.
    autres_inscriptions = Candidats.objects.filter(
        etudiant=etudiant, configVague=vague, statut="accepte"
    ).exclude(pk=candidat.pk).select_related("formation")

    return render(request, "administration/vague_inscription.html", {
        "vague": vague,
        "candidat": candidat,
        "etudiant": etudiant,
        "formation": formation,
        "paiements": paiements,
        "finances": finances,
        "tranches": tranches,
        "nb_chapitres": nb_chapitres,
        "nb_termines": nb_termines,
        "progression": progression,
        "resultat": resultat,
        "formateurs": formation.formateurs.filter(actif=True),
        "autres_inscriptions": autres_inscriptions,
        "est_archivee": Archive.objects.filter(configVague=vague).exists(),
    })


@admin_requis
def admin_mon_compte(request):
    """Modifie les informations du compte administrateur (table auth_user)."""
    user = request.user
    User = get_user_model()
    infos = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
    }

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "infos":
            infos = {cle: request.POST.get(cle, "").strip() for cle in infos}
            infos["email"] = infos["email"].lower()
            erreurs = []
            autres = User.objects.exclude(pk=user.pk)
            if not infos["username"]:
                erreurs.append("Le nom d’utilisateur est obligatoire.")
            elif autres.filter(username__iexact=infos["username"]).exists():
                erreurs.append("Ce nom d’utilisateur est déjà utilisé.")
            if infos["email"]:
                try:
                    validate_email(infos["email"])
                except ValidationError:
                    erreurs.append("L’adresse e-mail n’est pas valide.")
                else:
                    if autres.filter(email__iexact=infos["email"]).exists():
                        erreurs.append("Cette adresse e-mail est déjà utilisée par un autre compte.")
            if erreurs:
                for erreur in erreurs:
                    messages.error(request, erreur)
            else:
                for cle, valeur in infos.items():
                    setattr(user, cle, valeur)
                user.save(update_fields=list(infos))
                messages.success(request, "Vos informations ont été mises à jour.")
                return redirect("admin_mon_compte")

        elif action == "mot_de_passe":
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)
                messages.success(request, "Votre mot de passe a été modifié.")
                return redirect("admin_mon_compte")
            for liste in form.errors.values():
                for erreur in liste:
                    messages.error(request, erreur)

        elif action == "ajouter_admin":
            nouvel_admin = {cle: request.POST.get(f"nouveau_{cle}", "").strip() for cle in infos}
            nouvel_admin["email"] = nouvel_admin["email"].lower()
            password1 = request.POST.get("nouveau_password1", "")
            password2 = request.POST.get("nouveau_password2", "")
            erreurs = []
            # L'administrateur connecté doit confirmer avec son propre mot de passe.
            if not user.check_password(request.POST.get("mot_de_passe_actuel", "")):
                erreurs.append("Votre mot de passe actuel est incorrect. L’administrateur n’a pas été créé.")
            if not nouvel_admin["username"]:
                erreurs.append("Le nom d’utilisateur du nouvel administrateur est obligatoire.")
            elif User.objects.filter(username__iexact=nouvel_admin["username"]).exists():
                erreurs.append("Ce nom d’utilisateur est déjà utilisé.")
            if nouvel_admin["email"]:
                try:
                    validate_email(nouvel_admin["email"])
                except ValidationError:
                    erreurs.append("L’adresse e-mail du nouvel administrateur n’est pas valide.")
                else:
                    if User.objects.filter(email__iexact=nouvel_admin["email"]).exists():
                        erreurs.append("Cette adresse e-mail est déjà utilisée par un autre compte.")
            if password1 != password2:
                erreurs.append("Les deux mots de passe du nouvel administrateur ne correspondent pas.")
            else:
                try:
                    validate_password(password1, User(username=nouvel_admin["username"], email=nouvel_admin["email"]))
                except ValidationError as exc:
                    erreurs.extend(exc.messages)

            if erreurs:
                for erreur in erreurs:
                    messages.error(request, erreur)
            else:
                User.objects.create_superuser(
                    username=nouvel_admin["username"],
                    email=nouvel_admin["email"],
                    password=password1,
                    first_name=nouvel_admin["first_name"],
                    last_name=nouvel_admin["last_name"],
                )
                messages.success(request, f"L’administrateur « {nouvel_admin['username']} » a été créé.")
                return redirect("admin_mon_compte")

    administrateurs = User.objects.filter(is_superuser=True).order_by("username")
    return render(request, "administration/mon_compte.html", {
        "infos": infos,
        "administrateurs": administrateurs,
    })


# -----------------------------------------------------------------------------
# Pages d’erreur
# -----------------------------------------------------------------------------

def handel404(request, exception=None):
    return render(request, 'error_404.html', status=404)


def handel500(request):
    return render(request, 'error_500.html', status=500)
