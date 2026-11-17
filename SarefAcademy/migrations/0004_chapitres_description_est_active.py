from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("SarefAcademy", "0003_alter_etudiants_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="chapitres",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Résumé et objectifs pédagogiques du chapitre",
            ),
        ),
        migrations.AddField(
            model_name="chapitres",
            name="est_active",
            field=models.BooleanField(default=False, verbose_name="Visible par les apprenants"),
        ),
        migrations.AddField(
            model_name="chapitres",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Dernière mise à jour"),
        ),
    ]
