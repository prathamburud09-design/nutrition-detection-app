"""
=============================================================================
NutriLens AI - AI Vision & Nutrition Estimation Service
=============================================================================
This module handles:
1. High-speed multimodal neural vision processing for meal images.
2. Clinical Dietitian prompting for high macronutrient and micronutrient accuracy.
3. Complete Macro Extraction: Calories, Protein, Fat, Carbs, Dietary Fiber, and Health Insights.
4. Primary engine: Ultra-fast Google Gemini Vision models (gemini-3.5-flash-lite / gemini-3.5-flash / gemini-2.5-flash).
5. Secondary engine: Multimodal Groq Vision failover (qwen/qwen3.6-27b).
6. Smart Non-Food Detection: Instant 2-second recognition of non-food images without wasteful retries.
7. Resilient multi-stage JSON parser with reasoning tag stripping and fallback extraction.
8. In-memory caching for zero latency on duplicate scans.
9. Safe Error Masking: Ensures clean, user-friendly output with zero technical leakage.
=============================================================================
"""

import sys
import os
import json
import base64
import hashlib
import re
import io
import requests
from PIL import Image, ImageOps
from dotenv import load_dotenv
from groq import Groq

# Ensure UTF-8 console output on Windows/Linux/macOS
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# In-memory cache for duplicate image requests: { cache_key: analysis_data }
_IMAGE_CACHE = {}


def get_groq_client():
    """
    Initializes and returns the Groq client if key is present.
    """
    load_dotenv(override=True)
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        print(f"⚠️ Groq client initialization error: {e}")
        return None


def optimize_and_encode_image(image_path, max_dimension=768):
    """
    Resizes, corrects EXIF orientation, and compresses the image for optimal vision analysis.
    Returns: (raw_bytes, base64_string, mime_type)
    """
    try:
        with Image.open(image_path) as img:
            # Correct phone photo orientation from EXIF
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # Convert any non-RGB image (RGBA, P, LA, CMYK) to standard RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            image_bytes = buffer.getvalue()
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            return image_bytes, base64_string, "image/jpeg"
    except Exception as e:
        print(f"⚠️ Image optimization fallback: {e}")
        with open(image_path, "rb") as f:
            raw_bytes = f.read()
            return raw_bytes, base64.b64encode(raw_bytes).decode('utf-8'), "image/jpeg"


def build_dietitian_prompt(food_hint=None):
    """
    Constructs an academic, clinical-grade nutrition prompt for maximum accuracy.
    """
    hint_clause = f"User Context / Hint: '{food_hint}'. Use as reference." if food_hint else ""

    system_prompt = f"""You are an Elite Clinical Dietitian and AI Nutrition Vision Specialist.
Analyze the food items visible in this image with high biochemical accuracy.
{hint_clause}

CLINICAL ACCURACY GUIDELINES:
1. DISH IDENTIFICATION: Accurately identify all distinct culinary items (e.g., 'Sabudana Vada', 'Tomato Ketchup', 'Cheeseburger', 'French Fries', 'Idli', 'Sambar', 'Coconut Chutney', 'Masala Dosa', 'Paneer Tikka', 'Chapati', 'Dal', 'Grilled Chicken Salad', 'Poha', 'Biryani').
2. PORTION SIZING: Estimate realistic portion sizes and weights based on standard serving dishes (e.g. 6 pieces (180g), 1 burger (220g), 1 bowl (150g), 2 tbsp (30g)).
3. MACRO INTEGRITY: Accurately compute Protein (g), Fats (g), Carbs (g), Dietary Fiber (g), and Total Calories (kcal).
   Formula: Calories ≈ (Protein * 4) + (Carbs * 4) + (Fat * 9).
4. HEALTH INSIGHTS:
   - Provide 2-3 dietary tags (e.g., 'Complex Carbs', 'High Protein', 'High Fiber', 'Balanced Nutrition', 'Vegetarian', 'Fried Snack', 'Gluten-Free').
   - Provide 1 actionable dietitian recommendation on nutritional balance and health benefits.
5. If the image does NOT contain any food items, return exactly: {{"tags": [], "dietitian_tip": "No food detected", "items": []}}.
6. Reply ONLY with valid JSON matching this schema with no reasoning or markdown surrounding it:

{{
  "tags": ["High Protein", "Moderate Carbs", "Balanced"],
  "dietitian_tip": "Balanced meal providing essential macronutrients and energy.",
  "items": [
    {{
      "name": "Food Name",
      "quantity": "Portion size (e.g. 2 pieces (120g))",
      "calories": 350,
      "protein": 12.0,
      "fat": 10.0,
      "carbs": 52.0,
      "fiber": 3.5
    }}
  ]
}}"""
    return system_prompt


