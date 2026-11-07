from django.contrib import messages

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import (Candidats, Chapitres, ChapitreTermine, Etudiants, Formateurs,
                     Formation, Modules, Paiement)

# ============================================================
# Site Public & Formations
# ============================================================

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

def candidature_formation(request):
    return render(request, 'bourse_postule/candidature.html')

def connexion_etudiant(request):
    return render(request, 'Espace_etudiants/connexion.html')

def inscription_etudiant(request):
    return render(request, 'Espace_etudiants/inscription.html')

def dashboard_etudiant(request):
    return render(request, 'Espace_etudiants/dashboard.html')

def bourse_de_formation(request):
    return render(request, 'bourse_de_formation.html')

def inscription_valide(request):
    return render(request, 'info.html')

def tunel(request):
    return render(request, 'tunel.html')


# ============================================================
# Connexion & Authentification (Accès direct sans redirection)
# ============================================================

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

@login_required(login_url='connexion')
def changer_mot_de_passe(request):
    formateur = getattr(request.user, 'profil_formateur', None)
    if formateur is None:
        messages.error(request, "Cette page est réservée aux formateurs.")
        return redirect('connexion')
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


# ============================================================
# Espace Candidature
# ============================================================

def candidature(request):
    return render(request, 'candidature.html')


# ============================================================
# Espace Formateur
# ============================================================

def formateur_dashboard(request):
    formateur = getattr(request.user, 'profil_formateur', None)
    if formateur is None:
        return render(request, 'formateur/dashboard.html')
    formations = formateur.formations.all()
    modules = Modules.objects.filter(formation__in=formations).select_related('formation').prefetch_related('chapitres')
    chapitres = Chapitres.objects.filter(modules__formation__in=formations).distinct()
    return render(request, 'formateur/dashboard.html', {
        'formateur': formateur,
        'formations': formations,
        'modules': modules,
        'nb_modules': modules.count(),
        'nb_chapitres_actifs': chapitres.filter(est_active=True).count(),
        'nb_chapitres_sans_ressource': chapitres.filter(support_video_url__isnull=True, support_pdf='').count(),
        'nb_apprenants': Candidats.objects.filter(formation__in=formations, statut='accepte').values('etudiant_id').distinct().count(),
    })

def formateur_formation_detail(request, formation_id=1):
    formateur = getattr(request.user, 'profil_formateur', None)
    formation = None
    modules = Modules.objects.none()
    if formateur:
        formation = get_object_or_404(formateur.formations, pk=formation_id)
        modules = formation.modules.prefetch_related('chapitres').all()
    return render(request, 'formateur/formation_detail.html', {
        'formateur': formateur,
        'formation': formation,
        'formation_id': formation_id,
        'modules': modules,
    })

def formateur_module(request, pk=1):
    return render(request, 'formateur/module.html', {
        'pk': pk,
        'formateur': getattr(request.user, 'profil_formateur', None),
    })


# ============================================================
# Espace Apprenant
# ============================================================

def _apprenant_courant(request):
    etudiant = getattr(request.user, 'etudiant', None)
    if etudiant:
        return etudiant
    return (Etudiants.objects.filter(email='aicha.demo@example.com').first()
            or Etudiants.objects.order_by('pk').first())

def _candidatures_apprenant(etudiant):
    if etudiant is None:
        return Candidats.objects.none()
    return Candidats.objects.filter(etudiant=etudiant).select_related(
        'formation', 'configVague'
    ).prefetch_related('paiements', 'chapitres_termines')

