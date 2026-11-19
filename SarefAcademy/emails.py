"""Envoi des e-mails transactionnels via l'API Brevo (ex-Sendinblue).

Configuration attendue dans settings.py (ou variables d'environnement / .env) :
    BREVO_API_KEY        clé API v3 (Brevo > SMTP & API > Clés API)
    BREVO_SENDER_EMAIL   adresse expéditrice VALIDÉE dans Brevo (Expéditeurs)
    BREVO_SENDER_NAME    nom affiché de l'expéditeur
"""

import logging

import requests
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class EnvoiEmailErreur(Exception):
    """Levée quand l'e-mail n'a pas pu être remis à Brevo ; le message est affichable à l'utilisateur."""


def envoyer_email(destinataire, sujet, template, contexte, nom_destinataire=""):
    """Rend `template` (.html + .txt) et l'envoie via Brevo.

    Lève EnvoiEmailErreur avec un message clair en cas d'échec.
    """
    html = render_to_string(f"{template}.html", contexte)
    texte = render_to_string(f"{template}.txt", contexte)

    cle = getattr(settings, "BREVO_API_KEY", "")
    expediteur = getattr(settings, "BREVO_SENDER_EMAIL", "")

    # En développement sans clé : on affiche l'e-mail dans la console au lieu d'échouer.
    if not cle:
        if settings.DEBUG:
            logger.warning("BREVO_API_KEY absente : e-mail non envoyé.\nÀ : %s\nSujet : %s\n%s", destinataire, sujet, texte)
            print(f"\n[E-MAIL DEV] À : {destinataire} | {sujet}\n{texte}\n")
            return
        logger.error("BREVO_API_KEY n'est pas configurée.")
        raise EnvoiEmailErreur("Une erreur est survenue lors de l'envoi de l'e-mail. Veuillez réessayer plus tard.")
    if not expediteur:
        logger.error("BREVO_SENDER_EMAIL n'est pas configurée.")
        raise EnvoiEmailErreur("Une erreur est survenue lors de l'envoi de l'e-mail. Veuillez réessayer plus tard.")

    payload = {
        "sender": {"email": expediteur, "name": getattr(settings, "BREVO_SENDER_NAME", "Saref Academy")},
        "to": [{"email": destinataire, **({"name": nom_destinataire} if nom_destinataire else {})}],
        "subject": sujet,
        "htmlContent": html,
        "textContent": texte,
    }

    try:
        reponse = requests.post(
            BREVO_URL,
            json=payload,
            headers={"api-key": cle, "accept": "application/json"},
            timeout=10,
        )
    except requests.Timeout:
        logger.error("Brevo : délai dépassé pour %s", destinataire)
        raise EnvoiEmailErreur("Le serveur d'e-mails ne répond pas. Réessayez dans quelques instants.")
    except requests.RequestException as exc:
        logger.error("Brevo : erreur réseau pour %s : %s", destinataire, exc)
        raise EnvoiEmailErreur("Impossible de joindre le serveur d'e-mails. Vérifiez la connexion et réessayez.")

    if reponse.status_code in (200, 201, 202):
        return

    # Brevo renvoie {"code": "...", "message": "..."} : on le journalise pour l'admin.
    try:
        detail = reponse.json()
    except ValueError:
        detail = reponse.text[:300]
    logger.error("Brevo HTTP %s pour %s : %s", reponse.status_code, destinataire, detail)

    if reponse.status_code == 429:
        raise EnvoiEmailErreur("Trop d'envois en peu de temps. Patientez une minute puis réessayez.")
    if reponse.status_code == 400:
        raise EnvoiEmailErreur("L'e-mail n'a pas pu être envoyé à cette adresse. Vérifiez-la et réessayez.")
    # Pour 401 ou toute autre erreur serveur, message neutre pour l'utilisateur
    raise EnvoiEmailErreur("Une erreur est survenue lors de l'envoi de l'e-mail. Veuillez réessayer dans quelques instants.")
