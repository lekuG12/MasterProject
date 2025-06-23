from datetime import datetime, timedelta

class UserIntent:
    """A simple utility to determine user intent from short, conversational messages."""

    # Words indicating the user has more symptoms to add
    AFFIRMATIVE_WORDS = {'yes', 'yep', 'ya', 'sure', 'ok', 'absolutely', 'correct'}
    
    # Words indicating the user is finished providing symptoms
    NEGATIVE_WORDS = {'no', 'nope', 'nah', 'thats all', "that's all", 'done', 'finished'}

    @staticmethod
    def is_negative(message: str) -> bool:
        """
        Checks if the user's message indicates they are finished adding symptoms.
        Returns True if the user says "no", "that's all", etc.
        """
        return message.lower().strip() in UserIntent.NEGATIVE_WORDS

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
            return "Hello! How can I assist you today?"
            
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

    def update_session(self, phone_number, user_input=None):
        """Update session with the latest user input and interaction time."""
        now = datetime.now()
        if phone_number not in self.sessions:
            self.sessions[phone_number] = {'symptom_history': []}
        
        # Add new symptom to the history if provided
        if user_input:
            self.sessions[phone_number]['symptom_history'].append(user_input)
            
        self.sessions[phone_number]['last_interaction'] = now
        
    def clean_old_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired = [
            phone for phone, data in self.sessions.items()
            if now - data['last_interaction'] > self.session_timeout
        ]
        for phone in expired:
            del self.sessions[phone]
            
    def get_symptom_history(self, phone_number):
        """Get the accumulated list of symptoms for this conversation."""
        session = self.sessions.get(phone_number, {})
        return session.get('symptom_history', [])