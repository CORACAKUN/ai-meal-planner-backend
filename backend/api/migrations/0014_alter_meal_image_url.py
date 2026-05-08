from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0013_meal_ingredients"),
    ]

    operations = [
        migrations.AlterField(
            model_name="meal",
            name="image_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