def apprenant_dashboard(request):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    candidatures_acceptees = candidatures.filter(statut='accepte')
    paiements = Paiement.objects.filter(candidats__etudiant=etudiant).select_related('formation').order_by('-date') if etudiant else Paiement.objects.none()
    chapitres_termines = ChapitreTermine.objects.filter(candidats__etudiant=etudiant).count() if etudiant else 0
    formations_acceptees = candidatures.filter(statut='accepte').count()
    return render(request, 'apprenant/dashboard.html', {
        'etudiant': etudiant,
        'active_page': 'dashboard',
        'candidatures': candidatures,
        'candidatures_acceptees': candidatures_acceptees,
        'paiements_recents': paiements[:4],
        'nb_candidatures': candidatures.count(),
        'nb_formations_acceptees': formations_acceptees,
        'nb_chapitres_termines': chapitres_termines,
        'total_paye': sum(paiement.montant for paiement in paiements),
    })

def apprenant_formations(request):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    return render(request, 'apprenant/formations.html', {
        'etudiant': etudiant,
        'active_page': 'formations',
        'candidatures': candidatures,
        'nb_candidatures_acceptees': candidatures.filter(statut='accepte').count(),
        'nb_candidatures_en_attente': candidatures.filter(statut='en_attente').count(),
        'formations_disponibles': Formation.objects.filter(statut='active').exclude(
            pk__in=candidatures.values('formation_id')
        ),
    })

def apprenant_formation_detail(request, pk=1):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    candidat = candidatures.filter(pk=pk).first() or candidatures.filter(statut='accepte').first() or candidatures.first()
    modules = candidat.formation.modules.prefetch_related('chapitres').all() if candidat else Modules.objects.none()
    chapitres_termines = set(ChapitreTermine.objects.filter(candidats=candidat).values_list('chapitre_id', flat=True)) if candidat else set()
    total_chapitres = Chapitres.objects.filter(modules__formation=candidat.formation).count() if candidat else 0
    progression = round(len(chapitres_termines) * 100 / total_chapitres) if total_chapitres else 0
    return render(request, 'apprenant/formation_detail.html', {
        'etudiant': etudiant, 'active_page': 'formation_detail', 'candidat': candidat,
        'formation': candidat.formation if candidat else None,
        'modules': modules, 'chapitres_termines': chapitres_termines,
        'progression': progression, 'nb_chapitres': total_chapitres,
    })

def apprenant_modules(request):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    modules = Modules.objects.filter(formation__candidats__in=candidatures).select_related(
        'formation'
    ).prefetch_related('chapitres').distinct()
    return render(request, 'apprenant/modules.html', {
        'etudiant': etudiant, 'active_page': 'modules', 'candidatures': candidatures, 'modules': modules,
        'formations_acceptees': candidatures.filter(statut='accepte').values_list('formation_id', flat=True),
    })

def apprenant_module_detail(request, pk=1):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    module = Modules.objects.filter(pk=pk, formation__candidats__in=candidatures).select_related(
        'formation'
    ).prefetch_related('chapitres').first()
    candidat = candidatures.filter(formation=module.formation).first() if module else None
    chapter_id = request.GET.get('chapitre')
    chapitres = module.chapitres.all() if module else Chapitres.objects.none()
    chapitre = chapitres.filter(pk=chapter_id).first() if chapter_id else None
    chapitre = chapitre or chapitres.filter(est_active=True).first() or chapitres.first()
    is_accessible = bool(candidat and candidat.statut == 'accepte' and module and module.est_active)
    chapitres_termines = set(ChapitreTermine.objects.filter(candidats=candidat).values_list('chapitre_id', flat=True)) if candidat else set()
    return render(request, 'apprenant/module_detail.html', {
        'etudiant': etudiant, 'active_page': 'module_detail', 'candidat': candidat, 'module': module,
        'chapitre': chapitre, 'chapitres': chapitres,
        'chapitres_termines': chapitres_termines, 'is_accessible': is_accessible,
        'progression': round(len(chapitres_termines) * 100 / chapitres.count()) if chapitres.count() else 0,
    })

