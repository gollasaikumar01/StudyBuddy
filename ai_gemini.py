import json
import os



GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAvdkMPbUIYo0KWBqzyJW3uJx93v_vCn6E")

client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
    except ImportError:
        client = None
else:
    client = None


def summarize_text_gemini(text):
    """Generate summary using Gemini 2.5 Flash"""
    if not client or not GEMINI_API_KEY:
        return """
        <div class="summary-content">
            <h4><i class="fas fa-book"></i> Study Material Summary</h4>
            <div class="alert alert-info">
                <strong>Demo Content:</strong> This educational material contains approximately {} words and covers important academic concepts.
            </div>
            
            <h5>📚 Key Topics Covered:</h5>
            <ul>
                <li><strong>Fundamental Principles:</strong> Core concepts and theoretical foundations</li>
                <li><strong>Practical Applications:</strong> Real-world examples and use cases</li>
                <li><strong>Advanced Concepts:</strong> In-depth analysis and complex topics</li>
            </ul>
            
            <h5>🎯 Learning Objectives:</h5>
            <ul>
                <li>Understand the basic principles and concepts</li>
                <li>Apply knowledge to practical scenarios</li>
                <li>Develop critical thinking skills in this subject area</li>
            </ul>
            
            <div class="alert alert-warning">
                <strong>Note:</strong> This is a demo summary. Configure your Gemini API key for AI-powered summaries.
            </div>
        </div>
        """.format(len(text.split()))
    
    try:
        prompt = f"""Please create a well-structured, beginner-friendly summary of the following educational material. 

IMPORTANT: Format your response with HTML tags for web display:
- Use <h4> and <h5> tags for headings with relevant icons
- Use <ul> and <li> tags for bullet points
- Use <strong> tags for emphasis on key terms
- Use <div class="alert alert-info"> for important callouts
- Write in simple, clear language that even beginners can understand
- Break down complex concepts into easy-to-understand points
- Include practical examples where relevant

Structure the summary with these sections:
1. Main Topic Overview (with icon)
2. Key Concepts (bulleted list)
3. Important Points to Remember (numbered or bulleted)
4. Learning Takeaways (bulleted list)

Educational Material:
{text}"""
        
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        summary = response.text or "Error generating summary with Gemini"
        
       
        if not summary.startswith('<div class="summary-content">'):
            summary = f'<div class="summary-content">{summary}</div>'
            
        return summary.strip()
    except Exception as e:
        return f'<div class="alert alert-danger"><strong>Error:</strong> Could not generate summary - {str(e)}</div>'


def chat_with_gemini(question, context=""):
    """Chat functionality using Gemini 2.5 Flash"""
    if not client or not GEMINI_API_KEY:
        return f"Gemini Demo Response: I appreciate your question about '{question}'. As your AI learning assistant, I would provide detailed, educational explanations tailored to help you understand complex concepts. I would break down difficult topics into manageable parts and provide relevant examples to enhance your learning experience. This is a placeholder response since the Gemini API key is not configured."
    
    try:
        prompt = f"You are an AI tutor helping students learn. Please answer the following question clearly and educationally"
        if context:
            prompt += f" based on this study material context: {context}"
        prompt += f"\n\nQuestion: {question}"
        
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        return response.text or "Error getting answer from Gemini"
    except Exception as e:
        return f"Error getting answer: {str(e)}"


