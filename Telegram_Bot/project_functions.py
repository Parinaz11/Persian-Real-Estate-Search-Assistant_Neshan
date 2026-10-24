import pandas as pd
import json
from openai import OpenAI
import os
from rapidfuzz import process, fuzz

column_name_fa = {
    "city_slug": "شهر",
    "neighborhood_slug": "محله",
    "price_value": "قیمت",
    "building_size": "زیربنا (متر مربع)",
    "rooms_count": "تعداد اتاق",
    "floor": "طبقه",
    "has_balcony": "بالکن",
    "has_elevator": "آسانسور",
    "has_warehouse": "انبار",
    "has_parking": "پارکینگ",
    "has_warm_water_provider": "تامین‌کننده آب گرم",
    "construction_year": "سال ساخت",
    "deed_type": "نوع سند",
    "has_heating_system": "سیستم گرمایشی",
    "has_cooling_system": "سیستم سرمایشی",
    "has_restroom": "نوع سرویس بهداشتی",
    "building_direction": "جهت ساختمان",
    "floor_material": "جنس کف",
    "total_floors_count": "تعداد کل طبقات",
    "unit_per_floor": "تعداد واحد در هر طبقه",
    "is_rebuilt": "بازسازی شده یا نه"
}

COLUMNS_TO_USE = [
    # Main
    "city_slug",
    "neighborhood_slug",
    "price_value",
    "building_size",
    "rooms_count",
    
    # Secondary
    "floor",
    "has_balcony",
    "has_elevator",
    "has_warehouse",
    "has_parking",
    "has_warm_water_provider",
    "construction_year",
    "deed_type",
    "has_heating_system",
    "has_cooling_system",
    "has_restroom",
    "building_direction",
    "floor_material",
    
    # Optional / rarely used
    "total_floors_count",
    "unit_per_floor",
    "is_rebuilt"
]

# order of asking
FIELDS_ORDER = [
    "city_slug", "neighborhood_slug", "price_value", "building_size",
    "rooms_count", "floor", "has_parking", "has_elevator", "has_balcony",
    "has_warehouse", "construction_year", "deed_type", "has_warm_water_provider",
    "has_heating_system", "has_cooling_system", "has_restroom", "building_direction",
    "floor_material", "total_floors_count", "unit_per_floor", "is_rebuilt"
]

# ------ api ------
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-v1-2c...98e6",
)

DF_PATH = os.path.join(os.path.dirname(__file__), '../filtered_df_cleaned_v2.csv')
df = pd.read_csv(DF_PATH)