def apprenant_paiements(request):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    paiements = Paiement.objects.filter(candidats__in=candidatures).select_related('formation', 'candidats').order_by('-date')
    total_paye = sum(paiement.montant for paiement in paiements)
    montant_du = sum(c.formation.prix for c in candidatures.filter(statut='accepte'))
    return render(request, 'apprenant/paiements.html', {
        'etudiant': etudiant, 'active_page': 'paiements', 'candidatures': candidatures,
        'candidatures_acceptees': candidatures.filter(statut='accepte'), 'paiements': paiements,
        'total_paye': total_paye, 'montant_du': montant_du,
        'reste_a_payer': max(montant_du - total_paye, 0),
    })

def apprenant_profil(request):
    etudiant = _apprenant_courant(request)
    candidatures = _candidatures_apprenant(etudiant)
    return render(request, 'apprenant/profil.html', {
        'etudiant': etudiant, 'active_page': 'profil', 'candidatures': candidatures,
        'nb_formations_suivies': candidatures.filter(statut='accepte').count(),
    })

def apprenant_parametres(request):
    return render(request, 'apprenant/parametres.html', {
        'etudiant': _apprenant_courant(request), 'active_page': 'parametres',
    })


# ============================================================
# Espace Administration
# ============================================================

def admin_configuration_initiale(request):
    return render(request, 'admin/configuration_initiale.html')

def admin_configuration_vague(request):
    return render(request, 'admin/configuration_vague.html')

def admin_dashboard(request):
    return render(request, 'admin/dashboard.html')

def admin_candidatures(request):
    return render(request, 'admin/candidatures.html')

def admin_candidature_detail(request, pk=1):
    return render(request, 'admin/candidature_detail.html')

def admin_apprenants(request):
    return render(request, 'admin/apprenants.html')

def admin_apprenant_detail(request, pk=1):
    return render(request, 'admin/apprenant_detail.html')

def admin_resultats(request):
    return render(request, 'admin/resultats.html')

def admin_finance(request):
    return render(request, 'admin/finance.html')

def admin_organisation(request):
    formations = list(Formation.objects.prefetch_related('modules__chapitres', 'formateurs').all())
    for formation in formations:
        formation.nombre_chapitres = sum(module.chapitres.count() for module in formation.modules.all())
    return render(request, 'admin/organisation.html', {
        'formations': formations,
        'nombre_formations': len(formations),
        'nombre_formations_actives': sum(formation.statut == 'active' for formation in formations),
        'nombre_formations_brouillon': sum(formation.statut == 'brouillon' for formation in formations),
        'nombre_formateurs': Formateurs.objects.count(),
        'nombre_formateurs_affectes': Formateurs.objects.filter(formations__isnull=False).distinct().count(),
        'nombre_modules': sum(formation.modules.count() for formation in formations),
        'nombre_chapitres': sum(formation.nombre_chapitres for formation in formations),
    })

def admin_formations(request):
    return render(request, 'admin/formations.html')

def admin_formation_detail(request, pk=1):
    return render(request, 'admin/formation_detail.html')

