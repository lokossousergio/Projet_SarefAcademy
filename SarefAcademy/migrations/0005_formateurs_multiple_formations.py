from django.db import migrations, models
import django.db.models.deletion


def copy_primary_formation_to_assignments(apps, schema_editor):
    Formateurs = apps.get_model("SarefAcademy", "Formateurs")
    database = schema_editor.connection.alias
    for formateur in Formateurs.objects.using(database).exclude(formation_id=None).iterator():
        formateur.formations.add(formateur.formation_id)


def restore_primary_formation(apps, schema_editor):
    Formateurs = apps.get_model("SarefAcademy", "Formateurs")
    database = schema_editor.connection.alias
    for formateur in Formateurs.objects.using(database).iterator():
        first_formation = formateur.formations.using(database).first()
        if first_formation:
            formateur.formation_id = first_formation.pk
            formateur.save(using=database, update_fields=["formation"])


class Migration(migrations.Migration):
    dependencies = [("SarefAcademy", "0004_chapitres_description_est_active")]

    operations = [
        migrations.AlterField(
            model_name="formateurs",
            name="formation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="formateurs",
                to="SarefAcademy.formation",
            ),
        ),
        migrations.AddField(
            model_name="formateurs",
            name="formations",
            field=models.ManyToManyField(
                blank=True,
                related_name="formateurs_assignes",
                to="SarefAcademy.formation",
            ),
        ),
        migrations.RunPython(copy_primary_formation_to_assignments, restore_primary_formation),
        migrations.RemoveField(model_name="formateurs", name="formation"),
        migrations.AlterField(
            model_name="formateurs",
            name="formations",
            field=models.ManyToManyField(
                blank=True,
                related_name="formateurs",
                to="SarefAcademy.formation",
            ),
        ),
    ]
