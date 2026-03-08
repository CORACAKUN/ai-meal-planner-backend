from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0007_userprofile_activities_userprofile_weight_goal"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="allergies",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="maintenance_medications",
            field=models.TextField(blank=True, null=True),
        ),
    ]
