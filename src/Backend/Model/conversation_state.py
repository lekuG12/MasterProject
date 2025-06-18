from enum import Enum
from datetime import datetime

class ConversationState:
    def __init__(self):
        self.context = ""
        self.last_question = ""
        self.asked_questions = set()  # Add this line
        self.last_update = datetime.now()

_conversation_states = {}

def get_conversation_state(phone_number):
    """Get the current conversation state for a phone number"""
    return _conversation_states.get(phone_number, {}).get("state", ConversationState.GREETING)

def update_conversation_state(phone_number, state):
    """Update the conversation state for a phone number"""
    if phone_number not in _conversation_states:
        _conversation_states[phone_number] = {}
    _conversation_states[phone_number].update({
        "state": state,
        "last_update": datetime.now()
    })