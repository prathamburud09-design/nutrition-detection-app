from flask import Flask, render_template, request, jsonify
import os
import time
from werkzeug.utils import secure_filename

# Import your custom modules
try:
    from utils.ai_service import analyze_food_image
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}

def allowed_file(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

# Create uploads directory if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("📤 Upload endpoint called...")
    
    try:
        # Check if file part exists
        if 'food_image' not in request.files:
            print("❌ No 'food_image' in request.files")
            print(f"📁 Available files: {list(request.files.keys())}")
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['food_image']
        print(f"📄 File object: {file}")
        print(f"📄 Filename: {file.filename}")
        print(f"📄 Content type: {file.content_type}")
        
        # Check if file is selected
        if file.filename == '':
            print("❌ No file selected")
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file type
        if not allowed_file(file.filename):
            print(f"❌ Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Please upload JPG, PNG, JPEG, GIF, WEBP, BMP, or TIFF.'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"💾 Saving to: {filepath}")
        
        file.save(filepath)
        
        # Verify file was saved
        if not os.path.exists(filepath):
            print("❌ File failed to save")
            return jsonify({'error': 'Failed to save image'}), 500
        
        print(f"✅ File saved successfully: {filename}")
        print(f"📏 File size: {os.path.getsize(filepath)} bytes")
        
        # Step 1: Analyze with AI
        print("🤖 Starting AI analysis...")
        start_time = time.time()
        
        food_hint = request.form.get('food_hint', '').strip()
        print(f"💡 User Hint Provided: {food_hint}" if food_hint else "💡 No User Hint Provided")
        
        ai_results = analyze_food_image(filepath, food_hint)
        
        results = []
        total_calories = 0
        total_protein = 0
        total_fat = 0
        total_carbs = 0
        data_sources = []
        
        if ai_results:
            print(f"✅ AI detected {len(ai_results)} items")
            for item in ai_results:
                food_result = {
                    'food_name': item['name'],
                    'quantity': item['quantity'],
                    'calories': item['calories'],
                    'protein': item['protein'],
                    'fat': item['fat'],
                    'carbs': item['carbs'],
                    'source': 'Groq AI (Llama 4)'
                }
                results.append(food_result)
                
                total_calories += item['calories']
                total_protein += item['protein']
                total_fat += item['fat']
                total_carbs += item['carbs']
                data_sources.append('Groq AI (Llama 4)')
        if not results:
             return jsonify({'error': 'No food items detected!!'}), 400
        
        processing_time = round(time.time() - start_time, 2)
        
        print(f"🎉 Analysis complete in {processing_time}s")
        print(f"📈 Total Calories: {total_calories}")
        print(f"🔬 Data sources: {list(set(data_sources))}")
        print(f"📊 Results: {len(results)} food items")
        
        return render_template('result.html', 
                             results=results,
                             total_calories=round(total_calories, 2),
                             total_protein=round(total_protein, 2),
                             total_fat=round(total_fat, 2),
                             total_carbs=round(total_carbs, 2),
                             image_url=filename,
                             processing_time=processing_time,
                             data_sources=list(set(data_sources)))
            
    except Exception as e:
        print(f"💥 UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/debug')
def debug():
    """Debug page to check server status"""
    info = {
        'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'templates_exists': os.path.exists('templates'),
        'static_exists': os.path.exists('static'),
        'current_directory': os.getcwd()
    }
    return jsonify(info)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 AI NUTRITION DETECTION APP STARTING")
    print("=" * 60)
    print("📁 Upload folder:", app.config['UPLOAD_FOLDER'])
    print("🌐 Server: http://localhost:5000")
    print("🐛 Debug: http://localhost:5000/debug")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=5000)