def parse_nutrition_json(raw_text):
    """
    Resilient multi-stage parser to extract valid nutrition and health insights.
    Handles raw JSON, markdown code blocks, reasoning <think> tags, non-food detection, and regex fallback.
    """
    if not raw_text:
        return None

    # Step 1: Strip <think>...</think> reasoning tags (including unclosed <think> blocks)
    text_clean = re.sub(r'<think>[\s\S]*?(?:</think>|$)', '', raw_text, flags=re.DOTALL).strip()

    # Helper function to validate and format parsed dict
    def validate_and_format(data):
        if not isinstance(data, dict):
            return None
        
        items = data.get("items", [])
        # Check if the AI explicitly stated no food detected
        tip = str(data.get("dietitian_tip", "")).strip().lower()
        if isinstance(items, list) and len(items) == 0 and ("no food" in tip or tip in ["no food detected", "none", ""]):
            return {"no_food": True, "dietitian_tip": "No food detected", "items": [], "tags": []}

        if not isinstance(items, list) or len(items) == 0:
            return None
        
        cleaned_items = []
        for it in items:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name", "Dish")).strip()
            if not name or name.lower() in ["no food detected", "none", "unknown", "n/a"]:
                continue
            
            quantity = str(it.get("quantity", "1 serving")).strip()
            pro = round(max(0.0, float(it.get("protein", 0.0))), 1)
            fat = round(max(0.0, float(it.get("fat", 0.0))), 1)
            carbs = round(max(0.0, float(it.get("carbs", 0.0))), 1)
            fiber = round(max(0.0, float(it.get("fiber", 0.0))), 1)
            
            # Calorie calculation fallback if missing or zero
            cal_val = float(it.get("calories", 0.0))
            if cal_val <= 0.0:
                cal_val = round((pro * 4) + (carbs * 4) + (fat * 9), 1)
            else:
                cal_val = round(cal_val, 1)

            cleaned_items.append({
                "name": name,
                "quantity": quantity,
                "calories": cal_val,
                "protein": pro,
                "fat": fat,
                "carbs": carbs,
                "fiber": fiber
            })

        if cleaned_items:
            tags = data.get("tags", [])
            if not isinstance(tags, list) or not tags:
                tags = ["Nutritious Meal", "Balanced Nutrition"]
            
            coach_tip = str(data.get("dietitian_tip", "")).strip()
            if not coach_tip or coach_tip.lower() in ["no food detected", "none"]:
                coach_tip = "Balanced meal with essential macronutrients to support healthy sustained energy."

            return {
                "tags": [str(t).strip() for t in tags if str(t).strip()],
                "dietitian_tip": coach_tip,
                "items": cleaned_items
            }
        return None

    # Step 2: Extract from ```json ... ``` code fence
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text_clean if text_clean else raw_text)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            valid = validate_and_format(data)
            if valid:
                return valid
        except Exception:
            pass

    # Step 3: Parse cleaned text directly as JSON
    if text_clean:
        try:
            data = json.loads(text_clean)
            valid = validate_and_format(data)
            if valid:
                return valid
        except Exception:
            pass

    # Step 4: Find outer { ... "items" ... } block
    match = re.search(r'(\{[\s\S]*"items"\s*:\s*\[[\s\S]*\][\s\S]*\})', text_clean if text_clean else raw_text)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            valid = validate_and_format(data)
            if valid:
                return valid
        except Exception:
            pass

    # Step 5: Fallback - Extract individual item dictionary objects
    items = []
    item_blocks = re.findall(r'\{[^{}]*"name"[^{}]*\}', raw_text)
    for block in item_blocks:
        try:
            item_data = json.loads(block)
            if "name" in item_data and ("calories" in item_data or "protein" in item_data or "carbs" in item_data):
                pro = round(max(0.0, float(item_data.get("protein", 0.0))), 1)
                fat = round(max(0.0, float(item_data.get("fat", 0.0))), 1)
                carbs = round(max(0.0, float(item_data.get("carbs", 0.0))), 1)
                fiber = round(max(0.0, float(item_data.get("fiber", 0.5))), 1)
                
                cal = float(item_data.get("calories", 0.0))
                if cal <= 0.0:
                    cal = round((pro * 4) + (carbs * 4) + (fat * 9), 1)
                else:
                    cal = round(cal, 1)

                items.append({
                    "name": str(item_data.get("name", "Dish")).strip(),
                    "quantity": str(item_data.get("quantity", "1 serving")).strip(),
                    "calories": cal,
                    "protein": pro,
                    "fat": fat,
                    "carbs": carbs,
                    "fiber": fiber
                })
        except Exception:
            pass

    # Step 6: Regex fallback for broken JSON formats
    if not items:
        item_pattern = re.findall(
            r'["\']?name["\']?\s*:\s*["\']([^"\']+)["\'][\s\S]*?["\']?quantity["\']?\s*:\s*["\']([^"\']+)["\'][\s\S]*?["\']?calories["\']?\s*:\s*([0-9.]+)[\s\S]*?["\']?protein["\']?\s*:\s*([0-9.]+)[\s\S]*?["\']?fat["\']?\s*:\s*([0-9.]+)[\s\S]*?["\']?carbs["\']?\s*:\s*([0-9.]+)',
            raw_text
        )
        for match_item in item_pattern:
            try:
                items.append({
                    "name": match_item[0].strip(),
                    "quantity": match_item[1].strip(),
                    "calories": round(float(match_item[2]), 1),
                    "protein": round(float(match_item[3]), 1),
                    "fat": round(float(match_item[4]), 1),
                    "carbs": round(float(match_item[5]), 1),
                    "fiber": 1.5
                })
            except Exception:
                continue

    if items:
        tags = ["Nutritious Meal", "Balanced Nutrition"]
        tip = "Balanced meal with essential macronutrients and dietary fiber to support healthy digestion and energy."
        
        tags_match = re.search(r'"tags"\s*:\s*(\[[^\]]+\])', raw_text)
        if tags_match:
            try:
                parsed_tags = json.loads(tags_match.group(1))
                if isinstance(parsed_tags, list) and parsed_tags:
                    tags = parsed_tags
            except Exception:
                pass
                
        tip_match = re.search(r'"dietitian_tip"\s*:\s*"([^"]+)"', raw_text)
        if tip_match:
            tip = tip_match.group(1)

        return {
            "tags": tags,
            "dietitian_tip": tip,
            "items": items
        }

    return None


