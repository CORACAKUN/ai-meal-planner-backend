from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate
from .models import MealFeedback, UserProfile
from .models import Meal


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
        "username": user.username
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
    
    profile.budget_level = data.get("budget_level", profile.budget_level)
    profile.dietary_rules = data.get("dietary_rules", profile.dietary_rules)
    profile.culture_preference = "filipino"
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
        "budget_level": profile.budget_level,
        "dietary_rules": profile.dietary_rules,
        "culture_preference": profile.culture_preference,
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
    - budget_level: cheap/medium/expensive
    - culture_preference: a tag like "filipino"
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
        culture_bonus_val = culture_bonus(meal, profile)
        budget_bonus_val = budget_bonus(meal, profile)
        meal_time_bonus_val = meal_time_bonus(meal, profile)
        
        score += culture_bonus_val + budget_bonus_val + meal_time_bonus_val

        if score > 1.0:
            score = 1.0
        
        score = round(score, 3)

        feedback = MealFeedback.objects.filter(
            user=profile.user,
            meal=meal
        ).first()
        
        # Build detailed recommendation basis
        basis_parts = [scoring_basis]
        if culture_bonus_val > 0:
            basis_parts.append(f"Cultural match (+{culture_bonus_val:.2f})")
        if budget_bonus_val > 0:
            basis_parts.append(f"Budget match (+{budget_bonus_val:.2f})")
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


def culture_bonus(meal, profile):
    pref = (profile.culture_preference or "").strip().lower()
    if not pref:
        return 0.0

    tags = (getattr(meal, "culture_tags", "") or "").lower()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    return 0.10 if pref in tag_list else 0.0  # +0.10 boost

def budget_bonus(meal, profile):
    user_budget = (profile.budget_level or "").strip().lower()
    if not user_budget:
        return 0.0

    meal_price = (getattr(meal, "price_level", "") or "").strip().lower()
    if not meal_price:
        return 0.0

    return 0.08 if meal_price == user_budget else 0.0

def meal_time_bonus(meal, profile):
    pref = (profile.preferred_meal_time or "").strip().lower()
    if not pref:
        return 0.0

    meal_time = (getattr(meal, "meal_time", "") or "").strip().lower()
    if not meal_time:
        return 0.0

    return 0.06 if meal_time == pref else 0.0