def admin_formateurs(request):
    creation_data = {}
    created_access = None
    if request.method == 'POST' and request.POST.get('action') == 'create_formateur':
        has_creation_error = False
        creation_data = {
            'prenom': request.POST.get('prenom', '').strip(),
            'nom': request.POST.get('nom', '').strip(),
            'email': request.POST.get('email', '').strip().lower(),
            'telephone': request.POST.get('telephone', '').strip(),
            'formations': request.POST.getlist('formations'),
        }
        password = request.POST.get('password', '')
        try:
            validate_email(creation_data['email'])
        except ValidationError:
            messages.error(request, "Saisissez une adresse email valide.")
            has_creation_error = True
        if not all((creation_data['prenom'], creation_data['nom'], creation_data['telephone'], password)):
            messages.error(request, "Complétez tous les champs obligatoires.")
            has_creation_error = True
        if len(password) < 8:
            messages.error(request, "Le mot de passe provisoire doit contenir au moins 8 caractères.")
            has_creation_error = True
        User = get_user_model()
        if User.objects.filter(username=creation_data['email']).exists() or User.objects.filter(email=creation_data['email']).exists() or Formateurs.objects.filter(email=creation_data['email']).exists():
            messages.error(request, "Cette adresse email est déjà utilisée.")
            has_creation_error = True
        selected_formations = list(Formation.objects.filter(pk__in=creation_data['formations']))
        if len(selected_formations) != len(set(creation_data['formations'])) or not selected_formations:
            messages.error(request, "Sélectionnez au moins une formation valide.")
            has_creation_error = True
        if not has_creation_error:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=creation_data['email'], email=creation_data['email'],
                    first_name=creation_data['prenom'], last_name=creation_data['nom'],
                    password=password,
                )
                formateur = Formateurs.objects.create(
                    user=user, prenom=creation_data['prenom'], nom=creation_data['nom'],
                    email=creation_data['email'], telephone=creation_data['telephone'],
                    actif=True, doit_changer_mot_de_passe=True,
                )
                formateur.formations.set(selected_formations)
            phone = ''.join(char for char in creation_data['telephone'] if char.isdigit())
            from urllib.parse import quote
            message = (
                f"Bonjour {formateur.prenom} {formateur.nom}, voici vos accès à l’espace formateur SAREF Academy. "
                f"Lien : {request.build_absolute_uri('/connexion/')} Identifiant : {formateur.email}. "
                f"Mot de passe provisoire : {password}. Connectez-vous puis changez-le."
            )
            created_access = {
                'name': str(formateur), 'email': formateur.email, 'password': password,
                'whatsapp_url': f"https://wa.me/{phone}?text={quote(message)}" if phone else '',
            }
            creation_data = {}
            messages.success(request, "Le compte formateur a été créé. Transmettez ses identifiants via WhatsApp.")
    formateurs = list(Formateurs.objects.prefetch_related('formations').all())
    return render(request, 'admin/formateurs.html', {
        'formateurs': formateurs,
        'formations': Formation.objects.all(),
        'formateurs_actifs': sum(formateur.actif for formateur in formateurs),
        'formateurs_inactifs': sum(not formateur.actif for formateur in formateurs),
        'creation_data': creation_data,
        'created_access': created_access,
    })

