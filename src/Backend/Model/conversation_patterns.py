from datetime import datetime, timedelta

class ConversationManager:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = timedelta(minutes=30)
        
    def get_quick_response(self, message, phone_number):
        message = message.lower().strip()
        session = self.sessions.get(phone_number, {})
        
        # Check if this is a response to a previous follow-up question
        if 'pending_question' in session:
            # Add the user's response to context
            context_update = f"{session['pending_question']}: {message}"
            session['context_history'] = session.get('context_history', []) + [context_update]
            # Clear pending question
            session.pop('pending_question')
            self.sessions[phone_number] = session
            return None  # Allow AI to process this response
            
        # Handle standard quick responses
        if message in ['hi', 'hello', 'hey']:
            return "Hello! How can I assist you with your health concerns today?"
            
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
        """Update session with context and pending question"""
        now = datetime.now()
        if phone_number not in self.sessions:
            self.sessions[phone_number] = {}
            
        self.sessions[phone_number].update({
            'last_interaction': now,
            'last_context': context,
            'pending_question': question,
            'context_history': self.sessions.get(phone_number, {}).get('context_history', [])
        })
        
    def clean_old_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired = [
            phone for phone, data in self.sessions.items()
            if now - data['last_interaction'] > self.session_timeout
        ]
        for phone in expired:
            del self.sessions[phone]
            
    def get_context_history(self, phone_number):
        """Get accumulated context for this conversation"""
        session = self.sessions.get(phone_number, {})
        return session.get('context_history', [])