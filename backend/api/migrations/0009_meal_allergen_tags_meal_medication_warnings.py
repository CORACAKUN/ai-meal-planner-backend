from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0008_userprofile_allergies_userprofile_maintenance_medications"),
    ]

    operations = [
        migrations.AddField(
            model_name="meal",
            name="allergen_tags",
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
        migrations.AddField(
            model_name="meal",
            name="medication_warnings",
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]
