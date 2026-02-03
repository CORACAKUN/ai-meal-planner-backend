from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    age = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)

    activity_level = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.user.username


class Meal(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    calories = models.FloatField()
    protein = models.FloatField()
    carbs = models.FloatField()
    fats = models.FloatField()

    is_vegetarian = models.BooleanField(default=False)
    is_halal = models.BooleanField(default=False)

    image_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


class MealFeedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    rating = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.meal.name} ({self.rating})"
