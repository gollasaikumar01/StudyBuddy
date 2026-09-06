# StudyBuddy - AI-Powered Learning Platform

StudyBuddy is a comprehensive learning platform that helps students study more effectively using AI technology. Upload PDFs, get AI summaries, take quizzes, and manage your study tasks all in one place.

## 🚀 Features

- **PDF Upload & Processing**: Upload study materials in PDF format
- **AI-Powered Summaries**: Get structured summaries of your study materials
- **Interactive Quizzes**: AI-generated questions with detailed explanations
- **Smart Chat**: Ask questions about your study materials
- **Study Recommendations**: Get personalized learning resources
- **Todo Management**: Track your study tasks with priorities
- **Progress Tracking**: Monitor your quiz scores and improvement

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.11 or higher
- pip (Python package installer)

### Quick Start

1. **Navigate to the project directory:**
   ```bash
   cd StudySage
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install manually:
   ```bash
   pip install flask flask-cors google-generativeai pypdf2 requests werkzeug
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Open your browser and go to:**
   ```
   http://localhost:5000
   ```

## 📖 How to Use

### Getting Started
1. **Register/Login**: Create an account or login with existing credentials
2. **Upload PDF**: Choose a PDF file containing your study material
3. **Generate Summary**: Click to get an AI-powered summary of your content
4. **Take Quiz**: Test your knowledge with AI-generated questions
5. **Ask Questions**: Use the chat feature to ask specific questions
6. **Manage Tasks**: Add study tasks to your todo list

### Quiz Features
- **Multiple Attempts**: Each retry generates completely new questions
- **Detailed Feedback**: Get explanations for every answer
- **Progress Tracking**: Monitor your improvement over time
- **Difficulty Levels**: Choose from 3, 5, or 10 questions

### Study Tips
- Start with the summary to get an overview
- Take quizzes multiple times to reinforce learning
- Use the chat feature to clarify doubts
- Keep track of your study tasks with the todo list

## 🔧 Configuration

### AI Provider Setup (Optional)
The app works with demo content by default. For full AI functionality:

1. Get a Google Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Set the environment variable:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

### Database
The app uses SQLite database (`studybuddy.db`) which is created automatically on first run.

## 📁 Project Structure

```
StudySage/
├── app.py              # Main Flask application
├── ai_gemini.py        # AI integration module
├── templates/
│   └── index.html      # Frontend interface
├── uploads/            # PDF storage directory
├── studybuddy.db       # SQLite database
└── README.md           # This file
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**: Change the port in `app.py` or kill the process using port 5000
2. **PDF upload fails**: Ensure the file is a valid PDF and under 16MB
3. **Quiz not generating**: Make sure you've uploaded a PDF first
4. **Database errors**: Delete `studybuddy.db` to reset the database

### Error Messages
- "Please upload a PDF first" - Upload a PDF file before using other features
- "Quiz not found" - The quiz session expired, generate a new quiz
- "Please login first" - Your session expired, please login again

## 🎯 Tips for Best Results

1. **PDF Quality**: Use PDFs with clear, readable text for best AI processing
2. **File Size**: Keep PDFs under 16MB for optimal performance
3. **Study Strategy**: 
   - Read the summary first
   - Take quizzes multiple times
   - Use different question counts (3, 5, 10)
   - Ask follow-up questions in chat

## 🔒 Privacy & Security

- All uploaded files are stored locally
- User passwords are securely hashed
- Session-based authentication
- No data is shared with third parties

## 📞 Support

If you encounter any issues:
1. Check the troubleshooting section above
2. Ensure all dependencies are installed correctly
3. Verify Python version compatibility (3.11+)

## 🚀 Future Enhancements

- Support for more file formats (DOCX, TXT)
- Advanced quiz analytics
- Study group features
- Mobile app version
- Integration with more AI providers

---

**Happy Studying! 📚✨**