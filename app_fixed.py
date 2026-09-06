from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
from typing import Union, Any
import os
import json
import PyPDF2
import uuid
import requests
import sqlite3
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from ai_gemini import summarize_text_gemini, chat_with_gemini, generate_quiz_gemini, get_recommendations_gemini

app = Flask(__name__)
CORS(app)


app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  


DATABASE_PATH = 'studybuddy.db'


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyAvdkMPbUIYo0KWBqzyJW3uJx93v_vCn6E")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_files (
            file_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            text_content TEXT NOT NULL,
            summary TEXT DEFAULT NULL,
            session_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            file_id TEXT NOT NULL,
            attempt_count INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            FOREIGN KEY (file_id) REFERENCES uploaded_files(file_id),
            UNIQUE(session_id, file_id)
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            task TEXT NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')
    
    conn.commit()
    conn.close()


def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def require_session(session_id):
    """Verify session and return email or raise 401"""
    if not session_id:
        return None
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()
        return result['email'] if result else None

def create_user(email, name, password):
    """Create new user with hashed password"""
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
            (email, password_hash, name)
        )
        conn.commit()
        return True

def verify_user(email, password):
    """Verify user credentials"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, password FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        if result and check_password_hash(result['password'], password):
            return result['name']
    return None

def create_session(email):
    """Create new session"""
    session_id = str(uuid.uuid4())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_id, email) VALUES (?, ?)",
            (session_id, email)
        )
        conn.commit()
    return session_id

def save_uploaded_file(file_id, filename, text_content, session_id):
    """Save uploaded file to database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO uploaded_files (file_id, filename, text_content, session_id) VALUES (?, ?, ?, ?)",
            (file_id, filename, text_content, session_id)
        )
        conn.commit()

def get_uploaded_file(file_id, session_id):
    """Get uploaded file by ID and session"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filename, text_content, summary FROM uploaded_files WHERE file_id = ? AND session_id = ?",
            (file_id, session_id)
        )
        result = cursor.fetchone()
        
        if result:
            return {
                'filename': result[0],
                'text_content': result[1],
                'summary': result[2]
            }
        return None

def update_file_summary(file_id, session_id, summary):
    """Update the summary for an uploaded file"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE uploaded_files SET summary = ? WHERE file_id = ? AND session_id = ?",
            (summary, file_id, session_id)
        )
        conn.commit()

def save_chat_message(session_id, question, answer):
    """Save chat message to database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (session_id, question, answer) VALUES (?, ?, ?)",
            (session_id, question, answer)
        )
        conn.commit()

def get_quiz_attempt_count(session_id, file_id):
    """Get quiz attempt count for file"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT attempt_count FROM quiz_attempts WHERE session_id = ? AND file_id = ?",
            (session_id, file_id)
        )
        result = cursor.fetchone()
        return result['attempt_count'] if result else 0

def create_todo(session_id, task, priority='medium'):
    """Create a new todo in database"""
    todo_id = str(uuid.uuid4())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO todos (id, session_id, task, priority) VALUES (?, ?, ?, ?)",
            (todo_id, session_id, task, priority)
        )
        conn.commit()
    return todo_id

def get_todos(session_id):
    """Get all todos for a session"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM todos WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,)
        )
        todos = []
        for row in cursor.fetchall():
            todos.append({
                'id': row['id'],
                'task': row['task'],
                'completed': bool(row['completed']),
                'priority': row['priority'],
                'created_at': row['created_at']
            })
        return todos

def update_todo(session_id, todo_id, task=None, completed=None, priority=None):
    """Update a todo in database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        
        updates = []
        params = []
        
        if task is not None:
            updates.append("task = ?")
            params.append(task)
        if completed is not None:
            updates.append("completed = ?")
            params.append(completed)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE todos SET {', '.join(updates)} WHERE id = ? AND session_id = ?"
            params.extend([todo_id, session_id])
            
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
        return False

