from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate
from .models import MealFeedback, UserProfile
from .models import Meal


@api_view(['GET'])
def health_check(request):
    return Response({
        "status": "ok",
        "message": "AI Meal Planner API running"
    })

@api_view(['POST'])
def register(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')

    if not all([username, password, email, first_name, last_name]):
        return Response(
            {"error": "All fields are required"},
            status=400
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {"error": "Username already exists"},
            status=400
        )

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )

    return Response(
        {
            "message": "User registered successfully",
            "user_id": user.id
        },
        status=201
    )

@api_view(['POST'])
def login(request):
    data = request.data

    user = authenticate(
        username=data.get('username'),
        password=data.get('password')
    )

    if user is None:
        return Response(
            {"error": "Invalid username or password"},
            status=401
        )

    return Response({
        "message": "Login successful",
        "user_id": user.id,
        "username": user.username
    }, status=200)

@api_view(['PUT'])
def update_profile(request, user_id):
    user = User.objects.get(id=user_id)

    profile, created = UserProfile.objects.get_or_create(user=user)

    profile.age = request.data.get('age')
    profile.gender = request.data.get('gender')
    profile.height_cm = request.data.get('height_cm')
    profile.weight_kg = request.data.get('weight_kg')
    profile.activity_level = request.data.get('activity_level')

    profile.save()

    return Response(
        {
            "message": "Profile updated successfully",
            "created": created
        },
        status=200
    )


@api_view(['GET'])
def get_profile(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response(
            {"error": "Profile not found"},
            status=404
        )

    return Response({
        "user_id": user_id,
        "age": profile.age,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "activity_level": profile.activity_level
    }, status=200)


@api_view(['GET'])
def get_meals(request):
    meals = Meal.objects.all()

    data = []
    for meal in meals:
        data.append({
            "id": meal.id,
            "name": meal.name,
            "description": meal.description,
            "calories": meal.calories,
            "protein": meal.protein,
            "carbs": meal.carbs,
            "fats": meal.fats,
            "is_vegetarian": meal.is_vegetarian,
            "is_halal": meal.is_halal,
        })

    return Response(data, status=200)

def apply_constraints(meals, profile):
    filtered = []

    for meal in meals:
        # Vegetarian constraint
        if profile.activity_level and profile.activity_level == "vegetarian":
            if not meal.is_vegetarian:
                continue

        # Halal constraint
        if profile.activity_level and profile.activity_level == "halal":
            if not meal.is_halal:
                continue

        filtered.append(meal)

    return filtered

@api_view(['GET'])
def get_meals_with_constraints(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    meals = Meal.objects.all()
    allowed_meals = apply_constraints(meals, profile)

    data = []
    for meal in allowed_meals:
        data.append({
            "id": meal.id,
            "name": meal.name,
            "description": meal.description,
            "calories": meal.calories,
            "protein": meal.protein,
            "carbs": meal.carbs,
            "fats": meal.fats,
            "is_vegetarian": meal.is_vegetarian,
            "is_halal": meal.is_halal,
        })

    return Response(data, status=200)

def calculate_bmr(profile):
    """
    Mifflin–St Jeor Formula
    """
    if not profile.weight_kg or not profile.height_cm or not profile.age:
        return None

    if profile.gender == "male":
        return (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) + 5
    else:
        return (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) - 161


def calculate_tdee(bmr, activity_level):
    if bmr is None:
        return None

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }

    multiplier = activity_multipliers.get(activity_level, 1.2)
    return bmr * multiplier

@api_view(['GET'])
def get_nutrition_summary(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    bmr = calculate_bmr(profile)
    tdee = calculate_tdee(bmr, profile.activity_level)

    if bmr is None or tdee is None:
        return Response(
            {"error": "Incomplete profile data for nutrition calculation"},
            status=400
        )

    return Response({
        "bmr": round(bmr, 2),
        "tdee": round(tdee, 2)
    }, status=200)

def calculate_nutrition_match(meal, tdee):
    """
    Scores how close a meal's calories are to user's needs.
    Simple distance-based score (0 to 1).
    """
    if not tdee:
        return 0

    difference = abs(tdee - meal.calories)
    max_difference = tdee  # worst case

    score = 1 - (difference / max_difference)
    return max(score, 0)


def calculate_preference_match(meal, user):
    feedback = MealFeedback.objects.filter(user=user, meal=meal).first()

    if not feedback:
        return 0.5  # neutral if no feedback yet

    # Normalize rating (1–5) → (0.2–1.0)
    return feedback.rating / 5


def calculate_final_score(meal, tdee, user):
    nutrition_score = calculate_nutrition_match(meal, tdee)
    preference_score = calculate_preference_match(meal, user)

    final_score = (0.5 * nutrition_score) + (0.5 * preference_score)
    return round(final_score, 3)



@api_view(['GET'])
def get_recommended_meals(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    # Calculate nutrition needs
    bmr = calculate_bmr(profile)
    tdee = calculate_tdee(bmr, profile.activity_level)

    if bmr is None or tdee is None:
        return Response(
            {"error": "Incomplete profile data for recommendation"},
            status=400
        )

    # Get meals and apply constraints
    meals = Meal.objects.all()
    filtered_meals = apply_constraints(meals, profile)

    # Score meals
    scored_meals = []
    for meal in filtered_meals:
        score = calculate_final_score(meal, tdee, profile.user)

        feedback = MealFeedback.objects.filter(
            user=profile.user,
            meal=meal
        ).first()

        scored_meals.append({
            "id": meal.id,
            "name": meal.name,
            "description": meal.description,
            "calories": meal.calories,
            "protein": meal.protein,
            "carbs": meal.carbs,
            "fats": meal.fats,
            "image_url": meal.image_url,
            "score": score,
            "user_rating": feedback.rating if feedback else 0
        })

    # Sort by score (highest first)
    scored_meals.sort(key=lambda x: x["score"], reverse=True)

    return Response(scored_meals, status=200)


@api_view(['POST'])
def submit_feedback(request):
    data = request.data

    user_id = data.get('user_id')
    meal_id = data.get('meal_id')
    rating = data.get('rating')

    if rating is None or rating < 1 or rating > 5:
        return Response(
            {"error": "Rating must be between 1 and 5"},
            status=400
        )

    try:
        user = User.objects.get(id=user_id)
        meal = Meal.objects.get(id=meal_id)
    except (User.DoesNotExist, Meal.DoesNotExist):
        return Response({"error": "Invalid user or meal"}, status=404)

    feedback, created = MealFeedback.objects.update_or_create(
        user=user,
        meal=meal,
        defaults={"rating": rating}
    )

    return Response({
        "message": "Feedback submitted successfully",
        "rating": feedback.rating
    }, status=201)


