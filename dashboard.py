from flask import Flask, render_template, request
import json
from datetime import datetime
import os
import statistics
import locale
from babel.dates import format_datetime, get_timezone

app = Flask(__name__)

# ملفات البيانات
RATINGS_FILE = "ratings.json"
SPEED_TESTS_FILE = "speed_tests.json"

def load_ratings():
    try:
        with open(RATINGS_FILE, "r", encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"total_ratings": 0, "sum_ratings": 0, "average": 0, "ratings": []}

def load_speed_tests():
    try:
        with open(SPEED_TESTS_FILE, "r", encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"speed_tests": []}

def is_today(timestamp):
    return timestamp.startswith(datetime.now().strftime("%Y-%m-%d"))

def get_statistics():
    try:
        with open(SPEED_TESTS_FILE, 'r', encoding='utf-8') as f:
            tests = json.load(f)
        
        with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
            ratings = json.load(f)
        
        # حساب الإحصائيات
        total_tests = len(tests["speed_tests"])
        unique_users = len(set(test['user_id'] for test in tests["speed_tests"]))
        today_tests = len([test for test in tests["speed_tests"] if is_today(test['timestamp'])])
        
        # حساب المتوسطات
        if total_tests > 0:
            avg_download = sum(test['download_speed'] for test in tests["speed_tests"]) / total_tests
            avg_upload = sum(test['upload_speed'] for test in tests["speed_tests"]) / total_tests
            avg_ping = sum(test['ping'] for test in tests["speed_tests"]) / total_tests
        else:
            avg_download = avg_upload = avg_ping = 0
        
        # حساب متوسط التقييمات
        total_ratings = ratings.get("total_ratings", 0)
        avg_rating = ratings.get("average", 0)
        
        # دمج بيانات الاختبارات مع التقييمات
        tests_with_ratings = []
        for test in tests["speed_tests"]:
            test_rating = next((rating['rating'] for rating in ratings.get("ratings", []) if rating['user_id'] == test['user_id']), 0)
            test_copy = test.copy()
            test_copy['rating'] = test_rating
            tests_with_ratings.append(test_copy)
        
        # ترتيب الاختبارات حسب الوقت
        tests_with_ratings.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'total_tests': total_tests,
            'total_users': unique_users,
            'today_tests': today_tests,
            'average_download': avg_download,
            'average_upload': avg_upload,
            'average_ping': avg_ping,
            'average_rating': avg_rating,
            'all_tests': tests_with_ratings,  # جميع الاختبارات
            'recent_tests': tests_with_ratings[:10]  # آخر 10 اختبارات فقط
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return None

def get_formatted_dates():
    now = datetime.now()
    # التاريخ بالإنجليزية
    english_date = format_datetime(now, format='EEEE, MMMM d, yyyy', locale='en')
    # التاريخ بالعربية
    arabic_date = format_datetime(now, format='EEEE، d MMMM yyyy', locale='ar')
    return {
        'english': english_date,
        'arabic': arabic_date,
        'time': now.strftime('%I:%M %p')
    }

@app.route('/')
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = 5  # عدد السجلات في كل صفحة
    
    stats = get_statistics()
    if not stats:
        return render_template('dashboard.html', stats=None)
    
    dates = get_formatted_dates()
    
    # حساب عدد الصفحات
    total_tests = len(stats['all_tests'])
    total_pages = (total_tests + per_page - 1) // per_page
    
    # الحصول على سجلات الصفحة الحالية
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    stats['page_tests'] = stats['all_tests'][start_idx:end_idx]
    stats['pagination'] = {
        'current_page': page,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'pages': range(1, total_pages + 1)
    }
    stats['dates'] = dates
    
    return render_template('dashboard.html', stats=stats)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
