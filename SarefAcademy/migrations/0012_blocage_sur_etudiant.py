from django.db import migrations, models


def copier_blocages(apps, schema_editor):
    """Un étudiant dont au moins une candidature était bloquée devient bloqué."""
    Etudiants = apps.get_model("SarefAcademy", "Etudiants")
    Etudiants.objects.filter(candidats__est_bloque=True).update(est_bloque=True)


def restaurer_blocages(apps, schema_editor):
    Candidats = apps.get_model("SarefAcademy", "Candidats")
    Candidats.objects.filter(etudiant__est_bloque=True).update(est_bloque=True)


class Migration(migrations.Migration):

    dependencies = [
        ("SarefAcademy", "0011_candidats_cv"),
    ]

    operations = [
        migrations.AddField(
            model_name="etudiants",
            name="est_bloque",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copier_blocages, restaurer_blocages),
        migrations.RemoveField(
            model_name="candidats",
            name="est_bloque",
        ),
    ]
