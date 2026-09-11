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
# dd
# ============================================================
# page dacceuil du site 
def index(request):


    if request.method == 'POST':
        nom_prenom = request.POST.get('nom_prenom', "").strip()
        email = request.POST.get('email' , "").strip()
        number = request.POST.get('number', "").strip()
        niveau_etudes = request.POST.get('niveau_etudes', "").strip()
        motif_inscription=request.POST.get('reason',"").strip()
        from django.core.mail import send_mail

   
        # Create a new user instance
        users=Canditats.objects.create(nom_prenom=nom_prenom, email=email, number=number, niveau_etudes=niveau_etudes , motif_inscription=motif_inscription)
        request.session["inscription"]=True
        nom_prenom = users.nom_prenom  # Get the nom_prenom of the newly created user
        send_inscription_success_email(request, nom_prenom, users.email)  # Call the email sending function
     
        return redirect('insrciption-valide')  # Redirect to the index page after successful registration

    param = Parametre.objects.filter(Etat="Actif").first()

    
        

    return render(request, 'index.html' , {"param":param})


def insrciption_valide(request):
    return render(request , 'info.html')

# =======================================================================

def tunel(request):
    return render(request, 'tunel.html')




# ================================================================
# messages de confirmation envoyer par mail
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
def send_inscription_success_email(request, nom, email):
    """
    Envoie l'email de confirmation d'inscription au candidat.
    Retourne True si l'envoi a réussi, False sinon.
    """

    annee = datetime.now().year

    subject = "Inscription - Saref Academy"
    whatsapp_academy = "+229 01 54 15 05 30"

    html_message = f"""
<div style="padding:20px; font-family:'Segoe UI',Roboto,Arial,sans-serif;">
    <div style="max-width:520px; margin:auto; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(49,91,234,0.15);">

        <!-- Header -->
        <div style="background:#f4f7ff; padding:20px 20px 16px 20px; text-align:center; border-bottom:3px solid #315BEA;">
            <img src="https://i.postimg.cc/qMHxS6Wg/Whats-App-Image-2026-08-16-at-23-12-49-removebg-preview.png"
                alt="Saref Academy"
                style="height:90px; width:auto; object-fit:contain; display:block; margin:0 auto 10px auto; border-radius:8px">

            <p style="margin:0; color:#315BEA; font-size:11px; letter-spacing:4px; text-transform:uppercase; font-weight:600;">
                Inscription bourse de formation
            </p>
        </div>

        <!-- Content -->
        <div style="padding:32px 24px; text-align:center;">

            <p style="font-size:14px; color:#888; margin:0 0 4px 0;">
                Bonjour <strong style="color:#315BEA;">{nom}</strong>
            </p>

            <p style="font-size:19px; color:#111827; font-weight:700; margin:0 0 8px 0; line-height:1.35;">
                Attention, lisez ceci pour valider
            </p>

            <p style="font-size:13px; color:#888; margin:0 0 28px 0;">
                Vous avez postulé avec succès à la bourse de formation en Marketing Digital.
            </p>

            <!-- Derniere etape -->
            <div style="background:#EEF2FF; border:1px solid #DDE5FF; border-radius:16px; padding:24px 20px; margin:0 auto 24px auto; max-width:340px; text-align:center;">

                <div style="display:inline-block; background:#fff1e8; color:#ea580c; border-radius:8px; padding:5px 10px; margin:0 0 12px 0; font-size:10px; font-weight:800; letter-spacing:.06em; text-transform:uppercase;">
                    &#9888; Action requise
                </div>

                <p style="margin:0 0 6px 0; font-size:15px; font-weight:700; color:#111827;">
                    Une dernière étape importante
                </p>

                <p style="margin:0; font-size:13px; color:#475569; line-height:1.6;">
                    Rejoignez maintenant la <strong style="color:#111827;">chaîne WhatsApp officielle</strong>
                    de Saref Academy. C'est sur cette chaîne que nous partagerons toutes les informations
                    importantes concernant votre candidature : prochaines étapes, annonces, dates
                    importantes et instructions à suivre.
                    <br><br>
                    <a href="https://whatsapp.com/channel/0029VbD91sw545uo0Tesap18"
                       style="color:#315BEA; text-decoration:underline; font-weight:600;">
                        Cliquez ici pour rejoindre la chaîne WhatsApp
                    </a>
                </p>

            </div>

            <!-- Warning -->
            <div style="background:#fff8e1; border-radius:10px; padding:12px 16px; margin:0 auto; max-width:340px;">
                <p style="margin:0; font-size:12px; color:#b45309;">
                    ⏱️ Cette étape est indispensable pour recevoir toutes les informations, ne tardez pas
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

        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",

            headers={
                "accept": "application/json",
                "api-key": settings.BREVO_API_KEY,
                "content-type": "application/json",
            },

            json={
                "sender": {
                    "name": settings.BREVO_SENDER_NAME,
                    "email": settings.BREVO_SENDER_EMAIL,
                },

                "to": [
                    {
                        "email": email,
                        "name": nom,
                    }
                ],

                "subject": subject,
                "htmlContent": html_message,
            },

            timeout=20,
        )

        print("STATUS BREVO :", response.status_code)
        print("REPONSE BREVO :", response.text)

        if response.ok:

            print(f"[email] Email envoyé avec succès à {email}")

            return True

        else:

            print(
                f"[email] Erreur Brevo pour {email} : "
                f"{response.status_code} - {response.text}"
            )

            return False

    except requests.Timeout:

        print(f"[email] Timeout en envoyant à {email}")

        return False

    except requests.RequestException as e:

        print(f"[email] Erreur réseau Brevo pour {email} : {e}")

        return False

    except Exception as e:

        print(f"[email] Erreur inattendue pour {email} : {e}")

        return False
    
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
        email_wait="sarefacademy@gmail.com"
        password_wait="uSXL69"
  

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
        

# ==========================================================

def supprimer_candidat(request , id_user):

    Canditats.objects.filter(id=id_user).delete()
    return redirect ('admin_dashboard')
    
# =====================================================

# deconnexion admin
def deconnexion(request):
    request.session.flush()
    return redirect('connexion_admin')

# ============================================================
# views.py
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def telecharger_pdf_jour(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Liste_des_candidats_du_jour.pdf"'

    # Date du jour
    aujourdhui = timezone.now().date()

    # Filtrer les candidats inscrits aujourd'hui
    candidats = Canditats.objects.filter(date_inscription__date=aujourdhui)

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=16)
    date_style = ParagraphStyle('date', parent=styles['Normal'], fontSize=11, textColor=colors.grey)

    story = []
    story.append(Paragraph("Liste des candidats inscrits aujourd'hui", title_style))
    story.append(Paragraph(f"Date : {aujourdhui.strftime('%d/%m/%Y')}", date_style))
    story.append(Spacer(1, 14))

    # En-têtes et données du tableau
    headers = [ "N°" ,"Nom & Prénom", "Email", "Numéro", "Niveau d'études" ]
    data = [headers]
    for c in candidats:
        data.append([c.id , c.nom_prenom, c.email, c.number, c.niveau_etudes ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    doc.build(story)
    return response



# =====================================================

def telecharger_pdf_all(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Liste_des_candidats_général_campagne.pdf"'

   
    # Filtrer les candidats inscrits aujourd'hui
    candidats = Canditats.objects.all()

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=16)
    date_style = ParagraphStyle('date', parent=styles['Normal'], fontSize=11, textColor=colors.grey)

    story = []
    story.append(Paragraph("    Liste des candidats  incrits lors de la campagne", title_style))

    story.append(Spacer(1, 14))

    # En-têtes et données du tableau
    headers = [ "N°" ,"Nom & Prénom", "Email", "Numéro", "Niveau d'études" ]
    data = [headers]
    for c in candidats:
        data.append([ c.id ,c.nom_prenom, c.email, c.number, c.niveau_etudes ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    doc.build(story)
    return response