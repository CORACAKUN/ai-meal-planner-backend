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

    # Preference and safety filters
    dietary_rules = models.TextField(null=True, blank=True)  # e.g. "halal,no_blood,no_pork"
    preferred_meal_time = models.CharField(max_length=20, null=True, blank=True)  # breakfast/lunch/dinner/snack
    allergies = models.TextField(null=True, blank=True)
    maintenance_medications = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.user.username


class Meal(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True, null=True)

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
    allergen_tags = models.CharField(max_length=300, null=True, blank=True)  # e.g. "egg,milk,fish,peanut"
    medication_warnings = models.CharField(max_length=300, null=True, blank=True)  # e.g. "warfarin,statin"
    
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


class UserMealPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    scheduled_date = models.DateField()
    meal_time = models.CharField(max_length=20, null=True, blank=True)
    is_eaten = models.BooleanField(default=False)
    eaten_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date", "meal_time", "id"]

    def __str__(self):
        label = self.meal_time or "meal"
        return f"{self.user.username} - {self.meal.name} on {self.scheduled_date} ({label})"
