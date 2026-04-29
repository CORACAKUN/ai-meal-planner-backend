from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate
from .models import MealFeedback, UserProfile, UserMealPlan
from .models import Meal
from datetime import timedelta


# Activity to activity level mapping
ACTIVITY_LEVELS = {
    # sedentary (little/no exercise)
    "sitting": "sedentary",
    "desk_work": "sedentary",
    "office_job": "sedentary",
    
    # light (1-3 days light exercise)
    "walking": "light",
    "gentle_yoga": "light",
    "casual_cycling": "light",
    "stretching": "light",
    
    # moderate (3-4 days moderate exercise)
    "jogging": "moderate",
    "running": "moderate",
    "swimming": "moderate",
    "basketball": "moderate",
    "soccer": "moderate",
    "gym_workout": "moderate",
    "dancing": "moderate",
    "hiking": "moderate",
    
    # active (5-6 days intense exercise)
    "sprinting": "active",
    "crossfit": "active",
    "competitive_sports": "active",
    "weight_training": "active",
    "martial_arts": "active",
    
    # very active (daily intense exercise)
    "professional_athlete": "very_active",
    "intense_daily_training": "very_active",
    "construction_work": "very_active",
}

IGNORED_PROFILE_TOKENS = {"", "none", "n/a", "na", "nil", "no", "no meds", "no medication"}

ALLERGEN_SYNONYMS = {
    "soy": {"soy", "soya", "soybean", "soy sauce", "tofu", "edamame"},
    "fish": {"fish", "tuna", "tilapia", "salmon", "sardine", "anchovy"},
    "shellfish": {"shellfish", "shrimp", "prawn", "crab", "lobster", "mussel", "clam"},
    "egg": {"egg", "eggs", "egg yolk", "egg white", "mayo", "mayonnaise"},
    "milk": {"milk", "dairy", "cheese", "butter", "cream", "yogurt", "lactose"},
    "gluten": {"gluten", "wheat", "bread", "flour", "barley", "rye"},
    "peanut": {"peanut", "peanuts", "groundnut"},
    "tree_nut": {"tree nut", "tree nuts", "almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut"},
    "sesame": {"sesame", "sesame seed", "tahini"},
    "coconut": {"coconut", "gata", "coconut milk", "niyog"},
    "corn": {"corn", "maize", "cornstarch"},
    "sulfite": {"sulfite", "sulfites", "wine", "vinegar"},
}

MEDICATION_SYNONYMS = {
    "warfarin": {"warfarin", "coumadin"},
    "statin": {"statin", "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin"},
    "metformin": {"metformin", "glucophage"},
    "amlodipine": {"amlodipine", "norvasc"},
    "allopurinol": {"allopurinol", "zyloprim"},
    "levothyroxine": {"levothyroxine", "synthroid", "euthyrox"},
    "maoi": {"maoi", "phenelzine", "tranylcypromine", "isocarboxazid"},
    "digoxin": {"digoxin", "lanoxin"},
    "insulin": {"insulin", "novorapid", "lantus", "humalog"},
}

PHILIPPINE_CULTURE_TAGS = {"filipino", "philippines", "pinoy"}

MEAL_TIME_OPTIONS = {"breakfast", "lunch", "dinner", "snack"}
PRICE_LEVEL_OPTIONS = {"cheap", "medium", "expensive"}


def _tokenize_csv(raw_value):
    text = (raw_value or "").strip().lower()
    if not text:
        return set()
    for sep in [";", "\n", "|"]:
        text = text.replace(sep, ",")
    return {token.strip() for token in text.split(",") if token.strip()}


def _token_matches(a, b):
    return a == b or a in b or b in a


def _canonicalize(tokens, synonyms):
    canonical = set()
    for token in tokens:
        for key, alias_set in synonyms.items():
            if any(_token_matches(token, alias) for alias in alias_set):
                canonical.add(key)
    return canonical


