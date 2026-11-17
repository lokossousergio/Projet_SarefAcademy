from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from SarefAcademy.models import (
    Candidats,
    Chapitres,
    ChapitreTermine,
    ConfigVague,
    Etudiants,
    Formation,
    Formateurs,
    Modules,
    Paiement,
)


def build_demo_pdf():
    stream = b"BT /F1 18 Tf 72 720 Td (Support de demonstration SAREF Academy) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(pdf)


class Command(BaseCommand):
    help = "Ajoute un jeu de données de démonstration, sans doublons."

    def handle(self, *args, **options):
        now = timezone.now()
        vague = ConfigVague.objects.filter(est_courante=True).first()
        if vague is None:
            vague, _ = ConfigVague.objects.get_or_create(
                nom="Vague de démonstration",
                defaults={
                    "date_debut": now - timedelta(days=14),
                    "date_fin": now + timedelta(days=90),
                    "est_courante": True,
                    "annee_academique": str(now.year),
                },
            )
            if not vague.est_courante:
                vague.est_courante = True
                vague.save(update_fields=["est_courante"])

        web, _ = Formation.objects.get_or_create(
            nom="Développement Web — démonstration",
            defaults={"duree": 4, "prix": "120000.00", "nb_tranches": 3,
                      "description": "Parcours d'exemple pour découvrir la création de sites web.", "statut": "active"},
        )
        marketing, _ = Formation.objects.get_or_create(
            nom="Marketing Digital — démonstration",
            defaults={"duree": 3, "prix": "90000.00", "nb_tranches": 3,
                      "description": "Exemple de formation et de candidature en attente.", "statut": "active"},
        )
        module_web, _ = Modules.objects.get_or_create(
            formation=web, ordre=1,
            defaults={"titre": "Les bases du Web", "description": "Premiers pas avec les pages et les navigateurs.", "est_active": True},
        )
        module_marketing, _ = Modules.objects.get_or_create(
            formation=marketing, ordre=1,
            defaults={"titre": "Introduction au marketing numérique", "description": "Un module de démonstration en préparation.", "est_active": True},
        )
        demo_modules = [
            (web, 2, "HTML et structure des pages", "Construire les premières pages web.", True,
             [("Les balises essentielles", "Titres, paragraphes, liens et images.", 25, True),
              ("Créer une page complète", "Assembler le contenu d'une page web.", 30, True)]),
            (web, 3, "CSS et mise en forme", "Donner une identité visuelle au site.", False,
             [("Sélecteurs et couleurs", "Découvrir les règles et propriétés CSS.", 22, False),
              ("Mise en page responsive", "Adapter le site aux écrans mobiles.", 28, False)]),
            (marketing, 2, "Réseaux sociaux et contenu", "Créer une présence cohérente sur les réseaux.", True,
             [("Choisir ses plateformes", "Identifier les réseaux adaptés à son public.", 20, True),
              ("Construire un calendrier éditorial", "Planifier ses publications et formats.", 25, False)]),
            (marketing, 3, "Mesurer ses résultats", "Suivre les performances des actions numériques.", False,
             [("Indicateurs clés", "Comprendre portée, engagement et conversion.", 18, False),
              ("Lire un tableau de bord", "Interpréter les résultats d'une campagne.", 24, False)]),
        ]
        for demo_formation, order, title, description, active, chapter_specs in demo_modules:
            demo_module, _ = Modules.objects.get_or_create(
                formation=demo_formation, ordre=order,
                defaults={"titre": title, "description": description, "est_active": active},
            )
            for chapter_order, (chapter_title, chapter_description, duration, chapter_active) in enumerate(chapter_specs, start=1):
                Chapitres.objects.get_or_create(
                    modules=demo_module, ordre=chapter_order,
                    defaults={"nom": chapter_title, "description": chapter_description,
                              "duree": duration, "est_active": chapter_active},
                )
        chapter, _ = Chapitres.objects.get_or_create(
            modules=module_web, ordre=1,
            defaults={
                "nom": "Comment fonctionne le Web ?",
                "description": "Comprendre le rôle du navigateur, du serveur et des échanges HTTP.",
                "duree": 12,
                "support_video_url": "https://www.youtube.com/embed/aqz-KE-bpKQ",
                "est_active": True,
            },
        )
        if not chapter.support_pdf:
            chapter.support_pdf.save("support-demo-saref.pdf", ContentFile(build_demo_pdf()), save=True)
        Chapitres.objects.get_or_create(
            modules=module_web, ordre=2,
            defaults={"nom": "Préparer son environnement de travail",
                      "description": "Chapitre brouillon pour illustrer un contenu désactivé.",
                      "duree": 18, "est_active": False},
        )

        student, _ = Etudiants.objects.get_or_create(
            email="aicha.demo@example.com",
            defaults={"nom": "Mensah", "prenom": "Aïcha", "telephone": "+229 90 00 00 01", "niveau_etudes": "Licence"},
        )
        pending_student, _ = Etudiants.objects.get_or_create(
            email="paul.demo@example.com",
            defaults={"nom": "Adjovi", "prenom": "Paul", "telephone": "+229 90 00 00 02", "niveau_etudes": "Baccalauréat"},
        )
        accepted, _ = Candidats.objects.get_or_create(
            etudiant=student, formation=web, configVague=vague,
            defaults={"motif_inscription": "Je souhaite apprendre à créer des sites web.", "statut": "accepte", "date_decision": now},
        )
        Candidats.objects.get_or_create(
            etudiant=pending_student, formation=marketing, configVague=vague,
            defaults={"motif_inscription": "Je souhaite découvrir le marketing digital.", "statut": "en_attente"},
        )
        marie, _ = Formateurs.objects.get_or_create(
            email="marie.demo@example.com",
            defaults={"nom": "Hounkpe", "prenom": "Marie", "telephone": "+229 90 00 00 03", "actif": True},
        )
        marie.formations.add(web, marketing)
        self.ensure_formateur_account(marie)
        jean, _ = Formateurs.objects.get_or_create(
            email="jean.demo@example.com",
            defaults={"nom": "Kiki", "prenom": "Jean", "telephone": "+229 90 00 00 04", "actif": True},
        )
        jean.formations.add(marketing)
        self.ensure_formateur_account(jean)
        ChapitreTermine.objects.get_or_create(candidats=accepted, chapitre=chapter)
        Paiement.objects.get_or_create(
            candidats=accepted, tranche=1,
            defaults={"configVague": vague, "formation": web, "montant": "40000.00", "date": now, "mode": "mobile_money"},
        )
        self.stdout.write(self.style.SUCCESS("Données de démonstration ajoutées (ou déjà présentes)."))

    def ensure_formateur_account(self, formateur):
        User = get_user_model()
        user = formateur.user
        created = False
        if user is None:
            user, created = User.objects.get_or_create(
                username=formateur.email,
                defaults={
                    "email": formateur.email,
                    "first_name": formateur.prenom,
                    "last_name": formateur.nom,
                },
            )
            if created:
                user.set_password("SarefDemo2026!")
                user.save(update_fields=["password"])
            formateur.user = user
        if created:
            formateur.doit_changer_mot_de_passe = True
        formateur.save(update_fields=["user", "doit_changer_mot_de_passe"])