def generate_quiz_gemini(text, num_questions=5):
    """Generate quiz questions using Gemini 2.5 Pro"""
    if not client or not GEMINI_API_KEY:
        
        demo_questions = [
            {
                "question": "Based on the study material, what is the most important concept to understand first?",
                "options": ["A) Core foundations", "B) Advanced techniques", "C) Historical context", "D) Future applications"],
                "correct_answer": "A",
                "explanation": "Understanding core foundations provides the base for all other learning."
            },
            {
                "question": "Which study strategy would be most effective for this material?",
                "options": ["A) Speed reading", "B) Detailed analysis", "C) Skimming", "D) Random sampling"],
                "correct_answer": "B",
                "explanation": "Detailed analysis ensures comprehensive understanding of complex concepts."
            },
            {
                "question": "What type of follow-up study would reinforce this learning?",
                "options": ["A) Practice exercises", "B) Casual review", "C) Ignoring details", "D) Moving to unrelated topics"],
                "correct_answer": "A",
                "explanation": "Practice exercises help solidify understanding and identify knowledge gaps."
            },
            {
                "question": "How should you approach difficult concepts in this material?",
                "options": ["A) Skip them entirely", "B) Break them into smaller parts", "C) Memorize without understanding", "D) Only read once"],
                "correct_answer": "B",
                "explanation": "Breaking difficult concepts into smaller, manageable parts makes them easier to understand and remember."
            },
            {
                "question": "What is the best way to retain information from this study material?",
                "options": ["A) Read once and forget", "B) Passive reading only", "C) Active recall and practice", "D) Just highlight everything"],
                "correct_answer": "C",
                "explanation": "Active recall and practice help move information from short-term to long-term memory effectively."
            }
        ]
        return demo_questions[:num_questions]
    
    try:
        prompt = f"""Based on the following educational material, create {num_questions} beginner-friendly multiple choice questions.

IMPORTANT INSTRUCTIONS:
1. Make questions clear and easy to understand for beginners
2. Focus on key concepts and main ideas
3. Avoid overly complex or tricky questions
4. Provide helpful explanations that teach something new
5. Use simple, direct language
6. Make sure each question tests understanding, not just memorization

Format your response as valid JSON with this exact structure:
{{
  "questions": [
    {{
      "question": "Clear, simple question text",
      "options": ["A) First option", "B) Second option", "C) Third option", "D) Fourth option"],
      "correct_answer": "A",
      "explanation": "Clear explanation of why this answer is correct and what it teaches"
    }}
  ]
}}

Educational Material: {text[:3000]}"""

        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        if response.text:
            # Clean the response text to ensure it's valid JSON
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                result = json.loads(response_text)
                questions = result.get("questions", [])
                
                # Validate questions format
                valid_questions = []
                for q in questions:
                    if all(key in q for key in ["question", "options", "correct_answer", "explanation"]):
                        if len(q["options"]) == 4 and q["correct_answer"] in ["A", "B", "C", "D"]:
                            valid_questions.append(q)
                
                if valid_questions:
                    return valid_questions[:num_questions]
                else:
                    raise ValueError("No valid questions generated")
                    
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                raise ValueError("Invalid JSON response from Gemini")
        else:
            raise ValueError("Empty response from Gemini")
            
    except Exception as e:
        print(f"Quiz generation error: {e}")
        # Return fallback questions if API fails
        fallback_questions = [
            {
                "question": "What is the main topic discussed in the uploaded material?",
                "options": ["A) Basic concepts and principles", "B) Advanced theoretical frameworks", "C) Historical background only", "D) Future predictions"],
                "correct_answer": "A",
                "explanation": "Most educational materials start with basic concepts and principles as the foundation for learning."
            },
            {
                "question": "How should you approach studying this material effectively?",
                "options": ["A) Read everything once quickly", "B) Focus on understanding key concepts", "C) Memorize every detail", "D) Skip difficult sections"],
                "correct_answer": "B",
                "explanation": "Understanding key concepts provides a solid foundation that makes other details easier to learn and remember."
            },
            {
                "question": "What would be the best next step after reading this material?",
                "options": ["A) Immediately move to advanced topics", "B) Practice with examples and exercises", "C) Forget about it completely", "D) Only review once more"],
                "correct_answer": "B",
                "explanation": "Practicing with examples and exercises helps reinforce learning and identify areas that need more attention."
            }
        ]
        return fallback_questions[:num_questions]


def get_recommendations_gemini(topic):
    """Generate study recommendations using Gemini 2.5 Flash"""
    if not client or not GEMINI_API_KEY:
        # Return demo recommendations when API is not available
        return [
            {
                "title": f"Essential {topic} Learning Path",
                "type": "article",
                "description": f"Structured learning approach for mastering {topic} concepts",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+learning+path"
            },
            {
                "title": f"Advanced {topic} Resources",
                "type": "article",
                "description": f"Deep-dive materials and expert insights on {topic}",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+advanced+resources"
            },
            {
                "title": f"{topic} Quick Reference Guide",
                "type": "article",
                "description": f"Handy reference for {topic} formulas, concepts, and key points",
                "url": f"https://duckduckgo.com/?q={topic.replace(' ', '+')}+quick+reference"
            }
        ]
    
    try:
        prompt = f"""Generate study recommendations for the topic: {topic}
        
Provide 5 recommendations in JSON format:
{{
  "recommendations": [
    {{
      "title": "Recommendation title",
      "type": "article",
      "description": "Brief description",
      "url": "https://example.com"
    }}
  ]
}}"""

        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        if response.text:
            result = json.loads(response.text)
            return result.get("recommendations", [])
        else:
            raise ValueError("Empty response from Gemini")
            
    except Exception as e:
        # Return placeholder recommendations
        return [
            {
                "title": f"Study guide for {topic}",
                "type": "article", 
                "description": "Comprehensive study guide covering key concepts",
                "url": "https://duckduckgo.com/?q=" + topic.replace(" ", "+")
            }
        ]