def _has_token_conflict(user_raw, meal_raw, synonyms):
    user_tokens = {t for t in _tokenize_csv(user_raw) if t not in IGNORED_PROFILE_TOKENS}
    meal_tokens = {t for t in _tokenize_csv(meal_raw) if t not in {"", "none", "n/a", "na"}}
    if not user_tokens or not meal_tokens:
        return False

    # Direct token match (including contains checks like "soy" vs "soy sauce")
    if any(_token_matches(u, m) for u in user_tokens for m in meal_tokens):
        return True

    # Canonical match via synonym groups
    user_canonical = _canonicalize(user_tokens, synonyms)
    meal_canonical = _canonicalize(meal_tokens, synonyms)
    return bool(user_canonical & meal_canonical)


def _is_philippines_meal(meal):
    culture_tokens = _tokenize_csv(getattr(meal, "culture_tags", "") or "")
    return bool(culture_tokens & PHILIPPINE_CULTURE_TAGS)


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _serialize_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


def _serialize_meal(meal):
    return {
        "id": meal.id,
        "name": meal.name,
        "description": meal.description,
        "ingredients": meal.ingredients,
        "calories": meal.calories,
        "protein": meal.protein,
        "carbs": meal.carbs,
        "fats": meal.fats,
        "is_vegetarian": meal.is_vegetarian,
        "is_halal": meal.is_halal,
        "meal_time": meal.meal_time,
        "price_level": meal.price_level,
        "culture_tags": meal.culture_tags,
        "has_pork": meal.has_pork,
        "has_blood": meal.has_blood,
        "has_alcohol": meal.has_alcohol,
        "allergen_tags": meal.allergen_tags,
        "medication_warnings": meal.medication_warnings,
        "image_url": meal.image_url,
    }


def _serialize_feedback(feedback):
    return {
        "id": feedback.id,
        "user_id": feedback.user_id,
        "username": feedback.user.username,
        "meal_id": feedback.meal_id,
        "meal_name": feedback.meal.name,
        "rating": feedback.rating,
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
    }


def _serialize_meal_plan_item(item):
    return {
        "id": item.id,
        "user_id": item.user_id,
        "meal_id": item.meal_id,
        "scheduled_date": item.scheduled_date.isoformat(),
        "meal_time": item.meal_time,
        "is_eaten": item.is_eaten,
        "eaten_at": item.eaten_at.isoformat() if item.eaten_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "meal": _serialize_meal(item.meal),
    }


def _get_admin_actor(request):
    admin_user_id = request.query_params.get("admin_user_id") or request.data.get("admin_user_id")
    try:
        admin_user_id = int(admin_user_id)
    except (TypeError, ValueError):
        return None, Response({"error": "admin_user_id is required"}, status=400)

    try:
        admin_user = User.objects.get(id=admin_user_id)
    except User.DoesNotExist:
        return None, Response({"error": "Admin user not found"}, status=404)

    if not admin_user.is_superuser:
        return None, Response({"error": "Admin access required"}, status=403)

    return admin_user, None


def _validate_choice(raw_value, allowed_values):
    value = (raw_value or "").strip().lower()
    if not value:
        return None
    if value not in allowed_values:
        raise ValueError(f"Invalid value: {raw_value}")
    return value

def get_activity_level_from_activities(activities_str):
    """
    Convert comma-separated activities to overall activity level.
    Returns the highest activity level found.
    """
    if not activities_str:
        return "sedentary"
    
    activities = [a.strip().lower() for a in activities_str.split(",") if a.strip()]
    if not activities:
        return "sedentary"
    
    level_hierarchy = {"sedentary": 0, "light": 1, "moderate": 2, "active": 3, "very_active": 4}
    max_level = "sedentary"
    max_level_value = 0
    
    for activity in activities:
        level = ACTIVITY_LEVELS.get(activity, "moderate")  # default to moderate if unknown
        level_value = level_hierarchy.get(level, 2)
        if level_value > max_level_value:
            max_level = level
            max_level_value = level_value
    
    return max_level


@api_view(['GET'])
def health_check(request):
    return Response({
        "status": "ok",
        "message": "AI Meal Planner API running"
    })

@api_view(['POST'])
def register(request):
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password')
    email = (request.data.get('email') or '').strip()
    first_name = (request.data.get('first_name') or '').strip()
    last_name = (request.data.get('last_name') or '').strip()

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
    if User.objects.filter(email=email).exists():
        return Response(
            {"error": "Email already exists"},
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
        "username": user.username,
        "is_admin": user.is_superuser,
    }, status=200)

