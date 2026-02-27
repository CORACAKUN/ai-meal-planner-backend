from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    age = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)

    # Activities: comma-separated list (e.g., "walking,running,swimming")
    activities = models.TextField(null=True, blank=True)
    # Calculated activity level: sedentary/light/moderate/active/very_active
    activity_level = models.CharField(max_length=20, null=True, blank=True)
    
    # Weight goal: lose/maintain/gain
    weight_goal = models.CharField(max_length=20, null=True, blank=True)

    # 01 - Budget + Religion/Culture preferences (backend-first)
    budget_level = models.CharField(max_length=20, null=True, blank=True)  # cheap/medium/expensive
    dietary_rules = models.TextField(null=True, blank=True)  # e.g. "halal,no_blood,no_pork"
    culture_preference = models.CharField(max_length=100, null=True, blank=True)  # e.g. "filipino"
    preferred_meal_time = models.CharField(max_length=20, null=True, blank=True)  # breakfast/lunch/dinner/snack
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
    
    # 01 - Meal time + Budget + Culture tags
    meal_time = models.CharField(max_length=20, null=True, blank=True)  # breakfast/lunch/dinner/snack
    price_level = models.CharField(max_length=20, null=True, blank=True)  # cheap/medium/expensive
    culture_tags = models.CharField(max_length=200, null=True, blank=True)  # "filipino,japanese"

    # 01 - Religion/culture restrictions (minimal flags)
    has_pork = models.BooleanField(default=False)
    has_blood = models.BooleanField(default=False)
    has_alcohol = models.BooleanField(default=False)
    
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