def parse_user_query(user_text):
    prompt = f"""
        You are a JSON field extractor.
        The input will be a Persian text describing a property search.
        Your task:
        - Read the Persian text carefully.
        - Identify which fields from this dataset columns list the user mentioned: {COLUMNS_TO_USE}
        - Only assign a numeric value to a column if the text clearly states that number in direct connection with that column’s meaning
        - Only include columns that are explicitly mentioned or implied.
        - Extract the exact value for each mentioned column from the sentence.
        - For strings that denote place types or locations in Persian, return the natural English place name instead of a phonetic transliteration. Preserve other words unchanged unless they clearly denote locations.
          Example:
            - "فرودگاه" → "airport" (do not return "forudgah")
            - "دانشگاه" → "university" (do not return "daneshgah")
        - If a value is numeric, return it as a number (not a string).
        - If the user specifies a range like "حداقل", "حداکثر", "کمتر از", "بیشتر از", then instead of the exact column name, use "min_" or "max_" prefix. 
          Examples:
            - "حداقل ۸۰۰ میلیون" → "min_price_value": 800000000
            - "تا ۸۰۰ میلیون" → "max_price_value": 800000000

        - Output valid JSON only, with keys exactly as in the list and values.
        - Omit any field not mentioned.
        - If a number is given in Persian words (یک, دو, سه), convert to integer.
        - Ignore irrelevant text.

        ⚠️ Important rules for output:
        - Always extract **all valid house-related fields** mentioned in the input, even if there is only one field.
        - Do NOT ignore a valid field just because other fields are missing or irrelevant content is present.
          Example:
            - "سلام، می‌خوام یه خونه در مشهد بخرم" → "city_slug": "mashhad"
            - "یه خونه در تهران می‌خوام" → "city_slug": "tehran"
            - "خونه‌ای توی اصفهان برای اجاره می‌خوام" → "city_slug": "isfahan"
            - "می‌خوام یه آپارتمان در محله فرودگاه بخرم" → "neighborhood_slug": ""
        - Only output valid JSON.
        - Do NOT include any key with null/None/empty values.
        - If no fields are detected, return an empty JSON: {{}}
        

        Some of the columns and their allowed values:
        - deed_type: ["single_page", "written_agreement", "multi_page", "other"]
        - has_warm_water_provider: ["water_heater", "package", "powerhouse"]
        - has_heating_system: ["shoofaj", "heater", "duct_split", "floor_heating", "fan_coil", "split", "fireplace"]
        - has_cooling_system: ["air_conditioner", "water_cooler", "duct_split", "split", "fan_coil"]
        - has_restroom: ["squat_seat", "squat", "seat"]
        - floor_material: ["mosaic", "ceramic", "stone", "wood_parquet", "laminate_parquet", "carpet", "floor_covering"
        
        Example:
        User: "یه خونه سه خوابه تو قلهک تهران می‌خوام، قیمتش تا ۵۰ میلیارد، صد متره، بالکن و آسانسور داره، پارکینگ هم داره، طبقه ۲، سند تک‌برگه، آبگرم‌کن داره، سال ساخت ۱۴۰۰، شوفاژ و کولر داره، دستشویی ایرانیه، به سمت جنوبه، کفش موزاییکه، نوع ملک معمولیه، کل ساختمان ۴ طبقه و هر طبقه ۲ واحد، انبار نداره و بازسازی نشده"
        Output:
        {{
          "city_slug": "tehran",
          "neighborhood_slug": "gholhak",
          "rooms_count": 3,
          "price_value": 50000000000,
          "building_size": 100,
          "has_balcony": True,
          "has_elevator": True,
          "has_parking": True,
          "floor": 2,
          "deed_type": "single_page",
          "has_warm_water_provider": "water_heater",
          "construction_year": 1400,
          "has_heating_system": "shoofaj",
          "has_cooling_system": "air_conditioner",
          "has_restroom": "squat_seat",
          "building_direction": "south",
          "floor_material": "mosaic",
          "total_floors_count": 5,
          "unit_per_floor": 2,
          "is_rebuilt": False,
          "has_warehouse": False,
          "total_floors_count": 4
        }}
        """

    completion = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": prompt + "\nUser: " + user_text}
        ]
    )
    
    content = completion.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def fuzzy_match_column(value, df, column, cutoff=70):
    """
    Fuzzy match a user input against unique values of a DataFrame column.
    Returns the best match string if above cutoff, otherwise None.
    Does NOT modify df at all.
    """
    # replacing NaN with empty string just for comparison
    candidates = (
        df[column]
        .fillna("")             # keeping all rows, avoid dropping
        .astype(str)
        .str.lower()
        .unique()
        .tolist()
    )

    candidates = [c for c in candidates if c.strip() != ""]

    value_lower = str(value).lower()

    # 1) Substring match first
    substr = [c for c in candidates if value_lower in c or c in value_lower]
    if substr:
        chosen = min(substr, key=len)  # shortest match heuristic
        # print(f'substr was {substr} and returned {chosen}')
        return chosen

    # 2) Fallback to fuzzy
    match = process.extractOne(
        value_lower, candidates,
        scorer=fuzz.token_set_ratio
    )

    if match:
        print(f'the score for {value} is {match[1]}')
        if match[1] >= cutoff:
            return match[0]

    return None



