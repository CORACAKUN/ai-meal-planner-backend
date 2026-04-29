from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0012_usermealplan_eaten_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="meal",
            name="ingredients",
            field=models.TextField(blank=True, null=True),
        ),
    ]
