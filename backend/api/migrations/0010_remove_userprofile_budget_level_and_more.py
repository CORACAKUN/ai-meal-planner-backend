from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0009_meal_allergen_tags_meal_medication_warnings"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="budget_level",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="culture_preference",
        ),
    ]