def delete_todo(session_id, todo_id):
    """Delete a todo from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM todos WHERE id = ? AND session_id = ?",
            (todo_id, session_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def update_quiz_attempt(session_id, file_id, score=0):
    """Update or create quiz attempt"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO quiz_attempts (session_id, file_id, attempt_count, score) 
               VALUES (?, ?, 1, ?)
               ON CONFLICT(session_id, file_id) 
               DO UPDATE SET 
                   attempt_count = attempt_count + 1,
                   score = ?,
                   created_at = CURRENT_TIMESTAMP""",
            (session_id, file_id, score, score)
        )
        conn.commit()


def migrate_database():
    """Apply database migrations for existing databases"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='quiz_attempts'")
        result = cursor.fetchone()
        
        if result and 'UNIQUE(session_id, file_id)' not in result[0]:
            print("Applying database migration for quiz_attempts unique constraint...")
            
            
            cursor.execute("""
                DELETE FROM quiz_attempts 
                WHERE rowid NOT IN (
                    SELECT MAX(rowid) 
                    FROM quiz_attempts 
                    GROUP BY session_id, file_id
                )
            """)
            
            
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_attempts_session_file 
                ON quiz_attempts(session_id, file_id)
            """)
            
            conn.commit()
            print("Database migration completed successfully.")
        
        
        cursor.execute("PRAGMA table_info(uploaded_files)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'summary' not in columns:
            print("Applying database migration to add summary column...")
            cursor.execute("ALTER TABLE uploaded_files ADD COLUMN summary TEXT DEFAULT NULL")
            conn.commit()
            print("Summary column migration completed successfully.")
        
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()


init_db()
migrate_database()


active_quizzes = {}  


todo_reminders = {}  


@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        if not email or not password or not name:
            return jsonify({"success": False, "message": "Email, password, and name are required"}), 400
        
        if password != confirm_password:
            return jsonify({"success": False, "message": "Passwords do not match"}), 400
        
        if len(password) < 6:
            return jsonify({"success": False, "message": "Password must be at least 6 characters long"}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({"success": False, "message": "Please enter a valid email address"}), 400
        
       
        try:
            create_user(email, name, password)
        except sqlite3.IntegrityError:
            return jsonify({"success": False, "message": "Email already exists. Please use a different email or login."}), 400
        
        return jsonify({
            "success": True,
            "message": f"Registration successful! Welcome, {name}! You can now login."
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Registration error: {str(e)}"}), 500


@app.route('/login', methods=['POST'])
def login():
    """Authenticate user"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"success": False, "message": "Email and password are required"}), 400
        
        
        user_name = verify_user(email, password)
        if user_name:
            
            session_id = create_session(email)
            return jsonify({
                "success": True, 
                "message": f"Welcome back, {user_name}!",
                "session_id": session_id,
                "user": user_name
            })
        else:
            return jsonify({"success": False, "message": "Invalid email or password"}), 401
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Login error: {str(e)}"}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload and text extraction"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"}), 400
        
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            return jsonify({"success": False, "message": "Only PDF files are supported"}), 400
        
        
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
       
        try:
            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                
                if not text_content.strip():
                    return jsonify({"success": False, "message": "Could not extract text from PDF"}), 400
        except Exception as e:
            return jsonify({"success": False, "message": f"Error reading PDF: {str(e)}"}), 500
        
       
        save_uploaded_file(file_id, filename, text_content, session_id)
        
        return jsonify({
            "success": True, 
            "message": f"File '{filename}' uploaded successfully",
            "file_id": file_id,
            "text_preview": text_content[:200] + "..." if len(text_content) > 200 else text_content
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Upload error: {str(e)}"}), 500


@app.route('/summary', methods=['POST'])
def get_summary():
    """Generate AI summary of uploaded PDF content"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        data = request.get_json()
        file_id = data.get('file_id')
        ai_provider = 'gemini'  
        
        
        file_data = get_uploaded_file(file_id, session_id)
        if not file_data:
            return jsonify({"success": False, "message": "File not found. Please upload a PDF first"}), 400
        
        text_content = file_data['text_content']
        filename = file_data['filename']
        
        
        existing_summary = file_data.get('summary')
        if existing_summary:
            summary = existing_summary
        else:
           
            summary = summarize_text_gemini(text_content)
            
            
            update_file_summary(file_id, session_id, summary)
        
        return jsonify({
            "success": True,
            "summary": summary,
            "ai_provider": ai_provider,
            "filename": filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Summary error: {str(e)}"}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat questions with AI"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        data = request.get_json()
        question = data.get('question', '').strip()
        ai_provider = 'gemini' 
        file_id = data.get('file_id') 
        
        if not question:
            return jsonify({"success": False, "message": "Please provide a question"}), 400
        
        
        context = ""
        if file_id:
            file_data = get_uploaded_file(file_id, session_id)
            if file_data:
                
                if file_data['summary']:
                    context = file_data['summary']
                else:
                    context = file_data['text_content'][:2000]  # Fallback to limited text content
        
       
        answer = chat_with_gemini(question, context)
        
        
        save_chat_message(session_id, question, answer)
        
        return jsonify({
            "success": True,
            "question": question,
            "answer": answer,
            "ai_provider": ai_provider
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Chat error: {str(e)}"}), 500


def generate_new_quiz_questions(text_content, num_questions, attempt_number):
    """Generate new quiz questions based on attempt number"""
    
    prompt_variations = [
        "basic concepts and fundamental principles",
        "detailed analysis and advanced applications", 
        "practical scenarios and real-world examples",
        "critical thinking and synthesis questions",
        "comprehensive understanding and connections"
    ]
    
    variation = prompt_variations[min(attempt_number, len(prompt_variations) - 1)]
    
    
    modified_prompt = f"Focus on {variation} from this material and create {num_questions} challenging questions: {text_content}"
    
    return generate_quiz_gemini(modified_prompt, num_questions)


@app.route('/quiz', methods=['POST'])
def quiz_generate() -> Any:
    """Generate quiz questions with new questions on retakes"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        data = request.get_json() or {}
        file_id = data.get('file_id')
        ai_provider = 'gemini' 
        num_questions = data.get('num_questions', 5)
        
        
        file_data = get_uploaded_file(file_id, session_id)
        if not file_data:
            return jsonify({"success": False, "message": "Please upload a PDF first"}), 400
        
        text_content = file_data['text_content']
        
        
        attempt_number = get_quiz_attempt_count(session_id, file_id)
        
       
        if attempt_number == 0:
            questions = generate_quiz_gemini(text_content, num_questions)
        else:
            questions = generate_new_quiz_questions(text_content, num_questions, attempt_number)
        
       
        quiz_id = str(uuid.uuid4())
        if session_id not in active_quizzes:
            active_quizzes[session_id] = {}
        
        active_quizzes[session_id][quiz_id] = {
            "questions": questions,
            "current_question": 0,
            "score": 0,
            "completed": False,
            "file_id": file_id,
            "attempt_number": attempt_number + 1
        }
        
        return jsonify({
            "success": True,
            "quiz_id": quiz_id,
            "questions": questions,
            "ai_provider": ai_provider,
            "attempt_number": attempt_number + 1
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Quiz error: {str(e)}"}), 500


@app.route('/quiz/answer', methods=['POST'])
def quiz_answer() -> Any:
    """Validate quiz answers and update scores"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        data = request.get_json()
        quiz_id = data.get('quiz_id')
        question_index = data.get('question_index')
        selected_answer = data.get('selected_answer')
        
        if not quiz_id or session_id not in active_quizzes or quiz_id not in active_quizzes[session_id]:
            return jsonify({"success": False, "message": "Quiz not found"}), 400
        
        quiz_data = active_quizzes[session_id][quiz_id]
        questions = quiz_data['questions']
        
        if question_index >= len(questions):
            return jsonify({"success": False, "message": "Invalid question index"}), 400
        
        question = questions[question_index]
        correct_answer = question['correct_answer']
        is_correct = selected_answer == correct_answer
        
        if is_correct:
            quiz_data['score'] += 1
        
        
        is_completed = question_index >= len(questions) - 1
        if is_completed:
            quiz_data['completed'] = True
            score_percentage = (quiz_data['score'] / len(questions)) * 100
            update_quiz_attempt(session_id, quiz_data['file_id'], score_percentage)
        
        return jsonify({
            "success": True,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": question.get('explanation', ''),
            "is_completed": is_completed,
            "score": quiz_data['score'],
            "total_questions": len(questions),
            "score_percentage": (quiz_data['score'] / len(questions)) * 100 if is_completed else None
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Quiz answer error: {str(e)}"}), 500


@app.route('/quiz/submit', methods=['POST'])
def quiz_submit() -> Any:
    """Submit all quiz answers at once and get comprehensive results"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        data = request.get_json()
        quiz_id = data.get('quiz_id')
        answers = data.get('answers', [])  # Array of answers [A, B, C, etc.]
        
        if not quiz_id or session_id not in active_quizzes or quiz_id not in active_quizzes[session_id]:
            return jsonify({"success": False, "message": "Quiz not found"}), 400
        
        quiz_data = active_quizzes[session_id][quiz_id]
        questions = quiz_data['questions']
        
        if len(answers) != len(questions):
            return jsonify({"success": False, "message": "Number of answers doesn't match number of questions"}), 400
        
        # Grade all answers
        results = []
        total_correct = 0
        
        for i, user_answer in enumerate(answers):
            if i >= len(questions):
                break
                
            question = questions[i]
            correct_answer = question['correct_answer']
            is_correct = user_answer == correct_answer
            
            if is_correct:
                total_correct += 1
            
            results.append({
                "question_index": i,
                "question": question['question'],
                "options": question['options'],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "explanation": question.get('explanation', '')
            })
        
        # Calculate final score
        score_percentage = (total_correct / len(questions)) * 100
        
        # Update quiz attempt in database
        update_quiz_attempt(session_id, quiz_data['file_id'], score_percentage)
        
        # Mark quiz as completed
        quiz_data['completed'] = True
        quiz_data['score'] = total_correct
        
        # Generate performance-based recommendations
        recommendations = get_performance_recommendations(score_percentage)
        
        return jsonify({
            "success": True,
            "quiz_completed": True,
            "total_score": total_correct,
            "total_questions": len(questions),
            "score_percentage": score_percentage,
            "results": results,
            "recommendations": recommendations,
            "performance_level": get_performance_level(score_percentage)
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Quiz submission error: {str(e)}"}), 500


def get_performance_level(score_percentage):
    """Get performance level based on score"""
    if score_percentage >= 80:
        return "excellent"
    elif score_percentage >= 60:
        return "good"
    else:
        return "needs_improvement"


def get_performance_recommendations(score_percentage):
    """Get study recommendations based on quiz performance"""
    if score_percentage < 60:
        return {
            "level": "beginner",
            "message": "Focus on fundamentals and basic concepts",
            "resources": [
                {
                    "title": "Beginner Tutorial Videos",
                    "type": "video",
                    "url": "https://www.youtube.com/results?search_query=beginner+tutorial",
                    "description": "Start with basic explanations and step-by-step tutorials"
                },
                {
                    "title": "Fundamentals Study Guide",
                    "type": "search",
                    "url": "https://duckduckgo.com/?q=fundamentals+study+guide",
                    "description": "Search for comprehensive guides covering the basics"
                },
                {
                    "title": "Basic Concepts Explained",
                    "type": "search", 
                    "url": "https://duckduckgo.com/?q=basic+concepts+explained+simply",
                    "description": "Find simple explanations of core concepts"
                }
            ]
        }
    elif score_percentage < 80:
        return {
            "level": "intermediate",
            "message": "Good progress! Focus on practice and deeper understanding",
            "resources": [
                {
                    "title": "Intermediate Level Tutorials",
                    "type": "video",
                    "url": "https://www.youtube.com/results?search_query=intermediate+level+tutorial",
                    "description": "Build on your foundation with more detailed tutorials"
                },
                {
                    "title": "Practice Exercises",
                    "type": "search",
                    "url": "https://duckduckgo.com/?q=practice+exercises",
                    "description": "Find exercises to reinforce your learning"
                },
                {
                    "title": "Detailed Examples",
                    "type": "search",
                    "url": "https://duckduckgo.com/?q=detailed+examples",
                    "description": "Study comprehensive examples and use cases"
                }
            ]
        }
    else:
        return {
            "level": "advanced",
            "message": "Excellent work! Ready for advanced challenges",
            "resources": [
                {
                    "title": "Advanced Techniques",
                    "type": "video",
                    "url": "https://www.youtube.com/results?search_query=advanced+techniques",
                    "description": "Explore sophisticated methods and best practices"
                },
                {
                    "title": "Expert Level Resources",
                    "type": "search",
                    "url": "https://duckduckgo.com/?q=expert+level+resources",
                    "description": "Access cutting-edge materials and research"
                },
                {
                    "title": "Challenging Problems",
                    "type": "search",
                    "url": "https://duckduckgo.com/?q=challenging+problems",
                    "description": "Test your skills with complex scenarios"
                }
            ]
        }


def get_youtube_videos(topic, max_results=3):
    """Get YouTube videos for a topic using YouTube Data API"""
    if not YOUTUBE_API_KEY:
        # Return placeholder videos when API key is not available
        return [
            {
                "title": f"Learn {topic} - Complete Tutorial",
                "description": f"Comprehensive tutorial covering all aspects of {topic}",
                "url": f"https://www.youtube.com/results?search_query={topic.replace(' ', '+')}"
            },
            {
                "title": f"{topic} Explained Simply", 
                "description": f"Easy-to-understand explanation of {topic} concepts",
                "url": f"https://www.youtube.com/results?search_query={topic.replace(' ', '+')}+explained"
            }
        ]
    
    try:
        # YouTube Data API v3 search endpoint
        search_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': topic,
            'key': YOUTUBE_API_KEY,
            'maxResults': max_results,
            'type': 'video',
            'order': 'relevance'
        }
        
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        videos = []
        for item in data.get('items', []):
            videos.append({
                "title": item['snippet']['title'],
                "description": item['snippet']['description'][:200] + "...",
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            })
        
        return videos
        
    except Exception as e:
        # Fallback to search URLs if API fails
        return [
            {
                "title": f"{topic} Tutorial Videos",
                "description": f"Educational videos about {topic}",
                "url": f"https://www.youtube.com/results?search_query={topic.replace(' ', '+')}"
            }
        ]


def get_duckduckgo_recommendations(topic, quiz_score=None):
    """Get DuckDuckGo search recommendations based on topic and quiz performance"""
    base_searches = [
        f"{topic} study guide",
        f"{topic} tutorial", 
        f"{topic} practice problems"
    ]
    
    # Adjust recommendations based on quiz score
    if quiz_score is not None:
        if quiz_score < 60:
            # Lower scores get basic/beginner resources
            base_searches = [
                f"{topic} basics for beginners",
                f"{topic} fundamentals explained",
                f"{topic} step by step guide"
            ]
        elif quiz_score < 80:
            # Medium scores get intermediate resources  
            base_searches = [
                f"{topic} intermediate guide",
                f"{topic} practice exercises",
                f"{topic} concepts explained"
            ]
        else:
            # High scores get advanced resources
            base_searches = [
                f"{topic} advanced topics",
                f"{topic} expert level",
                f"{topic} master class"
            ]
    
    recommendations = []
    for search_term in base_searches:
        recommendations.append({
            "title": f"Search: {search_term.title()}",
            "type": "search",
            "description": f"Find comprehensive resources about {search_term}",
            "url": f"https://duckduckgo.com/?q={search_term.replace(' ', '+')}"
        })
    
    return recommendations


def get_context_aware_recommendations(topic, pdf_context, latest_score, avg_score):
    """Generate context-aware recommendations based on quiz performance and PDF content"""
    
    # Determine performance level
    score_to_use = latest_score if latest_score is not None else avg_score
    
    if score_to_use < 60:
        performance_level = "struggling"
        focus_areas = "fundamental concepts and basic understanding"
    elif score_to_use < 80:
        performance_level = "progressing"
        focus_areas = "intermediate concepts and practice exercises"
    else:
        performance_level = "excelling"
        focus_areas = "advanced topics and challenging applications"
    
    # Create context-aware recommendations
    recommendations = []
    
    if pdf_context:
        # PDF-based recommendations
        recommendations.extend([
            {
                "title": f"📚 Review Key Concepts from Your Material",
                "type": "study",
                "description": f"Focus on {focus_areas} from your uploaded document to improve understanding",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+{focus_areas.replace(' ', '+')}"
            },
            {
                "title": f"🎯 Practice Questions for {topic}",
                "type": "practice",
                "description": f"Find practice exercises tailored to your current performance level ({performance_level})",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+practice+questions+{performance_level}"
            }
        ])
    
    # Performance-based recommendations
    if score_to_use < 60:
        recommendations.extend([
            {
                "title": f"🔰 {topic} - Beginner's Guide",
                "type": "guide",
                "description": "Start with fundamentals to build a strong foundation",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+beginners+guide+fundamentals"
            },
            {
                "title": f"📖 Step-by-Step {topic} Tutorial",
                "type": "tutorial",
                "description": "Follow structured learning path for better understanding",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+step+by+step+tutorial"
            }
        ])
    elif score_to_use < 80:
        recommendations.extend([
            {
                "title": f"⚡ {topic} - Intermediate Practice",
                "type": "practice",
                "description": "Strengthen your knowledge with intermediate-level exercises",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+intermediate+practice+exercises"
            },
            {
                "title": f"🧠 {topic} - Concept Reinforcement",
                "type": "study",
                "description": "Deepen understanding of key concepts you're learning",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+concept+explanation+examples"
            }
        ])
    else:
        recommendations.extend([
            {
                "title": f"🚀 Advanced {topic} Challenges",
                "type": "challenge",
                "description": "Take on advanced problems to further excel in this subject",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+advanced+problems+challenges"
            },
            {
                "title": f"🎓 {topic} - Expert Level Resources",
                "type": "advanced",
                "description": "Explore cutting-edge materials and research in this field",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+expert+level+research+advanced"
            }
        ])
    
    return recommendations


@app.route('/recommendations', methods=['GET'])
def get_recommendations():
    """Get context-aware study recommendations based on quiz performance and PDF content"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        topic = request.args.get('topic', '').strip()
        ai_provider = 'gemini'  # Always use Gemini
        
        # Get quiz performance data and PDF context
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get latest quiz score and file info
            cursor.execute("""
                SELECT qa.score, qa.file_id, uf.filename, uf.summary, uf.text_content,
                       (SELECT AVG(score) FROM quiz_attempts WHERE session_id = ?) as avg_score
                FROM quiz_attempts qa
                LEFT JOIN uploaded_files uf ON qa.file_id = uf.file_id
                WHERE qa.session_id = ? 
                ORDER BY qa.created_at DESC 
                LIMIT 1
            """, (session_id, session_id))
            quiz_data = cursor.fetchone()
            
            latest_score = quiz_data[0] if quiz_data else None
            latest_file_id = quiz_data[1] if quiz_data else None
            pdf_filename = quiz_data[2] if quiz_data else ""
            pdf_summary = quiz_data[3] if quiz_data else ""
            pdf_text = quiz_data[4] if quiz_data else ""
            avg_score = quiz_data[5] if quiz_data else 0
        
        # Determine context for recommendations
        pdf_context = pdf_summary if pdf_summary else (pdf_text[:1000] if pdf_text else "")
        
        if not topic and pdf_context:
            # If no topic provided, use PDF content for context-aware recommendations
            context_topic = f"study material from {pdf_filename}" if pdf_filename else "uploaded study material"
            recommendation_context = pdf_context
        elif topic:
            # Use provided topic but include PDF context if available
            context_topic = topic
            recommendation_context = pdf_context if pdf_context else ""
        else:
            # Fallback to general study
            context_topic = "general study"
            recommendation_context = ""
        
        # Get context-aware AI recommendations
        ai_recommendations = get_context_aware_recommendations(
            context_topic, 
            recommendation_context, 
            latest_score, 
            avg_score
        )
        
        # Get YouTube videos based on context
        youtube_videos = get_youtube_videos(context_topic)
        
        # Format YouTube recommendations
        youtube_recs = []
        for video in youtube_videos:
            youtube_recs.append({
                "title": f"📺 {video['title']}",
                "type": "video",
                "description": video['description'],
                "url": video['url']
            })
        
        # Get performance-based DuckDuckGo recommendations
        duckduckgo_recs = get_duckduckgo_recommendations(context_topic, latest_score or avg_score)
        
        # Combine all recommendations
        all_recommendations = ai_recommendations + youtube_recs + duckduckgo_recs
        
        # Create contextual message
        if pdf_context and not topic:
            recommendation_message = f"Smart recommendations based on your uploaded PDF: {pdf_filename}"
        elif topic:
            recommendation_message = f"Recommendations for: {topic}"
        else:
            recommendation_message = "General study recommendations"
            
        if latest_score is not None:
            recommendation_message += f" (Latest quiz score: {latest_score:.1f}%)"
        elif avg_score > 0:
            recommendation_message += f" (Average score: {avg_score:.1f}%)"
        
        return jsonify({
            "success": True,
            "recommendations": all_recommendations,
            "topic": context_topic,
            "ai_provider": ai_provider,
            "message": recommendation_message,
            "latest_quiz_score": latest_score,
            "avg_quiz_score": avg_score,
            "has_pdf_context": bool(pdf_context),
            "pdf_filename": pdf_filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Recommendations error: {str(e)}"}), 500


@app.route('/todo', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_todo() -> Any:
    """Manage todo list with database persistence and full CRUD operations"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        if request.method == 'GET':
            # Get all todos from database
            todos_list = get_todos(session_id)
            
            # Check for reminder (still use in-memory for reminder tracking)
            reminder_message = check_todo_reminder(session_id)
            
            return jsonify({
                "success": True,
                "todos": todos_list,
                "reminder": reminder_message
            })
        
        elif request.method == 'POST':
            # Add new todo to database
            data = request.get_json()
            task = data.get('task', '').strip()
            priority = data.get('priority', 'medium')
            
            if not task:
                return jsonify({"success": False, "message": "Task description is required"}), 400
            
            if priority not in ['low', 'medium', 'high']:
                return jsonify({"success": False, "message": "Priority must be low, medium, or high"}), 400
            
            todo_id = create_todo(session_id, task, priority)
            
            # Get the created todo to return
            todos_list = get_todos(session_id)
            created_todo = next((todo for todo in todos_list if todo['id'] == todo_id), None)
            
            return jsonify({
                "success": True,
                "message": "Task added successfully",
                "todo": created_todo
            })
        
        elif request.method == 'PUT':
            # Update todo in database (supports editing task text, completion status, and priority)
            data = request.get_json()
            todo_id = data.get('id')
            task = data.get('task')
            completed = data.get('completed')
            priority = data.get('priority')
            
            if not todo_id:
                return jsonify({"success": False, "message": "Todo ID is required"}), 400
            
            if priority is not None and priority not in ['low', 'medium', 'high']:
                return jsonify({"success": False, "message": "Priority must be low, medium, or high"}), 400
            
            # Update todo in database
            updated = update_todo(session_id, todo_id, task=task, completed=completed, priority=priority)
            
            if updated:
                # Get the updated todo to return
                todos_list = get_todos(session_id)
                updated_todo = next((todo for todo in todos_list if todo['id'] == todo_id), None)
                
                return jsonify({
                    "success": True,
                    "message": "Task updated successfully",
                    "todo": updated_todo
                })
            else:
                return jsonify({"success": False, "message": "Task not found"}), 404
        
        elif request.method == 'DELETE':
            # Delete todo from database
            data = request.get_json()
            todo_id = data.get('id')
            
            if not todo_id:
                return jsonify({"success": False, "message": "Todo ID is required"}), 400
            
            deleted = delete_todo(session_id, todo_id)
            
            if deleted:
                return jsonify({
                    "success": True,
                    "message": "Task deleted successfully"
                })
            else:
                return jsonify({"success": False, "message": "Task not found"}), 404
                
    except Exception as e:
        return jsonify({"success": False, "message": f"Todo error: {str(e)}"}), 500


def check_todo_reminder(session_id):
    """Check if user needs a todo reminder (every hour)"""
    if session_id not in todo_reminders:
        todo_reminders[session_id] = {"last_reminder": datetime.now()}
        return None
    
    last_reminder = todo_reminders[session_id]["last_reminder"]
    current_time = datetime.now()
    
    # Check if an hour has passed
    if current_time - last_reminder >= timedelta(hours=1):
        # Update reminder time
        todo_reminders[session_id]["last_reminder"] = current_time
        
        # Count incomplete todos
        # Get incomplete todos from database
        todos_list = get_todos(session_id)
        incomplete_todos = [todo for todo in todos_list if not todo['completed']]
        
        if incomplete_todos:
                high_priority = [todo for todo in incomplete_todos if todo.get('priority') == 'high']
                
                if high_priority:
                    return f"⚡ Reminder: You have {len(high_priority)} high-priority tasks pending!"
                else:
                    return f"📝 Reminder: You have {len(incomplete_todos)} tasks to complete."
    
    return None


@app.route('/reminder-check', methods=['GET'])
def reminder_check():
    """Manual endpoint to check for todo reminders"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        reminder = check_todo_reminder(session_id)
        
        return jsonify({
            "success": True,
            "has_reminder": reminder is not None,
            "message": reminder
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Reminder check error: {str(e)}"}), 500


@app.route('/user-stats', methods=['GET'])
def get_user_stats():
    """Get user statistics for dashboard"""
    try:
        session_id = request.headers.get('Session-ID')
        user_email = require_session(session_id)
        if not user_email:
            return jsonify({"success": False, "message": "Please login first"}), 401
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get file upload count
            cursor.execute("SELECT COUNT(*) FROM uploaded_files WHERE session_id = ?", (session_id,))
            files_uploaded = cursor.fetchone()[0]
            
            # Get chat count
            cursor.execute("SELECT COUNT(*) FROM chat_history WHERE session_id = ?", (session_id,))
            total_chats = cursor.fetchone()[0]
            
            # Get quiz attempts and average score
            cursor.execute("SELECT COUNT(*), COALESCE(AVG(score), 0) FROM quiz_attempts WHERE session_id = ?", (session_id,))
            quiz_stats = cursor.fetchone()
            quizzes_taken = quiz_stats[0]
            avg_score = round(quiz_stats[1], 1) if quiz_stats[1] else 0
            
            # Get todo count from database
            cursor.execute("SELECT COUNT(*) FROM todos WHERE session_id = ?", (session_id,))
            todo_count = cursor.fetchone()[0]
            
            return jsonify({
                "success": True,
                "stats": {
                    "files_uploaded": files_uploaded,
                    "total_chats": total_chats,
                    "quizzes_taken": quizzes_taken,
                    "avg_score": avg_score,
                    "total_todos": todo_count
                }
            })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Stats error: {str(e)}"}), 500


@app.route('/status')
def status():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "message": "AI Learning Platform API is active",
        "features": {
            "quiz_retakes": "New questions generated on each attempt",
            "youtube_integration": "Video recommendations via YouTube API",
            "context_aware_recommendations": "Smart recommendations based on quiz performance and PDF content", 
            "todo_reminders": "Hourly reminder system for pending tasks"
        },
        "endpoints": [
            "/login - POST",
            "/upload - POST", 
            "/summary - POST",
            "/chat - POST",
            "/quiz - GET/POST (Enhanced with retake variations)",
            "/recommendations - GET (Context-aware with PDF and quiz integration)",
            "/todo - GET/POST/PUT/DELETE (Enhanced with reminders)",
            "/reminder-check - GET (New: Check for todo reminders)"
        ]
    })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "Internal server error"}), 500


if __name__ == '__main__':
    # Run Flask app on 0.0.0.0:5000 for Replit compatibility
    app.run(host='0.0.0.0', port=5000, debug=True)