def _run_primary_engine(base64_image, mime_type, food_hint=None):
    """
    Primary neural vision execution pipeline (Google Gemini).
    Uses ultra-fast gemini-3.5-flash-lite, with seamless fallback to gemini-3.5-flash and gemini-2.5-flash.
    """
    load_dotenv(override=True)
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == "your_google_api_key_here":
        return None

    system_prompt = build_dietitian_prompt(food_hint)

    # Prioritize fastest and highest-performing Gemini multimodal models
    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-2.5-flash"
    ]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": system_prompt + "\n\nAnalyze this meal and return the nutrition JSON."},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json"
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=25)
            if response.status_code == 200:
                res_json = response.json()
                candidates = res_json.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    texts = [p.get('text', '') for p in parts if not p.get('thought', False) and 'text' in p]
                    raw_text = "".join(texts) if texts else (parts[0].get('text', '') if parts else '')
                    parsed_data = parse_nutrition_json(raw_text)
                    if parsed_data:
                        print(f"✅ Gemini ({model_name}) succeeded.")
                        return parsed_data
            elif response.status_code == 429:
                print(f"⚠️ Gemini quota/rate limit reached (HTTP 429). Fast failover to next...")
                continue
            elif response.status_code == 404:
                continue
            else:
                print(f"⚠️ Gemini ({model_name}) HTTP {response.status_code}: {response.text[:120]}")
        except Exception as e:
            print(f"⚠️ Gemini ({model_name}) error: {e}")

    return None