@api_view(['PUT'])
def update_profile(request, user_id):
    data = request.data
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    profile, created = UserProfile.objects.get_or_create(user=user)

    profile.age = data.get("age", profile.age)
    profile.gender = data.get("gender", profile.gender)
    profile.height_cm = data.get("height_cm", profile.height_cm)
    profile.weight_kg = data.get("weight_kg", profile.weight_kg)
    
    # Handle activities - convert to activity level
    activities_str = data.get("activities")
    if activities_str:
        profile.activities = activities_str
        profile.activity_level = get_activity_level_from_activities(activities_str)
    elif data.get("activity_level"):
        # Fallback only when activities are not provided
        profile.activity_level = data.get("activity_level")
    
    # Handle weight goal
    profile.weight_goal = data.get("weight_goal", profile.weight_goal)
    
    profile.dietary_rules = data.get("dietary_rules", profile.dietary_rules)
    profile.preferred_meal_time = data.get("preferred_meal_time", profile.preferred_meal_time)
    profile.allergies = data.get("allergies", profile.allergies)
    profile.maintenance_medications = data.get("maintenance_medications", profile.maintenance_medications)
    profile.save()

    return Response(
        {
            "message": "Profile updated successfully",
            "activity_level": profile.activity_level,
            "weight_goal": profile.weight_goal,
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
        "activities": profile.activities,
        "activity_level": profile.activity_level,
        "weight_goal": profile.weight_goal,
        "dietary_rules": profile.dietary_rules,
        "preferred_meal_time": profile.preferred_meal_time,
        "allergies": profile.allergies,
        "maintenance_medications": profile.maintenance_medications,
    }, status=200)


@api_view(['GET'])
def get_meals(request):
    meals = [m for m in Meal.objects.all() if _is_philippines_meal(m)]

    data = []
    for meal in meals:
        data.append({
            "id": meal.id,
            "name": meal.name,
            "description": meal.description,
            "ingredients": meal.ingredients,
            "image_url": meal.image_url,
            "calories": meal.calories,
            "protein": meal.protein,
            "carbs": meal.carbs,
            "fats": meal.fats,
            "is_vegetarian": meal.is_vegetarian,
            "is_halal": meal.is_halal,
            "price_level": meal.price_level,
            "culture_tags": meal.culture_tags,
            "meal_time": meal.meal_time,
            "allergen_tags": getattr(meal, "allergen_tags", None),
            "medication_warnings": getattr(meal, "medication_warnings", None),
        })

    return Response(data, status=200)

def apply_constraints(meals, profile):
    """
    Filters meals based on profile constraints:
    - dietary_rules: comma-separated string (e.g. "halal,no_pork,no_blood")
    """
    filtered = [m for m in meals if _is_philippines_meal(m)]

    # --- Dietary rules ---
    rules_raw = (profile.dietary_rules or "").strip()
    rules = [r.strip().lower() for r in rules_raw.split(",") if r.strip()]

    # halal rule
    if "halal" in rules:
        filtered = [m for m in filtered if getattr(m, "is_halal", False) is True]
        filtered = [m for m in filtered if getattr(m, "has_alcohol", False) is False]
        filtered = [m for m in filtered if getattr(m, "has_pork", False) is False]

    # vegetarian rule
    if "vegetarian" in rules:
        filtered = [m for m in filtered if getattr(m, "is_vegetarian", False) is True]

    # no blood (INC-friendly)
    if "no_blood" in rules:
        filtered = [m for m in filtered if getattr(m, "has_blood", False) is False]

    # optional generic rules
    if "no_pork" in rules:
        filtered = [m for m in filtered if getattr(m, "has_pork", False) is False]

    if "no_alcohol" in rules:
        filtered = [m for m in filtered if getattr(m, "has_alcohol", False) is False]

    # --- Allergy safety filter ---
    user_allergies_raw = getattr(profile, "allergies", "") or ""
    if user_allergies_raw.strip():
        safe_meals = []
        for meal in filtered:
            meal_allergens_raw = getattr(meal, "allergen_tags", "") or ""
            if not _has_token_conflict(user_allergies_raw, meal_allergens_raw, ALLERGEN_SYNONYMS):
                safe_meals.append(meal)
        filtered = safe_meals

    # --- Medication caution filter ---
    # If meal warnings overlap with maintenance medication tokens or synonyms,
    # exclude the meal for safety.
    user_meds_raw = getattr(profile, "maintenance_medications", "") or ""
    if user_meds_raw.strip():
        safe_meals = []
        for meal in filtered:
            meal_warnings_raw = getattr(meal, "medication_warnings", "") or ""
            if not _has_token_conflict(user_meds_raw, meal_warnings_raw, MEDICATION_SYNONYMS):
                safe_meals.append(meal)
        filtered = safe_meals

    return filtered

