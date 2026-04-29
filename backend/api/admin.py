from django.contrib import admin
from .models import Meal, MealFeedback, UserMealPlan, UserProfile

admin.site.register(Meal)
admin.site.register(UserProfile)
admin.site.register(MealFeedback)
admin.site.register(UserMealPlan)