def _run_secondary_engine(base64_image, food_hint=None):
    """
    Secondary neural vision execution pipeline (Groq Multimodal Vision with qwen/qwen3.6-27b).
    """
    client = get_groq_client()
    if not client:
        return None

    system_prompt = build_dietitian_prompt(food_hint)

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt + "\nIMPORTANT: Do not output reasoning or explanation. Output ONLY the JSON object."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze the food image and output the nutrition JSON."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model="qwen/qwen3.6-27b",
            temperature=0.0,
            max_tokens=1500,
            timeout=25
        )
        raw_output = response.choices[0].message.content.strip()
        parsed_data = parse_nutrition_json(raw_output)
        if parsed_data:
            print("✅ Groq Vision Engine succeeded.")
            return parsed_data
    except Exception as e:
        print(f"⚠️ Groq Vision Engine error: {e}")

    return None


def analyze_food_image(image_path, food_hint=None):
    """
    Main orchestrator: Executes AI Vision Nutrition Analysis with automated failover.
    
    Returns:
        tuple: (data_dict, user_friendly_error_message)
    """
    print(f"🤖 NutriLens Vision: Processing image {os.path.basename(image_path)}...")

    # 1. Compress and encode image
    image_bytes, base64_image, mime_type = optimize_and_encode_image(image_path, max_dimension=768)

    # 2. Check in-memory cache to save compute
    cache_key = hashlib.md5(image_bytes).hexdigest()
    if food_hint:
        cache_key += f"_{food_hint.strip().lower()}"

    if cache_key in _IMAGE_CACHE:
        print("⚡ Returning cached nutrition analysis.")
        return _IMAGE_CACHE[cache_key], None

    # 3. Pipeline 1: Primary Vision Analysis (Gemini)
    primary_data = _run_primary_engine(base64_image, mime_type, food_hint)
    if primary_data:
        if primary_data.get("no_food"):
            print("ℹ️ Primary Engine: Image detected as non-food.")
            return None, "No food was detected in this photo. Please upload a clear photo of your meal or provide a food hint."
        
        if "items" in primary_data and len(primary_data["items"]) > 0:
            _IMAGE_CACHE[cache_key] = primary_data
            print(f"✅ Primary Engine (Gemini): Identified {len(primary_data['items'])} food item(s).")
            return primary_data, None

    # 4. Pipeline 2: Secondary Vision Analysis (Groq Failover)
    print("🔄 Primary engine unavailable. Switching to Secondary Vision Engine (Groq)...")
    # For Groq, use slightly more compact dimension to fit strict token budgets
    _, secondary_b64, _ = optimize_and_encode_image(image_path, max_dimension=512)
    secondary_data = _run_secondary_engine(secondary_b64, food_hint)
    if secondary_data:
        if secondary_data.get("no_food"):
            print("ℹ️ Secondary Engine: Image detected as non-food.")
            return None, "No food was detected in this photo. Please upload a clear photo of your meal or provide a food hint."
        
        if "items" in secondary_data and len(secondary_data["items"]) > 0:
            _IMAGE_CACHE[cache_key] = secondary_data
            print(f"✅ Secondary Engine (Groq): Identified {len(secondary_data['items'])} food item(s).")
            return secondary_data, None

    # 5. Safe, clean fallback message
    print("⚠️ Unable to identify food components from image.")
    return None, "Unable to analyze food in this photo. Please ensure the image is clear and well-lit, or add a food hint."
