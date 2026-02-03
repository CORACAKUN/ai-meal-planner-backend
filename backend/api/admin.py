from django.contrib import admin
from .models import Meal, UserProfile, MealFeedback

admin.site.register(Meal)
admin.site.register(UserProfile)
admin.site.register(MealFeedback)
