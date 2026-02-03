from django.urls import path
from .views import (
    health_check,
    register,
    login,
    update_profile,
    get_profile,
    get_meals,
    get_meals_with_constraints,
    get_nutrition_summary,
    get_recommended_meals,
    submit_feedback
)

urlpatterns = [
    path('health/', health_check),
    path('register/', register),
    path('login/', login),
    path('profile/<int:user_id>/', update_profile),             # PUT
    path('profile/<int:user_id>/get/', get_profile),            # GET
    path('meals/', get_meals),                                   # GET
    path('meals/<int:user_id>/filtered/', get_meals_with_constraints),  # GET
    path('nutrition/<int:user_id>/', get_nutrition_summary),    # GET
    path('recommend/<int:user_id>/', get_recommended_meals),    # GET
    path('feedback/', submit_feedback),                          # POST ⭐
]
