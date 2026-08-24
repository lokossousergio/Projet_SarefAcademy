from django.shortcuts import redirect, render
from django.http import HttpResponse
from .models import Canditats, Admin, Parametre
import requests

from django.http import HttpResponse
from django.contrib import messages
# makepassword 
from django.contrib.auth.hashers import make_password , check_password

from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.core.mail import get_connection, EmailMultiAlternatives


# Create your views here.
import requests
from django.shortcuts import render

# ============================================================
# page dacceuil du site 
def index(request):


    if request.method == 'POST':
        nom_prenom = request.POST.get('nom_prenom', "").strip()
        email = request.POST.get('email' , "").strip()
        number = request.POST.get('number', "").strip()
        niveau_etudes = request.POST.get('niveau_etudes', "").strip()

        # Create a new user instance
        users=Canditats.objects.create(nom_prenom=nom_prenom, email=email, number=number, niveau_etudes=niveau_etudes)
        nom_prenom = users.nom_prenom  # Get the nom_prenom of the newly created user
        send_inscription_success_email(request, nom_prenom, users.email)  # Call the email sending function
        
        messages.success(request, f'User registered successfully {nom_prenom}! ')
        return redirect('index')  # Redirect to the index page after successful registration

    param = Parametre.objects.filter(Etat="Actif").first()

    
        

    return render(request, 'index.html' , {"param":param})



# =======================================================================

def tunel(request):
    return render(request, 'tunel.html')






# ================================================================
# messages de confirmation envoyer par mail
from django.conf import settings

from datetime import datetime
annee = datetime.now().year   
def send_inscription_success_email(request, nom, email):
    """
    Envoie l'email de confirmation d'inscription au candidat.

    logo_url : URL absolue du logo, ex :
        request.build_absolute_uri(static('Images/WhatsApp_Image_2026-08-17_at_18.19.27-removebg-preview.png'))
    """

    subject = "Inscription confirmée - Saref Academy"
    whatsapp_academy = "+229 01 54 15 05 30"  # <-- remplace par le vrai numero

    html_message = f"""
    <div style="padding:20px; font-family:'Segoe UI',Roboto,Arial,sans-serif;">
    <div style="max-width:520px; margin:auto; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(49,91,234,0.15);">

        <!-- Header -->
        <div style="background:#ffffff; padding:20px 20px 16px 20px; text-align:center; border-bottom:3px solid #315BEA;">
            <img src="https://i.postimg.cc/HLznQTn2/Whats-App-Image-2026-08-16-at-23-12-49.jpg" alt="Saref Academy"
                style="height:90px; width:auto; object-fit:contain; display:block; margin:0 auto 10px auto; background:white; border-radius:8px">
            <p style="margin:0; color:#315BEA; font-size:11px; letter-spacing:4px; text-transform:uppercase; font-weight:600;">
                Inscription bourse de formation
            </p>
        </div>

        <!-- Content -->
        <div style="padding:32px 24px; text-align:center;">

            <p style="font-size:16px; color:#333; margin:0 0 6px 0;">
                Bonjour <strong style="color:#315BEA;">{nom}</strong>
            </p>

            <p style="font-size:13px; color:#888; margin:0 0 28px 0;">
                Votre candidature à la bourse de formation en Marketing Digital a bien été enregistrée
            </p>

      

        <!-- Derniere etape -->
<div style="background:#EEF2FF; border:1px solid #DDE5FF; border-radius:16px; padding:22px 20px; margin:0 auto 24px auto; max-width:340px; text-align:center;">

    <div style="width:42px; height:42px; margin:0 auto 14px auto; background:#315BEA; border-radius:50%; text-align:center; line-height:42px;">
        <span style="font-size:18px;">&#128241;</span>
    </div>

    <p style="margin:0 0 14px 0; font-size:13px; color:#475569; line-height:1.6;">
        Dernière étape pour valider votre place :<br>
        envoyez votre <strong style="color:#111827;">nom et prénom</strong> sur WhatsApp au numéro ci-dessous
    </p>

    <div style="display:inline-block; background:#315BEA; border-radius:50px; padding:11px 24px;">
        <span style="font-size:16px; font-weight:700; letter-spacing:.5px; color:#ffffff;">
            {whatsapp_academy}
        </span>
    </div>

</div>

            <!-- Warning -->
            <div style="background:#fff8e1; border-radius:10px; padding:12px 16px; margin:0 auto; max-width:340px;">
                <p style="margin:0; font-size:12px; color:#b45309;">
                    ⏱️ Cette étape valide définitivement votre place, ne tardez pas
                </p>
            </div>

            <p style="font-size:12px; color:#aaa; margin:20px 0 0 0;">
                🔒 Vos informations restent strictement confidentielles.
            </p>

        </div>

        <!-- Divider -->
        <div style="height:1px; background:linear-gradient(to right, transparent, #cfdcfa, transparent); margin:0 24px;"></div>

        <!-- Footer -->
        <div style="background:#f4f7ff; padding:20px 24px; text-align:center;">
            <p style="margin:0 0 6px 0; font-size:13px; font-weight:700; color:#315BEA;">
                Saref Academy
            </p>
            <p style="margin:0; font-size:11px; color:#aaa;">
                © {annee} Tous droits réservés
                &nbsp;·&nbsp;
                <a href="mailto:Sarefacademy@gmail.com"
                style="color:#315BEA; text-decoration:none;">
                    contact@sarefacademy.com
                </a>
            </p>
        </div>

    </div>
    </div>
    """

    try:
        email_msg = EmailMultiAlternatives(
            subject,
            "Votre client ne supporte pas HTML",
            settings.DEFAULT_FROM_EMAIL,
            [email]
        )
        email_msg.attach_alternative(html_message, "text/html")
        email_msg.send()
        return True  # ← succès

    except TimeoutError:
      
        pass
      

    except Exception as e:
    
        print(str(e))
       

        pass
    
