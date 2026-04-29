from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0011_usermealplan"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermealplan",
            name="is_eaten",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usermealplan",
            name="eaten_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