@api_view(['GET'])
def get_meals_with_constraints(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    meals = [m for m in Meal.objects.all() if _is_philippines_meal(m)]
    allowed_meals = apply_constraints(meals, profile)

    data = []
    for meal in allowed_meals:
        data.append({
            "id": meal.id,
            "name": meal.name,
            "description": meal.description,
            "ingredients": meal.ingredients,
            "image_url": meal.image_url,
            "calories": meal.calories,
            "protein": meal.protein,
            "carbs": meal.carbs,
            "fats": meal.fats,
            "is_vegetarian": meal.is_vegetarian,
            "is_halal": meal.is_halal,
            "price_level": meal.price_level,
            "culture_tags": meal.culture_tags,
            "meal_time": meal.meal_time,
            "allergen_tags": getattr(meal, "allergen_tags", None),
            "medication_warnings": getattr(meal, "medication_warnings", None),
        })

    return Response(data, status=200)

def calculate_bmr(profile):
    """
    Mifflin–St Jeor Formula
    BMR = Basal Metabolic Rate (calories burned at rest)
    """
    if not profile.weight_kg or not profile.height_cm or not profile.age:
        return None, None

    if profile.gender == "male":
        bmr = (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) + 5
    else:
        bmr = (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) - 161
    
    basis = f"BMR calculated using Mifflin-St Jeor formula (gender: {profile.gender}, age: {profile.age}, height: {profile.height_cm}cm, weight: {profile.weight_kg}kg)"
    return bmr, basis


def calculate_tdee(bmr, activity_level):
    """
    TDEE = Total Daily Energy Expenditure
    Multiplies BMR by activity level factor
    """
    if bmr is None:
        return None, None

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }

    multiplier = activity_multipliers.get(activity_level, 1.2)
    tdee = bmr * multiplier
    
    basis = f"TDEE = BMR × {multiplier} ({activity_level} activity level)"
    return tdee, basis


def calculate_bmi(height_cm, weight_kg):
    """
    BMI = Body Mass Index
    """
    if not height_cm or height_cm == 0:
        return None
    
    height_m = height_cm / 100
    return weight_kg / (height_m * height_m)


def get_bmi_category(bmi):
    """
    BMI categories according to WHO standards
    """
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal weight"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def calculate_weight_goal_recommendation(profile):
    """
    Recommend weight goal based on current BMI
    """
    if not profile.height_cm or not profile.weight_kg:
        return "maintain", "Insufficient data"
    
    bmi = calculate_bmi(profile.height_cm, profile.weight_kg)
    
    if bmi < 18.5:
        return "gain", "You are underweight. Consider gaining weight for better health."
    elif bmi < 25:
        return "maintain", "Your weight is in the healthy range. Focus on maintaining it."
    else:
        return "lose", "You are overweight or obese. Consider losing weight for better health."


def get_today_meal_plan_totals(user):
    today = timezone.localdate()
    eaten_entries = (
        UserMealPlan.objects.select_related("meal")
        .filter(user=user, scheduled_date=today, is_eaten=True)
    )

    totals = {
        "meal_count": 0,
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fats": 0.0,
    }

    for entry in eaten_entries:
        totals["meal_count"] += 1
        totals["calories"] += entry.meal.calories or 0.0
        totals["protein"] += entry.meal.protein or 0.0
        totals["carbs"] += entry.meal.carbs or 0.0
        totals["fats"] += entry.meal.fats or 0.0

    return {
        "date": today.isoformat(),
        "meal_count": totals["meal_count"],
        "calories": round(totals["calories"], 2),
        "protein": round(totals["protein"], 2),
        "carbs": round(totals["carbs"], 2),
        "fats": round(totals["fats"], 2),
    }


