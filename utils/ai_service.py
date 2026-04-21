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
            "You are an Elite Indian Culinary Expert AI. Your task is to identify food items in images with 100% accuracy.\n"
            "Analyze this image carefully. Indian food can be visually ambiguous, so look for subtle clues:\n"
            "- Texture: Is it a dry sabzi, a wet gravy, a fried snack, or sprouted granules?\n"
            "- Context: What is it served with? (e.g., Chana/Dal usually pairs with Roti/Rice; Puffs/Samosas are standalone).\n"
            "- Regional hints: Identify if it is North Indian, South Indian, Street Food, or Bakery.\n"
            "- Portion Size/Scale: Look at the size of the food relative to the plate, bowl, or hand in the image. Estimate the exact quantity in standard Indian measurements (e.g., '150g', '2 pieces', '1 medium katori/bowl', '200g').\n\n"
            "First, internally think about the visual features and deduce the exact authentic Indian culinary name. Do not assume generic Western dishes (e.g. NEVER say Empanada, Flatbread, or Bean Salad).\n\n"
            f"{hint_instruction}\n"
            "After deducing the items, estimate the portion size and provide the specific nutritional information (calories, protein, fat, carbs) for each.\n\n"
            "You MUST output your final answer as a valid JSON array wrapped in ```json ... ```.\n"
            "[\n"
            "    {\n"
            '        "name": "Exact Authentic Indian Name (e.g. Masoor Dal, Moong Sprouts, Veg Puff, Roti)",\n'
            '        "quantity": "estimated quantity (e.g. 1 cup, 100g)",\n'
            '        "calories": 100,\n'
            '        "protein": 10,\n'
            '        "fat": 5,\n'
            '        "carbs": 20\n'
            "    }\n"
            "]\n"
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
            temperature=0.0
        )
        
        # Clean up response text
        text = chat_completion.choices[0].message.content.strip()
        print(f"🤖 AI Raw Response: {text}")
        
        # Extract JSON array using regex
        import re
        match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            results = json.loads(json_str)
            return results
        elif "[]" in text:
            return []
        else:
            print("❌ AI did not return a valid JSON array")
            return None
        
    except Exception as e:
        print(f"❌ AI Analysis Error: {e}")
        return None
