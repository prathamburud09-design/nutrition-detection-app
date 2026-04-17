import os
import json
import base64
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def configure_ai():
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key or api_key == "your_groq_api_key_here":
        print("❌ GROQ_API_KEY not found or invalid in environment variables")
        return None
    
    return Groq(api_key=api_key)

def analyze_food_image(image_path, food_hint=None):
    """
    Analyze food image using Groq API
    Returns a list of detected food items with nutrition info
    """
    print(f"🤖 AI Service: Analyzing {image_path} with Groq")
    
    client = configure_ai()
    if not client:
        return None

    try:
        # Encode the image
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        hint_instruction = f"IMPORTANT: The user has identified this context/food as: '{food_hint}'. Trust this hint to explicitly identify the primary food, then deduce calories and macros accurately." if food_hint else "Carefully distinguish between visually similar Indian dishes (e.g., Rice, Poha, Upma) based strictly on texture."
        
        prompt = (
            "Analyze this image and identify EVERY distinct food item or dish shown in the picture (e.g., if it's a platter or Indian Thali, list each individual bowl/item separately like 'Butter Chicken', 'Dal', 'Rice', 'Roti', 'Yogurt'). Do NOT list individual raw spices/herbs (like 'salt', 'cilantro', 'pepper') unless they are standalone items.\n"
            f"{hint_instruction}\n"
            "For EACH distinct dish or food item detected, estimate its portion size and provide the specific nutritional information (calories, protein, fat, carbs) for that particular item.\n\n"
            "Return ONLY a valid JSON array with this structure:\n"
            "[\n"
            "    {\n"
            '        "name": "food name",\n'
            '        "quantity": "estimated quantity (e.g. 1 cup, 100g)",\n'
            '        "calories": 100,\n'
            '        "protein": 10,\n'
            '        "fat": 5,\n'
            '        "carbs": 20\n'
            "    }\n"
            "]\n"
            "If no food is detected, return an empty array [].\n"
            "Do not include markdown formatting like ```json or ```."
        )
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
        )
        
        # Clean up response text
        text = chat_completion.choices[0].message.content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        print(f"🤖 AI Response: {text}")
        
        results = json.loads(text)
        return results
        
    except Exception as e:
        print(f"❌ AI Analysis Error: {e}")
        return None