def validate_user_input(user_json, df):
    validated = {}

    # columns with preprocessing thresholds
    threshold_map = {
        'floor': 40,
        'extra_person_capacity': 40,
        'total_floors_count': 40,
        'unit_per_floor': 9,
        'construction_year': 1369,
    }

    persian_num_map = {
        'بدون اتاق': 0,
        'یک': 1,
        'دو': 2,
        'سه': 3,
        'چهار': 4,
        'پنج': 5,
        'پنج یا بیشتر': 6
    }

    for key, value in user_json.items():
        if key == 'info' or key == 'answer':
            continue

        # handle Persian numbers for rooms_count
        if key == 'rooms_count' and isinstance(value, str) and value in persian_num_map:
            value = persian_num_map[value]

        # handle preprocessing thresholds
        if key in threshold_map:
            if key == 'construction_year':
                # years below 1370 become 1369
                if isinstance(value, int) and value < 1370:
                    value = 1369
            else:
                # values above threshold become threshold
                if isinstance(value, int) and value > threshold_map[key]:
                    value = threshold_map[key]

        # handling min_/max_ prefixes
        if key.startswith("min_"):
            col = key[4:]
            min_val, max_val = df[col].min(), df[col].max()
            if col in threshold_map and isinstance(value, int) and value > threshold_map[col]:
                value = threshold_map[col]
            if value < min_val:
                validated[key] = "❌out of range"
            elif value > max_val:
                validated[key] = max_val
            else:
                validated[key] = value
            continue
        elif key.startswith("max_"):
            col = key[4:]
            min_val, max_val = df[col].min(), df[col].max()
            if col in threshold_map and isinstance(value, int) and value > threshold_map[col]:
                value = threshold_map[col]
            if value > max_val:
                validated[key] = "❌out of range"
            elif value < min_val:
                validated[key] = min_val
            else:
                validated[key] = value
            continue

        col_dtype = df[key].dtype

        # numerical columns
        if pd.api.types.is_numeric_dtype(col_dtype):
            min_val, max_val = df[key].min(), df[key].max()
            if key in threshold_map and isinstance(value, int) and value > threshold_map[key]:
                value = threshold_map[key]
            if value < min_val or value > max_val:
                validated[key] = "❌out of range"
            else:
                validated[key] = value

        # boolean columns (including nullable boolean)
        elif pd.api.types.is_bool_dtype(col_dtype) or pd.api.types.is_integer_dtype(col_dtype) and df[key].dropna().isin([0,1]).all():
            if value not in [True, False]:
                validated[key] = "❌out of range"
            else:
                validated[key] = value

        # categorical/string columns
        else:
            if key in ['city_slug', 'neighborhood_slug']:
                match = fuzzy_match_column(value, df, key, cutoff=70)
                if match:
                    validated[key] = match
                else:
                    validated[key] = "❌out of range"
            elif value in df[key].dropna().unique().tolist():
                validated[key] = value
            else:
                validated[key] = "❌out of range"

    return validated


def range_test(user_input):
    print('Testing for:', user_input, '\n------------------------------------------')
    validated_input = validate_user_input(user_input, df)
    return validated_input

# ------ extraction -------
def filter_dataframe(df: pd.DataFrame, user_filters: dict):
    filtered_df = df.copy()

    # --- First, group min_/max_ constraints per column ---
    range_constraints = {}
    for key, value in user_filters.items():
        if value in [None, "", "❌out of range"]:
            continue
        if key.startswith("min_") or key.startswith("max_"):
            base_col = key.replace("min_", "").replace("max_", "")
            if base_col not in df.columns:
                continue
            if base_col not in range_constraints:
                range_constraints[base_col] = {}
            if key.startswith("min_"):
                range_constraints[base_col]["min"] = value
            else:
                range_constraints[base_col]["max"] = value

    # --- applying all filters ---
    for key, value in user_filters.items():

        if key == 'info' or key == 'answer':
            continue

        if value in [None, "", "❌out of range"]:
            continue

        # --- handle ranges together ---
        if key.startswith("min_") or key.startswith("max_"):
            base_col = key.replace("min_", "").replace("max_", "")
            if base_col not in df.columns:
                continue

            bounds = range_constraints.get(base_col, {})
            if "min" in bounds and "max" in bounds:
                filtered_df = filtered_df[
                    (filtered_df[base_col] >= bounds["min"]) &
                    (filtered_df[base_col] <= bounds["max"])
                ]
            elif "min" in bounds:
                filtered_df = filtered_df[filtered_df[base_col] >= bounds["min"]]
            elif "max" in bounds:
                filtered_df = filtered_df[filtered_df[base_col] <= bounds["max"]]

            range_constraints.pop(base_col, None) # prevent double filtering
            continue

        # --- Handle booleans (stored as object strings sometimes) ---
        elif isinstance(value, bool):
            if key in df.columns:
                filtered_df = filtered_df[
                    filtered_df[key].astype(str).str.lower() == str(value).lower()
                ]

        # --- handling fuzzy string similarity (city, neighborhood) ---
        elif key == 'city_slug' and isinstance(value, str):
            best_city = fuzzy_match_column(value, filtered_df, 'city_slug', cutoff=60)
            if best_city:
                filtered_df = filtered_df[filtered_df['city_slug'].str.lower() == best_city.lower()]

        elif key == 'neighborhood_slug' and isinstance(value, str):
            # Only match neighborhood inside filtered city
            if 'city_slug' in user_filters and user_filters['city_slug']:
                city_val = user_filters['city_slug']
                city_match = fuzzy_match_column(city_val, filtered_df, 'city_slug', cutoff=60)

                df_city = filtered_df[filtered_df['city_slug'].str.lower() == city_match.lower()] if city_match else filtered_df
                
                best_neigh = fuzzy_match_column(value, df_city, 'neighborhood_slug', cutoff=60)
                if best_neigh:
                    filtered_df = df_city[df_city['neighborhood_slug'].str.lower() == best_neigh.lower()]
                else:
                    filtered_df = df_city

            else:  
                best_neigh = fuzzy_match_column(value, filtered_df, 'neighborhood_slug', cutoff=60)
                if best_neigh:
                    filtered_df = filtered_df[filtered_df['neighborhood_slug'].str.lower() == best_neigh.lower()]

        # --- Handle direct matches for other columns ---
        elif key in df.columns:
            filtered_df = filtered_df[filtered_df[key] == value]

    return filtered_df


