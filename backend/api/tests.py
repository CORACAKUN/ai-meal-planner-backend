from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Meal, UserProfile
from .views import randomize_similar_recommendations


class RecommendationTests(TestCase):
    def _create_profile(self, username, preferred_meal_time, weight_goal):
        user = User.objects.create_user(username=username, password="pass1234")
        UserProfile.objects.create(
            user=user,
            age=30,
            gender="male",
            height_cm=170,
            weight_kg=70,
            activities="walking",
            activity_level="light",
            weight_goal=weight_goal,
            preferred_meal_time=preferred_meal_time,
        )
        return user

    def _create_meal(self, name, calories, protein, carbs, fats, meal_time):
        return Meal.objects.create(
            name=name,
            description=f"{name} description",
            ingredients=f"{name} ingredients",
            calories=calories,
            protein=protein,
            carbs=carbs,
            fats=fats,
            is_halal=True,
            meal_time=meal_time,
            price_level="cheap",
            culture_tags="filipino,philippines,pinoy",
        )

    def test_recommendations_change_with_weight_goal_and_meal_time(self):
        self._create_meal(
            name="Light Breakfast Bowl",
            calories=280,
            protein=24,
            carbs=26,
            fats=7,
            meal_time="breakfast",
        )
        self._create_meal(
            name="Hearty Dinner Plate",
            calories=640,
            protein=34,
            carbs=72,
            fats=19,
            meal_time="dinner",
        )

        lose_user = self._create_profile("lose-user", "breakfast", "lose")
        gain_user = self._create_profile("gain-user", "dinner", "gain")

        lose_response = self.client.get(f"/api/recommend/{lose_user.id}/")
        gain_response = self.client.get(f"/api/recommend/{gain_user.id}/")

        self.assertEqual(lose_response.status_code, 200)
        self.assertEqual(gain_response.status_code, 200)

        lose_meals = lose_response.json()["meals"]
        gain_meals = gain_response.json()["meals"]

        self.assertEqual(lose_meals[0]["name"], "Light Breakfast Bowl")
        self.assertEqual(gain_meals[0]["name"], "Hearty Dinner Plate")

    def test_randomize_similar_recommendations_shuffles_close_scores_only(self):
        meals = [
            {"name": "Meal A", "score": 0.91, "recommendation_basis": "A"},
            {"name": "Meal B", "score": 0.90, "recommendation_basis": "B"},
            {"name": "Meal C", "score": 0.82, "recommendation_basis": "C"},
        ]

        def reverse_band(items):
            items.reverse()

        with patch("api.views.random.shuffle", side_effect=reverse_band):
            randomized = randomize_similar_recommendations([meal.copy() for meal in meals], score_window=0.03)

        self.assertEqual(
            [item["name"] for item in randomized],
            ["Meal B", "Meal A", "Meal C"],
        )
        self.assertIn("Variety rotation", randomized[0]["recommendation_basis"])
        self.assertNotIn("Variety rotation", randomized[2]["recommendation_basis"])
