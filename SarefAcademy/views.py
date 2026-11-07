from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render


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


# -----------------------------------------------------------------------------
# Candidatures
# -----------------------------------------------------------------------------

def candidature(request):
    return render(request, 'candidature.html')


def candidature_formation(request):
    return render(request, 'bourse_postule/candidature.html')


def connexion_etudiant(request):
    return render(request, 'Espace_etudiants/connexion.html')


def inscription_etudiant(request):
    return render(request, 'Espace_etudiants/inscription.html')


def dashboard_etudiant(request):
    return render(request, 'Espace_etudiants/dashboard.html')


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

def apprenant_dashboard(request):
    return render(request, 'apprenant/dashboard.html')


def apprenant_formations(request):
    return render(request, 'apprenant/formations.html')


def apprenant_formation_detail(request, pk=1):
    return render(request, 'apprenant/formation_detail.html')


def apprenant_modules(request):
    return render(request, 'apprenant/modules.html')


def apprenant_module_detail(request, pk=1):
    return render(request, 'apprenant/chapitre_detail.html')


def apprenant_paiements(request):
    return render(request, 'apprenant/paiements.html')


def apprenant_profil(request):
    return render(request, 'apprenant/profil.html')


def apprenant_parametres(request):
    return render(request, 'apprenant/parametres.html')


# -----------------------------------------------------------------------------
# Espace gestion
# -----------------------------------------------------------------------------

def admin_configuration_initiale(request):
    return render(request, 'admin/configuration_initiale.html')


def admin_configuration_vague(request):
    return render(request, 'admin/configuration_vague.html')


def admin_dashboard(request):
    return render(request, 'admin/dashboard.html')


def admin_candidatures(request):
    return render(request, 'admin/candidatures.html')


def admin_candidature_detail(request, pk=1):
    return render(request, 'admin/candidature_detail.html', {'pk': pk})


def admin_apprenants(request):
    return render(request, 'admin/apprenants.html')


def admin_apprenant_detail(request, pk=1):
    return render(request, 'admin/apprenant_detail.html', {'pk': pk})


def admin_resultats(request):
    return render(request, 'admin/resultats.html')


def admin_finance(request):
    return render(request, 'admin/finance.html')


def admin_organisation(request):
    return render(request, 'admin/organisation.html')


def admin_formations(request):
    return render(request, 'admin/formations.html')


def admin_formation_detail(request, pk=1):
    return render(request, 'admin/formation_detail.html', {'pk': pk})


def admin_chapitre_detail(request, formation_id=1, chapitre_id=1):
    return render(request, 'admin/chapitre_detail.html', {
        'formation_id': formation_id,
        'chapitre_id': chapitre_id,
    })


def admin_formateurs(request):
    return render(request, 'admin/formateurs.html')


def admin_formateur_detail(request, pk=1):
    return render(request, 'admin/formateur_detail.html', {'pk': pk})


def admin_vagues(request):
    return render(request, 'admin/vagues.html')


def admin_vague_archive(request, pk=1):
    return render(request, 'admin/vague_archive.html', {'pk': pk})


def admin_parametres(request):
    return render(request, 'admin/parametres.html')


# -----------------------------------------------------------------------------
# Pages d’erreur
# -----------------------------------------------------------------------------

def handel404(request, exception=None):
    return render(request, 'error_404.html', status=404)


def handel500(request):
    return render(request, 'error_500.html', status=500)