# ================Gestion des erreurs=======

def handel404( request , exception):  
    return render(request , 'error_404.html')

def handel500( request):
    return render(request , 'error_500.html')


# ================================================
# connexion admin
def connexion_admin(request):
    if request.method == 'POST':
        email = request.POST.get('email',"").strip()
        password = request.POST.get('password',"").strip()
        email_wait="lokossousergio156@gmail.com"
        password_wait="123"
        print(email)
        print(password)

        if email==email_wait and password==password_wait:
            request.session["Authentifiaction"]=True
            messages.success( request ,"Bienvenue dans votre espace administrateur")
           
          
            return redirect("admin_dashboard")
        else:

            messages.error( request ,"Email ou mot de passe incoreects veuillez ressayer")
            return redirect('connexion_admin')
        
    return render(request, 'connexion_admin.html')

# =======================================================

# administration page dashboad
def admin_dashboard(request):
     verify_Authentifiaction=request.session.get("Authentifiaction")
     print(verify_Authentifiaction)
     if not verify_Authentifiaction:
         return redirect('connexion_admin')
     else:

        from django.utils import timezone

        candidats_tle = Canditats.objects.count()

        candidats_insct_ajdh = Canditats.objects.filter(date_inscription__date=timezone.now().date() ).count()
        param = Parametre.objects.filter(Etat="Actif").first()
     

        candidats=Canditats.objects.all().order_by('-id')
    

        if request.method=="POST":
            date_ouverture=request.POST.get('date_ouverture')
            date_fermeture=request.POST.get('date_fermeture')
            print(date_fermeture)
            Parametre.objects.create(Date_ouverture_inscription=date_ouverture, Date_cloture_inscription=date_fermeture)
            
            return redirect ('admin_dashboard')
         
         
         

        return render(request , 'dashboard.html' ,{"param":param , "candidats":candidats , "nb_candidatures_tle": candidats_tle  , "nb_candidatures_aujourd_hui":candidats_insct_ajdh} )

# ============================================================

# suspension de la candidature en cours      
def suspension_delai_candidature(request):
    verify_Authentifiaction=request.session.get("Authentifiaction")
    print(verify_Authentifiaction)
    if not verify_Authentifiaction:
         return redirect('connexion_admin')
    else:
        if request.method=="POST":
            Parametre.objects.filter(Etat="Actif").delete()
            return redirect ('admin_dashboard')     
        
# =====================================================

# deconnexion admin
def deconnexion(request):
    request.session.flush()
    return redirect('connexion_admin')