def admin_formateur_detail(request, pk=1):
    formateur = get_object_or_404(Formateurs.objects.select_related('user').prefetch_related('formations'), pk=pk)
    formations = Formation.objects.all()
    access_to_share = None
    if request.method == 'POST':
        share_access = request.POST.get('submit_action') == 'share_access'
        provisional_password = request.POST.get('password_provisoire', '').strip()
        if share_access and not provisional_password:
            messages.error(request, "Saisissez ou générez un mot de passe provisoire avant de préparer le partage WhatsApp.")
            return render(request, 'admin/formateur_detail.html', {
                'formateur': formateur, 'formateur_id': formateur.pk, 'formations': formations,
            })
        email = request.POST.get('email', '').strip()
        username_conflict = get_user_model().objects.filter(username=email).exclude(pk=formateur.user_id).exists()
        email_conflict = Formateurs.objects.filter(email=email).exclude(pk=formateur.pk).exists()
        if not email or email_conflict or username_conflict:
            messages.error(request, "Cette adresse email est vide ou déjà utilisée.")
        else:
            formateur.prenom = request.POST.get('prenom', '').strip()
            formateur.nom = request.POST.get('nom', '').strip()
            formateur.email = email
            formateur.telephone = request.POST.get('telephone', '').strip()
            formateur.actif = request.POST.get('actif') == '1'
            formateur.save()
            formateur.formations.set(request.POST.getlist('formations'))
            if formateur.user_id:
                formateur.user.username = email
                formateur.user.email = email
                formateur.user.first_name = formateur.prenom
                formateur.user.last_name = formateur.nom
                formateur.user.save(update_fields=['username', 'email', 'first_name', 'last_name'])
            if provisional_password:
                User = get_user_model()
                user = formateur.user or User.objects.create_user(
                    username=email, email=email, first_name=formateur.prenom, last_name=formateur.nom,
                    password=provisional_password,
                )
                if formateur.user_id:
                    user.set_password(provisional_password)
                    user.save(update_fields=['password'])
                formateur.user = user
                formateur.doit_changer_mot_de_passe = True
                formateur.save(update_fields=['user', 'doit_changer_mot_de_passe'])
                if share_access:
                    from urllib.parse import quote
                    phone = ''.join(char for char in formateur.telephone if char.isdigit())
                    message = (
                        f"Bonjour {formateur.prenom} {formateur.nom}, voici vos accès à l’espace formateur SAREF Academy. "
                        f"Lien : {request.build_absolute_uri('/connexion/')} Identifiant : {formateur.email}. "
                        f"Mot de passe provisoire : {provisional_password}. Connectez-vous puis changez-le."
                    )
                    access_to_share = {
                        'password': provisional_password,
                        'whatsapp_url': f"https://wa.me/{phone}?text={quote(message)}" if phone else '',
                    }
                    messages.success(request, "Le nouveau mot de passe est enregistré. Vous pouvez maintenant partager les identifiants.")
                else:
                    messages.success(request, "Le profil est enregistré et un nouveau mot de passe provisoire a été défini.")
            else:
                messages.success(request, "Les informations du formateur ont été enregistrées.")
            if not share_access:
                return redirect('admin_formateur_detail', pk=formateur.pk)
    return render(request, 'admin/formateur_detail.html', {
        'formateur': formateur,
        'formateur_id': formateur.pk,
        'formations': formations,
        'access_to_share': access_to_share,
    })

def admin_vagues(request):
    return render(request, 'admin/vagues.html')

def admin_vague_archive(request, pk=1):
    return render(request, 'admin/vague_archive.html')

def admin_parametres(request):
    return render(request, 'admin/parametres.html')

def admin_chapitre_detail(request, formation_id=1, chapitre_id=1):
    return render(request, 'admin/chapitre_detail.html', {
        'formation_id': formation_id,
        'chapitre_id': chapitre_id
    })

def handel404(request, exception=None):
    return render(request, 'error_404.html', status=404)

def handel500(request):
    return render(request, 'error_500.html', status=500)

def formateur_apprenants(request):
    return render(request, 'formateur/apprenants.html', {
        'formateur': getattr(request.user, 'profil_formateur', None),
    })

def formateur_formations(request):
    formateur = getattr(request.user, 'profil_formateur', None)
    formations = formateur.formations.all().prefetch_related('modules') if formateur else Formation.objects.none()
    return render(request, 'formateur/formations.html', {
        'formateur': formateur,
        'formations': formations,
    })

def formateur_module_ajouter(request):
    # Redirige vers la page module (formulaire d'ajout à intégrer plus tard)
    return render(request, 'formateur/formations.html', {
        'formateur': getattr(request.user, 'profil_formateur', None),
    })

def formateur_module_modifier(request, pk=1):
    return render(request, 'formateur/formations.html', {'pk': pk, 'formateur': getattr(request.user, 'profil_formateur', None)})

def formateur_module_supprimer(request, pk=1):
    return render(request, 'formateur/formations.html', {'pk': pk, 'formateur': getattr(request.user, 'profil_formateur', None)})

def formateur_chapitre_ajouter(request):
    return render(request, 'formateur/formations.html', {
        'formateur': getattr(request.user, 'profil_formateur', None),
    })

def formateur_chapitre_detail(request, formation_id=1, chapitre_id=1):
    return render(request, 'formateur/chapitre_detail.html', {
        'formateur': getattr(request.user, 'profil_formateur', None),
        'formation_id': formation_id,
        'chapitre_id': chapitre_id,
    })