@api_view(['GET'])
def get_nutrition_summary(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    bmr, bmr_basis = calculate_bmr(profile)
    tdee, tdee_basis = calculate_tdee(bmr, profile.activity_level)

    if bmr is None or tdee is None:
        return Response(
            {"error": "Incomplete profile data for nutrition calculation"},
            status=400
        )
    
    bmi = calculate_bmi(profile.height_cm, profile.weight_kg)
    bmi_category = get_bmi_category(bmi)
    
    weight_goal, weight_goal_reason = calculate_weight_goal_recommendation(profile)
    user_goal = profile.weight_goal or weight_goal
    eaten_today = get_today_meal_plan_totals(profile.user)

    return Response({
        "bmr": round(bmr, 2),
        "bmr_basis": bmr_basis,
        "tdee": round(tdee, 2),
        "tdee_basis": tdee_basis,
        "bmi": round(bmi, 2),
        "bmi_category": bmi_category,
        "weight_goal": user_goal,
        "weight_goal_reason": weight_goal_reason,
        "activities": profile.activities,
        "activity_level": profile.activity_level,
        "eaten_today": eaten_today,
        "demographic_summary": {
            "age": profile.age,
            "gender": profile.gender,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
        }
    }, status=200)

def calculate_nutrition_match(meal, tdee):
    """
    Scores how close a meal's calories are to user's needs.
    Simple distance-based score (0 to 1).
    """
    if not tdee:
        return 0, ""

    difference = abs(tdee - meal.calories)
    max_difference = tdee

    score = 1 - (difference / max_difference)
    score = max(score, 0)
    
    basis = f"Nutrition match: {meal.calories} cal vs your daily need {tdee:.0f} cal (score: {score:.2f})"
    return score, basis


def calculate_preference_match(meal, user):
    """
    Score based on user's previous ratings
    """
    feedback = MealFeedback.objects.filter(user=user, meal=meal).first()

    if not feedback:
        score = 0.5  # neutral if no feedback yet
        basis = "No previous rating (neutral score)"
    else:
        score = feedback.rating / 5
        basis = f"Your previous rating: {feedback.rating}/5"
    
    return score, basis


def calculate_final_score(meal, tdee, user):
    nutrition_score, nutrition_basis = calculate_nutrition_match(meal, tdee)
    preference_score, preference_basis = calculate_preference_match(meal, user)

    final_score = (0.5 * nutrition_score) + (0.5 * preference_score)
    final_score = round(final_score, 3)
    
    scoring_basis = f"{nutrition_basis} | {preference_basis} | Base score: {final_score:.3f}"
    return final_score, scoring_basis


@api_view(['GET'])
def get_recommended_meals(request, user_id):
    try:
        profile = UserProfile.objects.get(user__id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    # Calculate nutrition needs
    bmr, bmr_basis = calculate_bmr(profile)
    tdee, tdee_basis = calculate_tdee(bmr, profile.activity_level)

    if bmr is None or tdee is None:
        return Response(
            {"error": "Incomplete profile data for recommendation"},
            status=400
        )

    # Get meals and apply constraints
    meals = [m for m in Meal.objects.all() if _is_philippines_meal(m)]
    filtered_meals = apply_constraints(meals, profile)

    # Score meals
    scored_meals = []
    for meal in filtered_meals:
        score, scoring_basis = calculate_final_score(meal, tdee, profile.user)
        
        # Calculate bonuses with reasons
        meal_time_bonus_val = meal_time_bonus(meal, profile)
        
        score += meal_time_bonus_val

        if score > 1.0:
            score = 1.0
        
        score = round(score, 3)

        feedback = MealFeedback.objects.filter(
            user=profile.user,
            meal=meal
        ).first()
        
        # Build detailed recommendation basis
        basis_parts = [scoring_basis]
        if meal_time_bonus_val > 0:
            basis_parts.append(f"Meal time match (+{meal_time_bonus_val:.2f})")
        
        recommendation_basis = " | ".join(basis_parts)

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
            "user_rating": feedback.rating if feedback else 0,
            "meal_time": getattr(meal, "meal_time", None),
            "price_level": getattr(meal, "price_level", None),
            "culture_tags": getattr(meal, "culture_tags", None),
            "has_pork": getattr(meal, "has_pork", False),
            "has_blood": getattr(meal, "has_blood", False),
            "has_alcohol": getattr(meal, "has_alcohol", False),
            "allergen_tags": getattr(meal, "allergen_tags", None),
            "medication_warnings": getattr(meal, "medication_warnings", None),
            "recommendation_basis": recommendation_basis,  # New: detailed basis
        })

    # Sort by score (highest first)
    scored_meals.sort(key=lambda x: x["score"], reverse=True)
    
    # Add summary info
    bmi = calculate_bmi(profile.height_cm, profile.weight_kg)
    bmi_category = get_bmi_category(bmi)

    return Response({
        "meals": scored_meals,
        "summary": {
            "tdee": round(tdee, 2),
            "bmi": round(bmi, 2),
            "bmi_category": bmi_category,
            "activity_level": profile.activity_level,
            "weight_goal": profile.weight_goal or "maintain",
            "total_recommendations": len(scored_meals),
        }
    }, status=200)


