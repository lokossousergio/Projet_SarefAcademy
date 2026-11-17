from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
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
from django.core.mail import send_mail
from django.utils import timezone


def mot_de_passe_valide(valeur):
    return len(valeur) >= 8 and any(c.isalpha() for c in valeur) and any(c.isdigit() for c in valeur)


def apprenant_requis(view):
    """Protège une page apprenant avec l'identifiant conservé en session."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        etudiant_id = request.session.get("etudiant_id")
        if not etudiant_id:
            messages.error(request, "Connectez-vous pour accéder à votre espace apprenant.")
            return redirect("connexion-etudiant")
        try:
            request.etudiant = Etudiants.objects.get(pk=etudiant_id)
        except Etudiants.DoesNotExist:
            request.session.flush()
            messages.error(request, "Votre session a expiré. Veuillez vous reconnecter.")
            return redirect("connexion-etudiant")
        return view(request, *args, **kwargs)
    return wrapper


def formateur_requis(view):
    """Laisse entrer uniquement un formateur connecté et actif."""
    @wraps(view)
    @login_required(login_url="connexion")
    def wrapper(request, *args, **kwargs):
        formateur = getattr(request.user, "profil_formateur", None)
        if formateur is None or not formateur.actif:
            logout(request)
            messages.error(request, "Connectez-vous avec un compte formateur actif.")
            return redirect("connexion")
        request.formateur = formateur
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

def connexion(request):
    if request.method == 'POST':
        role = request.POST.get('role', 'formateur')
        identifiant = request.POST.get('email', '').strip()
        user = authenticate(request, username=identifiant, password=request.POST.get('password', ''))
        if user is None:
            messages.error(request, "Identifiant ou mot de passe incorrect.")
        elif role == 'formateur':
            profil = getattr(user, 'profil_formateur', None)
            if profil is None or not profil.actif:
                messages.error(request, "Ce compte n’a pas accès à l’espace formateur.")
            else:
                login(request, user)
                if profil.doit_changer_mot_de_passe:
                    return redirect('changer_mot_de_passe')
                return redirect('formateur_dashboard')
        elif user.is_staff or user.is_superuser:
            login(request, user)
            return redirect('admin_configuration_vague')
        else:
            messages.error(request, "Ce compte n’a pas accès à l’administration.")
    return render(request, 'connexion.html')


def connexion_admin(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('email', '').strip(), password=request.POST.get('password', ''))
        if user and (user.is_staff or user.is_superuser):
            login(request, user)
            return redirect('admin_configuration_vague')
        messages.error(request, "Identifiant ou mot de passe administrateur incorrect.")
    return render(request, 'connexion_admin.html')


def deconnexion(request):
    logout(request)
    return redirect('connexion')



def changer_mot_de_passe(request):
    formateur = request.formateur
    form = PasswordChangeForm(request.user, request.POST or None)
    for field_name, field in form.fields.items():
        field.widget.attrs.update({
            'class': 'form-control',
            'autocomplete': 'current-password' if field_name == 'old_password' else 'new-password',
        })
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        formateur.doit_changer_mot_de_passe = False
        formateur.save(update_fields=['doit_changer_mot_de_passe'])
        messages.success(request, "Votre mot de passe a été modifié.")
        return redirect('formateur_dashboard')
    return render(request, 'changer_mot_de_passe.html', {'form': form, 'formateur': formateur})


# -----------------------------------------------------------------------------
# Candidatures
# -----------------------------------------------------------------------------

@apprenant_requis
def candidature_formation(request):
    """Gère l'enregistrement d'une candidature pour l'étudiant connecté."""
    etudiant = request.etudiant

    if request.method == "POST":
        donnees = {
            "formation": request.POST.get("formation", "").strip(),
            "motivation": request.POST.get("motivation", "").strip(),
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

        # 3. Vérification de la motivation
        if len(donnees["motivation"]) < 40:
            erreurs.append("Présentez votre motivation en 40 caractères minimum.")
        elif len(donnees["motivation"]) > 255:
            erreurs.append("Votre motivation ne doit pas dépasser 255 caractères.")

        # 4. Vérification du CV (PDF, max 5 Mo)
        if not cv:
            erreurs.append("Ajoutez votre CV au format PDF.")
        elif cv.size > 5 * 1024 * 1024:
            erreurs.append("Le CV ne doit pas dépasser 5 Mo.")
        elif (
            getattr(cv, "content_type", "").lower() != "application/pdf"
            and not cv.name.lower().endswith(".pdf")
        ):
            erreurs.append("Le CV doit être un fichier PDF.")

        # 5. Vérification si déjà postulé à cette formation
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

        # 6. Enregistrement dans la table Candidats
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

                Candidats.objects.create(
                    configVague=vague_active,
                    formation=formation,
                    etudiant=etudiant,
                    motif_inscription=donnees["motivation"],
                    cv=cv,
                )

            messages.success(request, "Votre candidature a été envoyée à l’équipe pédagogique.")
            return redirect("candidature-formation")

        except IntegrityError:
            messages.error(request, "Vous avez déjà postulé à cette formation.")
            request.session["candidature_form_data"] = donnees
            return redirect("candidature-formation")

    donnees = request.session.pop("candidature_form_data", None)
    vague_courante = ConfigVague.objects.filter(est_courante=True).first()
    candidatures_existantes = Candidats.objects.filter(
        etudiant=etudiant
    ).select_related("formation", "configVague")
    formations_deja_choisies = Formation.objects.filter(
        candidats__in=candidatures_existantes
    ).distinct().order_by("nom")
    formations_disponibles = Formation.objects.filter(
        statut="active"
    ).exclude(
        pk__in=formations_deja_choisies.values("pk")
    ).order_by("nom")

    toutes_les_formations = Formation.objects.filter(statut="active").order_by("nom")

    if not vague_courante:
        messages.error(request, "Aucune vague n’est en cours. Les candidatures sont fermées pour le moment.")
    elif not formations_disponibles:
        messages.info(request, "Vous avez déjà postulé à toutes les formations actuellement ouvertes.")

    return render(request, "bourse_postule/candidature.html", {
        "etudiant": etudiant,
        "vague_courante": vague_courante,
        "toutes_les_formations": toutes_les_formations,
        "formations_disponibles": formations_disponibles,
        "formations_deja_choisies": formations_deja_choisies,
        "donnees": donnees,
    })


def connexion_etudiant(request):
    if request.session.get("etudiant_id"):
        return redirect("apprenant_dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        etudiant = Etudiants.objects.filter(email__iexact=email).first()

        # Le mot de passe est vérifié directement sur le profil étudiant.
        if etudiant and etudiant.mot_de_passe and check_password(password, etudiant.mot_de_passe):
            request.session.cycle_key()
            request.session["etudiant_id"] = etudiant.pk
            return redirect("apprenant_dashboard")

        messages.error(request, "Adresse e-mail ou mot de passe incorrect.")

    return render(request, "Espace_etudiants/connexion.html")


def inscription_etudiant(request):
    if request.session.get("etudiant_id"):
        return redirect("apprenant_dashboard")

    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        prenom = request.POST.get("prenom", "").strip()
        email = request.POST.get("email", "").strip().lower()
        telephone = request.POST.get("telephone", "").strip()
        password = request.POST.get("password", "")
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
                niveau_etudes="Non renseigné",
                mot_de_passe=make_password(password),
            )
            request.session.cycle_key()
            request.session["etudiant_id"] = etudiant.pk
            messages.success(request, "Votre compte a été créé. Bienvenue sur Saref Academy !")
            return redirect("apprenant_dashboard")

    return render(request, "Espace_etudiants/inscription.html")


def deconnexion_etudiant(request):
    request.session.pop("etudiant_id", None)
    messages.success(request, "Vous êtes déconnecté(e).")
    return redirect("connexion-etudiant")


def mot_de_passe_oublie(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Saisissez une adresse e-mail valide.")
            return render(request, "Espace_etudiants/mot_de_passe_oublie.html")

        # Réponse identique pour éviter de révéler si une adresse est enregistrée.
        etudiant = Etudiants.objects.filter(email__iexact=email).first()
        if etudiant:
            code = f"{secrets.randbelow(1_000_000):06d}"
            request.session["reset_email"] = etudiant.email
            request.session["reset_code"] = code
            request.session["reset_expiration"] = (timezone.now() + timedelta(minutes=10)).isoformat()
            send_mail(
                "Code de réinitialisation — Saref Academy",
                f"Votre code de réinitialisation est : {code}. Il expire dans 10 minutes.",
                None,
                [etudiant.email],
                fail_silently=False,
            )
        request.session["reset_attempts"] = 0
        messages.success(request, "Si un compte correspond à cette adresse, un code vient d’être envoyé.")
        return redirect("verifier_code_etudiant")

    return render(request, "Espace_etudiants/mot_de_passe_oublie.html")


def verifier_code_etudiant(request):
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        expiration = request.session.get("reset_expiration")
        expired = not expiration or timezone.now() > datetime.fromisoformat(expiration)

        if expired:
            request.session.pop("reset_code", None)
            messages.error(request, "Le code a expiré. Recommencez la procédure.")
        elif request.session.get("reset_attempts", 0) >= 5:
            messages.error(request, "Trop de tentatives. Demandez un nouveau code.")
        elif code != request.session.get("reset_code"):
            request.session["reset_attempts"] = request.session.get("reset_attempts", 0) + 1
            messages.error(request, "Le code saisi est incorrect.")
        elif not mot_de_passe_valide(password):
            messages.error(request, "Le nouveau mot de passe doit contenir 8 caractères au minimum, avec une lettre et un chiffre.")
        elif password != password2:
            messages.error(request, "Les deux mots de passe ne correspondent pas.")
        else:
            etudiant = Etudiants.objects.filter(email__iexact=request.session.get("reset_email")).first()
            if etudiant:
                etudiant.mot_de_passe = make_password(password)
                etudiant.save(update_fields=["mot_de_passe"])
                for key in ("reset_email", "reset_code", "reset_expiration", "reset_attempts"):
                    request.session.pop(key, None)
                messages.success(request, "Votre mot de passe a été modifié. Vous pouvez vous connecter.")
                return redirect("connexion-etudiant")
            messages.error(request, "Aucun compte étudiant associé à cette demande.")

    return render(request, "Espace_etudiants/verifier_code.html")


def dashboard_etudiant(request):
    return redirect("apprenant_dashboard")


# -----------------------------------------------------------------------------
# Espace formateur
# -----------------------------------------------------------------------------


def formateur_dashboard(request):
    return render(request, 'formateur/dashboard.html')



def formateur_apprenants(request):
    return render(request, 'formateur/apprenants.html')



def formateur_formations(request):
    return render(request, 'formateur/formations.html')



def formateur_formation_detail(request, formation_id=1):
    return render(request, 'formateur/formation_detail.html', {'formation_id': formation_id})



def formateur_module(request, pk=1):
    return render(request, 'formateur/module.html', {'pk': pk})



def formateur_module_ajouter(request):
    return render(request, 'formateur/formations.html')



def formateur_module_modifier(request, pk=1):
    return render(request, 'formateur/formations.html', {'pk': pk})



def formateur_module_supprimer(request, pk=1):
    return render(request, 'formateur/formations.html', {'pk': pk})



def formateur_chapitre_ajouter(request):
    return render(request, 'formateur/formations.html')



def formateur_chapitre_detail(request, formation_id=1, chapitre_id=1):
    return render(request, 'formateur/chapitre_detail.html', {
        'formation_id': formation_id,
        'chapitre_id': chapitre_id,
    })


# -----------------------------------------------------------------------------
# Espace apprenant
# -----------------------------------------------------------------------------

@apprenant_requis
def apprenant_dashboard(request):
    etudiant = request.etudiant
    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    candidatures_acceptees = [c for c in candidatures if c.statut == "accepte"]
    return render(request, "apprenant/dashboard.html", {
        "etudiant": etudiant,
        "candidatures": candidatures,
        "candidatures_acceptees": candidatures_acceptees,
    })


@apprenant_requis
def apprenant_formations(request):
    etudiant = request.etudiant
    # Toutes les candidatures de l'apprenant
    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    # IDs des formations déjà postulées (pour ne pas les proposer en "disponibles")
    formations_postulees_ids = candidatures.values_list("formation_id", flat=True)
    # Formations actives auxquelles il n'a pas encore postulé
    formations_disponibles = Formation.objects.filter(statut="active").exclude(pk__in=formations_postulees_ids)
    return render(request, "apprenant/formations.html", {
        "etudiant": etudiant,
        "candidatures": candidatures,
        "formations_disponibles": formations_disponibles,
    })


@apprenant_requis
def apprenant_formation_detail(request, pk):
    etudiant = request.etudiant
    # pk ici est le pk de la Candidature (pas de la Formation)
    candidat = get_object_or_404(Candidats, pk=pk, etudiant=etudiant)
    formation = candidat.formation
    modules = formation.modules.prefetch_related("chapitres").filter(est_active=True) if candidat.statut == "accepte" else formation.modules.prefetch_related("chapitres")
    # Chapitres terminés par cet apprenant pour cette candidature
    chapitres_termines_ids = set(
        ChapitreTermine.objects.filter(candidats=candidat).values_list("chapitre_id", flat=True)
    )
    nb_chapitres = Chapitres.objects.filter(modules__formation=formation, est_active=True).count()
    progression = round(len(chapitres_termines_ids) / nb_chapitres * 100) if nb_chapitres else 0
    return render(request, "apprenant/formation_detail.html", {
        "etudiant": etudiant,
        "candidat": candidat,
        "formation": formation,
        "modules": modules,
        "chapitres_termines": chapitres_termines_ids,
        "nb_chapitres": nb_chapitres,
        "progression": progression,
    })


@apprenant_requis
def apprenant_modules(request):
    etudiant = request.etudiant
    # Formations acceptées de l'apprenant
    formations_acceptees_ids = set(
        etudiant.candidats.filter(statut="accepte").values_list("formation_id", flat=True)
    )
    # Tous les modules des formations de l'apprenant (acceptées ou non)
    formations_ids = set(etudiant.candidats.values_list("formation_id", flat=True))
    modules = Modules.objects.filter(
        formation_id__in=formations_ids
    ).select_related("formation").prefetch_related("chapitres").order_by("formation__nom", "ordre")
    return render(request, "apprenant/modules.html", {
        "etudiant": etudiant,
        "modules": modules,
        "formations_acceptees": formations_acceptees_ids,
    })


@apprenant_requis
def apprenant_module_detail(request, pk):
    etudiant = request.etudiant
    module = get_object_or_404(Modules, pk=pk)
    # Vérifier que l'apprenant a bien une candidature acceptée pour cette formation
    candidat = get_object_or_404(Candidats, etudiant=etudiant, formation=module.formation, statut="accepte")
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
    return render(request, "apprenant/chapitre_detail.html", {
        "etudiant": etudiant,
        "candidat": candidat,
        "module": module,
        "chapitre": chapitre,
        "chapitres": chapitres,
        "chapitres_termines": chapitres_termines_ids,
    })


@apprenant_requis
def apprenant_paiements(request):
    etudiant = request.etudiant
    candidatures_acceptees = etudiant.candidats.filter(
        statut="accepte"
    ).select_related("formation", "configVague").prefetch_related("paiements")
    # Tous les paiements de l'apprenant
    paiements = Paiement.objects.filter(
        candidats__etudiant=etudiant
    ).select_related("formation", "candidats__configVague").order_by("-date")
    # Montant dû = somme des prix des formations acceptées
    montant_du = sum(c.formation.prix for c in candidatures_acceptees)
    total_paye = paiements.aggregate(total=Sum("montant"))["total"] or 0
    reste_a_payer = max(montant_du - total_paye, 0)
    return render(request, "apprenant/paiements.html", {
        "etudiant": etudiant,
        "candidatures_acceptees": candidatures_acceptees,
        "paiements": paiements,
        "montant_du": montant_du,
        "total_paye": total_paye,
        "reste_a_payer": reste_a_payer,
    })


@apprenant_requis
def apprenant_profil(request):
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
                return redirect("apprenant_profil")
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
                return redirect("apprenant_profil")
    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    return render(request, "apprenant/profil.html", {
        "etudiant": etudiant,
        "candidatures": candidatures,
    })


@apprenant_requis
def apprenant_parametres(request):
    return render(request, "apprenant/parametres.html", {"etudiant": request.etudiant})


# -----------------------------------------------------------------------------
# Espace gestion
# -----------------------------------------------------------------------------

def admin_configuration_initiale(request):
    return render(request, 'admin/configuration_initiale.html')


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
    return render(request, "admin/configuration_vague.html", {
        "donnees": donnees,
        "vague_courante": vague_courante,
        "confirmation_remplacement": confirmation_remplacement,
        "noms_vagues": list(ConfigVague.objects.values_list("nom", flat=True)),
    })


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

    return render(request, 'admin/dashboard.html', {
        "vague_courante": vague_courante,
        "nb_candidatures": nb_candidatures,
        "nb_candidatures_attente": nb_candidatures_attente,
        "nb_etudiants": nb_etudiants,
        "candidatures_recentes": candidatures_recentes,
        "nb_formations": Formation.objects.count(),
        "nb_formations_actives": Formation.objects.filter(statut="active").count(),
        "nb_formateurs_actifs": Formateurs.objects.filter(actif=True).count(),
    })


def admin_candidatures(request):
    vague_courante = ConfigVague.objects.filter(est_courante=True).first()
    formations = Formation.objects.all().order_by("nom")
    vagues = ConfigVague.objects.all().order_by("-date_debut")

    candidatures_qs = Candidats.objects.select_related("etudiant", "formation", "configVague")

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

    vague_filtre = request.GET.get("vague", "").strip()
    if vague_filtre:
        candidatures_qs = candidatures_qs.filter(configVague__nom__icontains=vague_filtre)

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

    return render(request, "admin/candidatures.html", {
        "candidatures": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "vague_courante": vague_courante,
        "formations": formations,
        "vagues": vagues,
        "nb_total": stats["nb_total"] or 0,
        "nb_attente": stats["nb_attente"] or 0,
        "nb_accepte": stats["nb_accepte"] or 0,
        "nb_refuse": stats["nb_refuse"] or 0,
        "filtre_statut": statut,
        "filtre_q": q,
        "filtre_formation": formation_filtre,
        "filtre_vague": vague_filtre,
        "filtre_tri": tri,
    })


def admin_candidature_detail(request, pk=1):
    candidat = get_object_or_404(
        Candidats.objects.select_related("etudiant", "formation", "configVague"),
        pk=pk,
    )

    if request.method == "POST":
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
                    lien="/apprenant/formations/",
                )

        messages.success(request, f"La décision pour la candidature de {candidat.etudiant} a été enregistrée.")
        return redirect("admin_candidature_detail", pk=candidat.pk)

    autres_candidatures = Candidats.objects.filter(
        etudiant=candidat.etudiant
    ).exclude(pk=candidat.pk).select_related("formation", "configVague").order_by("-date_candidature")

    return render(request, "admin/candidature_detail.html", {
        "candidat": candidat,
        "autres_candidatures": autres_candidatures,
        "pk": pk,
    })


def admin_apprenants(request):
    formations = Formation.objects.all().order_by("nom")

    # Statistiques globales
    total_apprenants = Etudiants.objects.count()
    une_semaine = timezone.now() - timedelta(days=7)
    actifs_semaine = Etudiants.objects.filter(
        Q(candidats__chapitres_termines__date__gte=une_semaine)
        | Q(date_inscription__gte=une_semaine)
    ).distinct().count()

    avec_candidature_count = Etudiants.objects.filter(candidats__isnull=False).distinct().count()
    sans_candidature_count = total_apprenants - avec_candidature_count

    bloques_count = Etudiants.objects.filter(
        candidats__est_bloque=True
    ).distinct().count()

    etudiants_qs = Etudiants.objects.annotate(
        nb_candidatures=Count("candidats", distinct=True),
        nb_bloques=Count("candidats", filter=Q(candidats__est_bloque=True), distinct=True),
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
        etudiants_qs = etudiants_qs.filter(candidats__est_bloque=True)
    elif statut_filtre == "actif":
        etudiants_qs = etudiants_qs.filter(nb_bloques=0)

    etudiants_qs = etudiants_qs.distinct().order_by("-date_inscription")

    # Export CSV si demandé
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        nom_fichier = f"apprenants_{filtre_type or 'tous'}.csv"
        response["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
        writer = csv.writer(response)
        writer.writerow(["Nom", "Prénom", "Email", "Téléphone", "Niveau d'études", "Candidatures", "Inscrit le", "Statut"])
        for e in etudiants_qs:
            statut = "Bloqué" if e.nb_bloques > 0 else "Actif"
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

    return render(request, "admin/apprenants.html", {
        "etudiants": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "formations": formations,
        "total_apprenants": total_apprenants,
        "avec_candidature_count": avec_candidature_count,
        "sans_candidature_count": sans_candidature_count,
        "actifs_semaine": actifs_semaine,
        "bloques_count": bloques_count,
        "filtre_type": filtre_type,
        "filtre_q": q,
        "filtre_formation": formation_filtre,
        "filtre_statut": statut_filtre,
    })


def admin_apprenant_detail(request, pk=1):
    etudiant = get_object_or_404(Etudiants, pk=pk)

    candidatures = etudiant.candidats.select_related("formation", "configVague").order_by("-date_candidature")
    est_bloque = candidatures.filter(est_bloque=True).exists()

    if request.method == "POST":
        nouveau_blocage = not est_bloque
        with transaction.atomic():
            candidatures.update(est_bloque=nouveau_blocage)
        if nouveau_blocage:
            messages.warning(request, f"L’accès de {etudiant.prenom} {etudiant.nom} a été bloqué.")
        else:
            messages.success(request, f"L’accès de {etudiant.prenom} {etudiant.nom} a été rétabli.")
        return redirect("admin_apprenant_detail", pk=etudiant.pk)

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

    return render(request, "admin/apprenant_detail.html", {
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


def admin_resultats(request):
    return render(request, 'admin/resultats.html')


def admin_finance(request):
    return render(request, 'admin/finance.html')


def admin_organisation(request):
    return render(request, 'admin/organisation.html')


def admin_formations(request):
    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        description = request.POST.get("description", "").strip()
        photo = request.FILES.get("photo")

        # La couverture est facultative, mais limitée à 2 Mo et doit être une image.
        if photo and photo.size > 2 * 1024 * 1024:
            messages.error(request, "L’image de couverture ne doit pas dépasser 2 Mo.")
        elif photo and not photo.content_type.startswith("image/"):
            messages.error(request, "Le fichier de couverture doit être une image.")
        else:
            try:
                formation = Formation.objects.create(
                    nom=nom,
                    duree=int(request.POST.get("duree", "0")),
                    prix=Decimal(request.POST.get("prix", "0")),
                    nb_tranches=int(request.POST.get("nb_tranches", "3")),
                    description=description,
                    photo=photo,
                    statut=request.POST.get("statut", "active"),
                )
                messages.success(request, f"La formation « {formation.nom} » a été créée.")
                return redirect("admin_formations")
            except (ValueError, InvalidOperation):
                messages.error(request, "La durée, le prix et les tranches doivent être des nombres valides.")

    formations = Formation.objects.all().order_by("nom")
    return render(request, "admin/formations.html", {"formations": formations})


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
    return render(request, "admin/formation_detail.html", {
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

    return render(request, "admin/chapitre_detail.html", {
        "formation": formation,
        "formation_id": formation.pk,
        "module": module,
        "chapitre": chapitre,
        "chapitres": module.chapitres.all(),
    })


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
                        f"Lien : {request.build_absolute_uri('/connexion/')} Identifiant : {formateur.email}. "
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
    return render(request, "admin/formateurs.html", {
        "formateurs": formateurs,
        "formateurs_actifs": formateurs.filter(actif=True).count(),
        "formateurs_inactifs": formateurs.filter(actif=False).count(),
        "formations": formations,
        "creation_data": creation_data,
        "created_access": created_access,
    })


def admin_formateur_detail(request, pk=1):
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
                                f"Lien : {request.build_absolute_uri('/connexion/')} "
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
    return render(request, "admin/formateur_detail.html", {
        "formateur": formateur,
        "formations": formations,
        "form_data": form_data,
        "access_to_share": access_to_share,
    })


def admin_vagues(request):
    vagues = ConfigVague.objects.annotate(
        nb_apprenants=Count("candidats", filter=Q(candidats__statut="accepte"), distinct=True),
        nb_archives=Count("archive", distinct=True),
    ).order_by("-date_debut")
    return render(request, 'admin/vagues.html', {"vagues": vagues})


def admin_vague_archive(request, pk=1):
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

    apprenants = Candidats.objects.filter(
        configVague=vague,
        statut="accepte",
    ).select_related(
        "etudiant", "formation"
    ).order_by("formation__nom", "etudiant__nom", "etudiant__prenom")
    archive = Archive.objects.filter(configVague=vague).order_by("-date").first()
    return render(request, "admin/vague_archive.html", {
        "vague": vague,
        "apprenants": apprenants,
        "nb_apprenants": apprenants.count(),
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


def admin_parametres(request):
    return render(request, 'admin/parametres.html')


# -----------------------------------------------------------------------------
# Pages d’erreur
# -----------------------------------------------------------------------------

def handel404(request, exception=None):
    return render(request, 'error_404.html', status=404)


def handel500(request):
    return render(request, 'error_500.html', status=500)