MIN_REQUIRED = 4  # minimum fields to filter

def check_json_fields(json_data, min_required=MIN_REQUIRED):
    """Return out_of_range, missing, and number of filled fields."""
    out_of_range = [k for k, v in json_data.items() if v == "❌out of range"]
    normalized_fields = set()
    for k, v in json_data.items():
        if v not in (None, "", [], "❌out of range"):
            normalized_fields.add(k.replace("min_", "").replace("max_", ""))
    num_filled = len(normalized_fields)
    missing = [k for k in FIELDS_ORDER if k not in normalized_fields]
    return out_of_range, missing, num_filled

# --- Friendly response generator ---
def generate_friendly_response(user_text, extracted_fields=None, warning=None):
    """
    Generate a short, friendly Persian response that feels human and supportive.
    - Always max 3 short sentences.
    - No greetings, no verbose explanations.
    - If warning exists: just briefly acknowledge some details were missing, but sound positive and supportive.
    - If no warning: simply rephrase/acknowledge the user’s request in a natural, informal but professional way.
    - Never list or explain invalid/missing fields (handled elsewhere).
    - Always reply in informal Persian.
    """

    prompt = (
        "You are a real estate assistant. Reply in informal Persian. "
        "Never greet. Keep it max 3 short sentences. "
        "Always sound supportive and human-like. "
        "If warning is present, just briefly acknowledge that some info is missing but reassure the user. "
        "Do not list or explain the missing fields (they are handled elsewhere). "
        "If no warning, just rephrase/acknowledge the user’s request in a natural, informal way. "
        "Always reply in Persian.\n"
        f"User message: {user_text}"
    )


    if warning:
        prompt += f"\nWarning: {warning}"

    if extracted_fields:
        prompt += f"\nExtracted fields: {extracted_fields}"

    completion = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a real estate assistant. Reply only in informal Persian, max 3 short sentences, supportive tone."
            },
            {"role": "user", "content": prompt}
        ]
    )
    return completion.choices[0].message.content.strip()



def process_user_input(user_id: str, user_text: str, user_states: dict):
    """
    Stateful version: keep previously extracted fields and merge with new ones.
    """

    if user_id not in user_states:
        user_states[user_id] = {"valid_fields": {}}

    extracted = parse_user_query(user_text) # parsing only the NEW text (not the whole history)

    # merge with previous valid fields (stored in user_states)
    prev_valid = user_states[user_id].get("valid_fields", {})
    merged = {**prev_valid, **extracted}

    validated_range = range_test(merged)
    out_of_range, missing, _ = check_json_fields(validated_range, MIN_REQUIRED)

    valid_fields = {k: v for k, v in validated_range.items() if v != "❌out of range"}  # removing out-of-range for further processing

    user_states[user_id]["valid_fields"] = valid_fields   # saving back to state for next turn

    valid_normalized = set(k.replace("min_","").replace("max_","") for k in valid_fields)
    num_filled = len(valid_normalized)
    missing = [k for k in FIELDS_ORDER if k not in valid_normalized]

    out_str = "\n".join(
        f"- {column_name_fa.get(k.replace('min_','').replace('max_',''),k)}"
        for k in out_of_range
    ) if out_of_range else ""
    warning = f"\n⚠️ بعضی مقادیر نامعتبر بودن و در سرچ در نظر گرفته نمیشن:\n{out_str}\n" if out_of_range else ""

    friendly_prefix = generate_friendly_response(
        user_text=user_text,
        extracted_fields=valid_fields,
        warning=warning if warning else None
    )

    if num_filled >= MIN_REQUIRED:
        df_results = filter_dataframe(df, valid_fields)
        warning = friendly_prefix + warning
        return warning + f"🔎 پیدا کردن خونه با مشخصات گفته شده...", df_results

    needed = [f"- {column_name_fa.get(k,k)}" for k in missing[:5]]
    answer_text = warning + "لطفا اطلاعات بیشتری بده 🙏\n\n👇 از این موارد هم میتونی مشخص کنی:\n" + "\n".join(needed)
    answer_text = friendly_prefix + answer_text

    return answer_text, pd.DataFrame()