@api_view(['POST'])
def submit_feedback(request):
    data = request.data

    user_id = data.get('user_id')
    meal_id = data.get('meal_id')
    try:
        rating = int(data.get('rating'))
    except (TypeError, ValueError):
        return Response(
            {"error": "Rating must be an integer between 1 and 5"},
            status=400
        )

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


def meal_time_bonus(meal, profile):
    pref = (profile.preferred_meal_time or "").strip().lower()
    if not pref:
        return 0.0

    meal_time = (getattr(meal, "meal_time", "") or "").strip().lower()
    if not meal_time:
        return 0.0

    return 0.06 if meal_time == pref else 0.0


@api_view(["GET", "POST"])
def user_meal_plan(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    if request.method == "POST":
        data = request.data
        meal_id = data.get("meal_id")
        date_str = (data.get("scheduled_date") or "").strip()
        meal_time = (data.get("meal_time") or "").strip().lower() or None

        if not meal_id:
            return Response({"error": "meal_id is required"}, status=400)
        if not date_str:
            return Response({"error": "scheduled_date is required"}, status=400)

        scheduled_date = parse_date(date_str)
        if scheduled_date is None:
            return Response({"error": "scheduled_date must be YYYY-MM-DD"}, status=400)

        if meal_time and meal_time not in MEAL_TIME_OPTIONS:
            return Response({"error": "Invalid meal_time"}, status=400)

        try:
            meal = Meal.objects.get(id=meal_id)
        except Meal.DoesNotExist:
            return Response({"error": "Meal not found"}, status=404)

        entry = UserMealPlan.objects.create(
            user=user,
            meal=meal,
            scheduled_date=scheduled_date,
            meal_time=meal_time or (meal.meal_time or None),
        )

        return Response(
            {
                "message": "Meal added to plan",
                "entry": _serialize_meal_plan_item(entry),
            },
            status=201,
        )

    scope = (request.query_params.get("scope") or "daily").strip().lower()
    anchor_date_str = (request.query_params.get("date") or "").strip()
    anchor_date = parse_date(anchor_date_str) if anchor_date_str else None
    if anchor_date is None:
        return Response({"error": "date query parameter is required in YYYY-MM-DD format"}, status=400)

    if scope not in {"daily", "weekly"}:
        return Response({"error": "scope must be daily or weekly"}, status=400)

    if scope == "daily":
        start_date = end_date = anchor_date
    else:
        start_date = anchor_date - timedelta(days=anchor_date.weekday())
        end_date = start_date + timedelta(days=6)

    entries = (
        UserMealPlan.objects.select_related("meal")
        .filter(user=user, scheduled_date__gte=start_date, scheduled_date__lte=end_date)
        .order_by("scheduled_date", "meal_time", "id")
    )

    return Response(
        {
            "scope": scope,
            "anchor_date": anchor_date.isoformat(),
            "range_start": start_date.isoformat(),
            "range_end": end_date.isoformat(),
            "entries": [_serialize_meal_plan_item(item) for item in entries],
        },
        status=200,
    )


@api_view(["DELETE"])
def delete_meal_plan_entry(request, user_id, entry_id):
    try:
        entry = UserMealPlan.objects.get(id=entry_id, user_id=user_id)
    except UserMealPlan.DoesNotExist:
        return Response({"error": "Meal plan entry not found"}, status=404)

    entry.delete()
    return Response({"message": "Meal removed from plan"}, status=200)


@api_view(["PATCH"])
def update_meal_plan_entry_status(request, user_id, entry_id):
    try:
        entry = UserMealPlan.objects.select_related("meal").get(id=entry_id, user_id=user_id)
    except UserMealPlan.DoesNotExist:
        return Response({"error": "Meal plan entry not found"}, status=404)

    is_eaten = _parse_bool(request.data.get("is_eaten"), default=entry.is_eaten)
    entry.is_eaten = is_eaten
    entry.eaten_at = timezone.now() if is_eaten else None
    entry.save(update_fields=["is_eaten", "eaten_at"])

    return Response(
        {
            "message": "Meal status updated",
            "entry": _serialize_meal_plan_item(entry),
        },
        status=200,
    )


@api_view(["GET", "POST"])
def admin_users(request):
    admin_user, error = _get_admin_actor(request)
    if error:
        return error

    if request.method == "GET":
        users = User.objects.all().order_by("id")
        return Response({"users": [_serialize_user(user) for user in users]}, status=200)

    data = request.data
    username = (data.get("username") or "").strip()
    password = data.get("password")
    email = (data.get("email") or "").strip()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()

    if not username or not password:
        return Response({"error": "Username and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=400)

    if email and User.objects.filter(email=email).exists():
        return Response({"error": "Email already exists"}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    user.is_staff = _parse_bool(data.get("is_staff"), default=False)
    user.is_superuser = _parse_bool(data.get("is_superuser"), default=False)
    if user.is_superuser:
        user.is_staff = True
    user.is_active = _parse_bool(data.get("is_active"), default=True)
    user.save()

    return Response(
        {
            "message": f"User {user.username} created successfully",
            "user": _serialize_user(user),
            "acted_by": admin_user.username,
        },
        status=201,
    )


@api_view(["PUT", "DELETE"])
def admin_user_detail(request, user_id):
    admin_user, error = _get_admin_actor(request)
    if error:
        return error

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    if request.method == "DELETE":
        if user.id == admin_user.id:
            return Response({"error": "You cannot delete the active admin account"}, status=400)
        username = user.username
        user.delete()
        return Response(
            {"message": f"User {username} deleted successfully", "acted_by": admin_user.username},
            status=200,
        )

    data = request.data
    username = (data.get("username") or user.username).strip()
    email = (data.get("email") or "").strip()

    if User.objects.exclude(id=user.id).filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=400)

    if email and User.objects.exclude(id=user.id).filter(email=email).exists():
        return Response({"error": "Email already exists"}, status=400)

    user.username = username
    user.email = email
    user.first_name = (data.get("first_name") or "").strip()
    user.last_name = (data.get("last_name") or "").strip()
    user.is_active = _parse_bool(data.get("is_active"), default=user.is_active)
    user.is_staff = _parse_bool(data.get("is_staff"), default=user.is_staff)
    user.is_superuser = _parse_bool(data.get("is_superuser"), default=user.is_superuser)
    if user.is_superuser:
        user.is_staff = True

    password = data.get("password")
    if password:
        user.set_password(password)

    user.save()
    return Response(
        {
            "message": f"User {user.username} updated successfully",
            "user": _serialize_user(user),
            "acted_by": admin_user.username,
        },
        status=200,
    )


@api_view(["GET", "POST"])
def admin_meals(request):
    _, error = _get_admin_actor(request)
    if error:
        return error

    if request.method == "GET":
        meals = Meal.objects.all().order_by("name")
        return Response({"meals": [_serialize_meal(meal) for meal in meals]}, status=200)

    data = request.data
    name = (data.get("name") or "").strip()
    if not name:
        return Response({"error": "Meal name is required"}, status=400)

    try:
        meal = Meal.objects.create(
            name=name,
            description=(data.get("description") or "").strip(),
            ingredients=(data.get("ingredients") or "").strip() or None,
            calories=float(data.get("calories") or 0),
            protein=float(data.get("protein") or 0),
            carbs=float(data.get("carbs") or 0),
            fats=float(data.get("fats") or 0),
            is_vegetarian=_parse_bool(data.get("is_vegetarian")),
            is_halal=_parse_bool(data.get("is_halal")),
            meal_time=_validate_choice(data.get("meal_time"), MEAL_TIME_OPTIONS),
            price_level=_validate_choice(data.get("price_level"), PRICE_LEVEL_OPTIONS),
            culture_tags=(data.get("culture_tags") or "").strip() or None,
            has_pork=_parse_bool(data.get("has_pork")),
            has_blood=_parse_bool(data.get("has_blood")),
            has_alcohol=_parse_bool(data.get("has_alcohol")),
            allergen_tags=(data.get("allergen_tags") or "").strip() or None,
            medication_warnings=(data.get("medication_warnings") or "").strip() or None,
            image_url=(data.get("image_url") or "").strip() or None,
        )
    except ValueError:
        return Response({"error": "Numeric and choice fields must be valid"}, status=400)

    return Response({"message": "Meal created successfully", "meal": _serialize_meal(meal)}, status=201)


@api_view(["PUT", "DELETE"])
def admin_meal_detail(request, meal_id):
    _, error = _get_admin_actor(request)
    if error:
        return error

    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        return Response({"error": "Meal not found"}, status=404)

    if request.method == "DELETE":
        meal_name = meal.name
        meal.delete()
        return Response({"message": f"Meal {meal_name} deleted successfully"}, status=200)

    data = request.data

    try:
        meal.name = (data.get("name") or meal.name).strip()
        meal.description = (data.get("description") or "").strip()
        meal.ingredients = (data.get("ingredients") or "").strip() or None
        meal.calories = float(data.get("calories") if data.get("calories") is not None else meal.calories)
        meal.protein = float(data.get("protein") if data.get("protein") is not None else meal.protein)
        meal.carbs = float(data.get("carbs") if data.get("carbs") is not None else meal.carbs)
        meal.fats = float(data.get("fats") if data.get("fats") is not None else meal.fats)
        meal.is_vegetarian = _parse_bool(data.get("is_vegetarian"), default=meal.is_vegetarian)
        meal.is_halal = _parse_bool(data.get("is_halal"), default=meal.is_halal)
        meal.meal_time = _validate_choice(data.get("meal_time"), MEAL_TIME_OPTIONS)
        meal.price_level = _validate_choice(data.get("price_level"), PRICE_LEVEL_OPTIONS)
        meal.culture_tags = (data.get("culture_tags") or "").strip() or None
        meal.has_pork = _parse_bool(data.get("has_pork"), default=meal.has_pork)
        meal.has_blood = _parse_bool(data.get("has_blood"), default=meal.has_blood)
        meal.has_alcohol = _parse_bool(data.get("has_alcohol"), default=meal.has_alcohol)
        meal.allergen_tags = (data.get("allergen_tags") or "").strip() or None
        meal.medication_warnings = (data.get("medication_warnings") or "").strip() or None
        meal.image_url = (data.get("image_url") or "").strip() or None
    except ValueError:
        return Response({"error": "Numeric and choice fields must be valid"}, status=400)

    if not meal.name:
        return Response({"error": "Meal name is required"}, status=400)

    meal.save()
    return Response({"message": "Meal updated successfully", "meal": _serialize_meal(meal)}, status=200)


@api_view(["GET"])
def admin_feedback(request):
    _, error = _get_admin_actor(request)
    if error:
        return error

    feedback_items = (
        MealFeedback.objects.select_related("user", "meal")
        .all()
        .order_by("-created_at")
    )
    return Response(
        {"feedback": [_serialize_feedback(item) for item in feedback_items]},
        status=200,
    )
