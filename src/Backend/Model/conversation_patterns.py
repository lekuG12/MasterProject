from datetime import datetime, timedelta

class ConversationManager:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = timedelta(minutes=30)
        
    def get_quick_response(self, message, phone_number):
        """Handle common messages without AI model"""
        message = message.lower().strip()
        
        # Greetings
        if message in ['hi', 'hello', 'hey']:
            return "Hello! How can I assist you today today?"
            
        # Gratitude
        if message in ['thank you', 'thanks', 'thx']:
            return "You're welcome! Don't hesitate to reach out if you need anything else."
            
        # Goodbyes
        if message in ['bye', 'goodbye', 'good bye']:
            return "Take care! Remember to reach out if you need any health advice."
            
        # Session continuity
        session = self.sessions.get(phone_number)
        if session and 'last_context' in session:
            if message in ['yes', 'ok', 'sure']:
                return f"Great! {session['last_question']}"
            if message == 'no':
                return "Alright. Is there something else I can help you with?"
                
        return None  # No quick response available
    
    def update_session(self, phone_number, context=None, question=None):
        """Update session data for continuity"""
        now = datetime.now()
        self.sessions[phone_number] = {
            'last_interaction': now,
            'last_context': context,
            'last_question': question
        }
        
    def clean_old_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired = [
            phone for phone, data in self.sessions.items()
            if now - data['last_interaction'] > self.session_timeout
        ]
        for phone in expired:
            del self.sessions[phone]